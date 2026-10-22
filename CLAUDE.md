# grc-lite: instructions for Claude

My global `~/.claude/CLAUDE.md` workflow applies (I write the code, you draft and review; phases and small steps; one commit per step; PRs into a protected `main`; diary entry and study guide after each phase). The points below are specific to this project.

## What this is
A small compliance-as-code tool for gap assessments. Criteria, evidence and findings are YAML files in Git. A CLI validates them and generates a report. It is a portfolio project (cloud security / GRC) that grows from the exercises in `~/projects/grc/`.

- **Fictional data only.** The repo will be public. Never put real client, employer or personal data in it, and never any secrets, tenant IDs or subscription IDs.
- **Stack:** Python 3.10+ (use 3.14: `uv venv --python 3.14`; the system `python3` is 3.9 and too old), YAML files, Pydantic v2 for the data model, Typer for the CLI, pytest for tests, ruff for lint. `src/` layout, package `grc_lite`.
- **Keep it small.** No web framework, database or extra dependencies until a phase needs them. Lazy first, then expand.

## How to work with me here
- Default: draft each step as a short plan, the exact code, and a "things to understand" list. I type the code myself. Only edit files when I ask.
- Before each run, state the expected result (for example "pytest: 1 passed"). If the result differs, stop and find out why before I commit.
- Shell commands go one per code block.
- When I say "check before I commit", review the diff, run `ruff check` and `pytest` where possible, and say plainly whether it's ready.
- Don't say something is done or verified unless you've checked it.
- Never push to `main` directly once the branch rule exists. Branch from an up-to-date main: `git switch main`, `git pull`, `git switch -c <name>`.

## Phases (one commit per step)
1. Data model (criteria, evidence, findings), schema validation, `grc validate`
2. `grc report`: Markdown report with counts, ratings and a candidate-versus-selected summary, plus tests
3. CI on every PR (tests, lint, pip-audit, gitleaks), and a PR that gets blocked to prove the control
4. Import from my notes tool (`~/projects/grc/notes.html` download), request log, risk register
5. Evidence collectors for Entra and Azure (leavers, MFA status) compared against a rule

## Data model (matches my notes tool and the assessor playbook)
- **Criterion:** id (C-01), source, rule, evidence needed, ev refs, result (`not tested`, `meets`, `gap`, `can't test`).
- **Evidence:** id (E-01), date, source, type (`system`, `document`, `observation`, `interview`), what it shows, reliability note.
- **Finding:** id (F-01), title, status (`candidate`, `selected`, `dropped`), evidence strength (`strong`, `medium`, `weak`) and why, then for selected ones: criteria, condition, cause (optional), consequence, action, owner, due, likelihood, impact (with one-sentence reasons), control reference (optional). Rating = likelihood x impact; on the 1-3 scale 7-9 High, 4-6 Medium, 1-3 Low; on the 1-5 scale 20-25 Critical, 13-19 High, 6-12 Medium, 1-5 Low.
- IDs are never reused after deletion.

Reference: `~/projects/grc/00-assessor-playbook.md`.

## Current state
The skeleton exists (README, `.gitignore`, `pyproject.toml`, package, one smoke test, `data/example/`). **No git repo yet.** Next: Phase 1, Step 1 (git init, first commit, public GitHub repo, branch protection on `main`), then Step 2 (data model).

## Don't
- Don't add dependencies, CI or tooling that the current phase doesn't need.
- Don't commit anything that isn't fictional.
- Don't write the diary entry or study guide here unless I ask; they're handled in a separate chat.
