---
inclusion: auto
name: ritmo-workflow
description: When planning or running a RITMO spiral turn, a user story (US-XX), feature branches, or choosing the lane (Disciplined/Adaptive).
---

# RITMO Workflow, Lanes and Branches — PulsoFlota

## Risk-first order (Principle I)

- The backlog and the sequence of turns are ordered by technical and
  architectural risk (ASRs), not by static business priority.
- No adaptive-lane feature starts while a Level 1 risk (security or data
  integrity) remains unmitigated in the active turn.
- The order of turns and what each one adopts live in `docs/turns-ritmo.md`.

## 5 stages per spiral turn

1. **Plan** — Turn Owner: priority risk, the turn's closing date and operational
   hypotheses. Update `docs/turns-ritmo.md` for the next turn.
2. **Specify** — user story as a measurable SDD specification + contract gate if
   the schema changes.
3. **Build** — one story at a time on an isolated `feature/US-XX` branch
   (production code + tests + data rules).
4. **Verify** — CI (linting, unit tests, coverage > 80 %), DataOps contract tests
   and human reviewer inspection.
5. **Review (Value Gate)** — measure the impact on P(board ≤ t) with the
   dispatcher in the test/simulation environment.

## Branches

- One story at a time on an isolated `feature/US-XX` branch.
- Commit message convention: see `AGENTS.md` (Conventional Commits, inferred).

## Two development lanes

- **Disciplined Lane** (Ingestion, Message Contracts, Quality-Based Payment):
  strict Contract-First / SDD; low agent autonomy (only proposals validated in
  code and gates); maximum criticality; strict CI and DataOps contract tests.
- **Adaptive Lane** (Web Console, Visualization, Alert and Diversion Rules):
  iterations driven by value hypotheses with the dispatcher; medium autonomy;
  mandatory review by the module owner.

## Compliance

- At the close of each turn, review compliance with the 5 core principles and
  the norms adopted up to that turn.
- A detected violation immediately marks the CI build as failed.

## Constitutional amendments

- PR labeled `constitutional-amendment` + ADR + unanimous sign-off of the Turn
  Owner, the Architect (Software / Security) and the Dispatcher Representative.
  See constitution § Governance.
