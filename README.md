# grc-lite

A small compliance-as-code tool for gap assessments. Criteria, evidence and findings live as YAML files in Git, a CLI validates them, and a report is generated from them.

**Fictional data only.** Nothing in this repo is real client data, and it never should be.

## Status
Phase 1 in progress: data model and validation.

## Layout
- `src/grc_lite/`: the Python package
- `tests/`: pytest tests
- `data/example/`: fictional example assessment data

## Planned phases
1. Data model, schema validation, `grc validate`
2. `grc report` (Markdown report) and tests
3. CI: tests, lint, dependency and secret scanning
4. Import from the notes tool, request log, risk register
5. Evidence collectors for Entra and Azure
