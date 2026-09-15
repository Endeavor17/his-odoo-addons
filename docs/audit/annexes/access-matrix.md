# Annex: access matrix and rights probes

## Method

Every probe ran in `odoo shell` on a throwaway database (`audit_test`, or `audit_stock` for the meal wallet), as a **real user created with only the groups listed**, never as superuser. Each probe ran inside a savepoint that was rolled back, and the database was deleted afterwards.

The scripts are reproduced at the end of the report's reproduction section.

## Probe results

| # | Actor (groups) | Attempt | Result | Finding |
|---|---|---|---|---|
| P1f | HR Officer **plus** Recruitment Officer | create a job, put `base.group_system` in its roles, set that job on their own employee | **Became Settings administrator** and read `ir.config_parameter` | **S-1** |
| P1a | HR Officer | set a job that already carries `base.group_system` on their own employee | **Became administrator** | S-1 |
| P1b | HR Manager | same | **Became administrator** | S-1 |
| P1c | Recruitment Officer | write `base.group_system` into any job's roles | **Allowed** (holders get it at the next reconciliation) | S-1 |
| P1d | Campus+ recruiter | same | **Allowed** | S-1 |
| P1e | Recruitment Officer alone, holding a job | re-apply the job's roles themselves | Denied (no read on `hr.employee`) | this alone can't escalate |
| P4 | Plain internal user | read a candidate's contact | **Allowed**: name, email and phone via `res.partner`. `his.person` itself denied | **S-6** |
| P5 | Maintenance worker | read employees' private email and phone | Denied | control holds |
| P6 | Campus+ recruiter | read raw public submissions | Denied | control holds |
| P2 | Meal Officer | write `credits_total` on a subscription | **Allowed**: 1 → 500 credits, 0 ledger lines | **S-4** |
| P3 | Restaurant Cashier | read the whole meal ledger | **Allowed**: sees other students' lines | S-6 |
| P7 | Plain internal user | `get_meal_balance()` on any student | **Allowed**: matricule `HIS-2026-000001`, balance, plan | **S-6** |
| P8 | Meal Officer | edit a ledger line | Denied ("permanent record") | control holds |

The meal probes ran on `audit_stock`, which had categories seeded and a copy of `his_meal_management` whose two `pos.category` records were moved up (D-2). The repo itself was not changed.

## ACL overview (the repo's `ir.model.access.csv` files)

| Module | ACL rows | Rows open to `base.group_user` | Record rules |
|---|---|---|---|
| campus_teacher_management | 27 | 0 | 3 (submission and permission: managers; applicant: process permission) |
| insite_recruitment | 18 | 0 | 6 (driven by `campus.process.permission`) |
| maintenance_university | 18 | 0 | 12 (manager all, worker own, reporter own) |
| his_admission | 16 | 3, read-only (domaine, specialite, document type) | 1 |
| his_crm_pipeline | 14 | 1, read-only (deliverable type) | 8 (team, requester, direction) |
| his_meal_management | 9 | 0 | **0**: cashier and officer see every card, subscription and ledger line |
| his_person_core | 2 | 0 | 0 |
| his_hr_base | 2 | 0 | 0 |
| his_person_sync_sheets | 3 | 0 | 0 |
| his_academic_base | 1 | **1, read-only (`his.faculty`) not registered in `REFERENCE_PARTAGEE`**, so the policy test is red | 0 |
| his_stock_mdm | 1 | 0 | 0 |
| campus_identity_bridge | 1 | 0 | 0 |
| his_access_base | 0 | 0 | 0 |

**What the matrix shows:**
- **Deny-by-default holds at model level.** No business model grants write to all employees, and the policy test enforces it.
- **The gaps are at the edges of that policy:**
  - `res.partner` (Odoo core, read for all employees) carries student and candidate contact details through delegation (S-6);
  - `hr.job.group_ids` lets HR data decide security groups (S-1);
  - `his.meal.subscription` write access is broader than the module's own promise (S-4, pending).
