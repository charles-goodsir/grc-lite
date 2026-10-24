# grc-lite

A small compliance-as-code tool for gap assessments, with a local study app for working through them. Criteria, evidence, findings, evidence requests and risks live as YAML files in Git. A CLI validates them, generates a Markdown report, imports from the assessor notes tool and collects evidence from Entra ID. A local web app (`grc serve`) lets you read a level's files, take notes, log records, submit for review, import the grading and track progress. It is framework-agnostic: a criterion's `source` can be any standard, policy or contract clause, so it works for any gap assessment.

**Fictional data only.** Nothing in this repo is real client data, and it never should be.

## Quick start
Needs Python 3.10+.

```bash
uv venv --python 3.14 && uv pip install -e '.[dev]'
.venv/bin/grc serve ~/projects/grc/levels/02-ashgrove   # the study app
.venv/bin/grc init my-assessment      # blank folder with commented templates
.venv/bin/grc validate my-assessment  # exit 1 and every problem listed if invalid
.venv/bin/grc validate data/example   # a fictional worked example
.venv/bin/grc validate data/essential-eight   # a fictional Essential Eight assessment
.venv/bin/grc validate data/iso27001-starter   # a fictional ISO 27001 starter assessment
.venv/bin/grc report data/example -o report.md  # Markdown report (omit -o to print)
.venv/bin/grc import-notes notes.md my-assessment  # convert a notes-tool export, then validate
.venv/bin/grc collect leavers my-assessment --hr leavers.csv --users entra-users.json
```

## Study app
`grc serve <level>` opens a local page (`http://127.0.0.1:8765`). Your level's files are on the left (Markdown, CSV as a sortable, filterable table, text), the open file is in the middle, and tabs are on the right. Your work saves as you type, as the same YAML files the CLI reads, in `<level>/my-work/assessment/` (or `--assessment PATH`), so `grc validate`, `grc report` and Git work on what you log.

**Layout**
- A top bar with **Files** (hide the file list), **Reading mode** (hide both side panels, press Esc to leave) and a **Theme** switch (system, light, dark). The two dividers can be dragged, or focused and moved with the left and right arrow keys, and your widths and theme are remembered in the browser.
- The tabs are in four groups, Work, Review, Find and Finish. Pick a group and its tabs appear underneath, and the Review group shows how many things need a look (problems plus pre-submit checks).
- A **level stepper** above the tabs follows the playbook: read the scope, pull out the rules, test them, log what's missing, write findings, submit and review. It shows numbered dots with the current step named, ticks steps from what you have logged, and hovering a step shows what it means. Each step takes you to the right place.

**Working through a level**
- **Notes** for the open file.
- **Criteria, Evidence, Findings, Requests, Risks:** forms with the notes tool's fields. Evidence and criteria are picked from lists, findings show a live rating and what a selected finding still lacks, and the scale (1-3 or 1-5) and slots are set on the Findings tab. A **?** beside the main fields shows a short reminder from the playbook.
- **Problems:** everything `grc validate` would flag, each a link to its record. Drafts are allowed and show up here until complete.
- **Search** across the files you can see, your notes and your records.
- **Coverage:** where the assessment is thin: rules with no evidence or not tested, gaps no live finding covers, selected findings on weaker evidence, undecided candidates, evidence nothing uses, and requests still waiting, with a rules-by-evidence grid.
- **Check:** a pre-submit checklist and a finding coach. It checks that every rule has a result, every candidate is decided, every gap has a finding, selected findings pass the coach, the slots are used, can't-test rules have requests, and evidence has a reliability note. The coach flags a missing Cause line, a condition with no number or no evidence ID, evidence that is not in your log, a likelihood that contradicts its own reason, a finding linked to a rule marked meets, and selected findings on weaker evidence. Reminders from the mistakes you tagged in earlier gradings come first. These catch incomplete or inconsistent work, not wrong conclusions.
- **Cite this view** (on a CSV) records the filter and the row count as an evidence entry, so "5 of 31 rows" comes from a saved count. **Add selected text as evidence** quotes what you highlighted, with its source.
- **Report:** the Markdown report, built live from what you logged.

**Finishing and learning from a level**
- **Export:** the submission, the report (Markdown or a printable HTML page), an Excel workbook (`pip install 'grc-lite[xlsx]'`), a ZIP backup, and one CSV per tab. Spreadsheet cells that start with `=`, `+`, `-` or `@` are saved as text, so a note cannot run as a formula when you open the file.
- **Import:** reads a notes-tool `notes.md` into an empty assessment, including your per-file notes. It lists anything it could not map and refuses to overwrite existing records.
- **Submit and lock:** writes `submission.md` (the notes-tool format, so `grc import-notes` reads it back), records its SHA-256 in `submitted.yaml`, and turns editing off. You then send the file to be reviewed. The Export tab shows whether the file and your records still match what you submitted.
- **Grading:** import the grading file you get back (layout in [docs/grading-format.md](docs/grading-format.md)). It shows a scoreboard of planted gaps, the summary, what went well and what to do next time. The grader's notes appear on your own criteria, evidence and findings. Each miss and each "for next time" point goes in a mistake log with a tag you can change. Only then do the answer key and `graded/` files appear in the file list.
- **Progress:** every level's status (not started, in progress, submitted, graded), planted gaps caught, ratings that were off, a trend of caught percentage per graded level, and your mistakes counted by tag across levels. It looks at the folders next to the one you serve, or at `--levels PATH`. For each it reads one file, `my-work/assessment/grading.yaml`, and only checks that `submitted.yaml` exists.

The lock and the answer-key reveal are commitments to yourself, not security controls: deleting `submitted.yaml` reopens a level, and deleting `grading.yaml` seals the key again.

**Built to be safe to run on a laptop**
- It listens on `127.0.0.1` only and refuses any request whose `Host` header is not localhost, which blocks DNS rebinding.
- Every API call needs a random token created at startup, and writes must be JSON, so another web page cannot send writes to it.
- Paths cannot leave the level folder, including through symlinks. `CLAUDE.md`, dotfiles and `my-work/` are never listed or served. `answer-key*` files and `graded/` are hidden until the level is submitted and graded.
- File and record text is drawn with DOM text nodes only, under a strict Content-Security-Policy, so a hostile line in a data-room file or a note cannot run script.
- Progress reads no other level's data room or answer key, does not follow links, and lists only real folders holding `01-scope.md` or a `data-room`.

## An assessment folder
- `assessment.yaml`: name, risk `scale` (3 or 5), `slots`, and the highest ID number issued per prefix (so a deleted ID is not reused by the app)
- `criteria.yaml`: what you test against, with `result` (`not tested`, `meets`, `gap`, `can't test`)
- `evidence.yaml`: what you looked at (`system`, `document`, `observation`, `interview`)
- `findings.yaml`: `candidate`, `selected` or `dropped`; selected ones need the full write-up and a likelihood and impact score
- `requests.yaml`: the evidence request log; no `received` date means outstanding, and the report lists those
- `risks.yaml`: a risk register (`K-01`) with likelihood x impact, treatment and links to findings and criteria
- Written by the study app: `notes/`, `submission.md`, `submitted.yaml`, `grading.yaml`, `grading.md`

Rating = likelihood x impact. Scale 3: 7-9 High, 4-6 Medium, 1-3 Low. Scale 5: 20-25 Critical, 13-19 High, 6-12 Medium, 1-5 Low.

## What each command does
- **`grc validate`** checks field names and values (unknown keys are errors, so a typo is caught), ID formats and uniqueness, that every evidence, criterion and finding reference exists, that selected findings are complete, and that scores fit the scale. It lists every problem with the file and ID.
- **`grc report`** refuses to run on invalid data. The report has a summary (criteria by result, findings by status and rating), a candidate-versus-selected table, selected findings sorted by rating, criteria, evidence, a risk register, outstanding requests, and open items. Convert to HTML or PDF with a tool like pandoc.
- **`grc import-notes`** only translates a notes-tool `notes.md`. Anything it cannot map (a finding whose criteria it cannot match to an ID, a missing section) is left empty and reported as a warning, then `grc validate` shows what still needs fixing.
- **`grc collect`** reads Entra ID data, compares it to a rule, and adds an evidence entry (see below).
- **`grc serve`** is the study app above.
- **`grc check-ids <assessment>`** reads the Git history of the five records files (and the working tree) and fails if an ID that was deleted has come back. It reports the ID with the commits where it first appeared, vanished and returned. A deliberate revert will also be flagged, so say so in the pull request. It needs real history: a shallow clone is warned about, and CI's default shallow checkout would not be enough.
- **`grc guard-names`** rejects real client names from a deny-list that lives outside the repository (default `~/.config/grc-lite/denylist.txt`, or `GRC_DENYLIST`, one name per line). `grc guard-names PATH...` scans files and folders, `--staged` scans what is about to be committed, and `--install-hook` writes a pre-commit hook. It fails closed: a missing, empty or in-repo list is an error, never a clean result. A hit names the file and line and the list entry number, never the name. Matching is plain, case-insensitive text, so it will not catch misspellings, initials or a name written another way unless you list that too.

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
- Each detail file carries a random salt and a hash of it is recorded in the evidence entry, and a same-day rerun gets its own file instead of overwriting the first. `grc collect verify <assessment>` re-hashes the files and reports any that changed (exit 1) or are not on this machine. The hash shows a file is unchanged since it was collected. It does not show who collected it or when, and it needs the detail file, which is deliberately never committed.
- It never edits `criteria.yaml`. It prints the result it suggests and you decide.

## How it is built
```
src/grc_lite/
  models.py          Pydantic v2 data model: criteria, evidence, findings, requests, risks, rating
  loader.py          reads the YAML files, reports every error, checks cross-references
  report.py          renders a loaded assessment as Markdown
  importer.py        converts a notes-tool export into assessment YAML
  grading.py         reads a grading file and builds the mistake log
  coverage.py        finds the thin spots in an assessment
  coach.py           the finding coach and the pre-submit checks
  cli.py             Typer commands: init, validate, report, import-notes, collect, serve
  web/               the local study app
    app.py           the server and its guards (host, token, JSON-only, lock, security headers)
    files.py         which files may be shown, and safe path handling
    records.py       saving drafts, ID counters, problems
    export.py        submission, CSV, Excel, ZIP, printable report, submit-and-lock
    grades.py        grading storage and the answer-key reveal rule
    search.py        search across files, notes and records
    progress.py      status and scores across levels
    static/          the page: plain JavaScript modules, no build step
  collectors/
    compare.py       pure leavers and MFA comparisons (no I/O)
    sources.py       reads Graph JSON, users CSV and the HR leavers CSV
    graph.py         read-only Microsoft Graph client on the standard library
    record.py        appends the evidence entry and writes the private detail file
tests/               380+ tests, including a golden-file test of the example report and a check that the page code never parses HTML from a string
data/example/        a fictional worked example
data/essential-eight/  a fictional Essential Eight assessment at Maturity Level One (see docs/essential-eight.md)
data/iso27001-starter/  a fictional ISO 27001 starter assessment: ten Annex A controls and two clauses (see docs/iso27001-starter.md)
docs/                the grading file format, the Essential Eight and ISO 27001 notes, the live test runbook
```
Dependencies are Pydantic, PyYAML, Typer, FastAPI and uvicorn. Excel export needs the optional `openpyxl`; the tests also use `httpx`. Everything else is the standard library.

## CI
Every PR and every push to `main` runs six checks, and all six are required before merge (admins included):

- `test` on Python 3.10, 3.12 and 3.14, plus `grc validate` and `grc report` on the example
- `lint`: `ruff check` and `ruff format --check`
- `audit`: `pip-audit` on the installed dependencies
- `secrets`: gitleaks over the history that would merge

Actions are pinned to commit SHAs, the gitleaks binary is checksum-verified, and Dependabot is configured to propose updates weekly.

Each CI control was proved by a throwaway PR that should fail only its own check, then closed unmerged: a broken golden test failed `test`, an unused import failed `lint`, a pinned `jinja2==3.1.2` failed `audit`, and a fake AWS key failed `secrets`. The collector and study-app controls were proved by breaking each one locally and watching its test fail.

## Problems hit
- **The secret scan scanned every branch.** The first proof showed `secrets` red on three PRs with no secret in them, because `gitleaks git .` scans every ref the checkout fetches. A fake key on one branch failed everything. It is now limited to the checked-out history (`--log-opts="HEAD"`), and a second pair of PRs (one with a fake key, one harmless) showed only the key PR going red.
- **The importer said "Validation passed" on an export with no tables.** It now warns about each missing section.
- **A real export had a typo in a file name** (`suplier-policy`), which the "Rule N, file" matching could not resolve. The importer now also matches a finding's quoted rule text against the criteria.
- **A real level folder held a file I had not planned for.** Serving a scratch copy of a level showed its `CLAUDE.md` (the grader's rules) in the file list. It is now always hidden.
- **The progress bars were silently wrong.** They were sized with a style attribute, which the page's strict CSP blocks, so every bar drew full width. The polish pass found it by checking the page's real behaviour. They are now sized through the DOM, and a test bans style attributes, `innerHTML` and similar patterns in the page code.
- **Tests that passed for the wrong reason.** Three times a test proved nothing: an "IDs never reused" test whose deletes had silently failed with a 415, a symlink test that pointed at an invalid file so following the link looked the same as refusing it, and a break-the-control check whose pattern did not match the code. Each was found by checking that the test really fails when the control is removed, and rebuilt.

## Known shortcuts
- **Live Graph mode has not been run against a real tenant.** It is tested against fixtures with made-up `acme.example` addresses, so the response shapes follow the documentation and are unproved until someone runs it. The live run is parked: a separate workforce tenant needs a paid licence, and the lab tenant used for another project is deliberately kept out of it. [docs/live-test-runbook.md](docs/live-test-runbook.md) says what resuming needs.
- **The study app has only been tried on scratch copies of levels**, with your real notes and grading files as input. The interface is checked by hand in a browser, not by JavaScript tests, and only in a narrow window.
- The leavers check sees only the current state, so it cannot tell whether an account that is disabled now was disabled late.
- IDs are never reused by the app, which keeps a counter, and `grc check-ids` catches reuse from hand edits or the CLI importer by reading Git history. It is a command you run, not a required CI check, and it only sees what was committed.
- The app rewrites the YAML in a fixed layout, so template comments are dropped after the first save. Two browser tabs on one assessment is not supported: the last save wins.
- The grading import understands one layout (see the format doc). Mistake tags for "for next time" points come from a few keywords and are suggestions. The Excel export is a plain workbook, with no formulas or dropdowns.
- The importer drops any free text in the notes tool's "Ev # received" column beyond the evidence number. The request log and risk register are not in that export, so they are written by hand.
- The name guard is a safety net: a pre-commit hook can be skipped with `--no-verify`, and CI cannot run it because the list must stay private.
- Azure resource checks and a CSV import were not built.

## Teardown
No cloud resources: nothing is deployed, nothing costs money, and no budget alert is needed. The collectors read an existing tenant using your own `az` session and store no credentials. The study app runs only on your machine.

## Status
Complete: seven phases built and merged through pull requests into a protected `main`.
1. Data model, validation, `grc validate`, `grc init`
2. `grc report`
3. CI on every PR, with each control proved by a failing case
4. Request log, risk register, `grc import-notes`
5. Entra evidence collectors
6. The study app: files and notes, records, export, import, submit and lock, search, coverage
7. Grading import, mistake log, and progress across levels

## Development
```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```
