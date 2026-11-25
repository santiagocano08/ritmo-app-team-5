"""Deterministic coordinator of the multi-agent story factory.

The agents decide and argue; this script only applies rules. It validates every
file an agent writes against `factory/schemas/`, applies the policy floor to the
orchestrator's route plan, keeps the shared board (`board.json`) and decides the
next step: approve, run another round, or escalate to a person.

Rules that live here, not in a prompt:
- Mandatory reviewers (POLICY_FLOOR): the orchestrator may add reviewers, never drop these.
- A finding on a file the story did not change is dropped (the reviewer saw nothing there).
- At most MAX_ROUNDS review rounds. Open blockers or majors after the last round escalate.

Usage (all paths are explicit; the runner passes them):
  board.py plan     <route-plan.json> --issue N [--area AREA] --out <final.json>
  board.py findings <board.json> --changed <files.txt> <findings-*.json ...>
  board.py replies  <board.json> <replies.json>
  board.py verdicts <board.json> <verdicts-*.json ...>
  board.py decide   <board.json> --round R
  board.py summary  <board.json>
  board.py open     <board.json> [--reviewer AGENT]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

SCHEMAS = Path(__file__).resolve().parent / "schemas"
MAX_ROUNDS = 2
BLOCKING = {"blocker", "major"}
REVIEWERS = ("review-security", "review-contract", "review-acceptance")


class FactoryError(Exception):
    """An agent wrote something the rules reject."""


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def validate(doc: Any, schema: str, source: str) -> None:
    errors = sorted(
        jsonschema.Draft202012Validator(load_schema(schema)).iter_errors(doc), key=str
    )
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.absolute_path) or "(root)"
        raise FactoryError(
            f"{source}: does not match {schema}.schema.json at {where}: {first.message}"
        )


def read_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FactoryError(f"{path}: the agent did not write this file") from exc
    except json.JSONDecodeError as exc:
        raise FactoryError(
            f"{path}: not valid JSON ({exc.msg}, line {exc.lineno})"
        ) from exc


def write_json(path: str | Path, doc: Any) -> None:
    Path(path).write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


# --- route plan -----------------------------------------------------------------------------


def policy_floor(plan: dict[str, Any]) -> list[tuple[str, str]]:
    """Reviewers the rules require for this plan, with the rule that requires them."""
    required: list[tuple[str, str]] = [
        (
            "review-acceptance",
            "policy: every story is checked against its acceptance criteria",
        ),
    ]
    if plan["risk_level"] == 1 or plan["area"] in ("Backend", "Platform"):
        required.append(
            (
                "review-security",
                "policy: risk level 1, backend or platform stories get a security review",
            )
        )
    if plan["touches_contract"] or plan["area"] == "Data":
        required.append(
            (
                "review-contract",
                "policy: data stories and contract changes get a contract review",
            )
        )
    return required


def apply_policy(plan: dict[str, Any], area_hint: str | None = None) -> dict[str, Any]:
    final = json.loads(json.dumps(plan))
    chosen = {r["agent"] for r in final["reviewers"]}
    additions = []
    for agent, reason in policy_floor(final):
        if agent not in chosen:
            final["reviewers"].append({"agent": agent, "reason": reason})
            additions.append(agent)
    if (
        final["touches_contract"]
        and final["area"] == "Data"
        and "data-design" not in final["design_agents"]
    ):
        final["design_agents"].append("data-design")
        additions.append("data-design")
    final["reviewers"].sort(key=lambda r: REVIEWERS.index(r["agent"]))
    final["policy_additions"] = additions
    final["area_hint"] = area_hint
    final["area_disagreement"] = bool(area_hint and area_hint != final["area"])
    final["max_rounds"] = MAX_ROUNDS
    return final


def cmd_plan(args: argparse.Namespace) -> int:
    plan = read_json(args.plan)
    validate(plan, "route-plan", args.plan)
    if plan["issue"] != args.issue:
        raise FactoryError(
            f"{args.plan}: plan is for issue #{plan['issue']}, expected #{args.issue}"
        )
    final = apply_policy(plan, args.area)
    write_json(args.out, final)
    print(" ".join(r["agent"] for r in final["reviewers"]))
    return 0


# --- board ----------------------------------------------------------------------------------


def new_board() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "findings": [],
        "dropped": [],
        "rounds": [],
        "outcome": None,
    }


def load_board(path: str) -> dict[str, Any]:
    p = Path(path)
    return read_json(p) if p.exists() else new_board()


def add_findings(
    board: dict[str, Any], docs: list[tuple[str, dict[str, Any]]], changed: set[str]
) -> None:
    known = {f["id"] for f in board["findings"]}
    for source, doc in docs:
        validate(doc, "findings", source)
        prefix = {
            "review-security": "SEC",
            "review-contract": "CON",
            "review-acceptance": "ACC",
        }[doc["reviewer"]]
        for f in doc["findings"]:
            if not f["id"].startswith(prefix):
                raise FactoryError(
                    f"{source}: {doc['reviewer']} must use {prefix}- ids, got {f['id']}"
                )
            if f["id"] in known:
                raise FactoryError(f"{source}: duplicate finding id {f['id']}")
            known.add(f["id"])
            entry = {
                **f,
                "reviewer": doc["reviewer"],
                "round": 1,
                "status": "open",
                "reply": None,
                "verdict": None,
            }
            if f["file"] not in changed:
                entry["status"] = "dropped"
                entry["dropped_reason"] = "rule: file not changed by this story"
                board["dropped"].append(entry)
            else:
                board["findings"].append(entry)
        board["rounds"].append(
            {"round": 1, "reviewer": doc["reviewer"], "summary": doc["summary"]}
        )


def apply_replies(board: dict[str, Any], doc: dict[str, Any], source: str) -> None:
    validate(doc, "replies", source)
    by_id = {f["id"]: f for f in board["findings"]}
    for r in doc["replies"]:
        if r["finding_id"] not in by_id:
            raise FactoryError(f"{source}: reply to unknown finding {r['finding_id']}")
        by_id[r["finding_id"]]["reply"] = {
            "decision": r["decision"],
            "detail": r["detail"],
        }
    missing = [
        f["id"]
        for f in board["findings"]
        if f["status"] == "open" and f["reply"] is None
    ]
    if missing:
        raise FactoryError(
            f"{source}: no reply for open finding(s) {', '.join(missing)}"
        )


def apply_verdicts(
    board: dict[str, Any], docs: list[tuple[str, dict[str, Any]]]
) -> None:
    by_id = {f["id"]: f for f in board["findings"]}
    for source, doc in docs:
        validate(doc, "verdicts", source)
        for v in doc["verdicts"]:
            f = by_id.get(v["finding_id"])
            if f is None:
                raise FactoryError(
                    f"{source}: verdict on unknown finding {v['finding_id']}"
                )
            if f["reviewer"] != doc["reviewer"]:
                raise FactoryError(
                    f"{source}: {doc['reviewer']} cannot judge {f['id']}, raised by {f['reviewer']}"
                )
            f["verdict"] = {"status": v["status"], "detail": v["detail"]}
            f["status"] = "open" if v["status"] == "still_open" else v["status"]
            f["round"] = 2


def open_blocking(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        f
        for f in board["findings"]
        if f["status"] == "open" and f["severity"] in BLOCKING
    ]


def decide(board: dict[str, Any], round_no: int) -> str:
    """approved: nothing blocking is open. reply: the implementer answers and reviewers check again.
    escalated: blocking findings survive the last round; a person decides."""
    if not open_blocking(board):
        outcome = "approved"
    elif round_no < MAX_ROUNDS:
        outcome = "reply"
    else:
        outcome = "escalated"
    board["outcome"] = outcome if outcome != "reply" else None
    return outcome


def summary(board: dict[str, Any]) -> str:
    lines = ["## Multi-agent review board", ""]
    outcome = board.get("outcome") or "in progress"
    lines.append(f"**Outcome:** {outcome}")
    lines.append("")
    if not board["findings"]:
        lines.append("No findings on the files this story changed.")
    else:
        lines.append(
            "| ID | Reviewer | Severity | File | Claim | Reply | Verdict | Status |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for f in board["findings"]:
            reply = f["reply"]["decision"] if f.get("reply") else "-"
            verdict = f["verdict"]["status"] if f.get("verdict") else "-"
            where = f["file"] + (f":{f['line']}" if f.get("line") else "")
            claim = f["claim"].replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {f['id']} | {f['reviewer']} | {f['severity']} | `{where}` | {claim} | {reply} | {verdict} | {f['status']} |"
            )
    if board["dropped"]:
        lines.append("")
        lines.append(
            f"Dropped by rule (file not changed by the story): {', '.join(f['id'] for f in board['dropped'])}"
        )
    return "\n".join(lines) + "\n"


# --- CLI ------------------------------------------------------------------------------------


def _docs(paths: list[str]) -> list[tuple[str, dict[str, Any]]]:
    return [(p, read_json(p)) for p in paths]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan")
    p.add_argument("plan")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--area")
    p.add_argument("--out", required=True)

    p = sub.add_parser("findings")
    p.add_argument("board")
    p.add_argument("--changed", required=True)
    p.add_argument("files", nargs="+")

    p = sub.add_parser("replies")
    p.add_argument("board")
    p.add_argument("file")

    p = sub.add_parser("verdicts")
    p.add_argument("board")
    p.add_argument("files", nargs="+")

    p = sub.add_parser("decide")
    p.add_argument("board")
    p.add_argument("--round", type=int, required=True)

    p = sub.add_parser("summary")
    p.add_argument("board")

    p = sub.add_parser("open")
    p.add_argument("board")
    p.add_argument("--reviewer")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "plan":
            return cmd_plan(args)
        board = load_board(args.board)
        if args.cmd == "findings":
            changed = {
                line.strip()
                for line in Path(args.changed).read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
            add_findings(board, _docs(args.files), changed)
            write_json(args.board, board)
            print(
                f"{len(board['findings'])} finding(s), {len(open_blocking(board))} blocking, {len(board['dropped'])} dropped by rule"
            )
        elif args.cmd == "replies":
            apply_replies(board, read_json(args.file), args.file)
            write_json(args.board, board)
        elif args.cmd == "verdicts":
            apply_verdicts(board, _docs(args.files))
            write_json(args.board, board)
        elif args.cmd == "decide":
            outcome = decide(board, args.round)
            write_json(args.board, board)
            print(outcome)
        elif args.cmd == "summary":
            sys.stdout.write(summary(board))
        elif args.cmd == "open":
            rows = [
                f
                for f in board["findings"]
                if f["status"] == "open"
                and (not args.reviewer or f["reviewer"] == args.reviewer)
            ]
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    except FactoryError as exc:
        print(f"FACTORY-ERROR {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
