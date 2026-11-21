# Pre-implementation analysis — 003-ops-ci-reliability

Produced by Kiro `validate-plan` on 2026-11-20. Read-only analysis of spec `2bb565f`, plan `bbf06e8` and tasks `26da4cb` (branch `feature/003-ops-ci-reliability`), plus research, data-model, contracts and quickstart, against constitution v1.1.0 and `docs/turns-ritmo.md` (turn 1). Only this file and `checklists/pre-implementation.md` were written. `.specify/extensions.yml` does not exist, so no hooks ran. `check-prerequisites.sh` is not executable (permission denied); the feature directory was resolved from `.specify/feature.json` and the branch.

**Decision: GO, with three conditions.** 0 CRITICAL. Phases 1 and 2 can start now. H3 must be applied before Phase 3 starts, and H1 and H2 before Phase 4 starts.

## Findings

Counts: 0 CRITICAL, 3 HIGH, 6 MEDIUM, 7 LOW. Line numbers are from `grep -n` / `cat -n` of the committed files.

### HIGH

- **H1, the header translation (task-gate decision of 2026-11-20) is not in the tasks; they say "keep the Spanish header".** Every place that must change:
  - `tasks.md:137` (Phase 4 comparability rules): "header `t_s,events,max_event_ts,lag_ingesta_s,dup,otros_rech,ingestion,api,db`".
  - `tasks.md:146` (T040): `metrics.csv` header "exactly" the Spanish string. The test would fail on the translated header.
  - `tasks.md:147` (T041): the script must emit "the exact baseline header string".
  - `tasks.md:152` (T043): copies `metricas.csv` to `metrics.csv` "byte for byte as captured". After the decision only the header line is replaced; every data row stays byte for byte.
  - `tasks.md:153` (T044): "the exact baseline header" and the sampler columns.
  - `tasks.md:158` (T049): the lag-reading rule names `lag_ingesta_s`.
  - `tasks.md:163` (T051): names `otros_rech`.
  - `tasks.md:164` (T052): "the same columns" (true in meaning, but must name the translated header).
  - `research.md:504-505`: "header kept byte for byte, `lag_ingesta_s`, `otros_rech`".
  - `research.md:514`: "baseline files stay as captured (Spanish labels)". No longer true for the header.
  - `plan.md:80` and `plan.md:297-298` say "same metric columns". They stay true if the decision is added to the research "Gate decisions".
  - Not affected: spec, quickstart, contracts (they never name the columns).
  - Proposed names (meaning unchanged; `events`, `max_event_ts`, `ingestion`, `api`, `db` are already English): `t_s,events,max_event_ts,ingestion_lag_s,duplicates,other_rejections,ingestion,api,db`. That is `lag_ingesta_s` to `ingestion_lag_s`, `dup` to `duplicates`, `otros_rech` to `other_rejections`. Use the same string in T040 (baseline file), T041 and T044 (script), T049 (rule) and T051. The baseline README (T043) records the old to new mapping and that only the header line was edited. T040 should also check that the data rows equal the original rows.
  - Fix: add one line to research "Gate decisions" and amend T040, T041, T043, T044, T049, T051, T052 and line 137. This is an edit to approved artifacts and needs your OK.

- **H2, the T049 lag-reading rule does not reproduce the baseline numbers it is meant to compare (`tasks.md:158`, `spec.md:22`, `spec.md:190`, `quickstart.md:172-173`).**
  - Rule: "lag after F2 = last sample at or before the F3 injection mark, baseline 125 s at t = 232 s". The F3 mark in `eventos.log` is at 228 s. The last samples at or before 228 s are t=225 (118) and t=227 (120). The 125 s sample is at t=232, after the mark. The rule gives 120, not 125.
  - Rule: "lag after F3 = last sample before the end of the observation, about 207 to 209 s". The spec, SC-009, research R12 and the quickstart say 204 s. 204 is the sample at t=312. The end mark is at 318 s and later samples are 207 (t=314) and 209 (t=316). The rule gives 209, not 204.
  - Effect: the "before" column of `docs/ops/drill-rerun.md` (T049) would differ from the approved spec and SC-009. T039 only checks that the table has no `TBD`, so nothing would catch it.
  - Fix: define one rule that gives 125 and 204 on the baseline CSV (for example "first sample at or after mark + 4 s" for F2 and "sample 6 s before the end mark" for F3), or state 120 and 209 in the table and say the spec figures came from an earlier reading. Apply the same rule to the rerun in T051 and T052.

- **H3, the T028 ADR test cannot run in the Andon command or in CI (`tasks.md:111`).** It compares the ADR "with the committed text at the parent of the change". The `tests` service mounts only `docs/adr`, not `.git` (`docker-compose.yml:162-172`), and the container has no git. The CI `test` job runs the same container. The test would fail or have to be skipped, so the one-line guarantee (FR-019, SC-011) would not be enforced where the gate runs.
  - Fix: the container test asserts that the new addendum sentence is present and follows the `config` addendum, like `test_adr_0001_has_the_config_addendum` (`test_schema_init.py:151`). The "one line plus blank separator, nothing removed" check stays a host command (`git diff --numstat docs/adr`), which T037(2) and T055(4) already run.

### MEDIUM

- **M1, live tests are not gated against the host suite (`tasks.md:78`, `:113`, `:18`, `:47`, `:91`, `:126`).** T016 and T030 are `@pytest.mark.live` and "host only", but no task says how they skip when not selected. Line 18 says "`-m live` tests excluded by hand, see the verification tasks", and the verification tasks do not say how. With `DATABASE_URL` set and Docker present, `uv run pytest` (T009, T023, T037, T055) would run `docker compose stop db` for 30 s in the middle of the suite. The existing `test_refresh_live.py:21` skips with "run it explicitly with `-m live`". Make T016 and T030 do the same, and state it in T023 and T037.
- **M2, the verification steps run `docker compose down -v` on the developer's default compose project (`tasks.md:91` T023, `:126` T037; `quickstart.md:88`, `:128`).** That deletes the developer volume. Plan risk 12 and T041 protect only the drill. The live tests T016 and T030 also stop and start `db` on the default project. Use a dedicated project (for example `COMPOSE_PROJECT_NAME=pulsoflota-verify`, exported for the live tests too) or add an explicit warning and a pre-check. The drill itself is safe: T041 requires `COMPOSE_PROJECT_NAME=pulsoflota-drill`, every call under it and the port guard.
- **M3, the plan says four getters and four variables; the tasks create three and one (`plan.md:185-187`, `:193`; `tasks.md:83-84`, `:119-120`; `contracts/README.md:22-25`).** `config.py` gets three retry getters (T018). `INGESTION_HEALTH_MAX_AGE_S` is read in `health.py` (T033). T019 adds three variables to `.env.example` and compose; T034 adds the fourth. The tasks are right; the plan's file list is wrong.
- **M4, stale statements contradict the Gate decisions (`plan.md:286` risk 7; `research.md:417-447` R12).** Risk 7 says "the drill sets a long `SIM_DURATION_S`"; the Gate decisions (`research.md:503`) say it is not overridden. R12 also says `ops.ingestion_health` is sampled every 5 s (`research.md:432`), F3 is `docker compose kill ingestion`, and there is a "comparability caveat" (`research.md:445-447`). The Gate decisions note says it wins over R12, but plan risk 7 has no such note. Edit risk 7 or mark R12 as superseded.
- **M5, T044 does not say how F3 selects the process to kill (`tasks.md:153`, `:147`).** The original script killed every process whose cmdline contains the string (`.drill-input/run_drill.sh:46`). In the repo, the PID 1 `sh -c` line and the helper's own `-c` argument also contain `src.data.ingestion.run`. T036 solves this for the simulator with an exact-argv rule; T044 and T041 only say "the process matching `src.data.ingestion.run`". Require the same rule (argv after the interpreter is exactly `-m src.data.ingestion.run`, never PID 1, never the helper) and assert it in T041.
- **M6, the "nothing else changed" checks are uneven (`tasks.md:47`, `:91`, `:126`, `:170`).** T023 checks `bronze.py`, `validate.py`, `contracts/` and ADRs; T037 checks `contracts/`, `bronze.py` and `.github/CODEOWNERS`; none names `src/data/db/init/002_bronze.sql` (the bronze table definitions). T009 checks neither CODEOWNERS nor bronze. Add `002_bronze.sql` (and the other `00x_*.sql` scripts; only `006_ops.sql` is new) and `.github/CODEOWNERS` to every phase's `git status` / `git diff --stat` check.

### LOW

- **L1, the SC-008 bound differs (`spec.md:189`; `tasks.md:113`; `plan.md:259`; `contracts/ops-ingestion-health.md`).** The spec says 15 s plus one healthcheck interval; the tasks, plan and contract say 15 s + 5 s + the probe duration. The tasks are the more realistic reading. Say so in the verification report.
- **L2, SC-011 says "exactly one added line" (`spec.md:192`); the plan and tasks accept one content line plus the blank separator (`plan.md:124-126`, risk 8).** Documented, follows the 002 precedent, and T037 and T055 state the blank line.
- **L3, `db_recovered` is a third log line beyond FR-011 and FR-012 (`spec.md:135-136`; `plan.md:119-121`).** Documented in the plan with its reason; SC-005 counts `db_retry` only.
- **L4, the `scripts` mount is in Phase 4 in the plan and quickstart (`plan.md:266`, `quickstart.md:154-155`) but in Phase 3 in the tasks (T034, `tasks.md:120`).** The tasks order is right because T029 needs it. The quickstart also attributes the `feed_control` check to `test_ops_docs.py` (`quickstart.md:153-154`); the tasks use `tests/unit/test_drill_feed_control.py` (T029).
- **L5, only the header is translated.** `events.log` and `restarts.txt` keep Spanish text (`INICIO`, `FIN observacion`, `/simulacro-...`). T043 copies them as captured and T040 counts eight marks. Confirm this is intended and say it in the baseline README.
- **L6, Actions are pinned by major version, not by SHA (`tasks.md:41`).** Evolution (A03, turn 2), not blocking.
- **L7, T010 modifies `contracts/read/fixtures/` in probe P3 (`tasks.md:51`).** Only on throwaway branches closed unmerged, and the text says so. Noted so nobody reads it as a change to `contracts/`.

## Coverage

All 28 FRs and all 11 SCs have at least one task, and all 55 tasks trace to a requirement or a research decision.

| Requirement | Tasks |
|---|---|
| FR-001 to FR-007 | T002, T006, T008, T010 (T005 mounts) |
| FR-008 | T003, T007 |
| FR-009 to FR-012 | T011, T012, T013, T015, T016, T018, T019, T020, T021 |
| FR-013, FR-014 | T013, T015, T022, T025 |
| FR-015 | T015, T028 (write guard), T023, T037 |
| FR-016 to FR-018 | T025, T028, T032 |
| FR-019 | T028, T035, T037, T055 |
| FR-020, FR-021, FR-023 | T026, T027, T033, T034 |
| FR-022 | T027, T030, T034, T037 |
| FR-024 | T039, T046 |
| FR-025 | T039, T047, T054 |
| FR-026 | T039, T048, T053 |
| FR-027 | T039 to T041, T043 to T045, T049 to T052 |
| FR-028 | red-confirm tasks T004, T017, T031, T042 |
| SC-001, SC-002, SC-003 | T001, T008, T009, T010 |
| SC-004, SC-005 | T012, T016, T023 |
| SC-006 | T013, T015, T025 |
| SC-007, SC-008 | T025, T029, T030, T037 |
| SC-009 | T049 to T052 (see H2) |
| SC-010 | T039, T047, T054 |
| SC-011 | T028 (see H3), T037, T055 |

Tasks that trace to research rather than an FR: T001 (baseline, SC-002), T024 (R3), T038 (R5, R7), T045 (R12).

## Review points

- **Gate decisions:** FR-013 Option A is consistent in `spec.md:114`, `:137-138`, `plan.md:117-118`, data-model E1, T013, T015, T022 and T025. "Reuse the drill faults, windows and columns" is consistent in `tasks.md:137`, T041, T044 and T049, apart from H1, H2 and M4. "No CODEOWNERS entry for `.github/workflows/`" is consistent in `plan.md:198` and `:300-301`, `research.md` Gate decisions item 2, and the checks in T037 and T055 (M6 asks for the same check in T009 and T023).
- **Safety:**
  - Drill: T041 requires `COMPOSE_PROJECT_NAME=pulsoflota-drill`, every `docker compose` call under it, a port/stack guard, outputs only under `drill-out/`, and no secret literal. The exception is the manual verification steps (M2).
  - Secrets: none anywhere in the plan. `.env` is made from `.env.example` (T006, T044); T012, T026 and T033 forbid DSN, host, user, password and exception text in logs and health output; `.drill-input/` is never staged (T043, T055(5)). T012's secret-looking values are fake test inputs.
  - CI: needs no repository secrets (T002 asserts no `secrets.` reference; `permissions: contents: read`).
- **No forbidden edits:** no task edits `contracts/`, `bronze.py`, `validate.py`, the event contract, or an ADR line other than the T035 addendum. See M6 for the missing `002_bronze.sql` check.
- **CI test job:** T002 asserts the Andon command is unchanged and that no `--cov-fail-under` or other coverage flag is in the workflow (FR-002).
- **Test-first order:** each phase lists tests, a red-confirm task, implementation and a verification task (T001 to T009, T011 to T023, T025 to T037, T039 to T055). Each verification task runs the host suite and the Andon command (T009, T023, T037, T055). T008 runs local checks after the implementation tasks, and T001 is a baseline, not a test.
- **Constitution v1.1.0, turn 1:** no violation. Principle III is strengthened (ingestion depends only on `db`, asserted by T027). Principle V is automated by US1. Principles I, II and IV are untouched. Deferred items (SAST/SCA, Redis, OpenTelemetry, PostGIS, simulator resume, `arrival_ts` index, RBAC on `ops`) are named as evolution and not built.

## Next actions

1. Apply H1 (header) and H2 (lag rule) to the tasks, and add the decision to research "Gate decisions", before T040 starts. Apply H3 before T028 starts.
2. Decide M1, M2, M5 and M6 in the same edit.
3. Fix M3 and M4 in the plan and research when convenient; they do not change the tasks.
4. Start Phase 1 (T001 to T009) now; nothing above blocks it.

Would you like me to suggest the exact replacement text for H1 to H3 and M1 to M6? I will not edit the spec, plan or tasks without your approval.

---

## Fixes applied (2026-11-20)

Applied on the data owner's approval of 2026-11-20. Only files under `specs/003-ops-ci-reliability/` changed; `spec.md` changed only in the baseline numbers (H2). No code was written, nothing was committed or pushed. Line numbers are those of the edited files now. The findings above keep their original line numbers (they describe the files before this edit).

The repo copies of the baseline (`docs/ops/drill-baseline/`) do not exist yet; they are created by T043, which now carries the translation rules. I did not create them because they are outside `specs/`.

| Finding | Fix | Changed lines |
|---|---|---|
| **H1** header and labels | Header is now `t_s,events,max_event_ts,ingestion_lag_s,duplicates,other_rejections,ingestion,api,db` everywhere. Only the header line of the baseline CSV changes, data rows stay byte for byte (diff command in T043; row-equality test in T040). Spanish labels of `events.log` and `restarts.txt` are translated in the repo copies, with an explicit mapping; file names are English; `docs/ops/drill-baseline/README.md` says so. | `tasks.md`: comparability rules 139, T040 150, T041 151, T043 156, T044 157, T049 162, T051 167, T052 168. `research.md`: Gate decisions 509-523 (header, translated evidence). `plan.md`: key-decision row 80 and open question 1. `quickstart.md` 189-194. The old names remain only in the mapping text (`tasks.md` 139 and 156, `research.md` 511). |
| **H2** lag rule | One fixed rule for both columns: *lag after F2* = last sample strictly before the F3 mark, *F3 lag* = last sample of the window. Baseline: **120 s** (t=227, mark at 228 s) and **209 s** (t=316). Verified against `.drill-input/metricas.csv`. The note about the 125 s and 204 s reading is in each place. T039 now recomputes 120 and 209 from the baseline CSV and the `events.log` mark and checks the "before" cells. | `spec.md` 22, 23, 26 (note), SC-009 (192). `tasks.md` 141 (note), T039 149, T046 159, T049 162, T051 167, T052 168. `research.md` R12 (438-441) and Gate decisions 524-529. `quickstart.md` 189-196. `plan.md` row 80. `checklists/requirements.md` 35. |
| **H3** ADR check | The container test (T028) checks only the addendum sentence and its position after the `config` addendum; no git. The "one content line, at most the blank separator, nothing removed" check is a host check in T037(2) and T055(4). | `tasks.md` T028 113, T035 123, T037 128, T055 174. `quickstart.md` Phase 3 (green block and `git diff` comment). `plan.md` constitution re-check item 5 (125-128). |
| **M1** live tests | T016 and T030 skip unless `-m live` is passed (same fixture as `test_refresh_live.py:20`), and unless the dedicated project is set. The host-suite line in the conventions says the plain command never stops `db`. | `tasks.md` conventions 18, T016 80, T030 115. `quickstart.md` 15-25. |
| **M2** `down -v` | New "Verify project" convention (`COMPOSE_PROJECT_NAME=pulsoflota-verify`); T023, T037 and the quickstart live blocks export it. Cleanup is `down -v` under that project only. The drill keeps `pulsoflota-drill`. | `tasks.md` 19, T023 93, T037 128. `quickstart.md` 15-25 and both live blocks. `plan.md` risk 12 (294). `research.md` R12 and R14. |
| **M3** getters and variables | Plan now says three getters and three variables in Phase 2, the fourth variable (`INGESTION_HEALTH_MAX_AGE_S`, read in `health.py`) in Phase 3. | `plan.md` 187-188 (file lists), Phase 2 step 3, Phase 3 step 2. `contracts/README.md` env-variable text. |
| **M4** stale R12 and risk 7 | Plan risk 7 now says `SIM_DURATION_S` is not overridden. R12 has a "superseded in part" banner and its stale statements (long `SIM_DURATION_S`, 5 s sampling, `docker compose kill ingestion`, comparability caveat) are marked superseded. | `plan.md` 289. `research.md` 419-424, 431-441, 450-451. |
| **M5** F3 kill target | T044 and T041 require the exact-argv rule (argv after the interpreter is exactly `-m src.data.ingestion.run`, never PID 1, never the helper, never a substring match). T029 cross-references it. Research Gate decisions has an "F3 target" line. | `tasks.md` T029 114, T041 151, T044 157. `research.md` 530. `plan.md` row 80. |
| **M6** untouched check | One "Untouched check" definition in the conventions, referenced by T009, T023, T037 and T055. It lists `contracts/`, `bronze.py`, `validate.py`, `src/data/db/init/002_bronze.sql` (and `001`, `003`, `004`, `005`), `.github/CODEOWNERS`, `.drill-input/`, `drill-out/`, and the only allowed ADR change. | `tasks.md` 20, T009 49, T023 93, T037 128, T055 174. |
| **L1** SC-008 wording | One bound everywhere: 15 s + one 5 s interval + the probe duration, stated as the measured reading of the spec's "15 s plus one healthcheck interval". `spec.md` SC-008 is not edited. | `plan.md` 74. `contracts/ops-ingestion-health.md` bound paragraph. `tasks.md` T037 128. `quickstart.md` Phase 3 live text. |
| **L2** blank separator | T035, T037 and T055 say the addendum may include one blank separator line (002 precedent) and the check accepts it. | `tasks.md` T035 123, T037 128, T055 174. `plan.md` 125-128. |
| **L3** `db_recovered` | Listed as an extra informational log line in the contracts note; plan item 3 points to it. | `contracts/README.md` "Log lines" section. `plan.md` 119-122. |
| **L4** `scripts` mount | Moved to Phase 3 in plan and quickstart; `feed_control` test attributed to `tests/unit/test_drill_feed_control.py` (T029), not `test_ops_docs.py`. | `plan.md` Phase 3 step 2, Phase 4 step 1, file list 188. `quickstart.md` Phase 3 and Phase 4 red/green blocks. |
| **L5** Spanish text in evidence | Decided and written: translated in the repo copies, values and timestamps unchanged, README says so (see H1). | `tasks.md` T043 156, T040 150. |
| **L6**, **L7** | No change. L6 is evolution (A03, turn 2) and L7 is a note for readers of T010. | none |

### Coverage re-check

Re-run after the edits: all 28 FRs (FR-001 to FR-028) and all 11 SCs (SC-001 to SC-011) appear in at least one task; there are 55 tasks, T001 to T055 in order, and every task line matches `- [ ] T### [P] [US#] description with path`. The table in "Coverage" above still holds, with these changes: SC-009 is now proved by T039 (recomputation of 120 s and 209 s), T049 to T052; SC-011 by T028 (sentence), T037 and T055 (host diff); SC-004, SC-005 and SC-007/SC-008 by T016/T030, which now skip unless `-m live` is passed.

### Left as is

- `checklists/pre-implementation.md` still quotes 125 s and 204 s and the old line numbers in CHK007 and others; it is a review artifact of the analysis, not a plan document. Re-tick its items after the next review.
- The findings text in this file keeps the old figures and line numbers on purpose.
