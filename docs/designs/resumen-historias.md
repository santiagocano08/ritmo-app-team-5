# PulsoFlota · Summary of stories and mock-ups (UXUI-01 to UXUI-12)

PulsoFlota is a web control center for dispatchers and managers of an integrated transport system. The dispatcher watches the corridor live, receives recommendations to avoid bus bunching and gaps, and decides whether to apply them. The manager reviews service quality indicators per operator. The system recommends and the person decides.

Each story has three screens on the canvas: the story card, the desktop version (1280 px) and the mobile version (390 px). The screenshots are in `historias/`, `escritorio/` and `celular/`, named `UXUIxx-historia`, `UXUIxx-escritorio` and `UXUIxx-celular`.

The app's user interface is in Spanish. Screen names, menu items and on-screen copy are kept in Spanish in this document (in *italics* or «quotes»), with the English meaning alongside where it helps.

---

## Index

| Story | Topic | Role | Turn | Lane |
|---|---|---|---|---|
| UXUI-01 | Sign in (*Iniciar sesión*) | Dispatcher / manager | 2 · Value | Adaptive + security review |
| UXUI-02 | Recover password (*Recuperar contraseña*) | Any user | 2 · Value | Depends on UXUI-01 |
| UXUI-03 | Main navigation by role and data state (*Navegación principal por rol y estado del dato*) | Dispatcher / manager | 2 · Value | Adaptive · hypothesis |
| UXUI-04 | View the corridor live (*Ver el corredor en vivo*) | Dispatcher | 2 · Value | Adaptive · consumes the contract |
| UXUI-05 | Handle a regularity recommendation (*Atender una recomendación de regularidad*) | Dispatcher | 2 · Value | Mixed · firm real time |
| UXUI-06 | Service quality indicators (*Indicadores de calidad del servicio*) | Manager | 2 · Value | Disciplined · affects payment |
| UXUI-07 | Alerts inbox (*Bandeja de Alertas*) | Dispatcher | 2 · Value | Adaptive · depends on UXUI-05 |
| UXUI-08 | View the plan of the day (*Consultar el plan del día*) | Dispatcher | 2 · Value | Adaptive · no real time |
| UXUI-09 | Data quality per operator (*Calidad del dato por operador*) | Manager | 1 · Data and factory | Disciplined · DataOps |
| UXUI-10 | Get the instruction to the driver (*Hacer llegar la instrucción al conductor*) | Dispatcher | 2 · Value | Mixed · depends on UXUI-05 |
| UXUI-11 | See whether the recommendation worked (*Ver si la recomendación funcionó*) | Dispatcher | 2 · Value | Adaptive · depends on UXUI-10 |
| UXUI-12 | Report an operational incident (*Reportar una novedad operativa*) | Dispatcher | 2 · Value | Mixed · affects recommendations |

---

## UXUI-01 · Sign in (*Iniciar sesión*)

**Related to:** access to the application.

The user signs in with their institutional username and password and lands on their role's home view.

- **Desktop:** two panels. On the left, a navy panel with the brand and the message «Central del despachador» (dispatcher control center). On the right, the 400 px form with username, password (with a Mostrar/Ocultar — show/hide — button) and the link «¿Olvidaste tu contraseña?» (forgot your password?).
- **Mobile:** one column with fields and a 48 px button, the button full width.
- **States:** normal, error («Usuario o contraseña incorrectos» — wrong username or password — without saying which one failed) and account locked after 5 failed attempts in 15 min, showing the unlock time.
- **To be defined with the client:** whether the manager signs in through institutional single sign-on (SSO).

## UXUI-02 · Recover password (*Recuperar contraseña*)

**Related to:** access, follow-up to UXUI-01.

Reset the password with a link sent by email, without depending on support in the middle of a shift.

- **Three-step flow:** request the link, see the confirmation and set the new password.
- **Visible rules:** the confirmation message is always the same whether or not the account exists; the link is single-use and expires after 30 min; the new password requires 12 or more characters, one letter and one number, with the requirements checked live.
- **On save:** all open sessions are closed and the user returns to *Iniciar sesión* with a success notice.
- **Desktop:** centered card, 440 px max. **Mobile:** full width with 20 px margins.
- **To be defined:** who unlocks a locked account before the 15 min are up.

## UXUI-03 · Main navigation by role and data state (*Navegación principal por rol y estado del dato*)

**Related to:** application structure and trust in the data.

The app's fixed frame: it shows the role's sections, the active corridor, the time and whether the data is up to date.

- **Menu by role:** the dispatcher sees *Central en vivo*, *Alertas* and *Plan del día*; the manager sees *Indicadores de calidad* and *Plan del día*. A URL outside the role returns «Sin permiso» (403).
- **Data indicator:** *En vivo* (live), *Estimado* (estimated: a source dropped) or *Sin datos* (no data), always with text and the time of the last event. The last two show an explanatory banner.
- **Desktop:** 248 px sidebar and top bar. **Mobile:** compact top bar and bottom navigation with at most 4 items; the profile and *Cerrar sesión* (sign out) go under «Más» (more).
- **Session:** signing out invalidates the session, and there is a notice 2 min before it expires.
- **Hypothesis:** «En vivo» if the last event arrived less than 30 s ago; «Sin datos» after 2 min without events.

## UXUI-04 · View the corridor live (*Ver el corredor en vivo*)

**Related to:** real-time monitoring, the dispatcher's main screen.

A corridor diagram with each bus's position and its headway to the bus ahead, to spot bunching and gaps in time.

- **Desktop:** four indicators at the top (buses in service, scheduled headway, bunchings, gaps), a horizontal diagram with stations and buses, and a bus table with status and data type.
- **Mobile:** the corridor reads top to bottom, with the buses between their stops.
- **Rules:** the position updates with a delay of 10 s or less. A bus is «Agrupado» (bunched) if its headway is under 50 % of the scheduled one and «Hueco» (gap) if it is over 150 %. A bus whose source does not respond is drawn with a dotted border and the label «Estimado».
- **Hypothesis:** the 50 % and 150 % thresholds. The mock-up data are examples.
- **Prototype control:** a dotted «Simular recomendación» (simulate recommendation) button leads to UXUI-05.

## UXUI-05 · Handle a regularity recommendation (*Atender una recomendación de regularidad*)

**Related to:** system recommendations and the dispatcher's decision.

When bunching or a gap forms, the system proposes a concrete action with its expected effect, and the dispatcher applies or dismisses it, leaving a record.

- **Content of each recommendation:** action, bus, stop, duration, reason, expected effect on excess wait time (EWT) and data confidence.
- **Rules:** it appears in 10 s or less; with no answer in 2 min it expires; there are never more than 3 active; holding never exceeds 90 s; dismissing requires a reason; two recommendations on the same segment are marked «en conflicto» (in conflict).
- **Desktop:** 400 px side panel next to the corridor, with the affected area highlighted and a history of the shift's decisions. **Mobile:** a notice at the top and a bottom sheet with the list and the buttons within thumb reach.
- **Risk it addresses:** alert fatigue. **To be defined:** the channel the dispatcher uses to tell the driver.

## UXUI-06 · Service quality indicators (*Indicadores de calidad del servicio*)

**Related to:** pay-for-quality to operators (manager role).

The manager reviews P(abordar ≤ t) and excess wait time (EWT) per operator and time band, together with how much reliable data backs them.

- **Desktop:** filters (date, corridor, time band and t of 5, 10 or 15 min), three indicators and a table per operator. **Mobile:** a one-line filter summary and one card per operator.
- **Rules:** each value shows its coverage (% of valid events and % estimated); below 90 % the operator is marked «No apto para pago» (not eligible for payment). Only events that passed the data gate are used. The table exports to CSV.
- **To be defined with the client:** the 90 % threshold and the payment formula.

## UXUI-07 · Alerts inbox (*Bandeja de Alertas*)

**Related to:** follow-up of the shift's notices and recommendations.

An inbox with everything the system flagged during the shift, to pick up what was closed without a decision.

- **Three tabs with counters:** *Activas* (the same recommendations as UXUI-05), *Avisos del dato* (data notices) and *Historial* (history).
- **Data notices:** source down, bus without signal for more than 2 min or rejected events. They say what is affected and since when, and are marked resolved when the data returns. They make no sound.
- **History:** filters by outcome (applied, dismissed, expired) and shows time, action, reason and who decided.
- **Desktop:** tabs and tables. **Mobile:** segmented tabs and cards.
- **Opening an active one** takes the user to the control center with that recommendation open.

## UXUI-08 · View the plan of the day (*Consultar el plan del día*)

**Related to:** scheduling, demand and operating without live data.

It shows the scheduled departures from the transfer point next to the actual ones, and the expected Metro demand, as a guide when there is no live data.

- **Departures:** scheduled time, bus, actual time and deviation; more than 2 min is marked «Atrasada» (late) or «Adelantada» (early).
- **Expected demand:** in 30-min bands, computed from historical Metro ridership, next to the planned headway.
- **On open:** it scrolls to the current time with an «Ahora» (now) line and the next departure highlighted. Without live data, actual departures show as «Sin dato» (no data).
- **Desktop:** demand bars and a table. **Mobile:** compact bars and a departures list.
- **Read only:** it shows who loaded the plan and when. **To be defined:** who loads it and how often.

## UXUI-09 · Data quality per operator (*Calidad del dato por operador*)

**Related to:** trust in the payment indicators (manager role, turn 1 · Data and factory).

The manager sees how many events each operator sends, how many are rejected and why, the latency and the gaps per bus.

- **Per operator and day:** events received, % rejected, p95 latency and gaps.
- **Operator detail:** rejection causes (duplicate, outside the contract, impossible position, time out of range) and the buses with the most gaps.
- **Flags:** «Revisar» (review) if rejection exceeds 5 % or p95 latency exceeds 10 s; «Posible manipulación» (possible tampering) for suspicious patterns, always for human review, never an automatic sanction.
- **Desktop:** table and detail of the selected operator. **Mobile:** cards that expand to show the detail.
- **Impact on UXUI-03:** the manager's menu adds «Calidad del dato».

## UXUI-10 · Get the instruction to the driver (*Hacer llegar la instrucción al conductor*)

**Related to:** carrying out the applied recommendations.

After applying a recommendation, the dispatcher sends the instruction to the driver and follows its status.

- **States:** *Enviada* (sent), *Recibida* (received: the driver confirms) and *Ejecutada* (executed: the data show it was carried out). With no confirmation in 30 s it is marked «Sin confirmación» (unconfirmed) and can be resent or communicated by radio.
- **Rules:** the instruction reaches the bus console in 5 s or less; with no console or with the source down, only radio is offered; a hold counts as executed if the bus stays for the stated duration plus or minus 15 s.
- **Desktop:** tracking in the side panel, including what the driver sees. **Mobile:** a full-screen tracking card.
- **Strong assumption:** buses have a console to receive messages; this must be validated with the operators. The driver app is out of scope.

## UXUI-11 · See whether the recommendation worked (*Ver si la recomendación funcionó*)

**Related to:** learning from and evaluating the recommendations.

Minutes after a recommendation is executed, it shows how the headway and excess wait time changed.

- **Chart:** headway between the buses involved from 6 min before to 10 min after, next to the scheduled headway.
- **Outcome:** «Funcionó» (worked: achieved at least 50 % of the expected effect), «Efecto parcial» (partial effect), «No funcionó» (did not work) or «Sin dato suficiente» (not enough data: coverage below 90 %). There is a shift summary.
- **Accessed** from the Alerts history (UXUI-07).
- **On-screen note:** the outcomes evaluate the recommendations, not the dispatcher, and the outcome is a signal, not proof.
- **Desktop:** the shift's list and a detail view with the chart. **Mobile:** cards with a small chart.

## UXUI-12 · Report an operational incident (*Reportar una novedad operativa*)

**Related to:** context the data cannot see, and its effect on the recommendations.

The dispatcher reports an incident in seconds (broken-down bus, closed stop, detour, absent driver) so the system takes it into account.

- **Form:** type, affected bus or stop and estimated duration (or «hasta nuevo aviso» — until further notice); the note is optional. It is completed in under 15 s.
- **Effect:** a broken-down bus leaves the headway computation; a closed stop is not used for holds. The affected recommendations are recomputed and marked «Recalculada por novedad» (recomputed due to incident).
- **Visibility:** the incident shows on the diagram and in *Alertas* until it is closed; who reported it and when is recorded. The manager sees it as context in their indicators.
- **Desktop:** form in the side panel without losing sight of the corridor. **Mobile:** full-screen form with the button at the bottom.
- **To be defined with the client:** whether an incident outside the operator's control, such as a road closure, excludes those hours from the payment computation (UXUI-06).

---

## How the stories relate

- **Access:** UXUI-01 → UXUI-02 → UXUI-03.
- **Dispatcher, real time:** UXUI-04 → UXUI-05 → UXUI-10 → UXUI-11, with UXUI-07 (inbox) and UXUI-12 (incidents) around them.
- **Dispatcher, no real time:** UXUI-08.
- **Manager:** UXUI-06 (indicators) and UXUI-09 (data quality). UXUI-06 depends on the coverage measured by UXUI-09.
- **Shared screen:** UXUI-03 frames all of them; the menu changes by role.
