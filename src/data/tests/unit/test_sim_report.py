"""Decision report of a simulator run (src/data/sim_console/report.py): outcome, expiry reason, windows, archive."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.data.sim_console import report

T0 = datetime(2026, 11, 24, 22, 0, tzinfo=timezone.utc)


def at(s: float) -> datetime:
    return T0 + timedelta(seconds=s)


def rec(rid: str, status: str, proposed: float, close: float | None = None, ttl: float = 120, **kw):
    return {"rec_id": rid, "status": status, "stale": False, "case": "C1", "rank": 1, "action": "hold",
            "bus_id": "B-102", "stop_id": "P-884", "saving_s": 12.5, "reason_text": "r",
            "proposed_ts": at(proposed), "expires_ts": at(proposed + ttl),
            "close_ts": at(close) if close is not None else None, **kw}


def dec(rid: str, action: str, ts: float, bronze_id: int = 1):
    return {"bronze_id": bronze_id, "rec_id": rid, "action": action, "user_id": "u", "decided_at": at(ts)}


def one(r, events=(), as_of=1000.0, run_over=False):
    return report.rows([r], list(events), at(as_of), run_over)[0]


def test_applied_reports_who_and_how_long():
    o = one(rec("a", "applied", 100, close=130), [dec("a", "apply", 130)])
    assert (o["outcome"], o["decided_by"], o["decide_s"]) == ("applied", "u", 30.0)


def test_discarded():
    assert one(rec("a", "discarded", 100, close=110), [dec("a", "discard", 110)])["outcome"] == "discarded"


def test_expired_by_time_vs_bus_passed():
    assert one(rec("a", "expired", 100, close=220))["reason"] == "time"
    assert one(rec("a", "expired", 100, close=150))["reason"] == "bus_passed"


def test_open_has_remaining_simulated_seconds():
    o = one(rec("a", "proposed", 100), as_of=150)
    assert o["outcome"] == "open" and o["remaining_s"] == 70


def test_open_when_run_is_over_expires_with_run_ended_at_last_sim_time():
    o = one(rec("a", "proposed", 100), as_of=150, run_over=True)
    assert (o["outcome"], o["reason"], o["close_ts"]) == ("expired", "run_ended", at(150))


def test_proposed_past_expiry_is_expired_by_time_before_the_cycle_catches_up():
    o = one(rec("a", "proposed", 100), as_of=230)
    assert (o["outcome"], o["reason"], o["close_ts"], o["pending_cycle"]) == ("expired", "time", at(220), True)


def test_decision_waiting_for_the_cycle_counts_as_decided_and_wins_over_run_end():
    o = one(rec("a", "proposed", 100), [dec("a", "apply", 140)], as_of=150, run_over=True)
    assert (o["outcome"], o["pending_cycle"], o["decide_s"]) == ("applied", True, 40.0)


def test_first_decision_wins():
    events = [dec("a", "discard", 120, bronze_id=2), dec("a", "apply", 110, bronze_id=1)]
    assert report.first_decisions(events)["a"]["action"] == "apply"


def test_summary_window_counts_closes_inside_it_only():
    rows = report.rows([rec("a", "applied", 100, close=130), rec("b", "expired", 700, close=820),
                        rec("c", "discarded", 900, close=950), rec("d", "proposed", 980)],
                       [dec("a", "apply", 130), dec("c", "discard", 950)], at(1000), False)
    w = report.summary(rows, at(1000), T0, 600)       # 400..1000
    assert (w["proposed"], w["applied"], w["discarded"], w["expired"], w["open"]) == (3, 0, 1, 1, 1)
    assert w["decided_pct"] == 50.0 and w["median_decide_s"] == 50.0
    total = report.summary(rows, at(1000), T0, None)
    assert (total["proposed"], total["decided"], total["expired_time"]) == (4, 2, 1)


def test_buckets_cover_the_run_in_five_minute_steps():
    rows = report.rows([rec("a", "expired", 100, close=220), rec("b", "applied", 310, close=320)],
                       [dec("b", "apply", 320)], at(620), False)
    b = report.buckets(rows, at(620), T0)
    assert [(x["proposed"], x["applied"], x["expired"]) for x in b] == [(1, 0, 1), (1, 1, 0), (0, 0, 0)]


def test_archive_round_trip(tmp_path):
    rows = report.rows([rec("a", "applied", 100, close=130)], [dec("a", "apply", 130)], at(200), False)
    key = report.run_key(T0)
    assert report.valid_key(key) and not report.valid_key("../etc")
    report.write_archive(tmp_path, key, {"run_key": key, "rows": rows, "total": report.summary(rows, at(200), T0, None)})
    assert json.loads((tmp_path / key / "report.json").read_text())["rows"][0]["outcome"] == "applied"
    assert (tmp_path / key / "recommendations.csv").read_text().splitlines()[1].startswith("a,1,C1,hold")
    assert report.list_archives(tmp_path)[0]["total"]["applied"] == 1


def test_test_lab_command_check_matches_jsonschema():
    """The viewer's dependency-free check accepts what jsonschema accepts and rejects what it rejects."""
    import uuid as _uuid
    from pathlib import Path

    import jsonschema
    import pytest

    from src.data.test_lab.decisions import check_command

    schema = json.loads((Path(__file__).resolve().parents[4] / "contracts/read/command_event.schema.json").read_text())
    ok = {"source": "backend", "event_id": str(_uuid.uuid4()), "schema_version": "1.0.0", "event_type": "decision",
          "event_ts": "2026-11-24T22:10:00Z",
          "payload": {"rec_id": str(_uuid.uuid4()), "action": "apply", "user_id": "test-lab", "ts": "2026-11-24T22:10:00Z"}}
    jsonschema.validate(ok, schema)
    check_command(ok, schema)
    bad = [{**ok, "source": "frontend"}, {**ok, "extra": 1}, {**ok, "payload": {**ok["payload"], "action": "maybe"}},
           {**ok, "payload": {**ok["payload"], "note": "x"}}, {**ok, "payload": {**ok["payload"], "rec_id": "nope"}}]
    for ev in bad:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(ev, schema, format_checker=jsonschema.FormatChecker())
        with pytest.raises(ValueError):
            check_command(ev, schema)


def test_archived_series_averages_per_simulated_minute(tmp_path):
    key = report.run_key(T0)
    series = [{"as_of_ts": "2026-11-24T22:01:10+00:00", "mean_wait_s": 300.0, "computable": True, "in_service": 3, "bunched": 0},
              {"as_of_ts": "2026-11-24T22:01:35+00:00", "mean_wait_s": 320.0, "computable": True, "in_service": 4, "bunched": 1},
              {"as_of_ts": "2026-11-24T22:02:00+00:00", "mean_wait_s": 999.0, "computable": False, "in_service": 4, "bunched": 1}]
    report.write_archive(tmp_path, key, {"run_key": key, "rows": [], "total": {"applied": 2},
                                         "outcomes": {"series": series, "run": {"avg_wait_s": 310.0},
                                                      "effects": [{"close_ts": "x", "outcome": "applied"}]}})
    s = report.archived_series(tmp_path, key)
    assert s["minutes"] == [{"t": "2026-11-24T22:01:00Z", "wait": 310.0, "in_service": 3.5, "bunched": 0.5},
                            {"t": "2026-11-24T22:02:00Z", "wait": None, "in_service": 4.0, "bunched": 1.0}]
    assert s["marks"] == [{"t": "x", "outcome": "applied"}] and s["total"]["applied"] == 2
    assert report.archived_series(tmp_path, "../x") is None
