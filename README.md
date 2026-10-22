# grc-lite

A small compliance-as-code tool for gap assessments. Criteria, evidence and findings live as YAML files in Git, a CLI validates them, and `grc report` generates a Markdown report from them. It is framework-agnostic: a criterion's `source` can be any standard, policy or contract clause.

**Fictional data only.** Nothing in this repo is real client data, and it never should be.

## Quick start
Needs Python 3.10+.

```bash
uv venv --python 3.14 && uv pip install -e '.[dev]'
.venv/bin/grc init my-assessment      # blank folder with commented templates
.venv/bin/grc validate my-assessment  # exit 1 and every problem listed if invalid
.venv/bin/grc validate data/example   # a fictional worked example
.venv/bin/grc report data/example -o report.md  # Markdown report (omit -o to print)
```

## An assessment folder
- `assessment.yaml`: name and risk `scale` (3 or 5), optional
- `criteria.yaml`: what you test against, with `result` (`not tested`, `meets`, `gap`, `can't test`)
- `evidence.yaml`: what you looked at (`system`, `document`, `observation`, `interview`)
- `findings.yaml`: `candidate`, `selected` or `dropped`; selected ones need the full write-up and a likelihood and impact score

Rating = likelihood x impact. Scale 3: 7-9 High, 4-6 Medium, 1-3 Low. Scale 5: 20-25 Critical, 13-19 High, 6-12 Medium, 1-5 Low.

`grc validate` checks field names and values, ID formats and uniqueness, that every evidence and criterion reference exists, that selected findings are complete, and that scores fit the scale. IDs should never be reused after deletion; that is not machine-checked yet.

## CI
Every PR and every push to `main` runs six checks, and all six are required before merge (admins included):

- `test` on Python 3.10, 3.12 and 3.14, plus `grc validate` and `grc report` on the example
- `lint`: `ruff check` and `ruff format --check`
- `audit`: `pip-audit` on the installed dependencies
- `secrets`: gitleaks over the history that would merge

Actions are pinned to commit SHAs, the gitleaks binary is checksum-verified, and Dependabot proposes updates weekly.

Each control was proved by a throwaway PR that should fail only its own check, then closed unmerged: a broken golden test failed `test`, an unused import failed `lint`, a pinned `jinja2==3.1.2` failed `audit`, and a fake AWS key failed `secrets`. The first secret proof exposed a bug: the scan covered every branch, so one leak failed unrelated PRs. It is now limited to the checked-out history, and a second pair of PRs (one with a fake key, one harmless) showed only the key PR going red.

## Status
Phases 1-3 done: data model, validation, `grc init`, `grc validate`, `grc report`, CI.

The report has a summary (criteria by result, findings by status and rating), a candidate-versus-selected table, selected findings sorted by rating, criteria, evidence, and open items. It refuses to run on invalid data. Convert to HTML or PDF with a tool like pandoc.

## Planned phases
2. ~~`grc report`~~ done
3. ~~CI: tests, lint, dependency and secret scanning~~ done
4. Import from the notes tool, request log, risk register
5. Evidence collectors for Entra and Azure

## Development
```bash
.venv/bin/pytest
.venv/bin/ruff check .
```
