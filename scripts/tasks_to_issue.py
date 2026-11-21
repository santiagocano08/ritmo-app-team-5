#!/usr/bin/env python3
"""Turn a Spec Kit tasks.md into one GitHub issue (task checklist) and add it to a project.

Usage:
  python3 scripts/tasks_to_issue.py specs/001-base-simulator --project 10 --owner Yceballos \
      --turn "1 Data and minimal loop" --area Data [--dry-run]

One issue per spec (not one per task) keeps the board light; the checklist mirrors tasks.md.
Requires the GitHub CLI (gh) with the 'project' scope.
"""
import argparse, json, pathlib, re, subprocess, sys

def sh(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout

def build_body(spec_dir: pathlib.Path) -> tuple[str, str]:
    spec = (spec_dir / "spec.md").read_text(encoding="utf-8")
    title_m = re.search(r"^# Feature Specification:\s*(.+)$", spec, re.M)
    title = title_m.group(1).strip() if title_m else spec_dir.name
    lines = [f"Spec: `{spec_dir}/spec.md` · Plan: `{spec_dir}/plan.md` · Tasks: `{spec_dir}/tasks.md`",
             "", "_Checklist mirrors tasks.md (source of truth; implement-code marks [X] there)._", ""]
    for raw in (spec_dir / "tasks.md").read_text(encoding="utf-8").splitlines():
        if raw.startswith("## Phase"):
            lines += ["", "### " + raw[3:].strip()]
        m = re.match(r"^- \[( |x|X)\] (T\d+)\s*(.*)$", raw)
        if m:
            done = "x" if m.group(1).lower() == "x" else " "
            text = re.sub(r"`", "", m.group(3))
            text = (text[:140] + "…") if len(text) > 140 else text
            lines.append(f"- [{done}] **{m.group(2)}** {text}")
    return f"{spec_dir.name}: {title}", "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec_dir"); ap.add_argument("--project", required=True); ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", default="santiagocano08/ritmo-app-team-5")
    ap.add_argument("--turn"); ap.add_argument("--area"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    title, body = build_body(pathlib.Path(a.spec_dir))
    if a.dry_run:
        print(title); print(body); return
    url = sh("gh", "issue", "create", "--repo", a.repo, "--title", title, "--body", body).strip()
    item = json.loads(sh("gh", "project", "item-add", a.project, "--owner", a.owner, "--url", url, "--format", "json"))
    proj = json.loads(sh("gh", "project", "view", a.project, "--owner", a.owner, "--format", "json"))
    fields = json.loads(sh("gh", "project", "field-list", a.project, "--owner", a.owner, "--format", "json"))["fields"]
    def set_select(name, value):
        f = next((f for f in fields if f["name"] == name), None)
        opt = next((o for o in (f or {}).get("options", []) if o["name"] == value), None)
        if f and opt:
            sh("gh", "project", "item-edit", "--id", item["id"], "--project-id", proj["id"],
               "--field-id", f["id"], "--single-select-option-id", opt["id"])
    if a.turn: set_select("Turn", a.turn)
    if a.area: set_select("Area", a.area)
    set_select("Status", "Todo")
    spec_f = next((f for f in fields if f["name"] == "Spec"), None)
    if spec_f:
        sh("gh", "project", "item-edit", "--id", item["id"], "--project-id", proj["id"],
           "--field-id", spec_f["id"], "--text", a.spec_dir)
    print(url)

if __name__ == "__main__":
    sys.exit(main())
