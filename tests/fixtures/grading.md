# Northwind Traders (fictional): grading

## Grader notes

| Sheet | ID | Key rating | Grader note |
| --- | --- | --- | --- |
| Criteria | C-02 | | Marked meets. This is wrong: the rule is conditional, so test each case. |
| Evidence | E-02 | | Count should read 2 of 10, not 20%. |
| Candidates | F-02 | | Good call to drop: weak evidence. |
| Findings | F-01 | 6 Medium | Caught, rating matches. No Cause line. |

## Planted items

| # | Planted gap | Result | Your rating | Key rating | Finding |
| --- | --- | --- | --- | --- | --- |
| 1 | Leavers still enabled: 2 of 10 | Caught | 6 | 6 | F-01 |
| 2 | Shared logins | Caught, rated too low | 2 | 6 | F-04 |
| 3 | Review overdue | Caught, rated too high | 9 | 4 | F-05 |
| 4 | INC-04 not assessed | Missed | n/a | 9 | F-10 (added) |

## Grading summary

| Point | Detail |
| --- | --- |
| Planted gaps caught | 3 of 4. Missed: INC-04. |
| Slots | Only 3 findings submitted. |

## Done well

| Point | Detail |
| --- | --- |
| Candidate discipline | Dropped the weak candidate rather than padding. |

## For next time

| Point | Detail |
| --- | --- |
| 1 | When a rule is conditional, test the condition for every item. Do not count entries. |
| 2 | Give every finding a Cause line. |
| 3 | Check any claim in your notes against the source before it goes into a finding. |
| 4 | Use all the slots. |

## Findings

### F-10: Wrong-patient email was never assessed
- **Criteria:** Step 3, incident-procedure.md
- **Condition:** On 2026-07-23 a list was emailed to the wrong person. <script>alert(1)</script>
- **Rating:** Likelihood 3 (It happened) x Impact 3 (Health data) = 9 High [scale 1-3]
