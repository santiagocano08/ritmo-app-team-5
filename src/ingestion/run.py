"""
Ingestion entry point — STUB for US-2 container bring-up.

The real implementation is in US-3 (T015–T017).  This stub reads JSON-lines
from stdin and discards them, so the container pipe (simulator | ingestion)
keeps running without crashing.
"""
from __future__ import annotations

import sys


def main() -> None:
    """Consume JSON-lines from stdin; do nothing with them (stub).

    The real implementation (US-3) replaces this body with:
      validate → bronze.ingest() → bronze.rejections on failure
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        # Stub: discard. Real implementation validates and writes to bronze.


if __name__ == "__main__":
    main()
