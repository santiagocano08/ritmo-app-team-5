"""T041 - static checks of scripts/drill/run_drill.sh (the drill itself runs only by hand)."""
from __future__ import annotations

import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "drill" / "run_drill.sh"
HEADER = "t_s,events,max_event_ts,ingestion_lag_s,duplicates,other_rejections,ingestion,api,db"


def _text() -> str:
    assert SCRIPT.is_file(), f"script not found: {SCRIPT}"
    return SCRIPT.read_text(encoding="utf-8")


def _code_lines() -> list[str]:
    return [ln for ln in _text().splitlines() if ln.strip() and not ln.strip().startswith("#")]


def test_english_ascii_only():
    text = _text()
    assert text.isascii()
    for word in ("inyectada", "simulacro", "INICIO", "LIMPIO", "observacion", "rechazos"):
        assert word.lower() not in text.lower()


def test_strict_mode_and_dedicated_project():
    text = _text()
    assert re.search(r"^set -u", text, re.MULTILINE)
    assert re.search(r"^export COMPOSE_PROJECT_NAME=pulsoflota-drill$", text, re.MULTILINE)
    # No -p/--project-name flag that could point a call to another project.
    for line in _code_lines():
        assert not re.search(r"docker compose\s+(-p|--project-name)\b", line)
    assert "COMPOSE_PROJECT_NAME" in text.split("docker compose", 1)[0]  # exported before any call


def test_down_v_only_after_the_project_is_pinned():
    text = _text()
    first_compose = text.index("docker compose")
    assert text.index("export COMPOSE_PROJECT_NAME=pulsoflota-drill") < first_compose
    assert "down -v" in text


def test_port_and_stack_guard_aborts():
    text = _text()
    assert "/dev/tcp/" in text
    assert re.search(r"POSTGRES_PORT", text) and re.search(r"API_PORT", text)
    guard = text[: text.index("down -v")]
    assert "exit 1" in guard


def test_windows_in_order():
    sleeps = re.findall(r"^\s*sleep\s+(\d+)\s*;?", _text(), re.MULTILINE)
    # the sampler's own `sleep 2` is the first match inside the monitor function
    assert sleeps[0] == "2"
    assert sleeps[1:] == ["45", "30", "25", "30", "90", "90"]


def test_faults():
    text = _text()
    assert "docker compose stop api" in text
    assert "docker compose stop db" in text
    assert "kill -9" in text.lower() or "os.kill" in text


def test_ingestion_kill_uses_exact_argv_rule():
    text = _text()
    assert "src.data.ingestion.run" in text
    assert 'args[1:3] == ["-m", "src.data.ingestion.run"]' in text
    assert "!= 1" in text or "(1, " in text  # never PID 1
    assert "os.getpid()" in text  # never the helper itself
    assert not re.search(r"in\s+c(mdline)?\b.*src\.data\.ingestion\.run", text)  # no substring match
    assert "b'src" not in text and 'b"src' not in text


def test_header_and_outputs():
    text = _text()
    assert HEADER in text
    assert "drill-out" in text
    for name in ("metrics.csv", "events.log", "restarts.txt", "rejections.txt", "bronze_counts.txt",
                 "ingestion.log", "health_events.log", "retry_lines.log", "ingestion_inspect.txt"):
        assert name in text, name
    assert ".drill-input" not in text


def test_no_secret_literals():
    text = _text().lower()
    for needle in ("password=", "postgres_password=", "change_me", "postgresql://"):
        assert needle not in text
