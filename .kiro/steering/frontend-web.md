---
inclusion: auto
name: frontend-web
description: When working on the dispatcher web console (Streamlit/Dash/HTML5+WebSockets) - interactive map, headway and congestion visualization, Human-in-the-Loop UI and contingency mode.
---

# Dispatcher Web Console — PulsoFlota

## Stack

- Streamlit / Dash or HTML5/Jinja2 with WebSockets.
- `pulsoflota-web` modular monolith: supervisory console, metric calculation and
  interactive map. It belongs to the **Adaptive Lane** (see `ritmo-workflow.md`).

## Real-time interactive map

- Up-to-date geospatial position of every active bus in the corridor.
- Position refresh latency ≤ 2 s (validate with 100 simulated buses).

## Headway and regularity

- Compute and show the headway between consecutive vehicles on each standard
  route.
- Highlight deviations > ±15 % from the schedule.

## Road congestion

- Ingest traffic flow speed per segment and classify congestion with a color
  code:
  - **Green:** free flow.
  - **Yellow:** moderate.
  - **Red:** congested.

## Human-in-the-Loop (Principle IV, NON-NEGOTIABLE)

- Early fleet desynchronization alerts at least 3 min before *bunching* or a
  *gap* consolidates.
- Regulation recommendations (holding, early departure, reserve injection,
  diversion) are shown as **non-binding suggestions**.
- No command is sent to the fleet without an explicit **human confirmation
  click** from the dispatcher.
- Keep an audit log of authorized diversions (for compensation and contract
  compliance with operators).

## Contingency diversions

- Show the diversion recommendation on the map with the suggested route, the
  extra distance and the projected change in the service indicator.

## Contingency

- If the control center or the web app fails, the console switches to a local
  contingency mode based on predefined static dispatch plans.

## Access control

- The frontend must **not** be the only access-control mechanism; authorization
  is evaluated in the backend. See `security.md` (A01) and `backend-api.md`.
