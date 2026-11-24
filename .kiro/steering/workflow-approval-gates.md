---
inclusion: auto
name: workflow-approval-gates
description: When orchestrating or running any workflow (especially the develop-feature / Spec Kit pipeline) and a step pauses asking for approval. Governs how approval gates are handled.
---
# Workflow Approval Gates — Human-in-the-Loop

Every workflow gate requires **explicit human approval**. The orchestrating
agent must never approve a step on the user's behalf. This mirrors the
constitution's Human-in-the-Loop principle: automation proposes, the human
decides.

## Rule

When a workflow step pauses with a `warning` asking for approval — including the
`develop-feature` pipeline gates (`create-spec`, `create-plan`, `create-tasks`,
`validate-plan`, `implement-code`, `review-code`) — the agent MUST:

1. **Summarize** the step's output and what the agent found when reviewing it.
2. **Ask the user explicitly for `APPROVE` or `REJECT`.**
   - **APPROVE** → only then send `success` to the step's session so the
     workflow advances.
   - **REJECT** → ask the user what to change, relay it to the step agent to
     refine, and do **not** advance.
3. **Never** send `success` (never mark a gate approved) without the user's
   explicit word.

## What this forbids

- Judging an artifact correct and advancing the workflow on the agent's own
  initiative.
- Treating a fast review as a substitute for the user's decision.

The pipeline pausing and asking is correct behavior. The agent reviews and
advises; it does not take the user's place at the gate.
