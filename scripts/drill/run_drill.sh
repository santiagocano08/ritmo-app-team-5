#!/usr/bin/env bash
# Incident drill on the real stack of this repository (feature 003, rerun of the 2026-11-18 drill).
# F1: the API stops. F2: the database stops. F3: the ingestion process is killed (crash).
#
# Same faults, windows and sampling as the 2026-11-18 baseline (docs/ops/drill-baseline/):
#   start, 45 s, F1 30 s, 25 s, F2 30 s, 90 s, F3, 90 s, end; one sample every 2 s.
#
# Safety:
#   - Runs ONLY under its own Compose project, pulsoflota-drill, with its own volume. Every call
#     below inherits that project name, so the volume removal at start and end cannot touch the
#     developer's default stack.
#   - Uses non-default published ports (override with DRILL_POSTGRES_PORT / DRILL_API_PORT) and
#     aborts if they are already in use, so it can run next to the default stack.
#   - Writes only under drill-out/ (git-ignored). Never reads or writes the local baseline inputs.
#   - Prints no credential: the database user and name are read inside the db container.
#
# Usage: bash scripts/drill/run_drill.sh   (about 6 minutes)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1

export COMPOSE_PROJECT_NAME=pulsoflota-drill
export POSTGRES_PORT="${DRILL_POSTGRES_PORT:-55432}"
export API_PORT="${DRILL_API_PORT:-58000}"

# --- guard: refuse to start if a published port is taken --------------------------------------
port_in_use() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
for p in "$POSTGRES_PORT" "$API_PORT"; do
  if port_in_use "$p"; then
    echo "ABORT: port $p is already in use (another stack?). Free it or set DRILL_POSTGRES_PORT / DRILL_API_PORT." >&2
    exit 1
  fi
done
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "ABORT: .env was missing; created from .env.example. Set POSTGRES_PASSWORD in .env and run again." >&2
  else
    echo "ABORT: .env and .env.example are missing." >&2
  fi
  exit 1
fi

OUT="$ROOT/drill-out"
mkdir -p "$OUT"
CSV="$OUT/metrics.csv"; EV="$OUT/events.log"; INSPECT="$OUT/ingestion_inspect.txt"
HEALTH_RAW="$OUT/health_events.raw"
HEADER="t_s,events,max_event_ts,ingestion_lag_s,duplicates,other_rejections,ingestion,api,db"
T0=$(date +%s)
t() { echo $(( $(date +%s) - T0 )); }
mark() { echo "$(t)s $(date -u +%H:%M:%SZ) $*" | tee -a "$EV"; }
q() {
  docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAF, -c "$1"' sh "$1" 2>/dev/null
}
snap() {
  local cid
  cid=$(docker compose ps -aq ingestion 2>/dev/null | head -1)
  [ -n "$cid" ] && echo "$1 $(docker inspect -f 'restarts={{.RestartCount}} started_at={{.State.StartedAt}}' "$cid" 2>&1)" >> "$INSPECT"
}

monitor() {
  echo "$HEADER" > "$CSV"
  while [ -f "$OUT/.running" ]; do
    row=$(q "select (select count(*) from bronze.events),
                    (select to_char(max(event_ts) at time zone 'UTC','HH24:MI:SS') from bronze.events),
                    (select coalesce(extract(epoch from now()-max(arrival_ts))::int,-1) from bronze.events),
                    (select count(*) from bronze.rejections where reason='duplicate_event'),
                    (select count(*) from bronze.rejections where reason<>'duplicate_event')")
    [ -z "$row" ] && row="NA,NA,NA,NA,NA"
    st=$(for s in ingestion api db; do docker compose ps -a --format '{{.State}}' "$s" 2>/dev/null | head -1; done | paste -sd, -)
    echo "$(t),$row,$st" >> "$CSV"
    sleep 2
  done
}

# Convert the raw health events (epoch nanoseconds) to UTC timestamps.
health_to_utc() {
  python3 - "$HEALTH_RAW" "$OUT/health_events.log" <<'PY'
import sys
from datetime import datetime, timezone

src, dst = sys.argv[1], sys.argv[2]
with open(src) as fin, open(dst, "w") as fout:
    for line in fin:
        parts = line.split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        ts = datetime.fromtimestamp(int(parts[0]) / 1e9, tz=timezone.utc)
        fout.write(f"{ts.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]}Z {parts[1]}")
PY
}

kill_ingestion() {
  # Exact-argv rule: only the process whose argv after the interpreter is exactly
  # `-m src.data.ingestion.run`; never PID 1 (the shell of the pipeline), never this helper,
  # never a substring match on a command line.
  docker compose exec -T ingestion python - <<'PY'
import os, signal
own = os.getpid()
for entry in os.listdir("/proc"):
    if not entry.isdigit():
        continue
    pid = int(entry)
    if pid in (1, own):
        continue
    try:
        argv = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
    except OSError:
        continue
    args = [a.decode(errors="replace") for a in argv if a]
    if len(args) >= 3 and "python" in os.path.basename(args[0]) and args[1:3] == ["-m", "src.data.ingestion.run"]:
        os.kill(pid, signal.SIGKILL)
        print("killed", pid)
PY
}

cleanup() {
  rm -f "$OUT/.running"
  [ -n "${EVP:-}" ] && kill "$EVP" 2>/dev/null
  docker compose down -v >/dev/null 2>&1
}

# --- start --------------------------------------------------------------------------------------
docker compose down -v >/dev/null 2>&1
: > "$EV"; : > "$INSPECT"; : > "$HEALTH_RAW"; touch "$OUT/.running"
trap cleanup EXIT

docker events --filter event=health_status --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" \
  --format '{{.TimeNano}} {{.Actor.Attributes.name}} {{.Action}}' >> "$HEALTH_RAW" 2>/dev/null &
EVP=$!

T0=$(date +%s)
mark "START docker compose up (seed 42, pace 1 => 5x real time, project $COMPOSE_PROJECT_NAME)"
if ! docker compose up -d --build db api ingestion >/dev/null 2>&1; then
  echo "ABORT: the stack did not start (check .env and docker compose logs)." >&2
  exit 1
fi
monitor & MON=$!
snap "start"

sleep 45;  mark "F1 injected: docker compose stop api"; docker compose stop api >/dev/null 2>&1
sleep 30;  mark "F1 end: docker compose start api";     docker compose start api >/dev/null 2>&1
sleep 25;  snap "before_F2"; mark "F2 injected: docker compose stop db"; docker compose stop db >/dev/null 2>&1
sleep 30;  mark "F2 end: docker compose start db";      docker compose start db >/dev/null 2>&1
sleep 90;  snap "after_F2"; mark "F3 injected: kill -9 of the ingestion process (crash)"
kill_ingestion >/dev/null 2>&1
sleep 90;  snap "after_F3"; mark "END observation"

rm -f "$OUT/.running"; wait "$MON"
docker compose logs --no-color ingestion > "$OUT/ingestion.log" 2>&1
grep -E '"event": "(db_retry|db_recovered|db_retry_exhausted)"' "$OUT/ingestion.log" | sed -e 's/^[^{]*//' > "$OUT/retry_lines.log"
docker inspect -f '{{.Name}} restarts={{.RestartCount}}' $(docker compose ps -aq) > "$OUT/restarts.txt" 2>&1
q "select reason,count(*) from bronze.rejections group by 1 order by 1" > "$OUT/rejections.txt"
q "select count(*), count(distinct event_id) from bronze.events" > "$OUT/bronze_counts.txt"
kill "$EVP" 2>/dev/null; EVP=""
health_to_utc
docker compose down -v >/dev/null 2>&1
mark "CLEANED: drill containers and volume removed"
