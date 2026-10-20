# Usual vs Investment Purchases + Fixed Assets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Purchasing officer classifies requests as Usual (he finishes alone) or Investment (director approves up front, +20 % ceiling on orders); durable items tracked per serial in rooms and counted yearly.

**Architecture:** Part A amends `his_purchase` in place: `his_purchase_domain` (pos/general) becomes `his_purchase_type` (usual/investment), no longer derived from the department, with a migration. Part B is a new module `his_patrimoine` on top of `his_stock_mdm` and `maintenance_university`, using standard serial tracking, locations, putaway, `lot_sequence_id` and `cyclic_inventory_frequency` — no custom count UI.

**Tech Stack:** Odoo 19 Community, Python 3.12, `odoo.tests` (`TransactionCase`, `Form`).

**Spec:** `docs/superpowers/specs/2026-10-20-investment-purchases-and-fixed-assets-design.md`

## Global Constraints

- Source strings in ENGLISH, French in each module's `i18n/fr.po` (repo rule 2026-10-08).
- Roles go to positions, never set by hand in data.
- Officer may change the type freely until the director approves; after that only the director (`his_purchase.group_purchase_director`) can.
- Ceiling: `INVESTMENT_MARGIN = 0.20` constant in `purchase_order.py`, not a setting.
- Estimates are excluding tax; compare with order lines' `price_subtotal` (untaxed).
- `po_double_validation_amount` stays 0.
- The director never gets an activity for a usual purchase.
- Réforme, depreciation, class 2 accounts: NOT built. Patrimoine bills keep the default expense account.
- Comments in code follow the module's existing French-comment style.

## Test command

Local runner (see memory `local-dev-tools` / CI job): Odoo image `odoo:19.0`, worktree mounted, stop `his-odoo-addons-odoo-1` first, `MSYS_NO_PATHCONV=1`, `--http-port=8072`. Below, `RUN_TESTS <tags>` means:

```
-u <modules> --test-enable --test-tags <tags> --stop-after-init --http-port=8072
```
on a CI-like base (`l10n_dz,point_of_sale` installed + `tools/seed_categories.py`).

## Review Focus

1. Officer relabels a director-approved investment to usual via the **order** form (not the request) → must be refused; the order type is forced by its requests.
2. Investment request split into two orders each under +20 % but together over → second one needs the director.
3. Draft RFQs/alternatives (3 quotes) must not count against the ceiling — only orders in `to approve`, `purchase`, `done`.
4. A requester saving a new request through the form (`Form`, not ORM) with the type field absent/empty → saves (lesson of 2026-10-19).
5. A room created by hand under a building location gets the yearly count frequency; a patrimoine item in a room is never in `WH/Stock` availability.

Each line has its test in the owning task (marked RF1..RF5).

---

## Part A — `his_purchase`

### Task 1: Rename the field to Purchase Type, migrate, drop the department field

**Files:**
- Modify: `his_purchase/models/hr_department.py` (delete the field; move the selection constant to `his_purchase_request.py` as `PURCHASE_TYPES`; if the file becomes empty, delete it and its import in `models/__init__.py`)
- Modify: `his_purchase/models/his_purchase_request.py`, `purchase_order.py`, `purchase_requisition.py`, `wizard/his_purchase_request_source.py`, `wizard/purchase_requisition_create_alternative.py`
- Modify: views `his_purchase_request_views.xml:57`, `purchase_order_views.xml:10`, `purchase_requisition_views.xml:9`; delete `hr_department_views.xml` and its manifest entry
- Create: `his_purchase/migrations/19.0.2.0.0/pre-migration.py`, `post-migration.py`
- Modify: `his_purchase/__manifest__.py` version → `19.0.2.0.0`
- Modify tests: `tests/common.py` (departments without the field), `test_request.py`, `test_order.py`, `test_monthly.py`

**Interfaces:**
- Produces: `PURCHASE_TYPES = [("usual", "Usual Purchase"), ("investment", "Investment")]` in `his_purchase_request.py`; field `his_purchase_type` (string "Purchase Type", tracking) on `his.purchase.request`, `purchase.order`, `purchase.requisition`. On the request: plain stored field, **no compute, not required, empty by default**, still in `PROTECTED_FIELDS` and in `_his_drop_form_defaults`. On the order: same compute as today (source → its type, else keep, else `"usual"`). On the agreement: default `"usual"`, required.

- [ ] **Step 1: Write the failing tests** in `test_request.py` / `test_order.py` (replace the domain tests at `test_request.py:19,98-148`, `test_order.py:18,103,213-229,268`, `test_monthly.py:24,72`):

```python
def test_new_request_has_no_type(self):
    self.assertFalse(self._request().his_purchase_type)


def test_department_has_no_purchase_field(self):
    self.assertNotIn("his_purchase_domain", self.env["hr.department"]._fields)


def test_order_takes_request_type(self):  # from a request typed investment
    request = self._approved_request(purchase_type="investment")
    self.assertEqual(self._source_rfq(request, self.supplier_a).his_purchase_type, "investment")


def test_agreement_type_wins_and_defaults_usual(self): ...  # adapt test_order.py:213-222
```
`_approved_request` gains `purchase_type="usual"`; it is wired in Task 2 — until then the helper writes the type as `self.officer` then approves as today.

- [ ] **Step 2: Run, verify FAIL** — `RUN_TESTS /his_purchase` → errors on `his_purchase_type`.

- [ ] **Step 3: Implement the rename** everywhere listed; delete `_compute_his_purchase_domain` on the request and the department dependency.

- [ ] **Step 4: Migration.** `pre-migration.py`: for tables `his_purchase_request`, `purchase_order`, `purchase_requisition`: `ALTER TABLE … RENAME COLUMN his_purchase_domain TO his_purchase_type`, then `UPDATE … SET his_purchase_type = CASE his_purchase_type WHEN 'pos' THEN 'usual' WHEN 'general' THEN 'investment' END`. Guard each with a column-exists check (`openupgradelib` is not available; use `information_schema.columns`). Leave `hr_department.his_purchase_domain` column in place (Odoo drops field metadata itself). `post-migration.py` is written in Task 2 (needs `his_approved_amount`).

- [ ] **Step 5: Run, verify PASS** — `RUN_TESTS /his_purchase`; all pre-existing approval tests still pass with `pos`→`usual`, `general`→`investment` substitutions.

- [ ] **Step 6: Commit** `feat(his_purchase): purchase type usual/investment replaces the department domain`

### Task 2: Request goes to the officer; investment goes to the director with an approved amount

**Files:**
- Modify: `his_purchase/models/his_purchase_request.py` (`_compute_approver_id`, `_his_check_approver`, `action_approve`, line field label)
- Modify: `his_purchase/security/his_purchase_security.xml` (comment + `comment` field of `group_requester`: no department-head approval any more)
- Modify: `his_purchase/views/his_purchase_request_views.xml` (type editable `readonly="state not in ('submitted', 'approved')"`; `his_approved_amount` shown when set; search filter "To Approve by Me": `[('approver_id', '=', uid), ('state', '=', 'submitted')]`)
- Modify: `his_purchase/migrations/19.0.2.0.0/post-migration.py`
- Test: `his_purchase/tests/test_request.py`, `tests/common.py`

**Interfaces:**
- Consumes: `his_purchase_type` (Task 1).
- Produces: `his.purchase.request.his_approved_amount` (Monetary, readonly, copy=False, tracking) = `estimated_amount` when the director approves an investment, else 0; `his.purchase.request._his_director_approved() -> bool` = `his_purchase_type == "investment" and state not in ("draft", "submitted", "cancel")`.
  `common._approved_request(purchase_type="usual", **kw)`: submit as requester, set type as officer, approve as officer (usual) or director (investment).

- [ ] **Step 1: Failing tests**

```python
def test_submitted_request_goes_to_officer(self):
    request = self._request(); request.action_submit()
    self.assertEqual(request.approver_id, self.officer)

def test_approve_refused_without_type(self):  # UserError "Set the purchase type"
def test_officer_approves_usual(self):  # state approved, director not subscribed, no activity for director
def test_investment_needs_director(self):
    request = self._request(); request.action_submit()
    request.with_user(self.officer).his_purchase_type = "investment"
    self.assertEqual(request.approver_id, self.director)
    with self.assertRaises(AccessError):
        request.with_user(self.officer).action_approve()
    request.with_user(self.director).action_approve()
    self.assertEqual(request.his_approved_amount, 18000)  # 2 x 9000
def test_department_head_no_longer_approves(self):  # self.head -> AccessError
def test_requester_form_save_without_type(self):  # RF4: Form(... .with_user(self.requester)) save OK, type False
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement.** `_compute_approver_id` depends on `his_purchase_type`, `company_id.his_purchase_director_id`, `company_id.his_purchase_manager_id`: investment → director; otherwise → `company.his_purchase_officer_id or company.his_purchase_manager_id` (officer is computed non-stored: do not put it in `@api.depends`; `action_submit` re-triggers with `request._compute_approver_id()` before its approver check). `_his_check_approver`: investment → director group or su; otherwise → `_his_is_purchasing()` or director group. `action_approve`: raise `UserError(_("Set the purchase type of %s first.", name))` when empty; on investment write `his_approved_amount = estimated_amount`. Line field `estimated_price_unit` string → `"Estimated Unit Price (excl. tax)"`.

- [ ] **Step 4: `post-migration.py`**: `UPDATE his_purchase_request SET his_approved_amount = estimated_amount WHERE his_purchase_type = 'investment' AND state IN ('approved','sourcing','ordered','done')`; recompute `approver_id` for `state = 'submitted'` via ORM (`env["his.purchase.request"].search([("state","=","submitted")])._compute_approver_id()`).

- [ ] **Step 5: Run, verify PASS** (whole `/his_purchase`; fix tests that approved as `self.head`).

- [ ] **Step 6: Commit** `feat(his_purchase): officer triages requests, director approves investments up front`

### Task 3: Lock the type once the director approved

**Files:**
- Modify: `his_purchase/models/his_purchase_request.py` (`write`), `his_purchase/models/purchase_order.py` (`_compute_his_purchase_type`, `write`)
- Test: `his_purchase/tests/test_order.py`, `test_request.py`

**Interfaces:**
- Consumes: `_his_director_approved()` (Task 2), `purchase.order._his_requests()` (exists, `purchase_order.py:143`).
- Produces: `purchase.order._his_type_locked() -> bool` = `any(r._his_director_approved() for r in self._his_requests())`.

- [ ] **Step 1: Failing tests**

```python
def test_officer_cannot_relabel_approved_investment_request(self):  # UserError
def test_director_can_relabel_approved_investment(self):
def test_officer_cannot_relabel_order_of_approved_investment(self):  # RF1, order.with_user(officer).his_purchase_type = "usual" -> UserError
def test_agreement_usual_does_not_downgrade_locked_order(self):  # order from a usual agreement serving an approved investment request stays investment
def test_officer_can_relabel_before_director(self):  # submitted investment -> usual OK
```

- [ ] **Step 2: Run, verify FAIL.**
- [ ] **Step 3: Implement.** Request `write`: if `his_purchase_type` in vals and differs, and `_his_director_approved()`, and user not director/su → `UserError(_("%s was approved by the director as an investment: only the director can change its type.", name))`. Order compute: `"investment"` when `_his_type_locked()`, else today's rule; add `order_line.his_request_line_id` to `@api.depends`. Order `write`: same refusal when `_his_type_locked()` and the new value is not investment.
- [ ] **Step 4: Run, verify PASS.**
- [ ] **Step 5: Commit** `feat(his_purchase): director-approved investments keep their type`

### Task 4: Order approval with the +20 % ceiling

**Files:**
- Modify: `his_purchase/models/purchase_order.py:281-318` (`_his_approver_group` replaced, `_approval_allowed`, message in `button_approve`)
- Test: `his_purchase/tests/test_order.py`

**Interfaces:**
- Consumes: `his_approved_amount`, `_his_requests()`.
- Produces: `INVESTMENT_MARGIN = 0.20`; `purchase.order._his_director_reason() -> str | None` (`None` = purchase manager group may approve); used by Task 5.

Rule (`ensure_one`): usual → `None`. Investment: no served request, or a served request with `his_approved_amount == 0` → reason "no amount approved by the director". Else for each served request: `committed` = sum of `price_subtotal` of purchase lines linked to that request's lines (`his_request_line_id.request_id == request`), over orders in `("to approve", "purchase", "done")` **including self**; lines of self without `his_request_line_id` count for `self.his_request_id`. If `committed > approved * (1 + INVESTMENT_MARGIN)` (currency-rounded compare) → reason `_("%(order)s is more than 20%% above the amount the director approved: %(approved)s approved, %(ordered)s ordered.")` with formatted amounts.

- [ ] **Step 1: Failing tests** (request estimate 2 x 9000 = 18000, approved by director):

```python
def test_investment_order_within_20_percent_officer_approves(self):  # quoted 2 x 10800 = 21600 -> manager approves
def test_investment_order_over_20_percent_needs_director(self):  # 2 x 10801 -> manager UserError mentioning "20%", director OK
def test_split_orders_cannot_bypass_ceiling(self):  # RF2: two orders 1 x 10800 + 1 x 10801 (second over cumulative 21600)
def test_draft_alternatives_do_not_count(self):  # RF3: 3 RFQs drafted, confirm the cheapest -> manager approves
def test_investment_order_without_request_needs_director(self):
def test_usual_order_manager_approves(self):
```

- [ ] **Step 2: Run, verify FAIL.**
- [ ] **Step 3: Implement** `_approval_allowed`: keep threshold logic, then `return user.has_group("his_purchase.group_purchase_director") if self._his_director_reason() else user.has_group("purchase.group_purchase_manager")`. `button_approve` raises the reason text (or "can only be approved by a purchase manager or the executive director" for usual).
- [ ] **Step 4: Run, verify PASS.**
- [ ] **Step 5: Commit** `feat(his_purchase): investment orders over +20% go back to the director`

### Task 5: Reminders follow the type

**Files:**
- Modify: `his_purchase/models/his_purchase_request.py:459-481`, `his_purchase/models/purchase_order.py` `_his_step` (`"to approve"` branch, ~line 350)
- Test: `his_purchase/tests/test_followup.py`

**Interfaces:** Consumes `_his_director_reason()` (Task 4).

Request `submitted`: owner `approver_id`; chain usual/empty → `[(DAYS_TO_ESCALATE, manager - owner)]`, investment → `[]`. Request `approved`: chain `[(DAYS_TO_ESCALATE, manager - owner)]` plus the director step **only if investment**. Order `to approve`: `_his_director_reason()` → owner director, chain `[]`; else owner `manager or officer`, chain `[]`.

- [ ] **Step 1: Failing tests** in `test_followup.py`, using the existing late-step helpers there:
```python
def test_usual_request_never_escalates_to_director(self):  # run followup past every delay; no activity with user_id == director
def test_usual_order_never_reaches_director(self):
def test_investment_order_over_ceiling_assigned_to_director(self):
```
- [ ] **Step 2: Run, verify FAIL.** **Step 3: Implement.** **Step 4: Run whole `/his_purchase`, verify PASS.**
- [ ] **Step 5: Commit** `feat(his_purchase): reminders never send usual purchases to the director`

### Task 6: French, README, help texts

**Files:** `his_purchase/i18n/fr.po`, `his_purchase/README*` or module description, `__manifest__.py` description; `docs/superpowers/specs/2026-10-15-purchasing-design.md` gets a one-line pointer to the 2026-10-20 spec at the top.

- [ ] **Step 1:** Export the new/changed terms (`--i18n-export` or edit by hand) and translate: "Purchase Type" → "Type d'achat", "Usual Purchase" → "Achat courant", "Investment" → "Investissement", "Approved Amount" → "Montant approuvé", "To Approve by Me" → "À approuver par moi", the new error messages. Remove entries of deleted strings.
- [ ] **Step 2:** Run `RUN_TESTS /his_purchase` with `--load-language=fr_FR` on the base and open the request form in French — no English label left for the new fields (screenshot it, memory `verify-ui-by-rendering`).
- [ ] **Step 3: Commit** `docs(his_purchase): French terms and README for usual/investment`

## Part B — `his_patrimoine`

### Task 7: Module, categories, serial numbering, product guard

**Files:**
- Create: `his_patrimoine/__init__.py`, `__manifest__.py` (version `19.0.1.0.0`, depends `stock`, `his_stock_mdm`, `maintenance_university`, `his_purchase`), `data/product_category_data.xml`, `data/ir_sequence_data.xml`, `models/__init__.py`, `models/product_template.py`, `security/ir.model.access.csv` (only if a model is added — none planned), `i18n/fr.po`, `tests/__init__.py`, `tests/test_patrimoine.py`

**Interfaces:**
- Produces: categories `his_patrimoine.categ_patrimoine` (parent) and leaves `categ_mobilier` "Furniture", `categ_informatique` "IT Equipment", `categ_reseau` "Network & Security", `categ_climatisation` "Air Conditioning", `categ_vehicules` "Vehicles", `categ_cuisine` "Kitchen Equipment" — all `default_tracking = serial`, `property_cost_method = average`, `property_valuation = periodic`. Sequence `his_patrimoine.seq_patrimoine` (code `his.patrimoine`, prefix `PAT-`, padding 6). `product.template._his_is_patrimoine() -> bool` (category `child_of` `categ_patrimoine`).

- [ ] **Step 1: Failing tests**
```python
def test_patrimoine_product_gets_pat_serial_sequence(self):  # created in categ_mobilier -> lot_sequence_id == seq_patrimoine, is_storable, tracking serial
def test_patrimoine_product_must_be_serial(self):  # write tracking='none' -> ValidationError
def test_other_categories_untouched(self):
```
- [ ] **Step 2: Run** `RUN_TESTS /his_patrimoine` (with `-i his_patrimoine`), verify FAIL.
- [ ] **Step 3: Implement** `product.template` `create`/`write`: when `_his_is_patrimoine()`, set `is_storable=True`, `tracking="serial"`, `lot_sequence_id=seq_patrimoine` if missing; `@api.constrains("tracking", "is_storable", "categ_id")` refuses non-serial/non-storable. MDM rules of `his_stock_mdm` (internal reference, leaf category) still apply — tests create products with `default_code`.
- [ ] **Step 4: Run, verify PASS.** **Step 5: Commit** `feat(his_patrimoine): patrimoine categories with PAT- serials`

### Task 8: Locations — rooms per building, "To Assign", yearly count

**Files:**
- Create: `his_patrimoine/data/stock_location_data.xml`, `data/stock_putaway_data.xml`, `models/maintenance_building.py`, `models/stock_location.py`, `hooks.py` (`post_init_hook` creating locations for existing buildings)
- Test: `his_patrimoine/tests/test_patrimoine.py`

**Interfaces:**
- Produces: `his_patrimoine.loc_patrimoine` ("Patrimoine", internal, parent = `stock.warehouse0.view_location_id`, i.e. **outside** WH/Stock); `his_patrimoine.loc_a_affecter` ("To Assign", internal, parent = `stock.warehouse0.lot_stock_id` — a putaway target must sit under the receipt destination; items wait there only until placed); `maintenance.building.his_location_id` (Many2one `stock.location`, readonly); `YEARLY = 365`.
- Spec deviation to note in the README: "À affecter" sits under WH/Stock (putaway constraint), rooms do not.

- [ ] **Step 1: Failing tests**
```python
def test_building_creates_location_under_patrimoine(self):  # create building "Bloc A" -> his_location_id.location_id == loc_patrimoine, cyclic_inventory_frequency == 365
def test_building_rename_renames_location(self):
def test_room_under_building_counted_yearly(self):  # RF5: hand-created child location -> frequency 365
def test_receipt_of_patrimoine_goes_to_a_affecter(self):  # PO for a categ_mobilier product, receive with 2 serials -> quants in loc_a_affecter
def test_room_items_not_in_stock_availability(self):  # RF5: move a serial to a room -> product.with_context(location=WH/Stock).qty_available == 0
```
- [ ] **Step 2: Run, verify FAIL.**
- [ ] **Step 3: Implement.** Building `create`/`write(name)` sync the location; `unlink` archives it. `stock.location.create`: when parent is `child_of` `loc_patrimoine` and `cyclic_inventory_frequency` not in vals → `YEARLY`. Putaway rule (`stock.putaway.rule`, `category_id = categ_patrimoine`, `location_in_id = WH/Stock`, `location_out_id = loc_a_affecter`). `post_init_hook` loops existing buildings.
- [ ] **Step 4: Run, verify PASS.** **Step 5: Commit** `feat(his_patrimoine): rooms per building, to-assign location, yearly count`

### Task 9: Menu, item list, initial import

**Files:**
- Create: `his_patrimoine/views/patrimoine_views.xml` (menu Inventory ▸ Patrimoine ▸ Items = `stock.lot` action, domain `product_id.categ_id child_of categ_patrimoine`, list: name, product, location; ▸ Rooms = `stock.location` action, domain `location_id child_of loc_patrimoine`; ▸ Count = `stock.quant` inventory action filtered on `location_id child_of loc_patrimoine`)
- Create: `tools/import_patrimoine.py`, `tools/seed/patrimoine_template.csv`
- Modify: `his_patrimoine/i18n/fr.po`, README (labels = standard lot barcode report; annual closing = existing `his.inventaire.annuel`)

**Interfaces:**
- CSV columns: `building_code,room,category_xmlid,default_code,product_name,serial`. Empty `serial` → next from `seq_patrimoine`.
- `import_patrimoine.py` runs in `odoo shell` like `tools/import_seed_catalogue.py`: one savepoint per row, finds/creates building (by `code`), room location (by name under the building location), product (by `default_code`), lot, then `stock.quant.with_context(inventory_mode=True).create({... "inventory_quantity": 1}).action_apply_inventory()`. Prints `OK n / REJECTED m` with the reason per rejected row. Path via `PATRIMOINE_CSV` env var.

- [ ] **Step 1: Failing test** `test_import_rows(self)`: import a 3-row CSV (one bad category) from a temp file → 2 quants in the right rooms, 1 rejection reported, and a second run creates no duplicates.
- [ ] **Step 2: Run, verify FAIL.**
- [ ] **Step 3: Implement** the script as an importable function `import_rows(env, rows) -> tuple[int, list[str]]` + a shell `__main__` wrapper; views and menu (groups: Items/Rooms `stock.group_stock_user`, Count apply stays standard manager-only).
- [ ] **Step 4: Run, verify PASS;** install on a fresh base and click through Inventory ▸ Patrimoine in French, print one label from a serial (screenshot).
- [ ] **Step 5: Commit** `feat(his_patrimoine): patrimoine menu and initial import`

## Finish

- [ ] Run the full CI-equivalent locally for `his_purchase,his_stock_mdm,his_patrimoine` + ruff/pylint-odoo (memory `local-dev-tools`).
- [ ] Update memory `his-investment-and-patrimoine` with the branch state; superpowers:finishing-a-development-branch.
