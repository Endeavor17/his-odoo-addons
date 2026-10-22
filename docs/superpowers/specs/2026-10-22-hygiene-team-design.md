# Hygiene team planning, and rooms in maintenance

Date: 2026-10-22. Source: a design conversation with Mohamed about a request
from the hygiene (cleaning) team's manager. Builds on
`2026-10-20-investment-purchases-and-fixed-assets-design.md` (`his_patrimoine`,
rooms as stock locations) and on Abdo's `maintenance_university`.

## 1. Why

The hygiene team is all women. Most of them cannot use an information system
properly, so today their manager carries the team's whole administration in
her head. Each month she decides who cleans which area on which day. She has
no rule for it: she rotates people herself so that everyone stays satisfied.
When a woman is absent, another one takes her areas.

She wants what the maintenance team already has, adapted to cleaning:

- a monthly plan, published at the start of the month, assigning workers to
  areas day by day;
- the start, break and end of each working day;
- each area ticked done once it is cleaned;
- findings ("something is broken", "water spilled here");
- a monthly recap per worker and per area, and a way for each worker to see
  her own work.

Some of the women can use their phone; for the others the manager enters
everything on their behalf.

While we are at it, Mohamed wants **maintenance to work at room level too**
(today a maintenance request only knows its building). Rooms must stay a
single master list: one place where they are created, used by every team.

## 2. Goals, non-goals, anti-goals

Goals
- A **planning matrix**: rows are areas, columns are every day of the month,
  each cell holds the worker(s) assigned. The manager fills it freely.
- **Day clock** (start / break / resume / end) for hygiene workers, entered by
  the worker herself on her phone, or by the manager for her.
- **Area done**: one tick per area per day, by any worker assigned to it or by
  the manager.
- **Absences** recorded, and their areas visibly uncovered until reassigned.
- **Findings** of two kinds: *repair* (goes to maintenance) and *cleaning*
  (goes back to the hygiene manager as extra work).
- **Monthly recap** for the manager; **own view** for each worker.
- **Rooms in maintenance**: requests and findings get an optional room.

Non-goals (decided)
- No rotation rules, no automatic scheduling, no "suggest a replacement". The
  manager's judgement is the rule; the system records it.
- No link to HR leave (Time Off), no payroll.
- No second list of rooms, areas, buildings or people.

Anti-goals (this would be a failure even if it works)
- A planning screen slower to fill than her paper. The matrix is the product:
  if assigning 30 days × N areas is tedious, nothing else matters.
- A phone screen a non-technical worker cannot use without help: small
  buttons, menus, Odoo forms.
- Weakening maintenance's presence rule ("a leader who can clock someone in
  has defeated the point of a presence record") for the maintenance team.

## 3. Who uses it

| Role | Who | Does |
|---|---|---|
| **Hygiene Manager** | the team's manager | Plans the month, marks absences and replacements, clocks in/out for her team, ticks areas, logs and dispatches findings, reads the recap. |
| **Hygiene Worker** | women who can use their phone | Sees her plan, clocks her own day, ticks her areas done, logs findings, sees her own month. Sees nobody else's data. |
| (no account) | women who cannot use the system | Exist as `hr.employee` (from the identity referential) with no user. The manager does everything for them. |

Both roles are `res.groups`, granted through the job position like every
other role in the project (`his_access_base`, `hr.job.group_ids`): HR sets the
roles on the "Hygiene manager" and "Hygiene agent" positions, not by hand.

**Team membership is not a user group**: the women without an account have no
user, so "who is in the hygiene team" must be readable from the employee
record. The builder chooses how (a department, the job position, or an
explicit team list); it must be the same thing the manager's matrix, the
clock permission and the recap all read. *Builder's call, but it must cover
employees with no user.*

## 4. Places: one master list

Rooms and areas are `stock.location` records under each building's
Patrimoine location, `WH/Patrimoine/<building>/...`, exactly as
`his_patrimoine` already defines (`maintenance.building.his_location_id`).

- **Cleaning areas that are not rooms** (corridors, staircases, toilets,
  courtyards, a whole floor) are created in the same tree. There is no
  hygiene-specific area model holding names.
- An area may be a room or a parent of rooms (e.g. "Bloc A / Ground floor"
  with rooms beneath). Any descendant of a building's location is a valid
  area or room.
- Which locations appear as rows of the hygiene matrix is a hygiene setting
  (the manager picks the areas her team covers, and their order). That
  selection is hygiene data; the place itself is not.
- Archiving a location in Patrimoine removes it from every new planning, but
  history keeps pointing at it.
- **Outdoor areas** (courtyards, parking, paths) live under a building named
  "Campus" (my call): a normal `maintenance.building`, so maintenance can file
  outdoor repairs there too. No site-level exception to the rule above.

Known side effect, accepted: `his_patrimoine` gives every location under
Patrimoine a yearly count frequency, so corridors join the annual count with
nothing in them. Harmless; the builder may exclude locations with no
Patrimoine item if it is cheap.

### 4.1 Rooms in maintenance

- `maintenance.request` and `maintenance.university.finding` get an optional
  **Room** field: a location under the chosen building's Patrimoine location.
  Changing the building clears a room that no longer belongs to it.
- A finding converted to a request carries its room over.
- This lives in **`his_patrimoine`** (which already depends on
  `maintenance_university` and `stock`), not in `maintenance_university`, so
  maintenance keeps working without stock installed. Abdo's module is not
  modified for this.
- The maintenance recap's "by building" breakdown is unchanged; a "by room"
  view is not required.

## 5. Planning matrix (the core screen)

Chosen by Mohamed from mockups: **areas × every day of the month**, one
colour per worker, her initial(s) in the cell. "Matrix A is great as long as
we work on its design properly."

Behaviour
- One screen per month, with previous/next month navigation.
- Rows: the areas the team covers (§4), grouped by building.
- Columns: every day of the month; non-working days are shaded. Which days
  are non-working is configurable (default Friday and Saturday — *builder's
  guess, confirm with Mohamed*).
- A cell holds **zero, one or several workers**. A worker may appear in
  several cells on the same day.
- Fast filling is a requirement, not a nicety: assigning a worker to a cell
  must take one or two clicks, and the manager needs a way to fill a row or a
  range of days at once and to copy the previous month or week as a starting
  point.
- Absent worker on that day: her cells show as absent (struck/red), and the
  area is flagged **uncovered** until another worker is added. A replacement
  is visibly a replacement.
- **An absence is a whole day** (my call). A woman who leaves at 11:00 is not
  absent; the manager simply adds another worker to the areas left.
- Size (Mohamed): **fewer than 10 workers**, so one colour and one initial
  per worker holds; no virtualised rendering needed.
- Done areas are visibly done; past days that were not done are visibly
  missed.
- The manager can change any cell at any time, including today and past days
  (correcting the record).
- Publishing: the plan is visible to the workers as soon as it is saved; no
  separate publish step is required.

The underlying data is one record per **(day, area)** with its workers, a
done state, who ticked it and when. Exact model shape is the builder's.

This screen will need a design iteration with Mohamed before it is final
(mockups were rough). Expect a custom OWL view; Odoo's standard views do not
give this grid.

## 6. The working day

**Reuse `maintenance.university.workday`** and its segments (start, break,
resume, end, worked hours, break hours). Do not build a second clock.

The presence rule splits by team (decided by Mohamed):
- **Maintenance**: unchanged. Only the worker clocks herself; managers are
  refused server-side.
- **Hygiene**: the Hygiene Manager may start, pause, resume and end the day
  of any member of the hygiene team, including employees without a user. Every
  segment and day records **who entered it** (the worker herself or the
  manager), shown in the day's details and the recap.

Today `_my_employee()`, `_check_is_owner()` and the four actions assume "the
current user's own employee". The hygiene path needs variants that take an
employee and check "the caller is a Hygiene Manager and the employee is in the
hygiene team". How that is done (override in the hygiene module, or a small
hook added to the maintenance model) is the builder's call; it must not
loosen the maintenance path, and must be proven by a test that a maintenance
manager is still refused.

Corrections: the manager can fix a wrong time for her team (forgotten "end
day"). The original value stays traceable (chatter or an audit field).

**Clocking is optional (decided by Mohamed).** A day that is planned for a
worker and not marked absent **counts as a worked day**, whether or not
anyone clocked it. The manager is never required to tap start / break / end
for the women without an account; she may, when she wants hours. So the
recap counts **days from the plan** and **hours only from clocked days**, and
shows how many days had no clock, so a low hour total is not misread.

**Team privacy (my call).** Reusing the workday model must not show hygiene
presence to maintenance managers, nor maintenance presence to hygiene
managers. The workday carries its team, and the current "manager sees all"
rule in `maintenance_university` is narrowed to the maintenance team. This is
the one accepted change of behaviour in Abdo's module.

## 7. Worker phone screen

Mobile first: her own phone, in the browser.

- Top: the day clock — one big button at a time (*Start my day* / *Break* /
  *Resume* / *End my day*), with today's worked time ticking.
- Below: today's areas, each a large card with **Done**, and a **Report a
  problem** button.
- A tab or link to **my month**: her planned days and areas, done ticks,
  days worked, hours, absences.
- Nothing else in her menu.

The manager has the same "today" view for any worker of her team (pick the
worker, then the same big buttons), so entering on behalf of someone is the
same gesture.

## 8. Findings

From an area card (worker) or from the matrix (manager): a short text, an
optional photo, and a kind.

- **Repair** → a `maintenance.university.finding` (submitted), building and
  room pre-filled from the area, category a fixed **"Reported by hygiene"**
  maintenance category and default severity (my call: the worker never picks
  a category; the maintenance leader re-sorts before converting). That
  category must not be the inspection one. The maintenance leader converts it
  as today.
  The hygiene user needs just enough rights to create and submit it, not to
  see the maintenance pipeline.
- **Cleaning** → a hygiene finding sent to the Hygiene Manager. One click
  turns it into an extra assignment (area, day — today by default, workers).

The hygiene manager sees both kinds logged by her team.

## 9. Monthly recap (manager only)

Month navigation like the maintenance recap.

Per worker: days worked (from the plan, §6), days absent, worked and break
hours (clocked days only, with the count of unclocked days), areas done vs
planned, findings logged.

Per area: days planned, days done, days left uncovered.

Fairness table: workers × areas, number of days each woman spent in each
area that month (the mockup Mohamed saw as option B, as a recap not as the
planning tool).

## 10. Language and interface rules

House rule (`his-ui-langue-et-police`): English source strings, French in
`i18n/fr.po`, the single project font. Code comments in French, unaccented
ASCII in Python.

Any new field on `hr.employee` must carry `groups=` unless it belongs on the
public profile (the pos_hr blank-till trap).

## 11. Modules

- **New `his_hygiene`**: planning, assignments, absences, hygiene findings,
  phone screen, recap, the two roles. Depends on `his_patrimoine` (places) and
  `maintenance_university` (clock, repair findings).
- **`his_patrimoine`**: room on maintenance requests and findings (§4.1).
- **`maintenance_university`**: a team marker on the workday, the manager rule
  narrowed to the maintenance team (§6), and at most a small hook for the
  on-behalf clock. No other behaviour change for maintenance; a test proves a
  maintenance manager is still refused when clocking a worker.
- Add `his_hygiene` to the CI module list.

## 12. Left to the builder

- Data model shapes (assignment, absence, area selection, hygiene finding).
- How team membership is stored (§3), within the constraint given.
- How the hygiene clock reuses the workday model (§6).
- The matrix widget's implementation and bulk-fill gestures (§5), to be
  validated with Mohamed on a rendered screen.

## 13. Open with Mohamed

- Non-working days of the week (default Friday + Saturday assumed).
- Whether the maintenance recap should later gain a "by room" view.
