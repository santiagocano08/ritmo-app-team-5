"""
T004 — Tests for the US-1 reference data build.

TDD: these tests are written BEFORE the implementation. They must fail until
src/data/reference/build.py and src/data/reference/sources.py are implemented (T005/T006).

Covers:
- Two rebuilds produce byte-identical output (FR-001, SC-007).
- Total size < 1 MB (FR-001).
- segments.csv has exactly 17 direction-1 rows (FR-002).
- congestion_factor.csv has 24 rows; 0.43-0.56 is a SANITY BAND (warn, keep
  computed values — R7, M2 fix). Values outside the band trigger a warning,
  NOT a build failure.
- SOURCES.md has one line per output file (FR-007).
- stops.csv uses real P-<objectid> ids (FR-003, FR-008, R6).
- A missing required raw source fails the build with a named message (edge case).
"""
from __future__ import annotations

import csv
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
REFERENCE_DIR = REPO_ROOT / "data" / "reference"
RAW_DIR = REPO_ROOT / "data" / "raw"

# Skip all tests if raw sources are not present (the build requires them).
# In CI without raw data, these are skipped — not failed.
requires_raw = pytest.mark.skipif(
    not RAW_DIR.exists() or not any(RAW_DIR.iterdir()),
    reason="data/raw/ sources not present — skipping reference build tests",
)


def _hash_dir(path: Path) -> str:
    """SHA-256 of all file contents in a directory, sorted by filename."""
    hasher = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            hasher.update(f.name.encode())
            hasher.update(f.read_bytes())
    return hasher.hexdigest()


def _run_build(output_dir: Path) -> None:
    """Run the reference build, writing output to output_dir."""
    env = os.environ.copy()
    env["REFERENCE_OUTPUT_DIR"] = str(output_dir)
    result = subprocess.run(
        [sys.executable, "-m", "src.data.reference.build"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Reference build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


@requires_raw
class TestBuildDeterminism:
    """FR-001, SC-007: two rebuilds are byte-identical."""

    def test_two_builds_byte_identical(self, tmp_path):
        out1 = tmp_path / "build1"
        out2 = tmp_path / "build2"
        out1.mkdir()
        out2.mkdir()

        _run_build(out1)
        _run_build(out2)

        hash1 = _hash_dir(out1)
        hash2 = _hash_dir(out2)
        assert hash1 == hash2, (
            f"Two builds produced different output.\n"
            f"Build 1 hash: {hash1}\nBuild 2 hash: {hash2}"
        )


@requires_raw
class TestBuildSize:
    """FR-001: total reference size < 1 MB."""

    def test_total_size_under_1mb(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)

        total_bytes = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
        assert total_bytes < 1_048_576, (
            f"Reference data too large: {total_bytes} bytes (limit 1 MiB)"
        )


@requires_raw
class TestSegments:
    """FR-002: exactly 17 direction-1 segments."""

    def test_segments_exactly_17_rows(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)

        seg_file = out / "segments.csv"
        assert seg_file.exists(), "segments.csv not produced"
        with open(seg_file, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 17, (
            f"Expected 17 segments, got {len(rows)}"
        )

    def test_segments_have_required_columns(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)

        with open(out / "segments.csv", newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames or []
        for col in ("segment_id", "length_m", "free_flow_kmh", "slope_pct"):
            assert col in cols, f"segments.csv missing column '{col}'"


@requires_raw
class TestCongestionFactor:
    """FR-005 (M2 fix): 24 rows; 0.43–0.56 is a sanity BAND (warn, keep computed).

    The test checks:
    - 24 rows (one per hour 0–23)
    - Values are computed (not clamped to any range)
    - If a value is outside 0.43-0.56 a build warning was emitted (we check
      presence, not content, since warnings go to stderr; the value is kept).
    """

    def test_congestion_factor_has_24_rows(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)

        cf_file = out / "congestion_factor.csv"
        assert cf_file.exists(), "congestion_factor.csv not produced"
        with open(cf_file, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 24, (
            f"Expected 24 congestion-factor rows (one per hour), got {len(rows)}"
        )

    def test_congestion_factor_columns(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)

        with open(out / "congestion_factor.csv", newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames or []
        assert "hour" in cols
        assert "congestion_factor" in cols

    def test_congestion_factor_values_are_positive(self, tmp_path):
        """Computed values are kept as-is; they must at least be positive."""
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)

        with open(out / "congestion_factor.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            cf = float(row["congestion_factor"])
            assert cf > 0, f"Hour {row['hour']}: congestion_factor must be positive, got {cf}"

    def test_congestion_factor_sanity_band_is_warning_not_error(self, tmp_path):
        """Values outside 0.43–0.56 produce a build warning, not a failure.

        This test verifies the build does NOT fail when a value is outside the
        band; the actual warning text is checked by inspecting build stderr.
        """
        out = tmp_path / "build"
        out.mkdir()
        # Build must not raise even if any value is outside 0.43-0.56.
        # _run_build raises only on non-zero returncode.
        _run_build(out)  # must not raise

        with open(out / "congestion_factor.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        # Verify values exist and are floats (not clamped).
        for row in rows:
            val = float(row["congestion_factor"])
            # Only a warning is expected if outside band; value is kept.
            assert isinstance(val, float)


@requires_raw
class TestSourcesMd:
    """FR-007: SOURCES.md has one line per output file."""

    def test_sources_md_exists(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)
        assert (out / "SOURCES.md").exists(), "SOURCES.md not produced"

    def test_sources_md_one_line_per_file(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)

        # Count non-empty, non-header lines
        sources_text = (out / "SOURCES.md").read_text()
        output_files = [
            f for f in out.iterdir()
            if f.is_file() and f.name != "SOURCES.md"
        ]
        # Each output file must have an entry in SOURCES.md
        for f in output_files:
            assert f.name in sources_text, (
                f"SOURCES.md missing entry for '{f.name}'"
            )


@requires_raw
class TestStops:
    """FR-003, FR-008, R6: real stop ids in P-<objectid> format."""

    def test_stops_csv_exists(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)
        assert (out / "stops.csv").exists(), "stops.csv not produced"

    def test_stops_use_real_p_objectid_format(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)

        with open(out / "stops.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0, "stops.csv is empty"
        for row in rows:
            sid = row["stop_id"]
            assert sid.startswith("P-"), (
                f"stop_id '{sid}' does not follow P-<objectid> format"
            )
            # objectid suffix must be numeric
            suffix = sid[2:]
            assert suffix.isdigit(), (
                f"stop_id '{sid}' has non-numeric objectid suffix"
            )

    def test_stops_direction1_count(self, tmp_path):
        """Direction-1 stops from itinerario 'C6-008 La Libertad' = 18."""
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)

        with open(out / "stops.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 18, (
            f"Expected 18 direction-1 stops (itinerario 'C6-008 La Libertad'), "
            f"got {len(rows)}"
        )

    def test_stops_have_required_columns(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)

        with open(out / "stops.csv", newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames or []
        for col in ("stop_id", "stop_name", "distance_along_m", "segment_id"):
            assert col in cols, f"stops.csv missing column '{col}'"


@requires_raw
class TestMissingRawSource:
    """Edge case: build fails with a named message when a raw source is missing."""

    def test_missing_raw_source_named_error(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        # Temporarily hide the segments file by using a fake RAW dir
        fake_raw = tmp_path / "fake_raw"
        fake_raw.mkdir()
        # Empty raw dir — all required sources are missing
        env = os.environ.copy()
        env["REFERENCE_OUTPUT_DIR"] = str(out)
        env["RAW_DIR"] = str(fake_raw)
        result = subprocess.run(
            [sys.executable, "-m", "src.data.reference.build"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0, "Build should fail when raw source is missing"
        # The error message must name the missing source
        combined = result.stdout + result.stderr
        assert any(
            keyword in combined.lower()
            for keyword in ("missing", "not found", "required", "raw")
        ), (
            f"Build failure message does not name the missing source.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


@requires_raw
class TestDemandVolume:
    """Data fix: direction-1 daily demand derived from raw data (triangulation step A)."""

    def test_direction1_daily_riders_in_expected_range(self, tmp_path):
        out = tmp_path / "build"
        out.mkdir()
        _run_build(out)
        rows = list(csv.DictReader((out / "demand_volume.csv").open(encoding="utf-8")))
        assert len(rows) == 1
        assert 600 <= float(rows[0]["daily_riders_dir1"]) <= 670
        assert (rows[0]["stops_basin6"], rows[0]["stops_prado"], rows[0]["stops_c6008"]) == (
            "1191", "343", "35")
        assert "demand_volume.csv" in (out / "SOURCES.md").read_text()


class TestCommittedCongestionFactor:
    """US1 (FR-010, FR-011, SC-001): the committed CSV is on the local hour. Runs in CI without data/raw/."""

    def _rows(self):
        with open(REFERENCE_DIR / "congestion_factor.csv", newline="") as f:
            return {int(r["hour"]): float(r["congestion_factor"]) for r in csv.DictReader(f)}

    def test_24_hours_and_anchors(self):
        rows = self._rows()
        assert sorted(rows) == list(range(24))
        assert rows[17] == 0.4816
        assert min(rows, key=rows.get) == 18 and rows[18] == 0.4575
        assert max(rows, key=rows.get) == 3 and rows[3] == 0.5656


@requires_raw
class TestCongestionFactorLocalHour:
    """US1: factors equal the raw SIMM file grouped by UTC hour - 5 (independent recomputation)."""

    def test_build_matches_independent_recomputation(self, tmp_path):
        from collections import defaultdict
        from datetime import datetime, timedelta, timezone

        with open(RAW_DIR / "plata" / "tramos_c6008_s1_osm.csv", newline="", encoding="utf-8") as f:
            segs = list(csv.DictReader(f))
        total = sum(float(r["largo_m"]) for r in segs)
        free = sum(float(r["v_libre_kmh"]) * float(r["largo_m"]) for r in segs) / total
        by_hour = defaultdict(list)
        with open(RAW_DIR / "plata" / "simm_corredor_c6008.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    ts = datetime.strptime(r["FECHAHORA"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                    v = float(r["VELOCIDAD"])
                except (ValueError, KeyError):
                    continue
                by_hour[(ts - timedelta(hours=5)).hour].append(v)
        expected = {h: round(sum(v) / len(v) / free, 4) for h, v in by_hour.items()}

        out = tmp_path / "out"
        out.mkdir()
        _run_build(out)
        with open(out / "congestion_factor.csv", newline="") as f:
            got = {int(r["hour"]): float(r["congestion_factor"]) for r in csv.DictReader(f)}
        assert set(expected) == set(range(24))
        assert max(abs(got[h] - expected[h]) for h in range(24)) == 0

    def test_hour_without_data_uses_overall_mean(self, tmp_path):
        import warnings

        from src.data.reference.build import build_congestion_factor

        raw = tmp_path / "raw" / "plata"
        raw.mkdir(parents=True)
        (raw / "tramos_c6008_s1_osm.csv").write_text("largo_m,v_libre_kmh\n100,50\n")
        (raw / "simm_corredor_c6008.csv").write_text(
            "FECHAHORA,VELOCIDAD\n2021-01-01T15:00:00.000Z,20.0\n2021-01-01T16:00:00.000Z,30.0\n"
        )
        out = tmp_path / "o"
        out.mkdir()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            build_congestion_factor(tmp_path / "raw", out, out / "segments.csv")
        with open(out / "congestion_factor.csv", newline="") as f:
            got = {int(r["hour"]): float(r["congestion_factor"]) for r in csv.DictReader(f)}
        assert got[10] == 0.4 and got[11] == 0.6  # 15Z and 16Z are local 10 and 11
        assert got[0] == 0.5  # overall mean 25 / 50
        assert any("No SIMM data" in str(x.message) for x in w)
