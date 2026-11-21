# PROPOSAL: ingestion freshness SLI and SLO

Status: **PROPOSAL**. It is not an adopted norm. Adopting it needs a separate pull request labeled
`constitutional-amendment` (see the constitution, Governance).

## SLI

At every healthcheck probe (every 5 s) the service is *fresh* if the seconds since the last insert into
`bronze.events` are at most 15, and *stale* otherwise.

SLI = fresh probes / total probes, over a rolling window, counted only while a live feed is expected
(a finite simulator run that ended is not counted).

## Proposed SLO

99 % of probes fresh over a rolling 28 days.

Error budget: (1 - 0.99) x 28 x 24 x 60 = **403 minutes** of stale time per 28 days.

| Target | Error budget per 28 days |
|---|---|
| 99 % (proposed) | 403 minutes (403.2) |
| 99.5 % | 201.6 minutes |
| 99.9 % | 40.3 minutes |

## Reasoning

Measured in the drill rerun (`docs/ops/drill-rerun.md`), stale time seen by the healthcheck:

| Fault | Time `unhealthy` | Share of the 403-minute budget |
|---|---|---|
| F2: database stopped 31 s | 32.4 s (12:20:43.6Z to 12:21:15.9Z) | 0.13 % |
| F3: ingestion process killed | at least 73 s (from 12:22:55.9Z, still stale when observation ended at 12:24:09Z) | at least 0.30 % |

Seconds above the 15 s threshold: F2 about 18 s (last insert about 12:20:38Z, first new insert 12:21:11Z),
F3 at least 73 s. One F2-style outage and one F3-style crash together use under 2 minutes, about 0.5 % of
the budget, so 99 % over 28 days is not tight for these two faults. The budget would be spent by a crash
that is not recovered: the replay after F3 had not caught up when the window ended, so a single crash
during a busy period can cost more than the 73 s seen here. The numbers support keeping 99 %; they do not
justify a stricter target until the replay after a crash is fixed (not part of this feature).
