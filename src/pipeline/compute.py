"""`python -m src.pipeline.compute`: compute gold snapshots on demand (contracts/compute-and-refresh.md).

    --as-of TS                       one snapshot at UTC time TS
    --from TS --to TS [--step S]     replay: one snapshot every S seconds (default 5)
    --no-notify                      skip pg_notify (bulk replays)

Reads DATABASE_URL and LOG_LEVEL. Prints one JSON line per snapshot. Exit 0 on success, non-zero
after the first failed cycle (nothing published for it). Ignores REFRESH_CLOCK.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import psycopg

from src.pipeline.cycle import CycleError, run_cycle
from src.pipeline.reference import load_reference
from src.pulsoflota.config import get_db_dsn, get_log_level


def _timestamp(text: str) -> datetime:
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an ISO-8601 time: {text!r}") from None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _positive(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from None
    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return value


def _iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts.microsecond == 0 else ts.isoformat()


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.pipeline.compute", description=__doc__.split("\n")[0])
    p.add_argument("--as-of", type=_timestamp, metavar="TS", help="compute one snapshot at this UTC time")
    p.add_argument("--from", dest="from_ts", type=_timestamp, metavar="TS", help="replay start (UTC)")
    p.add_argument("--to", dest="to_ts", type=_timestamp, metavar="TS", help="replay end (UTC, inclusive)")
    p.add_argument("--step", type=_positive, default=5, metavar="S", help="replay step in seconds (default 5)")
    p.add_argument("--no-notify", action="store_true", help="do not send pg_notify")
    return p


def _times(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Iterator[datetime]:
    if args.as_of is not None:
        if args.from_ts or args.to_ts:
            parser.error("--as-of cannot be combined with --from/--to")
        yield args.as_of
        return
    if args.from_ts is None or args.to_ts is None:
        parser.error("give --as-of, or both --from and --to")
    if args.to_ts < args.from_ts:
        parser.error("--to must not be earlier than --from")
    t = args.from_ts
    while t <= args.to_ts:
        yield t
        t += timedelta(seconds=args.step)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    times = list(_times(args, parser))
    logging.basicConfig(level=get_log_level(), stream=sys.stderr, format="%(message)s")
    try:
        dsn = get_db_dsn()
    except RuntimeError as exc:
        print(json.dumps({"error": "configuration", "message": str(exc)}), file=sys.stderr)
        return 2
    with psycopg.connect(dsn) as conn:
        load_reference(conn)
        for as_of in times:
            try:
                result = run_cycle(conn, as_of, notify=not args.no_notify)
            except CycleError as exc:
                print(json.dumps({"error": "cycle_failed", "as_of_ts": _iso(as_of),
                                  "correlation_id": exc.correlation_id}), file=sys.stderr)
                return 1
            if result is not None:
                print(json.dumps({"snapshot_id": str(result.snapshot_id), "as_of_ts": _iso(result.as_of_ts),
                                  "max_bronze_id": result.max_bronze_id, "status": result.status}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
