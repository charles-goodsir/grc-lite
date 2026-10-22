# Grading file format

After a submitted level is reviewed, the grader returns one Markdown file. The study app's Grading tab imports it. Anything that does not fit this layout is listed as a warning and left out; nothing is guessed.

A file needs at least one of the sections below. Tables are ordinary Markdown tables, and extra columns are ignored.

## Sections

| Section | Columns | Used for |
|---|---|---|
| `## Grader notes` | Sheet, ID, Key rating, Grader note | A note shown on your own record. Sheet is `Criteria`, `Evidence`, `Candidates` or `Findings`. |
| `## Planted items` | #, Planted gap, Result, Your rating, Key rating, Finding | The scoreboard. |
| `## Grading summary` | Point, Detail | Shown as written. |
| `## Done well` | Point, Detail | Shown as written. |
| `## For next time` | Point, Detail | Each row becomes a mistake-log entry. |
| `## Findings` | `### F-10: title` blocks | Gaps you missed, shown as text. They are not added to your records. |

Result wording decides the outcome: `Caught`, `Caught, rated too low`, `Caught, rated too high`, `Missed`. Bold markers are ignored. Anything else is shown as written and counted as "other".

## The mistake log

Every planted item that is not a clean catch, and every "For next time" row, becomes an entry. Two kinds of tag are suggested automatically: `missed gap` for a missed item and `wrong rating` for a rating that is too low or too high. "For next time" rows are matched on a few keywords (cause, conditional, claim, count, rate), and anything else is tagged `other`. All suggestions can be changed in the app. The tags are:

missed gap, wrong rating, miscounted, conditional rule not tested, cause missing, weak evidence selected, unverified claim, other.

## When the answer key opens

`answer-key*` files and the `graded/` folder stay hidden until the level is submitted and a grading file has been imported. That is self-discipline, not security: deleting `grading.yaml` from the assessment folder seals them again, and creating one by hand opens them.

See `tests/fixtures/grading.md` for a small fictional example.
