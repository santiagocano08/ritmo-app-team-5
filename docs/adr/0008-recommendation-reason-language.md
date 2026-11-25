# ADR-0008: Recommendation `reason` is written in Spanish at the source

- Status: Proposed
- Date: 2026-11-25
- Turn: 1 — Data and Minimal Loop (active)
- Addresses: Principle II (the contract must say what a published field contains); turn-1 risk
  (the dispatcher reads the reason to decide, RF-2.3); story `.factory/story.md` (follow-up of #70).

## Context
The decision model (`src/data/rules/mpc.py`, `_reason`) writes `reason` in English. The console is
in Spanish, so the recommendations panel mixes languages. The data lab already translates five
templates in the browser.

## Options considered (max. 3)
1. **Translate in the console.** Pro: no data change. Con: the console would parse text, and the
   wording would be duplicated in a second place.
2. **Add a structured `reason_code` plus parameters.** Pro: language-neutral. Con: new field, schema
   version bump, more than this turn needs.
3. **Write Spanish text at the source, from the same fields.** Pro: smallest change, no schema
   change, the console renders `reason` as it comes. Con: the text is tied to one language.

## Decision
Option 3. `_reason` builds the text from the action's own fields (never parsed back), with these
templates (numbers formatted as today):

- `hold`: `retener {bus} {s} s en {stop} ahorra {saving} s por pasajero`
- `slow_down`: `reducir la velocidad de {bus} un {pct} % durante {min} min en {stop} ahorra {saving} s por pasajero`
- `reserve_dispatch`: `despachar la reserva {bus} ahorra {saving} s por pasajero`
- `adjust_departure`: `adelantar|retrasar {s} s la próxima salida desde {stop} ({bus}) ahorra {saving} s por pasajero`
- `skip_stop`: `saltar las paradas sin cola para {bus} desde {stop} ahorra {saving} s por pasajero`

Assumption: `reason` stays free text with no format guarantee beyond "plain Spanish, names action,
bus, stop when the action has one, and the saving per rider". Consumers must not parse it.
Reasons already stored in `gold.recommendation` are not translated.

## Consequences
Easier: one language on the console, no translation layer. Harder: a second language would need
option 2. Old English rows remain until they expire.

## Affected contract
`contracts/read/recommendation.schema.json`: **no change, no version bump** (the type is `string`,
`minLength` 1). Fixtures `contracts/read/fixtures/*/recommendation.json` change example text only.
`docs/data-contract.md` §4.5 gains one line on the language. Both are contract files, so the data
owner (CODEOWNERS) must review.

## Evolution
A language-neutral `reason_code` with parameters (option 2) if more than one language is needed.
