## 1-demo/01-scope.md

Scratch notes about the fictional company Northwind Traders. Not part of the import.

## Criteria sheet

| ID | Source | Rule | Evidence needed | Ev # received | Result |
| --- | --- | --- | --- | --- | --- |
| C-01 | access-policy.md rule 1 | Every user has their own account. | Account list | Ev-1: list shows no shared accounts | Meets |
| C-02 | access-policy.md rule 3 | Leavers are disabled by the end of their last day. | HR leavers list and account export | Ev-02: export; Ev-3: HR list | Gap: 2 of 10 still enabled |
| C-03 | access-policy.md rule 4 | Access is reviewed every 6 months \| signed. | Signed review | | Can't test |

## Evidence log

| ID | Date | Source | Type | What it shows | Reliability note |
| --- | --- | --- | --- | --- | --- |
| E-01 | 2026-02-02 | user-list.csv | system | 10 accounts, none shared | Exported by client |
| E-02 | 2026-02-02 | account-export.csv | system | 2 of 10 leavers still enabled | Exported by client |
| E-03 | 2026-02-03 | hr-leavers.md | document | 10 leavers in January | |

## Candidate findings

| ID | Title | Status | Evidence strength | Why |
| --- | --- | --- | --- | --- |
| F-01 | Leavers keep accounts | selected | strong | Two exports agree |
| F-02 | Reviews may be missed | candidate | weak | No review record seen |
| F-03 | Shared accounts | dropped | strong | Account list shows none |

## Findings

### F-01: Leavers keep accounts
- **Criteria:** Rule 3, access-policy.md, leavers are disabled by the end of their last day.
- **Condition:** 2 of 10 leavers (20%) still enabled. Ev-02
- **Cause:** Leavers are reported by email only.
- **Consequence:** Former staff could still sign in (and read data).
- **Action:** Add account removal to the leaver checklist. (Owner: Ops Manager; Due: 2026-06-30)
- **Rating:** Likelihood 2 (Enabled for weeks) x Impact 3 (Could reach customer data (names)) = 6 Medium [scale 1–3]
- **Control ref:** N/A
