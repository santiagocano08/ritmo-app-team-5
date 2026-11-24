"""Independent oracle for the stop-based EWT (005, US3; research R4, R5).

Recomputes everything from the raw simulator events (envelope dicts), never from `silver`, `gold` or
`src/data/rules/stop_metrics.py`. The same arithmetic the data owner's mock uses: headways between
consecutive departures at one stop, attributed to the closing departure; integer seconds, exact sums.

Local time is the fixed UTC-5 offset; a band is a clock-aligned 15-minute local interval.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

PLANNED_S = 420  # config.corridor_settings.headway_planned_s since issue #42 (600 before)
ESTIMATED_AFTER_S = 120
LOCAL_OFFSET_S = -5 * 3600
BAND_S = 900
STOPS = tuple(f"P-{n}" for n in range(883, 901))      # the 18 reference stops
CORRIDOR_STOPS = STOPS[5:]                            # P-888..P-900, the mock's stops
BUS_EVENTS = ("bus_position", "stop_arrival", "stop_departure")


def epoch(iso: str) -> int:
    """RFC 3339 UTC string (whole seconds) -> integer epoch seconds."""
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())


def band_of(ts: int) -> tuple[str, int]:
    """(local date, band 0..95) of an epoch second."""
    local = ts + LOCAL_OFFSET_S
    day, rest = divmod(local, 86400)
    return datetime.fromtimestamp(day * 86400, tz=timezone.utc).date().isoformat(), rest // BAND_S


def departures(events: list[dict]) -> dict[str, list[tuple[int, str, str, bool]]]:
    """stop -> sorted [(ts, bus, trip, estimated)] from the raw `stop_departure` events.

    `estimated` = the bus's previous report (any bus event type, strictly earlier time) is more than
    120 s before the departure; no earlier report means not estimated.
    """
    times: dict[str, set[int]] = defaultdict(set)
    for e in events:
        if e["event_type"] in BUS_EVENTS and e["source"] != "backend":
            times[e["payload"]["bus_id"]].add(epoch(e["event_ts"]))
    out: dict[str, list[tuple[int, str, str, bool]]] = defaultdict(list)
    for e in events:
        if e["event_type"] != "stop_departure" or e["source"] == "backend":
            continue
        p, ts = e["payload"], epoch(e["event_ts"])
        earlier = [t for t in times[p["bus_id"]] if t < ts]
        estimated = bool(earlier) and ts - max(earlier) > ESTIMATED_AFTER_S
        out[p["stop_id"]].append((ts, p["bus_id"], p["trip_id"], estimated))
    for rows in out.values():
        rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return out


def intervals(events: list[dict], stops=STOPS) -> list[tuple[str, int, int, bool]]:
    """[(stop, closing_ts, headway_s, excluded)] over the given stops."""
    deps = departures(events)
    result = []
    for stop in stops:
        rows = deps.get(stop, [])
        for a, b in zip(rows, rows[1:]):
            result.append((stop, b[0], b[0] - a[0], a[3] or b[3]))
    return result


def _sums(rows: list[tuple[str, int, int, bool]]) -> dict:
    used = [h for _, _, h, excluded in rows if not excluded]
    n = len(used)
    return {"n": n, "sum_h": sum(used), "sum_h2": sum(h * h for h in used),
            "sum_p": n * PLANNED_S, "sum_p2": n * PLANNED_S * PLANNED_S,
            "n_excluded": sum(1 for r in rows if r[3])}


def ewt(sums: dict) -> float | None:
    """Σh²/(2Σh) − Σhp²/(2Σhp); None when there is nothing to measure."""
    if sums["n"] == 0 or sums["sum_h"] <= 0:
        return None
    return sums["sum_h2"] / (2 * sums["sum_h"]) - sums["sum_p2"] / (2 * sums["sum_p"])


def window(events: list[dict], lo: int, hi: int, stops=STOPS) -> dict:
    """Sums of the headways whose closing departure is in (lo, hi], over the given stops."""
    return _sums([r for r in intervals(events, stops) if lo < r[1] <= hi])


def live_by_stop(events: list[dict], as_of: int, stops=STOPS) -> dict[str, dict]:
    """Trailing 15-minute sums per stop at `as_of` (every stop present, zeros when empty)."""
    rows = intervals(events, stops)
    return {s: _sums([r for r in rows if r[0] == s and as_of - BAND_S < r[1] <= as_of]) for s in stops}


def bands(events: list[dict], as_of: int, stops=STOPS) -> dict[tuple[str, int, str], dict]:
    """Closed bands only (end <= as_of): {(local date, band, stop): sums}; sparse like the gold table."""
    grouped: dict[tuple[str, int, str], list] = defaultdict(list)
    for r in intervals(events, stops):
        date, band = band_of(r[1])
        start_utc = (r[1] // BAND_S) * BAND_S  # the offset is whole hours, so UTC and local bands coincide
        if start_utc + BAND_S <= as_of:
            grouped[(date, band, r[0])].append(r)
    return {k: _sums(v) for k, v in grouped.items()}


def add(a: dict, b: dict) -> dict:
    return {k: a[k] + b[k] for k in a}


# -- 005 US4: P(board <= t), simple method (research R6; data-model E7) -----------------------------------------
THRESHOLDS_S = (300, 600, 900)


def riders(events: list[dict], as_of: int, stops=STOPS) -> dict[tuple[str, int, str], dict]:
    """{(local date, band of the arrival, stop): counts} for every `rider_arrival` at the given stops.

    One rider per (`source`, `event_id`). The wait is to the next departure of **any** bus from the stop with
    `arrival <= departure <= as_of` (a departure at the arrival second counts, wait 0); no such departure means
    the rider is only in `n_riders`. Independent of `src/data/rules/boarding.py`, `silver` and `gold`.
    """
    deps = {s: sorted(r[0] for r in rows) for s, rows in departures(events).items()}
    seen: set[tuple[str, str]] = set()
    out: dict[tuple[str, int, str], dict] = {}
    for e in events:
        if e["event_type"] != "rider_arrival":
            continue
        key = (e["source"], e["event_id"])
        a, stop = epoch(e["event_ts"]), e["payload"]["stop_id"]
        if key in seen or stop not in stops or a > as_of:
            continue
        seen.add(key)
        date, band = band_of(a)
        row = out.setdefault((date, band, stop), {"n_riders": 0, "n_le_5": 0, "n_le_10": 0, "n_le_15": 0})
        row["n_riders"] += 1
        d = next((x for x in deps.get(stop, []) if a <= x <= as_of), None)
        if d is not None:
            for name, t in zip(("n_le_5", "n_le_10", "n_le_15"), THRESHOLDS_S):
                row[name] += int(d - a <= t)
    return out


def riders_by_band(events: list[dict], as_of: int, stops=STOPS) -> dict[tuple[str, int], dict]:
    """The same counts summed over stops: {(local date, band): counts}."""
    out: dict[tuple[str, int], dict] = {}
    for (date, band, _stop), v in riders(events, as_of, stops).items():
        acc = out.setdefault((date, band), {k: 0 for k in v})
        for k, n in v.items():
            acc[k] += n
    return out
