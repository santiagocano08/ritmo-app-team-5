## What changes and why

<!-- One or two sentences. Link the spec (specs/NNN-*) or the issue. -->

## Data contract (required when the change touches data)

- [ ] I reviewed `docs/data-contract.md`, the schemas in `contracts/` and the related ADRs.
- [ ] **No contract impact**, because: <!-- reason -->
- [ ] **Contract impact**: the contract is updated in this PR, or in PR #<!-- number -->, and the version is bumped if a field changed meaning.

A data change is any change to silver/gold tables or views, metrics (EWT, P(board ≤ t), M1, M2), rules, the decision model, command events, reference data, or the simulator when it changes what gets published. See `.kiro/steering/data-contracts.md`.

## Tests

- [ ] The CI-ready command is green (`docker compose --profile tools run --rm tests`, coverage ≥ 80 %).
