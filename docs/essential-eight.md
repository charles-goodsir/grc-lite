# The Essential Eight example

`data/essential-eight/` is a fictional assessment of an invented firm, Fenwick & Reid Surveyors, against **Maturity Level One** of the Australian Signals Directorate's Essential Eight. I built it to learn the model by encoding it, so each entry says what the control is really testing and what evidence would show it.

## Source and what this is not
- **Source:** the ASD Essential Eight maturity model on cyber.gov.au. The page I read on 24 October 2026 showed *published 30 June 2017, last reviewed 27 November 2023*. ASD updates the model, so check the current version before using any of this.
- **Not a copy.** Each criterion is a short paraphrase of part of Maturity Level One, and cites the model by name and version in its `source` field. It covers a selection of the requirements for each strategy, not all of them. The model itself is the authority.
- **Not a compliance statement.** The organisation, people, counts and findings are invented. The example is for learning the method.

## What each strategy tests
| Strategy | What it really tests | Evidence to ask for | Criteria here |
|---|---|---|---|
| Application control | Whether only approved software can run, so a downloaded program cannot execute | Policy export from sample workstations, plus a test with an unapproved program | C-01 |
| Patch applications | How fast known flaws are fixed in online services, office software, browsers and PDF readers | Scanner results, and release and install dates for recent critical patches | C-02, C-03 |
| Patch operating systems | The same speed test for operating systems, with a longer allowance for workstations | Patch compliance report with dates, and the operating system versions in use | C-04 |
| Multi-factor authentication | Whether a stolen password alone is enough to get into a service holding sensitive data | A list of sensitive online services, and the MFA setting for each | C-05 |
| Restrict administrative privileges | Whether powerful accounts are few, separate from daily accounts, and kept away from the web and email | A privileged account list, the blocking policy, and recent access requests with approvals | C-06, C-07 |
| Restrict Microsoft Office macros | Whether a macro in a document from outside can run by default | The macro policy, and a test with a file from the internet | C-08 |
| User application hardening | Whether browsers and similar software are set up to cut off common attack routes | Browser policy export, and a check of a sample workstation | C-09 |
| Regular backups | Whether data can be recovered, and whether an attacker or an ordinary user could wipe the backups | The schedule, the last restore test, and who can delete backups | C-10, C-11 |

## What the example shows about the method
- **A result is not a finding.** Four rules fail, and each failure is a finding only once the evidence, cause, consequence and rating are written.
- **Some rules cannot be tested yet.** C-07 is "can't test" because the approval records have not arrived, so it has an outstanding request and a weak candidate, not a gap.
- **A rule can pass and still be worth testing.** C-08 meets, so the macro finding was dropped.
- **One rule is untouched.** C-09 is "not tested", which the pre-submit check would flag.
