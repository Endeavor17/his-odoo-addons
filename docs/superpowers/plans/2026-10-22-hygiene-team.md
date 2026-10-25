# Hygiene team Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the hygiene manager a monthly areas × days planning matrix, a phone screen for her workers (clock, areas done, findings), a monthly recap, and give maintenance requests/findings a room — all on the Patrimoine location tree.

**Architecture:** New module `his_hygiene` (planning, absences, hygiene findings, OWL screens) on top of `his_patrimoine` (places) and `maintenance_university` (day clock, repair findings). The clock is Abdo's `maintenance.university.workday`, given a team marker and two small hooks so hygiene can clock on behalf without loosening maintenance. Rooms on maintenance live in `his_patrimoine`.

**Tech Stack:** Odoo 19 Community, Python, OWL client actions, `odoo.tests.TransactionCase`.

**Spec:** `docs/superpowers/specs/2026-10-22-hygiene-team-design.md`

## Global Constraints

- UI strings in English source, French in `<module>/i18n/fr.po`; every msgid the module owns must be translated (test `his_access_base` `test_chaque_terme_a_sa_traduction_francaise`).
- Code comments in French, unaccented ASCII in Python files.
- Any new `hr.employee` field needs `groups=` (none planned: team membership is `his.hygiene.member`).
- No second list of rooms/buildings/people: places are `stock.location` under `his_patrimoine.loc_patrimoine`, people are `hr.employee`.
- Maintenance presence rule unchanged: a maintenance manager can never clock a worker.
- Non-working weekdays default Friday + Saturday: `ir.config_parameter` `his_hygiene.off_weekdays` = `"4,5"` (Python `date.weekday()`).
- Add `his_hygiene` to `MODULES` in `.github/workflows/ci.yml`.
- Lint like CI before every push: `ruff check .`, `ruff format --check .` (whole repo, includes `.md` blocks), `pylint --rcfile=.pylintrc <MODULES>`, `npx eslint .`, `python tools/verifier_polices.py`.
- Commits authored `Endeavor <mohamed.bounouaa@outlook.com>` with the `Co-Authored-By` trailer.

## Review Focus

1. A hygiene employee **with no user** clocked by the manager: start/pause/resume/end must all work, and `entered_by_id` is the manager → test in Task 4.
2. Changing building on a maintenance request after picking a room: the room must clear, never stay pointing into another building → test in Task 1.
3. `copy_previous_month` into a month with 31 vs 30 days, and onto a target off day → skipped, not crash → test in Task 5.
4. Marking a woman absent on a day she has areas: the cell reports `uncovered` until another member is added, and adding a member clears it → test in Task 5.
5. A hygiene worker calling the RPCs for another employee (`get_today(employee_id=<other>)`, `his_hygiene_clock(<other>)`) → refused → tests in Tasks 4 and 7.

## Test command

Local Postgres container `his-odoo-addons-db-1`; template DB `ci` (CI-like base, see `local-dev-tools` memory). Per run:

```bash
export MSYS_NO_PATHCONV=1
docker exec his-odoo-addons-db-1 psql -U odoo -d postgres -qc "DROP DATABASE IF EXISTS hyg" -c "CREATE DATABASE hyg TEMPLATE ci"
docker run --rm --network his-odoo-addons_default -e PYTHONDONTWRITEBYTECODE=1 \
  -v "C:/Users/Mohamed/his-hygiene-wt:/mnt/extra-addons" \
  -v "C:/Users/Mohamed/his-hygiene-wt/config/odoo.conf:/etc/odoo/odoo.conf:ro" \
  odoo:19.0 odoo -d hyg -i <MODS> -u <MODS> --test-enable --test-tags "<TAGS>" \
  --stop-after-init --http-port=8072 --log-level=test
```

Expected for a green run: no `FAIL:`/`ERROR:` lines, final `0 failed, 0 error(s)`.

---

### Task 1: Room on maintenance requests and findings (`his_patrimoine`)

**Files:**
- Create: `his_patrimoine/models/maintenance_room.py`, `his_patrimoine/views/maintenance_room_views.xml`
- Modify: `his_patrimoine/models/__init__.py`, `his_patrimoine/__manifest__.py` (version `19.0.1.1.0`, add view file), `his_patrimoine/i18n/fr.po`
- Test: `his_patrimoine/tests/test_maintenance_room.py` (+ `tests/__init__.py`)

**Interfaces:**
- Produces: `maintenance.request.his_room_id`, `maintenance.university.finding.his_room_id` — `Many2one("stock.location", string="Room")`, stored compute on `building_id` (`readonly=False`, `precompute=True`), cleared when not a descendant of `building_id.his_location_id`; related helper `his_building_location_id = building_id.his_location_id`.
- Produces: python constraint `_his_check_room_in_building` on both models (room must satisfy `room.parent_path.startswith(building.his_location_id.parent_path)` and differ from the building location itself).

- [ ] **Step 1: Write the failing tests**

```python
def test_la_salle_est_proposee_sous_le_batiment(self):
    req = self.env["maintenance.request"].create({"name": "Fuite", "building_id": self.bloc_a.id,
        "maintenance_category_id": self.cat.id, "his_room_id": self.salle_a1.id})
    self.assertEqual(req.his_room_id, self.salle_a1)

def test_changer_de_batiment_vide_la_salle(self):
    req = ...create(... his_room_id=self.salle_a1)
    req.building_id = self.bloc_b
    self.assertFalse(req.his_room_id)

def test_une_salle_d_un_autre_batiment_est_refusee(self):
    with self.assertRaises(ValidationError):
        ...create({"building_id": self.bloc_a.id, "his_room_id": self.salle_b1.id, ...})

def test_la_conversion_garde_la_salle(self):
    finding = Finding.create({"building_id": self.bloc_a.id, "his_room_id": self.salle_a1.id,
        "category_id": self.cat.id, "description": "Vitre cassee"})
    finding.action_submit(); finding.action_convert_to_request()
    self.assertEqual(finding.created_request_id.his_room_id, self.salle_a1)
```
Setup: two buildings via `maintenance.building.create` (their locations are auto-created), rooms = `stock.location.create({"name": "A1", "location_id": bloc_a.his_location_id.id})`, a non-inspection `maintenance.category`.

- [ ] **Step 2: Run, expect FAIL** (`his_room_id` unknown). Tags `/his_patrimoine`.
- [ ] **Step 3: Implement** both `_inherit`s in one file with a shared mixin-free helper function `_room_in_building(room, building) -> bool`; override `maintenance.university.finding.action_convert_to_request` to copy `his_room_id` onto `created_request_id` after `super()`.
- [ ] **Step 4: Views**: inherit `maintenance_university.view_maintenance_university_request_form`, `view_maintenance_university_finding_form`, `view_maintenance_university_report_form`: field `his_room_id` after `building_id`, `domain="[('id', 'child_of', his_building_location_id), ('id', '!=', his_building_location_id)]"`, `invisible="not building_id"`, same `readonly` as the building field it follows; add to request list after `building_id`.
- [ ] **Step 5: Run, expect PASS** (also `/maintenance_university` still green).
- [ ] **Step 6: Commit** `feat(patrimoine): salle sur les demandes et constats de maintenance`.

### Task 2: Team marker and hooks on the workday (`maintenance_university`)

**Files:**
- Modify: `maintenance_university/models/maintenance_university_workday.py`, `maintenance_university/security/maintenance_university_security.xml` (the two workday manager rules), `maintenance_university/__manifest__.py` (version `19.0.4.1.0`), `maintenance_university/i18n/fr.po`
- Test: `maintenance_university/tests/test_workday.py`

**Interfaces:**
- Produces: `his_team = fields.Selection([("maintenance", "Maintenance")], string="Team", required=True, default="maintenance", index=True)` on `maintenance.university.workday`.
- Produces: `_his_team_for(self, employee) -> str` (returns `"maintenance"`), `_start_day_for(self, employee) -> maintenance.university.workday` (current body of `action_start_day` minus `_my_employee()`, writes `his_team`), `_his_day_payload(self, day) -> dict` (the dict `get_my_day` returns after the employee lookup; `day` may be empty → `{"has_employee": True, "id": False, "state": False}`).
- `action_start_day()` becomes `return self._start_day_for(self._my_employee()).get_my_day()`; `get_my_day()` uses `_his_day_payload`. Public behaviour unchanged.
- Rules: `rule_maintenance_university_workday_manager_all` domain `[('his_team', '=', 'maintenance')]`; segment manager rule `[('workday_id.his_team', '=', 'maintenance')]`. Comment why (spec §6, team privacy).

- [ ] **Step 1: Failing tests** `test_une_journee_est_de_l_equipe_maintenance_par_defaut` (after `action_start_day`, `day.his_team == "maintenance"`) and `test_le_responsable_voit_les_journees_de_maintenance` (maintenance manager, after `invalidate_all()`, finds the day). The cross-team exclusion is tested in Task 4, where a second team exists.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** the field, the three helpers, the rule domains.
- [ ] **Step 4: Run `/maintenance_university`, expect all existing tests PASS** (the refactor must not change behaviour).
- [ ] **Step 5: Commit** `feat(maintenance): equipe sur la journee de travail, crochets pour l'hygiene`.

### Task 3: `his_hygiene` skeleton — roles, members, areas

**Files:**
- Create: `his_hygiene/__init__.py`, `__manifest__.py` (version `19.0.1.0.0`, depends `his_patrimoine`, `maintenance_university`, `hr`), `models/__init__.py`, `models/hygiene_member.py`, `models/hygiene_area.py`, `security/hygiene_security.xml`, `security/ir.model.access.csv`, `data/hygiene_data.xml` (ICP `his_hygiene.off_weekdays` = `4,5`, noupdate), `views/hygiene_config_views.xml`, `views/menus.xml`, `static/description/icon.svg`, `i18n/fr.po`, `README.md`
- Modify: `.github/workflows/ci.yml` (`MODULES` += `his_hygiene`)
- Test: `his_hygiene/tests/__init__.py`, `tests/common.py`, `tests/test_config.py`

**Interfaces:**
- Groups: `his_hygiene.group_hygiene_worker` (implies `base.group_user`), `his_hygiene.group_hygiene_manager` (implies worker; `user_ids` root + admin), own privilege + module category "Hygiene", same shape as maintenance's security file.
- `his.hygiene.member`: `employee_id` (M2o `hr.employee`, required, `ondelete="restrict"`, unique), `name` (related), `initials` (Char, stored compute from the first letters of the first two words of the name, upper, `readonly=False`), `color` (Integer 1–11, default = next unused), `sequence`, `active`. `@api.model _hygiene_members() -> recordset` (active, sudo).
- `his.hygiene.area`: `location_id` (M2o `stock.location`, required, unique, `ondelete="restrict"`), `building_id` (M2o `maintenance.building`, stored compute: the building whose `his_location_id` is the location or one of its ancestors), `name` (stored compute: `"<building> / <location path below the building>"`, or the building name), `sequence`, `active`. Constraint: `building_id` must be found ("An area must be a place under a building in Patrimoine.").
- `tests/common.py` → `class HygieneCase(TransactionCase)` with `setUpClass` creating: building `Bloc A` + locations `RDC`, `Amphi 1`; manager user (group manager) with employee; worker user Fatima (group worker) with employee; employee Karima **without user**; members for Fatima and Karima; areas for `RDC` and `Amphi 1`. Later tasks extend it.
- ACL: member/area read for worker, full for manager; `hr.employee` read for both hygiene groups (same as maintenance's `access_hr_employee_maintenance_worker`).
- Menus: root `menu_hygiene_root` "Hygiene" (groups worker); `Configuration` (manager) → `Team members`, `Areas`.

- [ ] **Step 1: Failing tests** `test_une_zone_hors_batiment_est_refusee` (location `WH/Stock` → `ValidationError`), `test_le_nom_de_zone_porte_le_batiment` (`"Bloc A / RDC"`), `test_un_salarie_n_est_membre_qu_une_fois` (second member same employee → `IntegrityError` via `mute_logger('odoo.sql_db')`), `test_initiales` (`"Fatima Zahra Benali"` → `"FZ"`).
- [ ] **Step 2: Run `-i his_hygiene` tags `/his_hygiene`, expect FAIL.**
- [ ] **Step 3: Implement** models, security, views (list editable for members with `color` widget `color_picker`; list for areas), menus, data, CI line.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat(hygiene): module, roles, equipe et zones`.

### Task 4: Hygiene clock on the shared workday

**Files:**
- Create: `his_hygiene/models/hygiene_workday.py`
- Modify: `his_hygiene/security/hygiene_security.xml` (4 rules), `security/ir.model.access.csv`
- Test: `his_hygiene/tests/test_clock.py`

**Interfaces:**
- Consumes: Task 2 `_his_team_for`, `_start_day_for`, `_his_day_payload`, `_check_is_owner`.
- `his_team` `selection_add=[("hygiene", "Hygiene")]`, `ondelete={"hygiene": "cascade"}`.
- `_his_team_for(employee)`: `"hygiene"` if `employee` is an active `his.hygiene.member`, else `super()`.
- `_check_is_owner()`: drop days with `his_team == "hygiene"` when caller has `group_hygiene_manager`, `super()` on the rest.
- `@api.model his_hygiene_clock(self, employee_id: int, action: str) -> dict` with `action in ("start", "pause", "resume", "end")`; checks `_his_hygiene_check_access(employee)` (member required; caller is `group_hygiene_manager` or `employee.user_id == env.user`, else `AccessError`); start → `_start_day_for(employee)`; else finds today's day (sudo) and calls `action_pause/action_resume/action_end_day`; returns `self._his_day_payload(day)`.
- `maintenance.university.workday.segment.entered_by_id` (M2o `res.users`, default `self.env.user`, readonly) and workday `ended_by_id` (set in an `action_end_day` override).
- Corrections: segment fields `corrected_by_id`, `original_date_start`, `original_date_end`; `write()` override: when `date_start`/`date_end` change on a closed segment, keep the first originals and set `corrected_by_id`. Recompute: `duration` already depends on the dates.
- Rules: workday + segment, manager `[('his_team','=','hygiene')]` / `[('workday_id.his_team','=','hygiene')]`; worker own (`employee_id.user_id = user.id`). ACL: worker read; manager read+write on workday and segment.
- Views: `views/hygiene_workday_views.xml` — manager menu `Work Days` (list of hygiene days: worker, date, state, worked, break, ended by; form with editable segment lines showing `entered_by_id`, `corrected_by_id`, originals). Action domain `[('his_team', '=', 'hygiene')]`.

- [ ] **Step 1: Failing tests**
  - `test_le_responsable_pointe_une_salariee_sans_compte`: manager `his_hygiene_clock(karima, "start")`, `pause`, `resume`, `end` → day state `done`, `his_team == "hygiene"`, every segment `entered_by_id == manager`.
  - `test_la_salariee_pointe_elle_meme`: Fatima `start` → `entered_by_id == fatima user`.
  - `test_une_salariee_ne_pointe_pas_une_autre` → `AccessError` for Fatima on Karima.
  - `test_le_responsable_maintenance_ne_pointe_pas_l_hygiene`: maintenance manager (group `maintenance_university.group_maintenance_manager` only) on a hygiene day `action_pause()` → `UserError`; and calling `his_hygiene_clock` → `AccessError`.
  - `test_le_responsable_hygiene_ne_pointe_pas_la_maintenance`: day of a maintenance worker, hygiene manager `action_pause()` → `UserError`.
  - `test_chaque_equipe_ne_voit_que_ses_journees`: after `invalidate_all()`, maintenance manager `search` excludes the hygiene day, hygiene manager excludes the maintenance day.
  - `test_une_correction_garde_l_heure_d_origine`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run `/his_hygiene,/maintenance_university`, expect PASS.**
- [ ] **Step 5: Commit** `feat(hygiene): pointage par la responsable, sans affaiblir la maintenance`.

### Task 5: Assignments, absences and the matrix RPC

**Files:**
- Create: `his_hygiene/models/hygiene_assignment.py`, `models/hygiene_absence.py`
- Modify: ACL csv, security xml (rules), `models/__init__.py`
- Test: `his_hygiene/tests/test_planning.py`

**Interfaces:**
- `his.hygiene.assignment`: `date` (required, index), `area_id` (required, `ondelete="restrict"`), `employee_ids` (M2m `hr.employee`, rel `his_hygiene_assignment_employee_rel`), `is_done`, `done_by_id` (res.users), `done_at` (Datetime), `finding_id` (M2o `his.hygiene.finding`, set for extra work, Task 6), `_planned_unique = models.UniqueIndex("(date, area_id) WHERE finding_id IS NULL")`. Constraint: all `employee_ids` are active members.
- `action_mark_done(self)` / `action_mark_undone(self)`: allowed to the manager or a user among `employee_ids.user_id`; writes sudo.
- `his.hygiene.absence`: `employee_id` (required), `date` (required), `reason` (Char); `UNIQUE(employee_id, date)`.
- `@api.model _hygiene_off_weekdays(self) -> set[int]` from the ICP.
- Manager-only `@api.model` RPCs (each starts with a `group_hygiene_manager` check → `AccessError`):
  - `get_matrix(year: int, month: int) -> dict`: `{"days": [{"date": "2026-11-01", "day": 1, "weekday": 6, "off": bool, "today": bool}], "areas": [{"id", "name", "building"}], "members": [{"id": employee_id, "name", "initials", "color"}], "cells": {"<area_id>|<date>": {"id", "employee_ids", "done", "extra": int, "uncovered": bool, "absent_ids": [...]}}, "absences": {"<employee_id>|<date>": reason or ""}}`.
  - `set_cell(area_id: int, date: str, employee_ids: list[int]) -> dict` (the cell; empty list on a not-done planned cell unlinks it; returns `{}`).
  - `fill_range(area_id: int, date_from: str, date_to: str, employee_ids: list[int]) -> int` (replace on each working day in range; returns count).
  - `copy_previous_month(year: int, month: int) -> int` (day N → day N; skip if target missing, off, already planned, area archived; drop non-member employees).
  - `toggle_absence(employee_id: int, date: str) -> bool` (new state).
- `uncovered` = working day, not done, and (`employee_ids` empty or every one absent that day).
- Rules: manager all; worker reads assignments where `employee_ids.user_id = user.id`; absences: manager all, worker own.

- [ ] **Step 1: Failing tests**
  - `test_une_case_peut_porter_deux_salariees` (`set_cell` with Fatima + Karima → cell `employee_ids` both).
  - `test_une_absence_decouvre_la_zone` (Karima only in cell, `toggle_absence(karima)` → `uncovered` True; `set_cell` adds Fatima → False).
  - `test_remplir_une_ligne_saute_les_jours_off` (Nov 2026: `fill_range` 1→7 = 5 cells, none on Fri 6 / Sat 7).
  - `test_copier_le_mois_precedent` (Oct 31 planned → Nov has no 31st, skipped; Oct 1 → Nov 1 copied; Nov off day skipped).
  - `test_une_salariee_coche_sa_zone` / `test_une_salariee_ne_coche_pas_la_zone_d_une_autre` (`AccessError`).
  - `test_seule_la_responsable_planifie` (Fatima `get_matrix` → `AccessError`).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat(hygiene): planning mensuel, absences et zones faites`.

### Task 6: Findings — repair to maintenance, cleaning to the manager

**Files:**
- Create: `his_hygiene/models/hygiene_finding.py`, `views/hygiene_finding_views.xml`
- Modify: `data/hygiene_data.xml` (category `category_reported_by_hygiene`, name "Reported by hygiene", `is_inspection` False, noupdate), ACL, rules, menus (`Findings`, manager)
- Test: `his_hygiene/tests/test_findings.py`

**Interfaces:**
- `his.hygiene.finding`: `area_id` (required), `date` (default today), `employee_id` (default: caller's employee via sudo search), `description` (Text, required), `image` (`fields.Image(max_width=1920, max_height=1920)`), `kind` (`[("repair", "Repair"), ("cleaning", "Cleaning")]`, required), `state` (`[("new", "New"), ("sent", "Sent to maintenance"), ("dispatched", "Dispatched")]`), `maintenance_finding_id`, `assignment_ids` (O2m on `finding_id`).
- `create()`: for `kind == "repair"` → `_his_send_to_maintenance()`: sudo create `maintenance.university.finding` with `building_id = area.building_id`, `his_room_id = area.location_id` unless it is the building location, `category_id = his_hygiene.category_reported_by_hygiene`, `description`, `severity="medium"`, `employee_id`, `state="submitted"`, photo as `ir.attachment` in `image_ids`; set `state="sent"`.
- `action_dispatch(self, date: str = None, employee_ids: list[int] = None) -> his.hygiene.assignment` (manager; cleaning only; default date today, default employees = that day's planned cell employees for the area) → `state="dispatched"`.
- Rules: manager all; worker own (`employee_id.user_id = user.id`). Worker ACL read+create.

- [ ] **Step 1: Failing tests** `test_une_panne_part_en_maintenance` (Fatima creates repair → maintenance finding submitted, room = `Amphi 1`, category = data record; Fatima has no access to `maintenance.request`), `test_un_salissure_revient_a_la_responsable` (cleaning → state new; `action_dispatch()` → assignment with `finding_id`, coexisting with the planned cell same day/area), `test_une_salariee_ne_dispatche_pas` (`AccessError`).
- [ ] **Step 2–4: FAIL → implement (list/form views, menu) → PASS.**
- [ ] **Step 5: Commit** `feat(hygiene): constats, panne vers la maintenance, salissure vers la responsable`.

### Task 7: Today, my month and the recap RPCs

**Files:**
- Create: `his_hygiene/models/hygiene_recap.py` (`AbstractModel his.hygiene.recap`)
- Test: `his_hygiene/tests/test_recap.py`

**Interfaces:**
- `get_today(employee_id: int = False) -> dict`: `{"employee": {"id", "name"}, "is_manager": bool, "members": [...] if manager, "day": _his_day_payload(...), "assignments": [{"id", "area", "done", "extra"}], "absent": bool}`. `employee_id` False → caller's employee; another employee → manager only (`AccessError`).
- `get_month(employee_id: int = False, month_offset: int = 0) -> dict`: `{"label", "days": [{"date", "areas": [names], "done": int, "absent": bool, "worked_hours": float|None}], "totals": {"days_worked", "days_absent", "worked_hours", "areas_done", "areas_planned"}}`. Same access rule.
- `get_recap(month_offset: int = 0) -> dict` (manager only): `{"label", "workers": [{"employee_id", "name", "days_worked", "days_absent", "worked_hours", "break_hours", "unclocked_days", "areas_done", "areas_planned", "findings"}], "areas": [{"id", "name", "planned", "done", "uncovered"}], "fairness": {"areas": [names], "rows": [{"name", "counts": [int]}]}}`.
- Definitions (spec §6, §9): a worked day = a date ≤ today where the employee is on a non-extra or extra assignment and not absent; hours/break from hygiene workdays only; `unclocked_days` = worked days with no workday; `planned` = assignments with `finding_id` empty; `uncovered` = planned past days not done whose employees were all absent.

- [ ] **Step 1: Failing tests** `test_un_jour_planifie_sans_pointage_compte` (Karima planned 2 days, no clock → `days_worked == 2`, `worked_hours == 0`, `unclocked_days == 2`), `test_un_jour_d_absence_ne_compte_pas`, `test_l_equite_compte_les_jours_par_zone`, `test_une_salariee_ne_lit_pas_le_mois_d_une_autre` (`AccessError`).
- [ ] **Step 2–4: FAIL → implement → PASS.**
- [ ] **Step 5: Commit** `feat(hygiene): journee, mois et recapitulatif`.

### Task 8: Planning matrix screen (OWL)

**Files:**
- Create: `his_hygiene/static/src/planning/planning.{js,xml,scss}`, `views/hygiene_actions.xml` (client action tag `his_hygiene_planning`), menu `Planning` (manager, sequence 10)
- Modify: `__manifest__.py` assets (`web.assets_backend`: `his_hygiene/static/src/**/*`)

**Interfaces:** Consumes Task 5 RPCs only.

Behaviour (spec §5): month navigation; sticky first column (areas grouped by building) and header (day + weekday initial, off days shaded, today outlined); a palette of members (colour + initials) — click a member to select her as the "brush", then click a cell to toggle her in/out, shift-click a second cell on the same row to `fill_range`; cell shows initials on the member colour (several = split), done = check mark, uncovered = red border, extra = `+n` badge; an **Absences** block under the matrix, one row per member, click toggles `toggle_absence`; button "Copy previous month" (confirmation through Odoo's `ConfirmationDialog`, never `window.confirm`).

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Verify by rendering** on the `hyg` DB with seeded data (10 areas, 8 members, a month filled): screenshot desktop width, check every behaviour above by clicking, console free of errors.
- [ ] **Step 3: Commit** `feat(hygiene): matrice de planning mensuelle`.

### Task 9: Phone screen "My Day" (OWL)

**Files:**
- Create: `his_hygiene/static/src/my_day/my_day.{js,xml,scss}`, client action `his_hygiene_my_day`, menu `My Day` (worker, sequence 5; first menu so the app opens on it)

**Interfaces:** Consumes Task 4 `his_hygiene_clock`, Task 5 `action_mark_done/undone`, Task 6 `his.hygiene.finding` create, Task 7 `get_today`, `get_month`.

Behaviour (spec §7): one big clock button at a time + ticking worked time; area cards with big **Done**; **Report a problem** opens a small dialog (kind as two big buttons, text, photo via `<input type="file" accept="image/*" capture="environment">`); tab **My month**; for a manager, a member picker on top (same screen for whoever is picked).

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Verify by rendering** at 390 px width as Fatima and as the manager picking Karima: clock round-trip, done, report with photo, month tab.
- [ ] **Step 3: Commit** `feat(hygiene): ecran telephone Ma journee`.

### Task 10: Recap screen (OWL)

**Files:**
- Create: `his_hygiene/static/src/recap/recap.{js,xml,scss}`, client action `his_hygiene_recap`, menu `Monthly Recap` (manager)

Behaviour: month arrows; workers table, areas table, fairness table (Task 7 payload); unclocked days shown next to hours.

- [ ] **Step 1: Implement. Step 2: Verify by rendering. Step 3: Commit** `feat(hygiene): recapitulatif mensuel`.

### Task 11: Translations, lint, full run

- [ ] **Step 1:** export `fr` for `his_hygiene`, `his_patrimoine`, `maintenance_university` on a DB with the CI module set; fill every msgid; check `git diff` lost no msgid.
- [ ] **Step 2:** run the whole CI lint set (Global Constraints).
- [ ] **Step 3:** run tests `/his_access_base,/his_hygiene,/his_patrimoine,/maintenance_university,/his_stock_mdm` on a fresh copy of `ci`; expect 0 failed.
- [ ] **Step 4:** README of `his_hygiene` (what it does, roles to put on positions, setup: members, areas, Campus building); commit `docs(hygiene): traductions et mode d'emploi`.
