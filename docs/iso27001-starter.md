# The ISO 27001 starter example

`data/iso27001-starter/` is a fictional assessment of an invented company, Larkspur Analytics Ltd, against a small selection of ISO/IEC 27001:2022. It is written like the Essential Eight example: invented people, counts and findings, with evidence reliability notes and a mix of results.

## Sources and what this is not
- **I did not read the standard.** ISO/IEC 27001:2022 is paid. I used only control numbers and short titles, which I checked against two public lists on 24 October 2026: the Annex A controls list on hightable.io and the ISO 27001:2022 control list on haitmg.pl. Both gave the same number and title for all ten Annex A controls used here. For clause 6.1.3 and clause 9.2 I relied on several public summaries, which agree on what each clause is about, and I cite them at clause level only.
- **Where titles differ in length** between sources (for example the incident planning control), I used the shorter form that both share.
- **The rules are my own plain-English tests,** written from each control's title. They are not the standard's wording, and they are not a statement of what the standard requires. Read the standard for that.
- **It is not an audit.** A real ISO 27001 assessment tests an organisation's own management system and its own Statement of Applicability against the standard itself.

## The structure to know
Annex A in the 2022 edition has 93 controls in four themes: organisational (clause 5), people (6), physical (7) and technological (8). An organisation does not have to implement all of them. It decides which apply through a risk assessment and records that in a **Statement of Applicability**, which is a requirement of clause 6.1.3. That is why this example has a finding about exclusions with no reason, and why the standard's management-system clauses (such as 9.2, internal audit) matter as much as the controls.

## What each criterion tests
| Criterion | Control or clause | What it really tests | Evidence to ask for |
|---|---|---|---|
| C-01 | A.6.5 | Whether a person's access ends when their employment does | HR leavers list against the account list; the leaver checklist |
| C-02 | A.5.15 | Whether there is a rule for who may use what, and it is applied | The access policy; a sample of real permissions |
| C-03 | A.5.18 | Whether access is given, reviewed and removed through a process | Review schedule and the last two review records |
| C-04 | A.8.2 | Whether powerful access is limited, approved and reviewed | Administrator list with approvals and the last review |
| C-05 | A.8.5 | Whether sign-in strength matches the system, such as MFA for administrators | Authentication policy; the MFA registration report |
| C-06 | A.8.13 | Whether data can be recovered, and the backups are tested | Backup policy; the latest restore test |
| C-07 | A.8.15 | Whether security events are recorded, protected and actually reviewed | Logging standard; retention settings; review records |
| C-08 | A.8.8 | Whether known weaknesses are found and fixed in a set time | Scanner reports and fix dates |
| C-09 | A.5.19 | Whether supplier security is agreed and supplier risk managed | Supplier register with risk ratings; contract terms |
| C-10 | A.5.24 | Whether incidents are planned for, with roles people know | Incident procedure; awareness records or a test |
| C-11 | clause 6.1.3 | Whether exclusions from Annex A are justified by risk | The Statement of Applicability and risk treatment plan |
| C-12 | clause 9.2 | Whether the system is audited objectively at planned intervals | The audit programme and last report, with who wrote it |

## How it relates to the rest of grc-lite (my mapping, not an official one)
I found no official mapping between these, so this is my own judgement, and it is the first thing to question.

| Essential Eight strategy or collector | Closest control here |
|---|---|
| Multi-factor authentication; `grc collect mfa` | A.8.5 secure authentication, and A.8.2 for administrators |
| Restrict administrative privileges | A.8.2 privileged access rights, with A.5.18 for reviews |
| Patch applications; patch operating systems | A.8.8 management of technical vulnerabilities |
| Regular backups | A.8.13 information backup |
| `grc collect leavers` | A.6.5 responsibilities after termination or change of employment, with A.5.18 |
| Application control, Office macros, user application hardening | No control selected in this starter, so unmapped here |

## What the example shows about the method
- **A control and a clause are different tests.** C-11 and C-12 test the management system itself, which a technical collector cannot.
- **Evidence strength matters.** F-03 is selected on medium evidence because the retention setting is exported but how often logs are read rests on one interview, and the coach says so as a tip.
- **Some things wait.** C-09 is "can't test" until the supplier register arrives, and F-06 stays a weak candidate.
- **One rule is untouched,** C-10, which the pre-submit check flags as "not tested".
