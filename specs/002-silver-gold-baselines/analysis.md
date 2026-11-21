# Pre-implementation analysis — 002-silver-gold-baselines

Produced by Kiro `validate-plan` on 2026-11-18 (22:51). The agent could not write this file (non-interactive permission denial); it was transcribed verbatim from the run log by Claude. Decision: **GO**.

## Findings
Counts: 0 CRITICAL, 2 HIGH, 7 MEDIUM, 5 LOW. Line numbers come from search output; where I couldn't capture one, I name the task or section.

**HIGH**
- **H1, tasks.md:162 (T051):** it says "date change at 19:00Z → 00:00 local". With UTC−5, 19:00Z is 14:00 local, and local midnight is 05:00Z. T027 and T076 have the correct values. A test written from T051 would assert the wrong thing.
- **H2, plan.md:246-259:** "What is cut" still lists all of Phase 4 as cut #1 and says "Not cuttable: Phases 0–2". tasks.md:41-45 keeps the loop (T064, T065, T069, T070 and the short T071) and Phases 0–3 uncuttable, apart from CUT-2 and CUT-3. tasks.md should win, but the plan doesn't say so.

**MEDIUM**
- **M1, spec.md:196 and :219, plan.md:232, quickstart.md:69:** they still say SC-002 covers 4 fixtures and `c1_bunching` is excluded. T038 and T075 now cover 5.
- **M2, research.md:220 vs tasks.md:110 (T032):** R7 says SQL uses `AT TIME ZONE 'America/Bogota'`; T032 forbids it and requires the fixed UTC−5 offset. data-model.md:179 says "America/Bogotá".
- **M3, spec.md:144 and :170 vs research.md:152 (R5):** FR-016 and FR-036 promise one snapshot per cycle. R5 skips the insert and the `NOTIFY` when `(as_of_ts, rules_version, max_bronze_id)` repeats. In `REFRESH_CLOCK=data` mode an idle stream therefore produces no snapshot.
- **M4, tasks.md:41, 194, 196-198:** if CUT-1 is taken, "the loop continues after a failed cycle" (FR-040) has no test, because it lives only in T066. SC-009 cadence is also unverified, because only T068 covers it.
- **M5, tasks.md:43 and :166 (T054):** the R13 x.5 rounding test (research.md:354) sits only in T054, which CUT-3 can drop. T053 has no x.5 case.
- **M6, quickstart.md:99, compute-and-refresh.md:19:** Phase 4 is still labelled "cuttable". spec.md:79 says "first story to cut"; the spec is approved, so I'd leave it.
- **M7, tasks.md:45 and the "Implementation Strategy" section:** the minimum delivery is stated two ways. In effect it is Phases 0–3 plus T064, T065, T069, T070 and the short T071.

**LOW**
- **L1:** FR-020 says nothing about clamping negative headways to 0 (decided in R8, tested in T034).
- **L2:** tasks.md:23 says test files use the names in plan.md, but about 11 test files are not in the plan tree.
- **L3:** T025 cannot fail first. T075 combines the fixture fix and its test in one task. T072 adds tests after the fact.
- **L4:** no task asserts that snapshots are retained.
- **L5:** deferrals only, and consistent with turn 1. FR-004 (live time is current UTC) against the R3 `data` default for the demo, and no configuration version in lineage (R15).

## Your review points
- **Coverage:** all 41 FRs and all 11 SCs have at least one task, and all 76 tasks trace to a requirement or research item. SC-009 is covered only by CUT-1 tasks and the short T071 check.
- **Gate decisions:** Q1–Q3, R3, R8, R11, R12, R13 and R14 appear consistently in plan, data-model and tasks. The exceptions are M2 and M5, plus the idle-stream case in M3.
- **Five task-gate adjustments:** I read them as T075, T076, the narrowed CUT-1, the fixed UTC−5 offset in T032, and the compose wiring of `SIM_PLANNED_HEADWAY_S`. Please confirm that's your list. Stale copies remain for the first, third and fourth (M1, M2, H2/M6).
- **Cut list:** the loop is outside CUT-1, and Phases 0–3 are outside every cut except CUT-2 and CUT-3.
- **Contracts, bronze, boundary:** T075 is the only edit under `contracts/`. T024 and T073 check this with `git diff --stat`, and they also check `db/init/001_*`, `db/init/002_*` and ingestion code. T004 changes simulator schedule generation only, and T021 adds one line to the ADR.
- **Test-first order:** each phase lists tests before implementation and ends with a verification task. The exceptions are in L3.
- **Constitution v1.1.0, turn 1:** no violations, and nothing deferred is implemented.

I only checked the first two buses of the `normal`, `c2_gap`, `c5_breakdown` and `d1_source_outage` fixtures. T075's new consistency check runs over every fixture, so I haven't confirmed it passes on the rest. For `c1_bunching`, 960 s keeps B-102 `gap` and `n_gaps` at 1.

## Next actions
1. Fix H1 (T051) and H2 (plan "What is cut"). Both edit approved artifacts, so I need your OK.
2. Move the "loop continues after a failed cycle" case into T064, and one x.5 case per M2 path into T053 (M4, M5).
3. Align the remaining stale text in one pass (M1, M2, M6, M7).
4. Start `/speckit.implement` at T001.


## Resolution 2026-11-18

Fixes approved by the data owner on 2026-11-18. `spec.md` is unchanged (approved). No code written.

- **H1 resolved (tasks.md T051):** the date change is now 05:00Z = 00:00 local (UTC−5), tested at 04:59:59Z (hour band 23, M2 band 95) and 05:00:00Z (hour band 0, M2 band 0); 19:00Z is stated as 14:00 local. Consistent with T027 and T076.
- **H2 resolved (plan.md "What is cut"):** CUT-1 is only T066, T067, T068 and the 10-minute part of T071. The loop (T064, T065, T069, T070) and the short T071 check are not cuttable. Phases 0–3 are not cuttable except CUT-2 and CUT-3. The phase 4 row of the phase table was aligned, and `tasks.md` is declared authoritative for the cut list.
- **M1 resolved:** plan.md (phase 2 row) and quickstart.md now say SC-002 covers 5 fixtures, with `c1_bunching` fixed by T075.
- **M2 resolved:** research.md (R7) and data-model.md (S5 `hour_band`) use the fixed UTC−5 offset, not `America/Bogota`.
- **M3 resolved (declared limitation, no design change):** research.md R3 now states that in `REFRESH_CLOCK=data` mode, if the whole feed stops, `as_of_ts` freezes (R5 then inserts no snapshot and sends no `NOTIFY`) and buses do not turn Estimated. Single-bus outages (D1) work because other buses advance the clock. `wall` mode detects a whole-feed outage.
- **M4 resolved:** the "next cycle runs normally after a failed cycle" case (FR-040) moved into T064 (unit, fake cycle that raises once), so it survives CUT-1. The short T071 check now also records that the first-minute notification intervals are roughly 5 s (informal SC-009 smoke, no pass threshold). quickstart.md Phase 4 rows updated and marked CUT-1.
- **M5 resolved:** T053 now holds one x.5 rounding case per M2 path (observed {2, 3} → 3; reference path through the formula), so R13 survives CUT-3. T054 keeps only the R12 edge cases, and the CUT-3 row was updated.
- **M6 resolved:** quickstart.md and contracts/compute-and-refresh.md no longer label Phase 4 as cuttable; they say the loop is not cuttable and only its expensive checks are.
- **M7 resolved:** the minimum delivery is stated once, in tasks.md "Implementation Strategy": Phases 0–3 plus T064, T065, T069, T070 and the short T071. The cut list, plan.md and quickstart.md refer to it.
- **L1–L5:** accepted as is.
