"""Rules of the multi-agent factory coordinator (factory/board.py)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "factory_board", ROOT / "factory" / "board.py"
)
assert _spec and _spec.loader
board_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(board_mod)


def plan(**over):
    base = {
        "schema_version": "1.0",
        "issue": 53,
        "area": "Frontend",
        "risk_level": 2,
        "touches_contract": False,
        "rationale": "Small UI change in the header; no data or contract involved.",
        "design_agents": [],
        "reviewers": [
            {"agent": "review-acceptance", "reason": "check the acceptance criteria"}
        ],
    }
    base.update(over)
    return base


def finding(fid, file="src/frontend/src/App.tsx", severity="major"):
    return {
        "id": fid,
        "severity": severity,
        "file": file,
        "line": 10,
        "claim": "The badge text is not escaped before rendering.",
        "evidence": "+ <div dangerouslySetInnerHTML={{__html: label}} />",
        "suggested_fix": "Render the label as text.",
    }


def findings_doc(reviewer, items):
    return {
        "schema_version": "1.0",
        "reviewer": reviewer,
        "round": 1,
        "summary": "Checked the diff.",
        "findings": items,
    }


CHANGED = {"src/frontend/src/App.tsx", "src/frontend/tests/App.test.tsx"}


# --- schemas ---------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["route-plan", "findings", "replies", "verdicts"])
def test_schemas_are_valid_json_schema(name):
    board_mod.jsonschema.Draft202012Validator.check_schema(board_mod.load_schema(name))


def test_invalid_plan_is_rejected():
    with pytest.raises(board_mod.FactoryError, match="route-plan"):
        board_mod.validate(plan(area="Mobile"), "route-plan", "plan.json")


# --- policy floor ----------------------------------------------------------------------------


def test_policy_keeps_frontend_low_risk_plan_as_is():
    final = board_mod.apply_policy(plan())
    assert [r["agent"] for r in final["reviewers"]] == ["review-acceptance"]
    assert final["policy_additions"] == []
    assert final["max_rounds"] == 2


def test_policy_adds_security_for_backend_even_if_orchestrator_skipped_it():
    final = board_mod.apply_policy(plan(area="Backend"))
    assert "review-security" in [r["agent"] for r in final["reviewers"]]
    assert final["policy_additions"] == ["review-security"]


def test_policy_adds_contract_review_and_data_design_for_data_contract_story():
    final = board_mod.apply_policy(
        plan(area="Data", touches_contract=True, reviewers=[])
    )
    agents = [r["agent"] for r in final["reviewers"]]
    assert agents == ["review-contract", "review-acceptance"]
    assert final["design_agents"] == ["data-design"]


def test_policy_never_removes_an_extra_reviewer_the_orchestrator_chose():
    extra = [
        {"agent": "review-acceptance", "reason": "acceptance"},
        {"agent": "review-security", "reason": "renders user text"},
    ]
    final = board_mod.apply_policy(plan(reviewers=extra))
    assert [r["agent"] for r in final["reviewers"]] == [
        "review-security",
        "review-acceptance",
    ]


def test_area_disagreement_with_the_board_is_recorded():
    final = board_mod.apply_policy(plan(area="Frontend"), area_hint="Data")
    assert final["area_disagreement"] is True


def test_plan_for_another_issue_is_rejected(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan(issue=99)))
    rc = board_mod.main(
        ["plan", str(p), "--issue", "53", "--out", str(tmp_path / "final.json")]
    )
    assert rc == 3


# --- findings, replies, verdicts -------------------------------------------------------------


def test_finding_on_unchanged_file_is_dropped_by_rule():
    b = board_mod.new_board()
    board_mod.add_findings(
        b,
        [
            (
                "f.json",
                findings_doc(
                    "review-security", [finding("SEC-1", file="src/api/main.py")]
                ),
            )
        ],
        CHANGED,
    )
    assert b["findings"] == []
    assert b["dropped"][0]["id"] == "SEC-1"


def test_reviewer_must_use_its_own_prefix():
    b = board_mod.new_board()
    with pytest.raises(board_mod.FactoryError, match="SEC-"):
        board_mod.add_findings(
            b,
            [("f.json", findings_doc("review-security", [finding("ACC-1")]))],
            CHANGED,
        )


def test_every_open_finding_needs_a_reply():
    b = board_mod.new_board()
    board_mod.add_findings(
        b,
        [
            (
                "f.json",
                findings_doc("review-security", [finding("SEC-1"), finding("SEC-2")]),
            )
        ],
        CHANGED,
    )
    replies = {
        "schema_version": "1.0",
        "round": 1,
        "replies": [
            {
                "finding_id": "SEC-1",
                "decision": "fixed",
                "detail": "Rendered as text, added a test.",
            }
        ],
    }
    with pytest.raises(board_mod.FactoryError, match="SEC-2"):
        board_mod.apply_replies(b, replies, "replies.json")


def test_reviewer_cannot_judge_another_reviewers_finding():
    b = board_mod.new_board()
    board_mod.add_findings(
        b, [("f.json", findings_doc("review-security", [finding("SEC-1")]))], CHANGED
    )
    verdicts = {
        "schema_version": "1.0",
        "reviewer": "review-acceptance",
        "round": 2,
        "verdicts": [
            {"finding_id": "SEC-1", "status": "resolved", "detail": "looks fine"}
        ],
    }
    with pytest.raises(board_mod.FactoryError, match="cannot judge"):
        board_mod.apply_verdicts(b, [("v.json", verdicts)])


# --- decision --------------------------------------------------------------------------------


def _board_with(severity):
    b = board_mod.new_board()
    board_mod.add_findings(
        b,
        [
            (
                "f.json",
                findings_doc("review-security", [finding("SEC-1", severity=severity)]),
            )
        ],
        CHANGED,
    )
    return b


def test_only_minor_findings_are_approved_in_round_one():
    assert board_mod.decide(_board_with("minor"), 1) == "approved"


def test_blocking_finding_in_round_one_asks_for_a_reply():
    assert board_mod.decide(_board_with("major"), 1) == "reply"


def test_resolved_after_reply_is_approved():
    b = _board_with("blocker")
    board_mod.apply_replies(
        b,
        {
            "schema_version": "1.0",
            "round": 1,
            "replies": [
                {
                    "finding_id": "SEC-1",
                    "decision": "fixed",
                    "detail": "Rendered as text, added a test.",
                }
            ],
        },
        "r.json",
    )
    board_mod.apply_verdicts(
        b,
        [
            (
                "v.json",
                {
                    "schema_version": "1.0",
                    "reviewer": "review-security",
                    "round": 2,
                    "verdicts": [
                        {
                            "finding_id": "SEC-1",
                            "status": "resolved",
                            "detail": "Fix verified in the diff.",
                        }
                    ],
                },
            )
        ],
    )
    assert board_mod.decide(b, 2) == "approved"


def test_still_open_after_last_round_escalates_to_a_person():
    b = _board_with("blocker")
    board_mod.apply_replies(
        b,
        {
            "schema_version": "1.0",
            "round": 1,
            "replies": [
                {
                    "finding_id": "SEC-1",
                    "decision": "wont_fix",
                    "detail": "The label never contains user input.",
                }
            ],
        },
        "r.json",
    )
    board_mod.apply_verdicts(
        b,
        [
            (
                "v.json",
                {
                    "schema_version": "1.0",
                    "reviewer": "review-security",
                    "round": 2,
                    "verdicts": [
                        {
                            "finding_id": "SEC-1",
                            "status": "still_open",
                            "detail": "The label comes from the API.",
                        }
                    ],
                },
            )
        ],
    )
    assert board_mod.decide(b, 2) == "escalated"
    assert "escalated" in board_mod.summary(b)
