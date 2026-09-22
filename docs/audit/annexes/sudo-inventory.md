# Annex: `sudo()` inventory

`sudo()` switches off access rules and record rules for the call it wraps. The repo has **175** calls:
- about 110 in business code;
- the rest in tests, migrations and shell scripts, which are excluded below.

Each business-code call is sorted into one of three verdicts:
- **justified**: the system records a fact the user's gesture implies, and the gesture itself was already checked;
- **too broad**: correct intent, but it opens more than it needs;
- **risky**: data an untrusted or lower-privileged caller controls reaches a privileged write.

## Summary

| Verdict | Calls | Where |
|---|---|---|
| justified | about 88 | CRM, admission, identity bridges, meal ledger writes, maintenance workday |
| too broad | about 14 | see list |
| risky | **5 places** | see list |

The codebase is disciplined here. Nearly every `sudo()` carries a comment saying *why* (for example "la conseillere n'a que la LECTURE sur le dossier", or "sudo() here only unlocks the specific privileged calls it just authorized"). That is uncommon and worth keeping.

## Risky

| # | Location | Why | Finding |
|---|---|---|---|
| 1 | `his_access_base/models/res_users.py:88` | Writes `group_ids` on a user under `sudo`, from `hr.job.group_ids`. Anyone who can set a job's groups or an employee's job decides someone's groups, admin included. | S-1 |
| 2 | `campus_teacher_management/controllers/application_api.py:131,185` | Public, unauthenticated route creates `campus.submission` and `hr.applicant` under `sudo`. Guarded by a rate limit that can be bypassed (S-2) and no body size cap (S-3). | S-2, S-3 |
| 3 | `his_meal_management/models/pos_order.py:60` | Grants plan credits under `sudo` for any order line whose product grants credits, **whatever the price paid**. | S-5 |
| 4 | `maintenance_university/wizard/maintenance_university_worker_create.py:38-39` | Creates `res.users` under `sudo`. Correctly gated by `has_group(manager)`. The group list is fixed to Worker, so no escalation, but the generated password is then stored in plain text. | S-7 |
| 5 | `maintenance_university/models/hr_employee.py:92` | Adds the Worker group to **any** new employee's user under `sudo`. Low impact (the least-privileged group), but it's a silent write on `res.users`. | Info |

## Too broad

| Location | What it opens | Narrower form |
|---|---|---|
| `his_meal_management/models/res_partner.py:124,142` | Reads the whole ledger to compute one person's allowance | Already filtered by `partner_id`. Fine in effect, noted only. |
| `his_meal_management/models/res_partner.py:397-415` (`get_meal_balance`) | Any caller of this public method gets name, matricule and balance for **any** `partner_id` they pass | Check the caller is a cashier (`group_meal_cashier`) before the `sudo` read |
| `maintenance_university/models/maintenance_university_finding.py:49` | `default=` searches all employees under `sudo` | Only `user_id = uid` is needed, which is acceptable |
| `campus_teacher_management/controllers/application_api.py:92` | Rate-limit counts over all submissions | Fine; the problem is the IP it counts by, not the `sudo` |
| `his_person_core/models/his_person.py:367` | Writes a category onto partners under `sudo` | Acceptable: a system tag |
| `insite_recruitment/security/insite_security.xml:19-62` | Record-rule domains evaluate `campus.process.permission` under `sudo` | Acceptable, but it makes every access decision depend on a second permission table |

## Justified (representative)

- `his_admission/models/his_engagement.py:307-364`: the Finance desk records a payment it has no write access to. The gesture is checked in `_encaisser()`; the write follows from it.
- `his_crm_identity_bridge/models/crm_lead.py:174`: creates a lifelong matricule at the stage decided by business rules, not by the user's rights.
- `his_meal_management/models/res_partner.py:375`: ledger lines are written only by the system; the ledger refuses `write` and `unlink`.
- `maintenance_university/models/maintenance_university_workday.py:119-195`: every write is preceded by `_check_is_owner()`, as the module's own comment explains.
