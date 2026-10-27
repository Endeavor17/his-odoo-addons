# Roles MDM: one master list of business roles

Design for making access rights in HIS Odoo come from one place, before
production goes live.

The governing idea, stated first:

> **The administrator picks business roles, never Odoo groups.** A job post
> points at HIS business roles ("Cafeteria Cashier", "Magasinier"); each role
> is defined once and knows which Odoo groups and which tills it means. Odoo's
> groups become an implementation detail of the role list.

Inputs: the staging role audit and map of 2026-10-27
(`/root/recette/carte-roles/` on 169.58.77.161, copy in the session
scratchpad), the till audit of the same day, and the decisions below.

---

## 1. Why now

- Setting up a person today means knowing raw groups. A meals cashier needs
  `point_of_sale.group_pos_user` + `his_meal_management.group_meal_cashier` +
  one till group; the post "Caissier repas" on staging forgets the till group.
- Inside a till, every employee of the company can tap their name, with no
  PIN, Administrator included: the pos_hr employee lists are empty, and empty
  means "everyone" (`pos_hr/models/pos_config.py::_employee_domain`).
  Reproduced locally 2026-10-27 on the Cafeteria till.
- Production (197.140.11.218) has no data yet. Building this before go-live
  means prod starts clean and **nothing is migrated** there. Every staging user,
  employee and post is test data.

## 2. Decisions (Mohamed, 2026-10-27)

1. **Access comes from the job post.** The admin sets a person's post, and the
   rights follow. A role added by hand on a user stays possible for real
   exceptions, and it shows up for review.
2. **A job post points at business roles, not Odoo groups.**
3. **Only the administrator** creates business roles and chooses a post's
   roles. HR assigns people to posts.
4. **Tills: the counter PC stays logged in, and cashiers tap their name.** The
   names offered at a till come only from job posts.
5. **A tapped-in cashier can sell, refund, change prices and give discounts**,
   for simplicity. Each cashier has a **PIN**. The cashier closes the till.
6. **Accounts that aren't people:** counter accounts (one per till) and
   service accounts (n8n) are built now. **No read-only/observer role now**;
   it is added as one more business role when someone needs it. For an outside
   accountant, Odoo's `account.group_account_readonly` already exists.
7. **Don't rebuild every module's levels.** Fix the real defects only, show
   what each role really grants, and group HIS roles under one heading.
8. **Ready before production goes live.**
9. **Everyone who logs in has an employee record with a job post**, except
   counter and service accounts.
10. **Beta modules are out of scope for now:** CRM/admissions
    (`his_crm_pipeline`, `his_admission`), content production, Campus+ and
    recruitment (`campus_teacher_management`, `insite_recruitment`). Their
    groups stay as they are and get roles later.
11. **POS managers stay on every till's list**, Administrator included. They
    are the supervisor who closes a till with a cash gap above tolerance.
12. **A PIN is required to appear at a till.** HR and the admin set it.

## 3. Goals, non-goals, anti-goals

**Goals**
- One master list of business roles, editable by the admin without a release.
- Job post → business roles → Odoo groups and till lists, applied automatically.
- Every till's list of names derived from job posts, with PINs.
- Counter and service accounts as first-class account types, not exceptions.
- Sensitive groups can never be given through a post or a role.
- The baseline test (`test_le_socle_ne_contient_que_les_outils_communs`) green.

**Non-goals**
- Renaming or restructuring existing module groups (CRM chains, purchase,
  Abdo's maintenance and hygiene levels).
- A general read-only role.
- Changing Odoo core implied groups (HR officer → equipment manager, POS
  manager → inventory user, …). They are shown, not changed.
- Per-cashier restrictions inside the till (refund, price, discount stay open).
- Migrating staging data. Staging is reseeded.

**Anti-goals** (failure even if it technically works)
- The admin still has to know a raw group name to set someone up.
- A till list or a user's groups drift from posts silently.
- A resync erases an exception someone set by hand (today's guarantee is kept).
- A post or role can hand out administration or another sensitive group.
- A colleague's module breaks or loses data because of this work.

## 4. Design

### 4.1 The business role (`his.role`, in `his_access_base`)

| Field | Meaning |
|---|---|
| `name` | Business name in English (`i18n/fr.po` gives the French) |
| `description` | What the person does with it, one or two lines |
| `kind` | `employee` · `counter` · `service`: which accounts may carry it |
| `group_ids` | Odoo groups the role grants (may be empty) |
| `granted_group_ids` | Computed: `group_ids` + everything they imply. Shown on the form |
| `job_ids` | Inverse: posts that carry the role |

- **Who edits it:** `base.group_erp_manager` (the Access Rights admin) only.
  Everyone with `base.group_user` may read it, so names show on posts.
- **The form shows everything the role really grants**, implied groups
  included, so "POS manager → inventory user" is visible before saving.
- **Constraint:** a role cannot grant a sensitive group, directly or through
  implication (§4.5).
- Lives in `his_access_base`, which stays free of business dependencies
  (its manifest's rule: it installs next to modules that don't know it).

### 4.2 Job post → roles → user groups

- `hr.job.role_ids` (Many2many `his.role`, `kind = employee` only) **replaces**
  `hr.job.group_ids`. Only `base.group_erp_manager` may write it (field
  `groups=` plus a write check, as the current admin-group constraint does).
- The groups a post grants = union of its roles' `group_ids`. The existing
  reconcile logic (`res.users._his_reconcilier_roles`, `role_ids_du_poste`,
  triggers on employee create and `job_id`/`user_id` change, the drift cron)
  is kept as is. Only its input changes, from `job.group_ids` to
  `job.role_ids.group_ids`.
- Exceptions stay as today: any group on a user that didn't come from the post
  is an exception and is never removed by a resync. The existing access-review
  view (`revue_acces_views.xml`) is the review list.
- **Drift is shown, not only logged (my call).** Today
  `_cron_reconcilier_roles` writes a server log line that nobody reads. Its
  findings (accounts out of sync with their post, tills with an empty list,
  and the till checks of §4.4) are shown to the admin in the access-review
  menu instead.
- **Editing a role re-applies it** to every account that holds it, through its
  posts or directly (my call).
- A person in two jobs: a post with several roles. One employee has one post
  (Odoo standard); no multi-post feature.

### 4.3 Account types

`res.users.his_account_type`: `employee` (default) · `counter` · `service`.

- **employee**: rights come from the job post of the linked employee (§4.2).
- **counter** and **service**: no employee. They carry
  `res.users.his_role_ids` directly (roles of the matching `kind`). The same
  reconcile logic applies, with the user's own roles as input instead of a
  post. The drift cron treats them as expected, not as exceptions.
- Only `base.group_erp_manager` sets the type and these roles.

### 4.4 Tills

Two things decide what happens at a till, and both now come from roles:

| Question | Answered by | Source |
|---|---|---|
| Which till may this PC open? | the **counter account's** role (`kind = counter`) | grants `his_stock_mdm.group_caisse_<till>` + `point_of_sale.group_pos_user` (+ `group_meal_cashier` for meal tills). The existing `pos.config.his_group_ids` check is kept unchanged |
| Whose names appear at this till? | the **employees' job post** (`kind = employee` role linked to the till) | a new `pos_config_ids` on `his.role` |

- **Till lists are derived, never edited.** For each till, the pos_hr list is
  set to every employee whose post carries a role linked to that till. It is
  recomputed when a post's roles, a role's tills, or an employee's post change.
  An employee does **not** need an Odoo user to be on the list (most cashiers
  only tap their name).
- **Which pos_hr list:** `advanced_employee_ids` (in-till "manager"), because
  cashiers do cash in/out and close the till (decision 5). `basic` and
  `minimal` stay empty. Note: closing with a cash gap above the till's
  authorized difference still needs an employee whose own user is a POS
  manager (`pos_hr` `closing_popup.js`); that tolerance is per till config.
- **The list must actually restrict (my call).** Core `pos_hr`
  `_employee_domain` only filters when `basic_employee_ids` is non-empty, so
  cashiers in `advanced_employee_ids` alone would still leave every employee
  tappable. Override it in `his_stock_mdm` so that any non-empty list
  restricts the till to the employees on the three lists.
- **pos_hr re-adds POS managers.** Core `pos.config.write` adds the employee
  of every `point_of_sale.group_pos_manager` user to `advanced_employee_ids`
  on every write, creating an employee for a manager who has none. The
  derived-list sync works with this, not against it: managers stay on every
  list (decision 11). The staging check "only Cafeteria cashiers appear"
  allows for POS managers.
- **No PIN, not on the list (my call on decision 12).** An employee whose post
  carries a till role but who has no PIN is left off that till's list and
  shown to the admin in the drift review ("cashier without PIN"). Saving is
  never blocked, so HR can create the employee first and set the PIN after.
  Writing `hr.employee.pin` stays with the HR officer group and the admin.
- **A till with no cashier role linked** keeps an empty list, which pos_hr
  reads as "everyone". The derived-list code must never leave a till in that
  state by accident: a till with module_pos_hr on and zero derived employees
  is reported by the drift cron.
- **The till-roles editor and `pos_hr` lists become read-only in the UI** (the
  POS settings page shows them, with a note that they come from job posts).
- **Price control:** `restrict_price_control` stays off and `manual_discount`
  stays on (decision 5).
- **Where this code lives:** `his_stock_mdm` (which already owns the till
  roles and the three tills), adding `pos_hr` and `his_access_base` to its
  dependencies. `pos_hr` is installed on every HIS till but declared by no
  module today.

### 4.5 Sensitive groups: never through a post or a role

The current `ADMIN_GROUP_XMLIDS` (`base.group_system`,
`base.group_erp_manager`) becomes a wider list, checked with implication as
today:

- `base.group_system`, `base.group_erp_manager`
- `base.group_sanitize_override` (bypass HTML sanitizing)
- `mail.group_mail_template_editor`
- `account.group_account_manager`
- `base.group_allow_export`
- `api_doc.group_allow_doc`

A role or post carrying one is refused. The admin can still give one by hand
to a specific user; it then appears as an exception in the access review.
The reconcile step keeps stripping these as defence in depth.

### 4.6 Defects fixed along the way

- **Dashboards open to every employee:** the root menu "Tableaux de bord"
  (and "Tests") has no group. Close it at the data level, not only the menu,
  so the baseline test passes.
- **Maintenance Manager doesn't include Reporter**
  (`maintenance_university`, Abdo's module): add the implication. Tell Abdo
  in the PR.
- **One "HIS" heading:** HIS groups are spread over Odoo categories ("Supply
  chain", "Sales", …). Move every HIS-defined group's privilege under one HIS
  category so the user rights screen reads.

### 4.7 Starting catalogue

Shipped as data with `noupdate="1"`, so the admin's edits survive upgrades.
One role per real job, built from today's posts and the map. Beta modules
are left out (decision 10).

| Area | Roles |
|---|---|
| Tills | Cafeteria / Restaurant / Copy Center Cashier (employee, till-linked, no groups) · Cafeteria / Restaurant / Copy Center Counter (counter) · POS Supervisor (`point_of_sale.group_pos_manager`) |
| Meals | Meals Officer |
| Stock | Magasinier · Stock Manager · Catalogue Manager |
| Purchase | Purchase Requester · Buyer · Executive Director |
| Accounting | Invoicing clerk · Accountant (accounting manager is sensitive, §4.5: by hand only) |
| HR & identity | HR Officer · People Register Manager (`his_person_core`) · Directory reader (`his_access_base.group_annuaire`) |
| Helpdesk | Helpdesk Agent (own / team / all) · Helpdesk Manager |
| Maintenance | Reporter · Worker · Manager |
| Hygiene | Hygiene Worker · Hygiene Manager |
| Dashboards | No role of its own: each Metabase dashboard already opens to its area's manager group (`his_metabase` data), so it follows the manager roles above |
| Service | n8n Service |

The exact groups for each are taken from the map's current posts and checked
against it.

## 5. Constraints

- Odoo 19 Community. Source strings in English, French in `i18n/fr.po`.
- Menu groups are changed with `(4, …)` / `(3, …)`, never `(6, 0, …)`
  (`his_access_base` note: that is what once left the Apps menu open).
- `docs/rbac.md` policy tests stay green, and are extended (§6).
- Commits authored `Endeavor <mohamed.bounouaa@outlook.com>`, no trailer.
- Abdo owns `maintenance_university` and `his_hygiene`: changes there are
  minimal and signalled.
- Dev freeze since 2026-10-17: this is stabilisation (it closes recette P-18
  and the till audit), not a new feature.

## 6. How we know it works

- Tests: a post with "Cafeteria Cashier" puts its employee (no user) on the
  Cafeteria advanced list and on no other till; changing the post removes
  them; a till with roles never ends up with an empty list.
- Tests: a role carrying any sensitive group (directly or implied) is refused.
- Tests: a hand-added group survives a role change on the post.
- Tests: counter and service accounts are not reported as drift.
- `test_le_socle_ne_contient_que_les_outils_communs` green.
- Rendered on staging (a clean install is not verification): the Cafeteria counter
  account opens only the Cafeteria; only Cafeteria cashiers appear at its lock
  screen, each asked for a PIN; the admin creates a role and sees everything
  it grants.
- `regenerer/` of the role map rerun on staging after the change: every post
  points at roles only, no till has an empty list.

## 7. Left to the builder

- Field and XML ids, view layout, and how the till lists are recomputed
  (compute-stored vs explicit sync on write), as long as no path leaves a
  list stale.
- Whether the starting catalogue lives in `his_access_base` or in each
  business module (roles that need a module's groups probably belong with
  that module, or in a module that depends on it).
- Order of work: a plan (superpowers:writing-plans) splits this into
  independent PRs.
