"""SIM_WARMUP_S: the first N simulated seconds are written without the pace; the bytes never change."""
from __future__ import annotations

import io

import pytest

from src.data.simulator import main as sim_main


def _run(monkeypatch: pytest.MonkeyPatch, warmup: str | None, duration: int = 60) -> tuple[str, list[float]]:
    sleeps: list[float] = []
    monkeypatch.setattr(sim_main.time, "sleep", lambda s: sleeps.append(s))
    for name in ("SIM_SCENARIO_FILE", "SIM_HOLDS", "SIM_TRUTH_PATH", "SIM_DEMAND_SCALE", "SIM_START_HOUR"):
        monkeypatch.delenv(name, raising=False)
    if warmup is None:
        monkeypatch.delenv("SIM_WARMUP_S", raising=False)
    else:
        monkeypatch.setenv("SIM_WARMUP_S", warmup)
    buf = io.StringIO()
    sim_main.main(["--seed", "42", "--duration", str(duration), "--pace", "1"], out=buf)
    return buf.getvalue(), sleeps


def test_warmup_skips_the_pace_before_it_and_keeps_it_after(monkeypatch: pytest.MonkeyPatch) -> None:
    base, paced = _run(monkeypatch, None)
    warm, after = _run(monkeypatch, "30")
    assert warm == base                       # same bytes
    assert len(paced) == 11                   # every 5 s step after the first is paced
    assert len(after) == 5                    # only the steps that land after 30 s: 35, 40, 45, 50, 55 s
    assert sum(after) == pytest.approx(5.0)


def test_warmup_longer_than_the_run_never_sleeps(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(monkeypatch, "600")[1] == []


@pytest.mark.parametrize("raw", ["-1", "abc", "14401"])
def test_invalid_warmup_exits_before_any_event(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, raw)
    assert exc.value.code == 2
