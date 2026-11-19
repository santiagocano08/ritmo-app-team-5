"""Quality and derivation rules (deterministic code, no I/O in the Python modules).

`RULES_VERSION` is stamped on every gold row (FR-017). Any change to a rule in this
package bumps it (research R1).
"""

RULES_VERSION = "1.0.0"

# A bus whose newest report is strictly older than this many seconds, relative to the cycle
# reference time, is Estimated (FR-010, ADR-0001). The only definition of the threshold: SQL
# receives it as the `estimated_after_s` parameter, never as a literal.
ESTIMATED_AFTER_S = 120
