# maintenance_university — University Maintenance

Maintenance for the Groupe HIS-HTC-IRA campus: buildings instead of equipment, a
request pipeline with real time tracking, inspection tours that produce
findings, and a monthly recap for the leader.

> **This module IS core Odoo's Maintenance app, extended.** It inherits
> `maintenance.request` directly rather than shipping a lookalike model beside
> it. The technical name stays `maintenance.request` everywhere — views, other
> modules, security. Core's own generic Maintenance menu is hidden so there is
> no collision.

---

## 1. Roles

Three groups, in two ladders.

| Group | Implies | Sees | Menus |
|---|---|---|---|
| **Worker** | `base.group_user` | Only requests they are assigned to | My Work |
| **Manager** | Worker | Everything | + Monthly Recap, Requests, Findings & Reports, Work Days, Worker Summary, Configuration |
| **Reporter** | `base.group_user` | Only their own standalone reports. **No requests at all** | Report a Problem |

**Reporter is a sibling, not a lesser Worker.** It has its own
`res.groups.privilege`, so Settings renders it as a separate checkbox rather
than a rung on the Worker/Manager dropdown. Someone can be a Reporter without
ever being a Worker — a secretary who reports a broken door is not maintenance
staff.

That distinction is enforced in code too: `hr_employee.create()` defaults a new
employee's user to Worker *unless* they already hold Worker **or Reporter**.
Without the Reporter half of that check, giving a Reporter an employee record
would silently also make them assignable to real repair work.

---

## 2. The request lifecycle

`state` is **computed and stored** from core's real `stage_id` + `kanban_state`,
not an independently writable column. Every existing domain, filter and search
that reads `state` keeps working, while the pipeline stays core's.

```
new ──assign──> assigned ──start──> in_progress ──done──> done
                                       │    ▲
                                    pause  resume
                                       ▼    │
                                     paused ┘

  any open state ──cancel──> cancelled
```

**Paused is not its own stage.** It is `kanban_state = 'blocked'` while the card
stays in *In Progress* — a pause is not a different step in the pipeline.

### Who may press what

| Action | Who | Enforced by |
|---|---|---|
| Create / delete a request | Manager only | `create()` / `unlink()` |
| Assign | Manager only | needs at least one worker selected |
| Start / Pause / Resume / Done | **Assigned worker only — no manager bypass** | `_check_is_assigned_worker()` |
| Cancel | Manager *or* an assigned worker | `_check_can_operate()` |
| Submit inspection report | Manager or assigned worker | posts to the chatter |

The no-manager-bypass on Start/Done is deliberate: a leader assigns and tracks
work, they do not perform it. Letting them close a job themselves would defeat
the point of assigning it out.

### What a worker may edit

Only `WORKER_WRITABLE_FIELDS` — stage, kanban state, the three dates,
`inspection_report`, `finding_ids`, `close_date`. Everything else defines the job
itself (what / where / who / when) and is manager-only, **including through
direct API calls**, because the check lives in `write()`.

`close_date` is in that set only because core Maintenance sets it as a side
effect of reaching a done stage, from a nested `write()` inside our own action.

---

## 3. Models

| Model | Type | Purpose |
|---|---|---|
| `maintenance.request` | inherit | The job. Buildings, workers, time logs, findings |
| `maintenance.building` | new | Where. Name, code, description |
| `maintenance.category` | new | What kind of problem. One may be flagged *Inspection* |
| `maintenance.university.finding` | new | An observation. Two distinct uses — see §4 |
| `maintenance.university.request.time` | new | One work segment on a request: start, end, computed duration |
| `maintenance.university.workday` | new | One worker's presence on one day: arrival, breaks, departure |
| `maintenance.university.workday.segment` | new | A stretch of that day, `work` or `pause` |
| `maintenance.university.dashboard` | abstract | Monthly recap data, no table |
| `hr.employee` | inherit | Start date, maintenance stats, temporary password |
| `maintenance.university.worker.create` | transient | The Create Workers wizard |

### Fields redirected rather than duplicated

The module reuses core's field slots instead of adding parallel ones:

- **`category_id`** → repointed at `maintenance.category`. Core's version is
  `related='equipment_id.category_id'`, an asset taxonomy; we have buildings,
  not equipment, so it would always be empty.
- **`request_date`** → `Date` becomes `Datetime`, because the dashboard compares
  month windows.
- **`duration`** → core's static schedule estimate becomes the real sum of
  logged time segments.
- **`priority`** → same four keys (`0`–`3`), only the labels change.

> ### The trap that redirecting `category_id` created
>
> Core declares, on **its own** category model:
>
> ```
> maintenance/models/maintenance.py:43
>     maintenance_ids = fields.One2many('maintenance.request', 'category_id')
> ```
>
> The ORM therefore records *"the inverse of `category_id` is called
> `maintenance_ids`"* and looks for it on the comodel — which is now
> `maintenance.category`. While that field did not exist, the first `onchange`
> on a category raised `KeyError: 'maintenance_ids'` and the Categories form
> could not be opened at all.
>
> `maintenance.category.maintenance_ids` exists for exactly this reason. **Do
> not remove it.** `tests/test_category_inverse.py` reproduces the original
> crash if it goes.

---

## 4. Findings — one model, two jobs

`maintenance.university.finding` serves two different people, separated by
whether `request_id` is set.

| | Inspection finding | Reporter's problem report |
|---|---|---|
| `request_id` | the inspection request | **empty** |
| Filed by | a worker on a tour | anyone with the Reporter role |
| Visible to | manager, and the assigned worker | only its author |

**Lifecycle:** `draft → submitted → converted`.

Once submitted, the fields that define what it says — building, category,
description, severity, photos, notes — are locked to non-managers. Whoever
converts it is acting on those exact values, so the author must not be able to
change them mid-review. A submitted item can no longer be deleted either.

**Converting** is manager-only and produces a real request, mapping severity
onto priority:

```
low → 0 (Low)        medium   → 1 (Normal)
high → 2 (High)      critical → 3 (Urgent)
```

A finding may not use the Inspection category — converting it would create
another inspection instead of a repair.

One subtlety worth keeping: the *Reported By* default runs `sudo()`. A Reporter
has no read access to `hr.employee` at all, but the default still executes on
every create regardless of which view is in use, so without `sudo()` every
Reporter submission raised an `AccessError`.

---

## 5. Time tracking

Start, Pause, Resume and Done open and close segments in
`maintenance.university.request.time`. The request's `duration` is their sum.

Two rules keep it honest:

- **Never two open segments at once.** `_open_time_segment()` closes any open one
  first; a stale segment would later be closed by an unrelated action and
  inflate the total.
- **The segment is logged under whoever clicked**, not "the first assigned
  worker" — several people can share a job.

### The work day — presence, not task time

`maintenance.university.workday` records when a worker arrived, every break, and
when they left. One row per employee per day (`UNIQUE(employee_id, date)`), with
`maintenance.university.workday.segment` children of kind `work` or `pause` —
the same open-ended-row shape as the request time log above, including its
duration compute. `worked_hours` excludes breaks; `paused_hours` accounts for
them; `state` is derived from the segments, never stored as something writable.

The worker drives it from a **banner across the top of My Work**: Start working,
Take a break, Back to work, End day. That banner is a kanban variant selected by
`js_class`, so My Work stays an ordinary window action and keeps New, opening a
card, breadcrumbs, filters and the pager — all the action service's job.

**This is deliberately a different number from the request time above.** Presence
keeps running between jobs and through a break; task time does not. The gap is
travel and idle time, which is the interesting figure for a leader, and the
Monthly Recap reports both.

Two rules of its own:

- **The worker cannot rewrite it.** A Worker holds read access and nothing more;
  all four buttons write under `sudo()` after establishing the day is theirs. A
  presence record the measured person can edit measures nothing — and the record
  rule scopes them to their own day, which is exactly the day they would change.
- **Nothing auto-closes.** A day left running stays open until a manager corrects
  it on the **Work Days** screen. Better a visibly wrong record than a quietly
  invented end time.

---

## 6. Manager screens

**Worker Summary** — `hr.employee` scoped to workers who are *not* managers.
Without that exclusion every employee in the university appeared, almost all
with zero stats. The views are `create="0" edit="0" delete="0"`: it is a stats
screen, not a way to create people. The form shows the worker's **Login** and
**Temporary Password**.

It also answers *who is working right now*: a **Today** column reading Working /
On break / Not started, with the arrival time and hours so far, and on the form a
**Work Days** tab where each day opens onto its segments — which is where *when
was he on a break* gets answered, since a pause carries its own start and end. A
list does not poll, so this is current as of opening the screen.

**Work Days** — every day for every worker, with *Still Running* and *On Break*
filters. This is where a manager closes a day someone forgot to end; nothing
auto-closes.

**Monthly Recap** — hours, tasks done, findings logged and critical findings per
worker, plus breakdowns by category and building. `get_recap_data()` re-checks
the Manager group itself: the menu is already restricted, but the method is
reachable by RPC regardless of which menu called it.

---

## 7. Create Workers

**Maintenance → Configuration → Create Workers.** The only door that produces
everything a maintenance worker needs in one step:

```
res.users  +  hr.employee  +  his.person (+ matricule)  +  Worker group  +  password
```

### The duplicate guard

Typing a name that already exists in the referential **stops the button**. The
line offers three columns:

| Column | Meaning |
|---|---|
| *Existing Person* | Attach to this identity. Nothing new is minted |
| *Referential* | The match found, with its matricule |
| *New Person* | Tick to assert this is a genuine namesake |

Without one or the other, the wizard refuses. This exists because
`hr.employee.create()` falls into `his_hr_base._create_his_person()` whenever
`person_id` is empty, minting a fresh identity and a fresh **lifetime**
matricule on every run — one human ended up with several records that way.

When an existing person is picked:

- their existing **contact** is reused — a second `res.users` would otherwise
  forge a second `res.partner`, which is the exact fork delegation exists to
  prevent;
- their existing **login** is reused if they have one — no second account, and
  no password is shown, because their password is theirs;
- the employee is created with `person_id` set, so `_create_his_person()` is
  skipped by `his_hr_base`'s own `if not employee.person_id` guard. **Nothing in
  the identity layer needed to change.**

An archived person is still *suggested* — that warning is the point — but cannot
be attached to. A person who already has an employee record is refused.

The name match reuses `his_person_core`'s own `normalize_text()`, so
`ABDO CHABOUTI`, `Abdo Chabouti` and `Chabouti Abdo` all resolve to one another.

> It deliberately does **not** call `his.person._find_or_flag_match()`. That
> method scores a rich import row: name weighs 0.40 against a 0.75 threshold, so
> given the two fields this wizard has it could never return a candidate — it
> would answer *"new"* for a name that matches somebody perfectly.

### Passwords

Type one, or leave the column blank and one is generated: 12 characters, with
`0 O o I l 1` excluded because these get read aloud and hand-copied.

`hr.employee.initial_password` stores it, carrying
`groups="maintenance_university.group_maintenance_manager"` — an **ORM-level**
restriction, so a Worker cannot read it even through a direct API call. Look it
up later in Worker Summary.

New accounts are forced to `ar_DZ`, not `ar_001`: Odoo's web client hardcodes
Arabic-Indic digits for `ar_001`, and dates would render with non-Latin numerals.

---

## 8. Security — read this before changing a rule

**Record rules attached to groups combine with `OR`, never `AND`.** A tighter
rule added next to a permissive one grants nothing back — it changes nothing at
all. Two consequences, both already paid for here:

1. **Core's own rules had to be switched off, not overridden.** A Worker who
   merely *followed* a request they were not assigned to could see it, because
   core's `base.group_user` rule OR'd with ours. Both core records are
   `noupdate="1"`, so an XML override is silently ignored — only a direct ORM
   write works. That is why `post_init_hook` deactivates
   `maintenance.equipment_request_rule_user` and
   `maintenance.equipment_rule_user`.

2. **A Reporter needs an explicit deny-all rule** on `maintenance.request`.
   Core's ACL grants every internal user full access to that model; without
   `[('id','=',False)]` a Reporter would inherit visibility into every request in
   the university.

**`ir.model.access` only ever grants.** It cannot restrict what another group
already allows — which is why create and unlink on `maintenance.request` are
enforced in Python, not in the ACL file. The same defence-in-depth shape repeats
on the finding model and on the dashboard method.

Record rules are deliberately **not** `noupdate`, so a corrected domain reaches
databases that already have the module installed.

---

## 9. Identity

This module owns **no** identity. It reads it.

- `matricule_institutionnel` on `hr.employee` is a stored `related` from
  `person_id`, owned by `his_person_core` and mirrored by `his_hr_base`. This
  module only displays it.
- `date_start_working` is defined **here** — it is HR data, unrelated to the
  identity model — but `his_hr_base` reads it to pick the matricule's year, so a
  hire entered late or signed for the autumn carries its real year.
- The module once had its own matricule sequence and uniqueness constraint. A
  group-wide identifier was being issued by a private counter inside a
  maintenance app, uncoordinated with the student matricules issued elsewhere.
  That is gone, and `tests/test_matricule_is_mirrored.py` asserts it never comes
  back.

---

## 10. Gotchas

- **Creating any employee makes them a maintenance Worker.** If the employee has
  a linked user and holds neither Worker nor Reporter, `hr_employee.create()`
  adds Worker — otherwise they would log in to a blank home screen. A cashier
  created through the Employees form is therefore also a maintenance worker
  until you remove the group.
- **A user created from Settings → Users is not an employee.** Nothing links
  `res.users` to `hr.employee` automatically. Use Create Workers, or core's
  **Create User** button on the employee form — it passes `partner_id`, so no
  second contact is made. The button needs `base.group_erp_manager` and appears
  only while `user_id` is empty.
- **At least one worker is required** before a request leaves *New* — except on
  the path straight to *Cancelled*.
- **Explicit `view_ids` on actions over shared models.** `maintenance.request`
  and `maintenance.university.finding` each carry more than one list/form pair,
  so default view resolution is ambiguous. Confirmed live: the kanban tab once
  silently rendered core's view, with none of our buttons on it.

---

## 11. Install and test

```bash
docker compose run --rm odoo odoo -d <db> -i maintenance_university --stop-after-init

docker compose run --rm odoo odoo -d <db> -u maintenance_university \
  --test-enable --test-tags /maintenance_university --stop-after-init
```

On Git Bash, prefix with `MSYS_NO_PATHCONV=1` or the `--test-tags` path is
mangled into a Windows path.

Python changes need `docker compose restart odoo`; view and data changes need
`-u`. A restart alone does not reload XML.

| Test file | Covers |
|---|---|
| `test_matricule_is_mirrored.py` | The matricule is read here, never issued |
| `test_worker_create.py` | The wizard's duplicate guard, contact and account reuse |
| `test_category_inverse.py` | The `maintenance_ids` inverse, and the crash without it |

**Depends on** `base`, `mail`, `hr`, `his_hr_base`, `maintenance`.
