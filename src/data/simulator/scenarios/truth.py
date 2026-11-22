"""Hidden scenario truth (004 FR-010, FR-011; research R2; data-model E2).

One JSON object per injector, written as JSON lines to `SIM_TRUTH_PATH` or to stderr when the
simulator run ends. The pipeline never reads it (static guard `test_no_truth_reads.py`). Records hold
ids, times and the validated parameters only: no event payload, no secret.

Order: by effective time, then configuration order; injectors that never fired come last in
configuration order. Hold records (004 Phase 2, `add_record`) follow, in the order they happened.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Sequence, TextIO

_COMMON_DROP = {"id", "type", "bus", "stop"}


class TruthSink:
    def __init__(self, scenarios: Sequence[Any], path: str | Path | None = None,
                 stream: TextIO | None = None) -> None:
        self._path = Path(path) if path else None
        self._stream = stream
        self._closed = False
        self._records: dict[str, dict] = {}
        self._order: list[str] = []
        self._extra: list[dict] = []  # hold records: appended as they happen
        for s in scenarios:
            params = {k: v for k, v in s.model_dump().items() if k not in _COMMON_DROP}
            rec: dict[str, Any] = {
                "scenario_id": s.id, "type": s.type, "params": params,
                "bus": getattr(s, "bus", None), "stop": getattr(s, "stop", None),
                "fired": False, "effective_ts": None,
            }
            if s.type == "C1":
                rec.update(follower_gap_s=None, target_reached=None)
            elif s.type == "D1_DUPLICATES":
                rec.update(event_ids=[])
            self._records[s.id] = rec
            self._order.append(s.id)

    def record(self, scenario_id: str) -> dict:
        """The live record of a scenario; the injectors fill it in."""
        return self._records[scenario_id]

    def fire(self, scenario_id: str, effective_ts: str) -> dict:
        rec = self._records[scenario_id]
        rec["fired"] = True
        rec["effective_ts"] = effective_ts
        return rec

    def add_record(self, record: dict) -> None:
        """Append a record that is not an injector of the scenario file (a hold order, 004 Phase 2)."""
        self._extra.append(record)

    def records(self) -> list[dict]:
        """Final order: fired by (effective time, configuration order), then never-fired ones."""
        index = {sid: i for i, sid in enumerate(self._order)}
        fired = sorted((r for r in self._records.values() if r["fired"]),
                       key=lambda r: (r["effective_ts"], index[r["scenario_id"]]))
        unfired = [self._records[sid] for sid in self._order if not self._records[sid]["fired"]]
        return fired + unfired + list(self._extra)

    def close(self) -> None:
        """Write the records once. Nothing is written when there is no injector."""
        if self._closed:
            return
        self._closed = True
        if not self._records and not self._extra:
            return
        lines = [json.dumps(r, sort_keys=True) for r in self.records()]
        if self._path is not None:
            self._path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            out = self._stream if self._stream is not None else sys.stderr
            out.write("\n".join(lines) + "\n")
            out.flush()
