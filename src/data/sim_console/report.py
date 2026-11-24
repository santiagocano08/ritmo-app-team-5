"""Decision report of one simulator run (data team harnesses — not product code).

Shared by the sim console (8090, which saves a run before every reset) and the data flow viewer (8085, which
shows the report and lets you decide). Pure functions, except `write_archive` / `list_archives`, which read and
write the run archive folder (`src/data/sim_console/runs/archive/<run_key>/`, git-ignored).

What it answers for the people watching a demo:
- was each recommendation decided (applied / discarded) or did it expire, and why it expired;
- how many were proposed, decided and expired in the last X simulated minutes, and per 5-minute bucket;
- how long the dispatcher took to decide.

Status mirrors the pipeline (`rules/mpc.derive_all`, FR-021): the first decision wins, else the time-to-live
or the bus passing the stop expires it. Two cases the gold table cannot show yet are derived here:

- a decision event already in bronze but not yet folded in by the next refresh cycle (<= 5 s): reported with
  that decision;
- a proposal still open when the run is over. The simulated clock stops with the simulator, so the pipeline never
  reaches `expires_ts` and the row would stay `proposed` forever. The report closes it as expired with reason
  `run_ended` at the last simulated time. Nothing is written to gold (no contract change).

All times are simulated time (`as_of_ts` of the newest snapshot), never the wall clock.
"""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

BUCKET_S = 300
OUTCOMES = ("open", "applied", "discarded", "expired")
EXPIRY_REASONS = ("time", "bus_passed", "run_ended")


def first_decisions(events: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """rec_id -> its first decision event (bronze id order), like the pipeline: the first decision wins."""
    out: dict[str, Mapping[str, Any]] = {}
    for e in sorted(events, key=lambda x: x["bronze_id"]):
        rid = str(e["rec_id"]).lower()
        if rid not in out and e.get("action") in ("apply", "discard"):
            out[rid] = e
    return out


def outcome(rec: Mapping[str, Any], decision: Mapping[str, Any] | None, as_of: datetime,
            run_over: bool) -> dict[str, Any]:
    """Outcome of one recommendation at simulated time `as_of`."""
    status = rec["status"]
    if status in ("applied", "discarded") or (status == "proposed" and decision is not None):
        act = "applied" if status == "applied" or (status == "proposed" and decision["action"] == "apply") else "discarded"
        decided_at = (decision or {}).get("decided_at") or rec.get("close_ts") or as_of
        return {"outcome": act, "reason": None, "close_ts": decided_at,
                "decided_by": (decision or {}).get("user_id"),
                "decide_s": max(0.0, (decided_at - rec["proposed_ts"]).total_seconds()),
                "pending_cycle": status == "proposed"}
    if status == "expired":
        close = rec.get("close_ts") or rec["expires_ts"]
        reason = "time" if close >= rec["expires_ts"] else "bus_passed"
        return {"outcome": "expired", "reason": reason, "close_ts": close, "decided_by": None, "decide_s": None,
                "pending_cycle": False}
    # still proposed in gold
    if as_of > rec["expires_ts"]:
        return {"outcome": "expired", "reason": "time", "close_ts": rec["expires_ts"], "decided_by": None,
                "decide_s": None, "pending_cycle": True}
    if run_over:
        return {"outcome": "expired", "reason": "run_ended", "close_ts": as_of, "decided_by": None,
                "decide_s": None, "pending_cycle": False}
    return {"outcome": "open", "reason": None, "close_ts": None, "decided_by": None, "decide_s": None,
            "pending_cycle": False, "remaining_s": (rec["expires_ts"] - as_of).total_seconds()}


def rows(recs: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]], as_of: datetime,
         run_over: bool) -> list[dict[str, Any]]:
    """One row per recommendation with its outcome, newest first (open ones on top)."""
    dec = first_decisions(events)
    out = []
    for r in recs:
        o = outcome(r, dec.get(str(r["rec_id"]).lower()), as_of, run_over)
        out.append({k: r.get(k) for k in ("rec_id", "rank", "case", "action", "bus_id", "stop_id", "saving_s",
                                          "reason_text", "stale", "proposed_ts", "expires_ts", "status")} | o)
    out.sort(key=lambda x: (x["outcome"] != "open", -x["proposed_ts"].timestamp(), x.get("rank") or 0))
    return out


def _count(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    c = {k: 0 for k in OUTCOMES} | {f"expired_{k}": 0 for k in EXPIRY_REASONS}
    for x in items:
        c[x["outcome"]] += 1
        if x["outcome"] == "expired":
            c[f"expired_{x['reason']}"] += 1
    return c


def summary(report_rows: Sequence[Mapping[str, Any]], as_of: datetime, start: datetime,
            window_s: int | None) -> dict[str, Any]:
    """Counts in the window [as_of - window_s, as_of] (the whole run when `window_s` is None).

    `proposed` counts what was proposed in the window; `applied`/`discarded`/`expired` count what closed in it;
    `open` is what is still waiting now."""
    lo = start if window_s is None else max(start, as_of - timedelta(seconds=window_s))
    proposed = [r for r in report_rows if lo <= r["proposed_ts"] <= as_of]
    closed = [r for r in report_rows if r["close_ts"] is not None and lo <= r["close_ts"] <= as_of]
    c = _count(closed)
    decided = c["applied"] + c["discarded"]
    times = [r["decide_s"] for r in closed if r["decide_s"] is not None]
    return {
        "from_ts": lo, "to_ts": as_of, "window_s": window_s,
        "proposed": len(proposed),
        "applied": c["applied"], "discarded": c["discarded"], "decided": decided,
        "expired": c["expired"], **{f"expired_{k}": c[f"expired_{k}"] for k in EXPIRY_REASONS},
        "open": sum(1 for r in report_rows if r["outcome"] == "open"),
        "decided_pct": round(100 * decided / (decided + c["expired"]), 1) if decided + c["expired"] else None,
        "median_decide_s": round(median(times), 1) if times else None,
    }


def buckets(report_rows: Sequence[Mapping[str, Any]], as_of: datetime, start: datetime,
            size_s: int = BUCKET_S) -> list[dict[str, Any]]:
    """Per `size_s` of simulated time from the run start: proposed, applied, discarded and expired in it."""
    if as_of < start:
        return []
    n = int((as_of - start).total_seconds() // size_s) + 1
    out = []
    for i in range(n):
        lo = start + timedelta(seconds=i * size_s)
        hi = min(lo + timedelta(seconds=size_s), as_of + timedelta(microseconds=1))
        closed = [r for r in report_rows if r["close_ts"] is not None and lo <= r["close_ts"] < hi]
        c = _count(closed)
        out.append({"from_ts": lo, "proposed": sum(1 for r in report_rows if lo <= r["proposed_ts"] < hi),
                    "applied": c["applied"], "discarded": c["discarded"], "expired": c["expired"]})
    return out


# ------------------------------------------------------------------------------- archive
CSV_COLUMNS = ("rec_id", "rank", "case", "action", "bus_id", "stop_id", "saving_s", "proposed_ts", "expires_ts",
               "outcome", "reason", "close_ts", "decided_by", "decide_s", "stale", "reason_text")


def run_key(first_arrival: datetime | None) -> str | None:
    """Stable id of a pfsim run: wall-clock arrival of its first simulator event (the database is reset per run)."""
    return first_arrival.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") if first_arrival else None


def valid_key(key: str) -> bool:
    return len(key) == 16 and key[8] == "T" and key[-1] == "Z" and (key[:8] + key[9:15]).isdigit()


def _default(o: Any) -> Any:
    return o.isoformat() if isinstance(o, datetime) else str(o)


def write_archive(directory: Path, key: str, doc: Mapping[str, Any]) -> Path:
    """Write <directory>/<key>/report.json (everything) and recommendations.csv (one row per recommendation).

    The same run always writes the same folder, so a later save replaces it with what happened since."""
    folder = directory / key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "report.json").write_text(json.dumps(doc, default=_default, indent=1, ensure_ascii=False))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    w.writeheader()
    for r in doc.get("rows", []):
        w.writerow({k: _default(v) if isinstance(v, datetime) else v for k, v in r.items()})
    (folder / "recommendations.csv").write_text(buf.getvalue())
    return folder


def archived_series(directory: Path, key: str) -> dict[str, Any] | None:
    """Per simulated minute of a saved run: mean wait, buses in service and bunched (averaged within the minute),
    plus the decision marks. Minutes line up across runs with the same start hour, so two runs can be overlaid."""
    f = directory / key / "report.json"
    if not valid_key(key) or not f.exists():
        return None
    d = json.loads(f.read_text())
    out = d.get("outcomes") or {}
    by_min: dict[str, list[dict[str, Any]]] = {}
    for p in out.get("series", []):
        by_min.setdefault(str(p["as_of_ts"])[:16], []).append(p)

    def avg(ps: list[dict[str, Any]], k: str, need_ok: bool = False) -> float | None:
        vals = [p[k] for p in ps if p.get(k) is not None and (p.get("computable") or not need_ok)]
        return round(sum(vals) / len(vals), 1) if vals else None

    minutes = [{"t": m + ":00Z", "wait": avg(ps, "mean_wait_s", True), "in_service": avg(ps, "in_service"),
                "bunched": avg(ps, "bunched")} for m, ps in sorted(by_min.items())]
    marks = [{"t": e["close_ts"], "outcome": e["outcome"]} for e in out.get("effects", [])]
    return {"run_key": key, "run": out.get("run"), "total": d.get("total"), "minutes": minutes, "marks": marks}


def list_archives(directory: Path) -> list[dict[str, Any]]:
    """Saved runs, newest first, with their whole-run summary."""
    out = []
    for f in sorted(directory.glob("*/report.json"), reverse=True):
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        cfg = d.get("config") or {}
        out.append({"run_key": d.get("run_key"), "archived_at": d.get("archived_at"), "trigger": d.get("trigger"),
                    "saved_by": d.get("saved_by"), "scenario": cfg.get("scenario"), "start_ts": d.get("start_ts"),
                    "as_of_ts": d.get("as_of_ts"), "run_over": d.get("run_over"), "total": d.get("total"),
                    "outcome": (d.get("outcomes") or {}).get("run"),
                    "groups": (d.get("outcomes") or {}).get("groups")})
    return out
