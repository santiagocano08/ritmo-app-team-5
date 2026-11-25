# Research: Status Badge Readable Time

No open clarifications. Decisions:

## D1. Local-time formatting
- **Decision**: Use `Date` getters (`getHours`, `getMinutes`, `getSeconds`) with manual zero-padding, producing `HH:MM:SS` / `HH:MM`.
- **Rationale**: Guarantees 24 h, zero-padded output regardless of locale. `toLocaleTimeString` output varies by locale/ICU (SC-002).
- **Alternatives**: `Intl.DateTimeFormat` with fixed `en-GB` and `hour12:false` (midnight can render `24:00` in some engines); a date library (new dependency, rejected).

## D2. Test time-zone independence
- **Decision**: Set `test.env.TZ = "America/Bogota"` in `vite.config.ts`, so tests assert `22:42:08Z` → `17:42:08` on any host. Run the tests without `-e TZ`.
- **Rationale**: Matches the spec's UTC-5 scenario; pinned in config as required. Risk: Vitest sets `process.env` after Node starts, so TZ is only reliable if applied before the first `Date` use. The task must verify it by running in UTC and a non-UTC container default. If `test.env` is too late, fall back to `process.env.TZ` assignment in `tests/setup.ts` (or a `globalSetup` that sets it), which is also in-repo config.
- **Alternatives**: `docker -e TZ` (forbidden, not reproducible by reviewers); mocking `Date` (does not cover the zone).

## D3. Earliest "since" and invalid values
- **Decision**: Take the minimum parsed `since` among `sources_down`, ignoring unparsable values. If none is usable, detail is generic: `Una fuente no responde`. An unparsable `as_of_ts` for `live` yields `Último evento` without time.
- **Rationale**: Spec edge cases require no failure; generic fallback is the stated assumption.
- **Alternatives**: Throwing or showing the raw string (violates SC-001).

## D4. Placement
- **Decision**: `statusDetail.ts` in `components/shell/`, exporting `formatStatusDetail(status, asOfTs, sourcesDown)`; `App.tsx` calls it instead of the inline template string.
- **Rationale**: FR-006 (separate, unit-testable); smallest footprint.
- **Alternatives**: New `lib/` folder (unrequested structure).
