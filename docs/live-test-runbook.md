# Live test runbook: running the Entra collectors against a real tenant

Status: a plan. Nothing in this file has been run. Until a run is recorded in the README, live mode is described there as **not yet run against a real tenant**.

The collectors (`grc collect leavers`, `grc collect mfa`) are tested only against fixtures built from the Microsoft Graph documentation. This runbook is how to find out where real responses differ.

## Rules for every live run
- **A throwaway tenant only**, one you own and can delete. Never a work or client tenant.
- **Read-only.** Every request is a `GET`, and the app registration (later) gets read permissions only.
- **Nothing identifying leaves the machine.** No tenant IDs, subscription IDs, tokens, user names or email addresses in a commit, a pull request, a screenshot, a chat or a log you share. Real output stays in `collected/` (mode 600, ignores itself).
- **Ask before each live call.** The person running it decides, and reads the command first.
- **State the expected result before each run**, and stop and find out why if the real one differs.
- **Say what a run did and did not cover.** One tenant, one licence tier and a handful of fake users prove very little about other tenants.

## 1. Choose the tenant
Pick one and write down which. Check the current Microsoft terms and eligibility yourself, because they change.

| Option | Good for | Watch out for |
|---|---|---|
| A free Entra ID tenant you create under your own account | Users, roles, the user list | Some reports and sign-in data need a paid licence, so the MFA report may return nothing or an error. That is itself a finding. |
| A Microsoft 365 developer sandbox, if you are eligible | Sample users, a paid licence tier, real audit and report data | Eligibility rules; the sandbox expires if unused. |
| An existing lab tenant from another project | Already set up | Make sure nothing real is in it. |

**Find out and record before relying on it:** which licence the tenant has, how many days of audit log it keeps (I believe free tenants keep about 7 days and paid ones about 30, but check), and whether the authentication-methods reports are available at all. Step 5 of the plan (leavers from the audit log) depends on the answer.

## 2. Create the fake users
Use a clearly fake naming pattern, such as `test.leaver1`, so nobody mistakes them for people. Create these cases:

| Case | How to create it | What the collector should say |
|---|---|---|
| A leaver still enabled | An enabled user whose leave date in your HR CSV is more than a day ago | gap |
| A leaver disabled in time | A user you disable now, with a leave date today | meets |
| A late-disabled leaver | A user you disable after their leave date (only visible in the audit log, step 5) | meets today, a finding once step 5 exists |
| An admin without MFA | A user with an admin role who has never signed in or registered | gap |
| An admin with MFA | A second admin who signs in once and registers an authenticator method | meets |
| An ordinary user | No role | in scope only for `--scope all` |

Notes:
- If security defaults are on, they push admins to register MFA at first sign-in. Leave the "admin without MFA" user unsigned in, or turn security defaults off in the throwaway tenant.
- Keep the HR leavers CSV in `collected/` or outside the repo. It uses the fake users' principal names, but treat it as real.

## 3. Sign in for the first runs
The collectors currently take a token from your Azure CLI session. For the first runs (plan step 2), sign in to the **test tenant only**:

```bash
az login --tenant <your test tenant> --allow-no-subscriptions
```

Then confirm locally, and do not paste the output anywhere, that the account and tenant shown are the throwaway ones:

```bash
az account show --query "{tenant:tenantDisplayName, user:user.name}" -o table
```

If it shows anything you do not recognise as the throwaway tenant, run `az logout` and stop.

The app registration with read-only permissions comes later (plan step 4), so the first runs do not depend on it.

## 4. Before each run
1. `git status` is clean, and the folder you will write to is outside any repo you push, or is the self-ignoring `collected/` folder.
2. You have written the expected result, for example "leavers: gap, 1 of 3 leavers enabled".
3. You know which command, and that it is `--live`, which only reads.

```bash
.venv/bin/grc collect leavers <assessment folder> --hr <hr csv> --live
```

```bash
.venv/bin/grc collect mfa <assessment folder> --live --scope admins
```

## 5. After each run
1. Compare the result with the expected one.
2. Write a short findings note (below). Do not paste raw responses. Until the shape probe exists (plan step 2), describe differences in words.
3. Check that `git status` shows no new tracked files and that the detail file is in `collected/`.

### Findings note template
```
Run: <date>, tenant licence: <free / paid>, users: <n>
Command: leavers | mfa
Expected: ...
Got: ...
Differences from the documented response: (one bullet each)
  - field/permission/paging/error behaviour, and what the code assumed
Not covered by this run: ...
```

## 6. When you are finished
- `az logout`.
- Remove any app registration or consent you no longer need.
- Delete the throwaway tenant, or note that it remains and what is in it.
- Update the README to say exactly what was run and what was not.

## Unknowns this run should settle
- Which Graph permission each call actually needs. The README's list came from the documentation, not from a run.
- Whether the response shapes match the fixtures (field names, nesting, paging, the `$select` behaviour for `accountEnabled`).
- What an unlicensed tenant returns for the MFA registration report.
- How long audit events are kept, which decides how far back "late disable" can be found.
