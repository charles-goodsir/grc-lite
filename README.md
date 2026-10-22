# grc-lite

A small compliance-as-code tool for gap assessments. Criteria, evidence, findings, evidence requests and risks live as YAML files in Git. A CLI validates them, generates a Markdown report, imports from the assessor notes tool, and collects evidence from Entra ID. It is framework-agnostic: a criterion's `source` can be any standard, policy or contract clause, so it works for any gap assessment.

**Fictional data only.** Nothing in this repo is real client data, and it never should be.

## Quick start
Needs Python 3.10+.

```bash
uv venv --python 3.14 && uv pip install -e '.[dev]'
.venv/bin/grc init my-assessment      # blank folder with commented templates
.venv/bin/grc validate my-assessment  # exit 1 and every problem listed if invalid
.venv/bin/grc validate data/example   # a fictional worked example
.venv/bin/grc report data/example -o report.md  # Markdown report (omit -o to print)
.venv/bin/grc import-notes notes.md my-assessment  # convert a notes-tool export, then validate
.venv/bin/grc collect leavers my-assessment --hr leavers.csv --users entra-users.json
```

## An assessment folder
- `assessment.yaml`: name and risk `scale` (3 or 5), optional
- `criteria.yaml`: what you test against, with `result` (`not tested`, `meets`, `gap`, `can't test`)
- `evidence.yaml`: what you looked at (`system`, `document`, `observation`, `interview`)
- `findings.yaml`: `candidate`, `selected` or `dropped`; selected ones need the full write-up and a likelihood and impact score
- `requests.yaml`: the evidence request log; no `received` date means outstanding, and the report lists those
- `risks.yaml`: a risk register (`K-01`) with likelihood x impact, treatment and links to findings and criteria

Rating = likelihood x impact. Scale 3: 7-9 High, 4-6 Medium, 1-3 Low. Scale 5: 20-25 Critical, 13-19 High, 6-12 Medium, 1-5 Low.

## What each command does
- **`grc validate`** checks field names and values (unknown keys are errors, so a typo is caught), ID formats and uniqueness, that every evidence, criterion and finding reference exists, that selected findings are complete, and that scores fit the scale. It lists every problem with the file and ID.
- **`grc report`** refuses to run on invalid data. The report has a summary (criteria by result, findings by status and rating), a candidate-versus-selected table, selected findings sorted by rating, criteria, evidence, a risk register, outstanding requests, and open items. Convert to HTML or PDF with a tool like pandoc.
- **`grc import-notes`** only translates a notes-tool `notes.md`. Anything it cannot map (a finding whose criteria it cannot match to an ID, a missing section) is left empty and reported as a warning, then `grc validate` shows what still needs fixing.
- **`grc collect`** reads Entra ID data, compares it to a rule, and adds an evidence entry (see below).

## Evidence collectors
```bash
.venv/bin/grc collect leavers my-assessment --hr leavers.csv --users entra-users.json --criterion C-01
.venv/bin/grc collect mfa my-assessment --registrations mfa.json --users entra-users.json --scope admins
.venv/bin/grc collect leavers my-assessment --hr leavers.csv --live   # read straight from Microsoft Graph
```

- **leavers:** each person in the HR CSV (`upn`, `leave_date`) must have a disabled account within `--max-days` (default 1) of their leave date.
- **mfa:** every enabled account in `--scope` (`admins` or `all`) has MFA registered. Pass `--users` to skip disabled accounts.
- **Inputs:** file mode takes Graph JSON (`{"value": [...]}`) or, for users, a CSV with `userPrincipalName` and `accountEnabled` columns. `--live` takes a token from your signed-in `az` session and needs read access to users (`User.Read.All`) and the MFA registration report (`AuditLog.Read.All`, an Entra reports role).

What it protects:
- The evidence entry holds counts only. Account names go to `collected/<kind>-<date>.json` (mode 600) next to the assessment, in a folder that contains its own `.gitignore` with `*`, so they are not committed by accident.
- Live mode is GET-only, sends the token only to `graph.microsoft.com`, refuses a paging link or redirect that points elsewhere, and keeps the token and request headers out of every error message.
- It never edits `criteria.yaml`. It prints the result it suggests and you decide.

## How it is built
```
src/grc_lite/
  models.py          Pydantic v2 data model: criteria, evidence, findings, requests, risks, rating
  loader.py          reads the YAML files, reports every error, checks cross-references
  report.py          renders a loaded assessment as Markdown
  importer.py        converts a notes-tool export into assessment YAML
  cli.py             Typer commands: init, validate, report, import-notes, collect
  collectors/
    compare.py       pure leavers and MFA comparisons (no I/O)
    sources.py       reads Graph JSON, users CSV and the HR leavers CSV
    graph.py         read-only Microsoft Graph client on the standard library
    record.py        appends the evidence entry and writes the private detail file
tests/               pytest, including a golden-file test of the example report
data/example/        a fictional worked example
```
Dependencies are Pydantic, PyYAML and Typer. Everything else is the standard library.

## CI
Every PR and every push to `main` runs six checks, and all six are required before merge (admins included):

- `test` on Python 3.10, 3.12 and 3.14, plus `grc validate` and `grc report` on the example
- `lint`: `ruff check` and `ruff format --check`
- `audit`: `pip-audit` on the installed dependencies
- `secrets`: gitleaks over the history that would merge

Actions are pinned to commit SHAs, the gitleaks binary is checksum-verified, and Dependabot proposes updates weekly.

Each control was proved by a throwaway PR that should fail only its own check, then closed unmerged: a broken golden test failed `test`, an unused import failed `lint`, a pinned `jinja2==3.1.2` failed `audit`, and a fake AWS key failed `secrets`. The collector controls were proved by breaking each one locally and watching its test fail.

## Problems hit
- **The secret scan scanned every branch.** The first proof showed `secrets` red on three PRs with no secret in them, because `gitleaks git .` scans every ref the checkout fetches. A fake key on one branch failed everything. It is now limited to the checked-out history (`--log-opts="HEAD"`), and a second pair of PRs (one with a fake key, one harmless) showed only the key PR going red.
- **The importer said "Validation passed" on an export with no tables.** It now warns about each missing section.
- **A real export had a typo in a file name** (`suplier-policy`), which the "Rule N, file" matching could not resolve. The importer now also matches a finding's quoted rule text against the criteria.

## Known shortcuts
- IDs should never be reused after deletion. That is not machine-checked, because the tool keeps no history of deleted IDs.
- **Live Graph mode has not been run against a real tenant.** It is tested against fixtures with made-up `acme.example` addresses, so the response shapes follow the documentation and are unproved until someone runs it.
- The leavers check sees only the current state, so it cannot tell whether an account that is disabled now was disabled late.
- The importer drops any free text in the notes tool's "Ev # received" column beyond the evidence number, and only understands that tool's format. The request log and risk register are not in that export, so they are written by hand.
- Azure resource checks, a CSV import and HTML or PDF output were not built.

## Teardown
No cloud resources: nothing is deployed, nothing costs money, and no budget alert is needed. The collectors read an existing tenant using your own `az` session and store no credentials.

## Status
Complete: five phases built and merged through pull requests into a protected `main`.
1. Data model, validation, `grc validate`, `grc init`
2. `grc report`
3. CI on every PR, with each control proved by a failing case
4. Request log, risk register, `grc import-notes`
5. Entra evidence collectors

## Development
```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```
