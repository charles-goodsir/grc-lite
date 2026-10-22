# grc-lite

A small compliance-as-code tool for gap assessments. Criteria, evidence and findings live as YAML files in Git, a CLI validates them, and (next) a report is generated from them. It is framework-agnostic: a criterion's `source` can be any standard, policy or contract clause.

**Fictional data only.** Nothing in this repo is real client data, and it never should be.

## Quick start
Needs Python 3.10+.

```bash
uv venv --python 3.14 && uv pip install -e '.[dev]'
.venv/bin/grc init my-assessment      # blank folder with commented templates
.venv/bin/grc validate my-assessment  # exit 1 and every problem listed if invalid
.venv/bin/grc validate data/example   # a fictional worked example
```

## An assessment folder
- `assessment.yaml`: name and risk `scale` (3 or 5), optional
- `criteria.yaml`: what you test against, with `result` (`not tested`, `meets`, `gap`, `can't test`)
- `evidence.yaml`: what you looked at (`system`, `document`, `observation`, `interview`)
- `findings.yaml`: `candidate`, `selected` or `dropped`; selected ones need the full write-up and a likelihood and impact score

Rating = likelihood x impact. Scale 3: 7-9 High, 4-6 Medium, 1-3 Low. Scale 5: 20-25 Critical, 13-19 High, 6-12 Medium, 1-5 Low.

`grc validate` checks field names and values, ID formats and uniqueness, that every evidence and criterion reference exists, that selected findings are complete, and that scores fit the scale. IDs should never be reused after deletion; that is not machine-checked yet.

## Status
Phase 1 done: data model, validation, `grc init`, `grc validate`.

## Planned phases
2. `grc report` (Markdown report)
3. CI: tests, lint, dependency and secret scanning
4. Import from the notes tool, request log, risk register
5. Evidence collectors for Entra and Azure

## Development
```bash
.venv/bin/pytest
.venv/bin/ruff check .
```
