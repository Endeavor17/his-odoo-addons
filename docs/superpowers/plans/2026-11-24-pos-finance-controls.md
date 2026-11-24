# POS Finance Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new module `his_pos_finance` that puts Finance's point-of-sale procedure into Odoo: per-activity journals and accounts, a discrepancy form for every cash gap, transfers between cash boxes with a slip, daily counts for the Finance and Direction boxes, and manager-PIN authorisation on the till.

**Architecture:** Odoo already posts a closing gap to the cash journal's loss/profit account; we point both at 476000 and hang a discrepancy form (`his.cash.discrepancy`) on every gap, which Finance closes by posting 476 → final account. Transfers (`his.cash.transfer`) go through 581000; on a till they are statement lines of the open session. Finance/Direction boxes get a daily count record (`his.cash.count`) instead of being tills. Till-side changes are OWL patches inside the same module.

**Tech Stack:** Odoo 19 Community (`odoo:19.0@sha256:dd9013e669caaa23d26765dc55814655eaeecca7cfc2c265dbabae913bce22fd`), Python, OWL (POS frontend, pos_hr), QWeb PDF.

**Spec:** `docs/superpowers/specs/2026-11-24-pos-finance-controls-design.md`

## Global Constraints

- Module name `his_pos_finance`, version `19.0.1.0.0`, license LGPL-3, author "Groupe HIS-HTC-IRA". Add it to `MODULES` in `.github/workflows/ci.yml`.
- Depends: `point_of_sale`, `pos_hr`, `his_stock_mdm`, `his_purchase_finance`, `his_purchase`, `his_metabase`.
- Source strings in ENGLISH, French in `his_pos_finance/i18n/fr.po`. Code comments in French, unaccented ASCII in Python.
- Journal codes ≤ 5 chars: sales `VGEN VCOP VCAF VRES`, cash `CDIR CFIN CCOP CCAF CRES`.
- Accounts (6 digits): 530000 530001 530100 530200 530300, 581000, 476000 (reconcile), 657000, 757000, 700100 700200 700300, 701200 701300, 706000 706100 706200, 411000 411100 411200 411300, 445600 445720. Create only missing ones (l10n_dz has some; CI may load the generic chart).
- Tiers (company settings, DA): minor ≤ 5, significant ≤ 2000, important ≤ 5000, major > 5000.
- A "gap" is any amount where `currency.compare_amounts(amount, 0) != 0`.
- Commits authored `Endeavor <mohamed.bounouaa@outlook.com>`, NO `Co-Authored-By` trailer. Messages `[ADD] his_pos_finance : ...` / `[FIX] ...` in French.
- Docker is a snap: never mount or write under `/tmp`; pipe docker output through `| cat`.

**Test command** (used by every task; worktree is under `$HOME`):

```bash
# once: a base with the CI prerequisites (compose db must be up: `docker compose up -d db` from the main repo)
IMG=odoo:19.0@sha256:dd9013e669caaa23d26765dc55814655eaeecca7cfc2c265dbabae913bce22fd
RUN="docker run --rm -i --user root --network his-odoo-addons_default -v $PWD:/mnt/ws $IMG"
DB="--db_host=db --db_user=odoo --db_password=odoo"
ADD="--addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/ws"
$RUN odoo $DB $ADD -d pf_base --without-demo=True --stop-after-init -i l10n_dz,point_of_sale,his_person_core,his_academic_base | cat
cat tools/charger_plan_comptable_dz.py | $RUN odoo shell $DB $ADD -d pf_base --no-http --log-level=warn | cat
cat tools/seed_categories.py | $RUN odoo shell $DB $ADD -d pf_base --no-http --log-level=warn | cat
$RUN odoo $DB $ADD -d pf_base --without-demo=True --stop-after-init -i his_stock_mdm,his_purchase_finance,his_meal_management,his_pos_copy_center,his_pos_tva,his_metabase,his_role_catalogue | cat
# each run: copy the base, install with tests
$RUN bash -c "dropdb -h db -U odoo --if-exists pf_run; createdb -h db -U odoo -T pf_base pf_run" ; \
$RUN odoo $DB $ADD -d pf_run --without-demo=True --stop-after-init -i his_pos_finance -u his_stock_mdm,his_role_catalogue \
  --test-enable --test-tags /his_pos_finance,/his_stock_mdm,/his_role_catalogue --log-level=test 2>&1 | grep -E "FAIL|ERROR|tests$|Traceback" | cat
```
(`PGPASSWORD=odoo` env may be needed for `createdb`: add `-e PGPASSWORD=odoo` to `RUN`.) Pass = the last line reads `0 failed, 0 error(s) of N tests`.

Mohamed wants few, grouped test runs: write a whole task, then run once.

## Review Focus

1. **Coded prices must not ask for a PIN:** the Copy Center bulk price (`his_pos_copy_center/static/src/app/pos_order_patch.js`, `setUnitPrice`) and the 0 DA meal-on-credits (`his_meal_management/static/src/app/pos_store.js`, `setUnitPrice(0)`) must sell with no dialog. → Task 8 tour step.
2. **A session closed from the back end** (manager "Close" button, rescue session, imbalance wizard) with a gap and no `closing_notes` must still close and still get a form, explanation empty. → Task 4 test.
3. **Sub-rounding gaps** (0.004 DA) create no form and no entry. → Task 4 test.
4. **Handover amount ≤ 0, or above the session's expected cash**, is refused with a clear message; nothing is posted. → Task 5 test.
5. **Accepting a form twice** (double click, two Finance users) posts one regularisation only. → Task 3 test.

---

### Task 1: Module skeleton, groups, settings, accounting setup

**Files:**
- Create: `his_pos_finance/__init__.py`, `__manifest__.py`, `hooks.py`, `models/__init__.py`, `models/res_company.py`, `security/his_pos_finance_security.xml`, `security/ir.model.access.csv`, `views/res_config_settings_views.xml`, `tests/__init__.py`, `tests/common.py`, `tests/test_setup.py`, `README.md`
- Modify: `.github/workflows/ci.yml` (MODULES), `his_role_catalogue/data/his_role_data.xml` (role "Finance Head"), `his_role_catalogue/__manifest__.py` (depend on `his_pos_finance`)

**Interfaces:**
- Produces: group `his_pos_finance.group_finance_head` (implies `his_purchase_finance.group_finance`); company fields `his_gap_minor` (Float, 5.0), `his_gap_significant` (Float, 2000.0), `his_gap_important` (Float, 5000.0), related in `res.config.settings`; `hooks.setup_pos_finance(env, company) -> None` (idempotent); `hooks.post_init_hook(env)`; `account.journal.his_holder_id` (Many2one res.users); `pos.config.his_float_amount` (Monetary); test base class `tests.common.HisPosFinanceCase` with `cls.company`, `cls.cafeteria` (`his_stock_mdm.pos_config_cafeteria`), users `cls.cashier_user` (group `his_stock_mdm.group_caisse_cafeteria`), `cls.pos_manager` (`point_of_sale.group_pos_manager`), `cls.finance` (`his_purchase_finance.group_finance`), `cls.finance_head` (`group_finance_head`), `cls.director` (`his_purchase.group_purchase_director`), and helpers `_open_session(config) -> pos.session` / `_sell_cash(session, amount) -> pos.order` / `_balance(code: str) -> float` (posted balance of that account for the company). Helpers named only inside one test file (`_form`, `_sent`, `_sent_handover`, `_backend_transfer`, `_count`) are local to that file.

- [ ] **Step 1: Write `tests/test_setup.py`**

```python
def test_accounts_and_journals(self):
    acc = lambda c: self.env["account.account"].search([("code", "=", c), ("company_ids", "in", self.company.id)])
    for code in (
        "530000",
        "530001",
        "530100",
        "581000",
        "476000",
        "657000",
        "757000",
        "700300",
        "701300",
        "706200",
        "411300",
    ):
        self.assertTrue(acc(code), code)
    self.assertTrue(acc("476000").reconcile)
    j = lambda c: self.env["account.journal"].search([("code", "=", c), ("company_id", "=", self.company.id)])
    self.assertEqual(j("CCAF").type, "cash")
    self.assertEqual(j("CCAF").default_account_id, acc("530200"))
    self.assertEqual(j("CCAF").loss_account_id, acc("476000"))
    self.assertEqual(j("CCAF").profit_account_id, acc("476000"))
    self.assertEqual(j("VCAF").type, "sale")
    self.assertEqual(self.company.transfer_account_id, acc("581000"))


def test_till_config(self):
    c = self.cafeteria
    self.assertEqual(c.journal_id.code, "VCAF")
    self.assertEqual(c.invoice_journal_id.code, "VCAF")
    self.assertTrue(c.cash_control)
    self.assertFalse(c.set_maximum_difference)
    self.assertTrue(c.restrict_price_control)
    cash = c.payment_method_ids.filtered("is_cash_count")
    self.assertEqual(cash.journal_id.code, "CCAF")
    fp = c.default_fiscal_position_id
    self.assertFalse(fp.tax_ids)  # comptes seulement, la TVA reste celle de his_pos_tva
    self.assertIn(self.env["account.account"].search([("code", "=", "700200")]), fp.account_ids.account_dest_id)


def test_setup_is_idempotent(self):
    from odoo.addons.his_pos_finance.hooks import setup_pos_finance

    n = self.env["account.journal"].search_count([])
    setup_pos_finance(self.env, self.company)
    self.assertEqual(self.env["account.journal"].search_count([]), n)


def test_setup_refuses_open_session(self):
    from odoo.addons.his_pos_finance.hooks import setup_pos_finance

    self._open_session(self.cafeteria)
    with self.assertRaisesRegex(UserError, "Close every till"):
        setup_pos_finance(self.env, self.company)
```

- [ ] **Step 2: Implement `hooks.py`.** Follow `his_purchase_finance/hooks.py` (ACCOUNTS / JOURNALS tables, create only missing, warn and return when `company.chart_template` is empty). Also:
  - Refuse with `UserError("Close every till before installing Finance controls.")` when any `pos.session` of the company is not `closed`. Exception: no write is needed because everything already matches; check this first so a re-run on a live base never blocks.
  - Cash journals: `type="cash"`, `default_account_id` = its 530 account, `loss_account_id` = `profit_account_id` = 476000.
  - `company.transfer_account_id` = 581000.
  - Assign 445720 / 445600 as the repartition account of the `his_pos_tva` sale taxes (tax lines of `company.account_sale_tax_id` and its sibling service tax).
  - Per till (`his_stock_mdm.pos_config_copy_center|cafeteria|restaurant`): `journal_id` = `invoice_journal_id` = its V journal; its cash payment method (`is_cash_count`) gets the C journal (create a "Cash <till>" method if none); `cash_control=True`, `set_maximum_difference=False`, `restrict_price_control=True`; `default_fiscal_position_id` = a fiscal position "Revenue – <till>" with account mappings only.
  - Fiscal position mappings: base accounts by product category are set in the same hook. Copy categories `categ_copy_impression|photocopie|scan` → 706200; `categ_copy_bureautique|flexy`, `categ_book` → 700100; `categ_cafe_*` → 700200; `his_pos_menu.product_category_menu` and the meal product category → 701300. The Restaurant position maps 700200 → 700300. The Cafeteria position maps nothing for 701300. The Copy Center position maps 700200 → 700100. Read the exact meal category in `his_meal_management/data/` before coding; leave 701200 for Cafeteria prepared items, assigned by Finance by hand.
  - Mark `account.journal.his_holder_id` with help "Person who holds this cash box".

- [ ] **Step 3: Groups and role.** `group_finance_head` named "Finance Head", privilege `his_purchase_finance.res_groups_privilege_finance`, implies `his_purchase_finance.group_finance`. Role record `role_finance_head` ("Finance Head", description "Closes important and major cash gaps; reviews Direction cash box gaps.") in `his_role_catalogue`, `forcecreate="0"`, like `role_accountant`.

- [ ] **Step 4: Run the test command.** Expected: `test_setup` passes, 0 failed.

- [ ] **Step 5: Commit** `[ADD] his_pos_finance : journaux, comptes et caisses de la procedure points de vente`.

---

### Task 2: Till rights

**Files:**
- Modify: `his_stock_mdm/models/pos_config.py` (`_his_sync_tills`), `his_stock_mdm/tests/test_caisses_postes.py`
- Create: `his_pos_finance/models/pos_session.py` (cash in/out guard), `his_pos_finance/static/src/app/navbar.xml` (close button), `his_pos_finance/tests/test_till_rights.py`

**Interfaces:**
- Produces: cashiers in `pos.config.basic_employee_ids` (managers stay in `advanced_employee_ids` via pos_hr).

- [ ] **Step 1: Tests.** In `test_caisses_postes.py`, every assertion on a cashier switches from `advanced_employee_ids` to `basic_employee_ids`. `self.chef_employe` stays in `advanced_employee_ids`. In `test_till_rights.py`:

```python
def test_cash_in_out_refused_on_tills(self):
    s = self._open_session(self.cafeteria)
    with self.assertRaisesRegex(UserError, "hand over"):
        s.with_user(self.pos_manager).try_cash_in_out("out", 100, "fournisseur", False, {"translatedType": "out"})
```

- [ ] **Step 2: Implement.**
  - `_his_sync_tills` writes `basic_employee_ids = caissiers`, and `advanced_employee_ids` keeps only the managers (`Command.set(responsables.ids & ...)`, see its current skip condition). Update its docstring: cashiers sell and close; cash in/out and price changes belong to managers.
  - `pos.session.try_cash_in_out` raises `UserError("Cash only leaves a till by a hand over to Finance.")`.
  - Navbar patch (an xpath on `pos_hr`'s `Close Register` `t-if`, assets `point_of_sale._assets_pos`): show the item when `pos.config.module_pos_hr and pos.cashier`, so a basic cashier tapped in can close.
  - `his_pos_finance` `post_init_hook` also calls `env["pos.config"]._his_sync_tills()`, so existing cashiers move to "basic" at install. Test: after the hook, a cashier set up in "advanced" before is in `basic_employee_ids`.

- [ ] **Step 3: Run the test command.** Expected: 0 failed.

- [ ] **Step 4: Commit** `[FIX] Caisses : caissiers en liste « basique », fermeture gardee, plus de sortie d'especes libre`.

---

### Task 3: Discrepancy form

**Files:**
- Create: `his_pos_finance/models/his_cash_discrepancy.py`, `wizard/his_cash_discrepancy_decide.py`, `views/his_cash_discrepancy_views.xml`, `wizard/his_cash_discrepancy_decide_views.xml`, `data/ir_sequence_data.xml`, `tests/test_discrepancy.py`; ACL lines in `security/ir.model.access.csv`

**Interfaces:**
- Consumes: Task 1 groups and company tiers.
- Produces:
  - Model `his.cash.discrepancy` with the fields of spec §5.4 (`name`, `date`, `kind` ∈ opening/closing/handover/count, `journal_id`, `session_id`, `transfer_id`, `count_id`, `holder_id`, `holder_employee_id`, `expected`, `counted`, `amount` = counted − expected, `nature` ∈ shortage/surplus, `tier` ∈ minor/significant/important/major, `explanation`, `manager_note`, `finance_decision` ∈ accepted/refused/investigating, `finance_note`, `provisional_move_id`, `regularisation_move_id`, `closed_date`, `state` ∈ to_review/finance/direction/closed). Mail thread.
  - `@api.model his_open(kind: str, journal, expected: float, counted: float, provisional_move, explanation: str = "", **links) -> his.cash.discrepancy`: sudo create, returns the record, or an empty recordset when there is no gap.
  - `action_send_to_finance()`: needs `explanation` and `manager_note`.
  - `action_decide(decision: str, account=None, note: str = "")`.
  - `action_direction_approve()`, `action_send_back(note: str)`.
  - `_his_reviewer_group() -> str` xmlid; `_his_decider_group() -> str` xmlid.

- [ ] **Step 1: Tests** (`test_discrepancy.py`). Build forms with `his_open` on a hand-posted provisional move (530200 ↔ 476000).

```python
def test_tier_and_nature(self):
    for amount, tier in ((-3, "minor"), (-5, "minor"), (-6, "significant"), (2500, "important"), (-5001, "major")):
        f = self._form(amount)
        self.assertEqual(f.tier, tier)
        self.assertEqual(f.nature, "surplus" if amount > 0 else "shortage")


def test_no_form_without_gap(self):
    self.assertFalse(self._form(0.004))


def test_reviewer_per_box(self):
    self.assertEqual(self._form(-10, journal="CCAF")._his_reviewer_group(), "point_of_sale.group_pos_manager")
    self.assertEqual(self._form(-10, journal="CFIN")._his_reviewer_group(), "his_purchase.group_purchase_director")
    self.assertEqual(self._form(-10, journal="CDIR")._his_reviewer_group(), "his_pos_finance.group_finance_head")


def test_cashier_cannot_send(self):
    with self.assertRaises(AccessError):
        self._form(-10).with_user(self.cashier_user).action_send_to_finance()


def test_accept_loss_posts_and_reconciles(self):
    f = self._form(-100, explanation="Monnaie rendue", manager_note="Verifie")
    f.with_user(self.pos_manager).action_send_to_finance()
    f.with_user(self.finance).action_decide("accepted")
    self.assertEqual(f.state, "closed")
    lines = f.regularisation_move_id.line_ids
    self.assertEqual(lines.filtered(lambda l: l.debit).account_id.code, "657000")
    self.assertTrue(
        all(
            l.reconciled
            for l in (f.provisional_move_id | f.regularisation_move_id).line_ids.filtered(
                lambda l: l.account_id.code == "476000"
            )
        )
    )


def test_important_needs_finance_head(self):
    f = self._sent(-3000)
    with self.assertRaises(AccessError):
        f.with_user(self.finance).action_decide("accepted")
    f.with_user(self.finance_head).action_decide("accepted")


def test_major_goes_to_director(self):
    f = self._sent(-6000)
    f.with_user(self.finance_head).action_decide("accepted")
    self.assertEqual(f.state, "direction")
    self.assertFalse(f.regularisation_move_id)
    f.with_user(self.director).action_direction_approve()
    self.assertEqual(f.state, "closed")
    self.assertTrue(f.regularisation_move_id)


def test_refused_goes_back(self):
    f = self._sent(-10)
    f.with_user(self.finance).action_decide("refused", note="Recompter")
    self.assertEqual(f.state, "to_review")


def test_accept_twice_posts_once(self):  # Review Focus 5
    f = self._sent(-10)
    f.with_user(self.finance).action_decide("accepted")
    with self.assertRaises(UserError):
        f.with_user(self.finance).action_decide("accepted")
    self.assertEqual(len(self.env["account.move"].search([("ref", "=", f.name)])), 1)


def test_other_account_for_surplus(self):
    f = self._sent(50)
    sale = self.env["account.account"].search([("code", "=", "700200")])
    f.with_user(self.finance).action_decide("accepted", account=sale)
    self.assertEqual(f.regularisation_move_id.line_ids.filtered(lambda l: l.credit).account_id, sale)
```

- [ ] **Step 2: Implement.**
  - Tier boundaries are inclusive: `abs(amount) <= his_gap_minor` → minor, and so on.
  - Default counterparts: 657000 for a shortage, 757000 for a surplus.
  - Regularisation move: in the company's first `type="general"` journal, `ref = form.name`, posted. It reverses the 476 side of the provisional move and puts the counterpart on the chosen account. Reconcile the two 476 lines.
  - Guards: every action checks `state` first (raise `UserError` on a wrong state) and the group via `self.env.user.has_group` (raise `AccessError`).
  - `accepted` on a major tier → `direction`, keeping the chosen account in a stored field `his_account_id`.
  - `investigating` stays at `finance`; `refused` → `to_review`, with the note posted to chatter.
  - Amounts, `expected`, `counted` and moves are readonly in views.
  - Decide wizard with fields `decision`, `account_id` (domain: no receivable/payable), `note`.
  - Views: form with statusbar and buttons shown per state, list, search with group-by journal / holder / month / tier / state. Menu "Cash Discrepancies" under Point of Sale > Orders and under Accounting > Accounting, visible to `group_pos_manager`, `group_finance`, `group_purchase_director`.
  - Sequence `his.cash.discrepancy`, prefix `ECART/%(year)s/`, padding 4.
  - ACL: read and write for those three groups, no create or unlink (code creates in sudo).

- [ ] **Step 3: Run the test command.** Expected: 0 failed.

- [ ] **Step 4: Commit** `[ADD] his_pos_finance : fiche d'ecart et regularisation par la Finance`.

---

### Task 4: Closing and opening gaps

**Files:**
- Modify: `his_pos_finance/models/pos_session.py`
- Create: `his_pos_finance/static/src/app/closing_popup.js`, `static/src/app/opening_popup.js`, `tests/test_session_gaps.py`

**Interfaces:**
- Consumes: `his.cash.discrepancy.his_open` (Task 3).
- Produces: `pos.session.his_discrepancy_ids` (One2many).

- [ ] **Step 1: Tests.**

```python
def test_close_with_gap_needs_notes(self):
    s = self._open_session(self.cafeteria)
    self._sell_cash(s, 600)
    s.post_closing_cash_details(590)
    s.update_closing_control_state_session("")
    res = s.close_session_from_ui()
    self.assertFalse(res["successful"])
    self.assertIn("Explain", res["message"])


def test_close_with_gap_opens_form_on_476(self):
    s = self._open_session(self.cafeteria)
    self._sell_cash(s, 600)
    s.post_closing_cash_details(590)
    s.update_closing_control_state_session("Erreur de monnaie")
    self.assertTrue(s.close_session_from_ui()["successful"])
    f = s.his_discrepancy_ids
    self.assertEqual((f.kind, f.amount, f.explanation), ("closing", -10, "Erreur de monnaie"))
    self.assertIn("476000", f.provisional_move_id.line_ids.account_id.mapped("code"))


def test_back_end_close_without_notes_still_opens_form(self):  # Review Focus 2
    s = self._open_session(self.cafeteria)
    self._sell_cash(s, 600)
    s.cash_register_balance_end_real = 590
    s.with_user(self.pos_manager).action_pos_session_closing_control()
    self.assertEqual(s.state, "closed")
    self.assertEqual(s.his_discrepancy_ids.explanation, False)


def test_sub_rounding_gap_ignored(self):  # Review Focus 3
    s = self._open_session(self.cafeteria)
    self._sell_cash(s, 600)
    s.post_closing_cash_details(600.004)
    s.update_closing_control_state_session("")
    self.assertTrue(s.close_session_from_ui()["successful"])
    self.assertFalse(s.his_discrepancy_ids)


def test_opening_gap_posts_once(self):
    s1 = self._open_session(self.cafeteria)
    s1.post_closing_cash_details(1000)
    s1.update_closing_control_state_session("x")
    s1.close_session_from_ui()
    s2 = self._open_session(self.cafeteria, cashbox=980, notes="Billet manquant")
    self.assertEqual(s2.cash_register_balance_start, 1000)
    self.assertEqual(s2.cash_register_balance_end, 980)  # attendu = compte, pas 960
    self.assertEqual(s2.his_discrepancy_ids.kind, "opening")
```
(`_open_session(config, cashbox=None, notes="")` calls `action_pos_session_open()` then `set_opening_control(cashbox, notes)` when `cashbox` is given; extend the Task 1 helper.)

- [ ] **Step 2: Implement.**
  - `_cannot_close_session`: after `super()`, when `cash_control` and the cash gap (`cash_register_difference`) is non-zero with the currency and `closing_notes` is empty, return `{"successful": False, "message": _("Explain the cash difference before closing."), "redirect": False}`.
  - `_post_statement_difference(amount)`: record `statement_line_ids` before and after `super()`. When a line was added, call `his_open("closing", self.cash_journal_id, expected=self.cash_register_balance_end, counted=self.cash_register_balance_end_real, provisional_move=<new line>.move_id, explanation=self.closing_notes or "", session_id=self.id, holder_id=self.user_id.id, holder_employee_id=<employee_id if field exists>)`.
  - `_set_opening_control_data(cashbox_value, notes)`: `expected = self.cash_register_balance_start` before `super()`. After it, when there is a gap and a cash journal: set `cash_register_balance_start = expected`, create an `account.bank.statement.line` (journal = cash journal, amount = gap, `pos_session_id`, `counterpart_account_id` = 476000, `payment_ref` "Opening difference"), then `his_open("opening", …, explanation=notes)`.
  - JS patches: the closing and opening popups disable their confirm button while a cash gap is shown and the notes are empty, with the hint "Explain the difference". Patch the popups' confirm-enabled getters; read `closing_popup.js` / `opening_control_popup` in the core to pick the getter.

- [ ] **Step 3: Run the test command.** Expected: 0 failed.

- [ ] **Step 4: Commit** `[ADD] his_pos_finance : ecart de cloture et d'ouverture -> 476 et fiche`.

---

### Task 5: Transfers between cash boxes (back end, accounting, slip)

**Files:**
- Create: `his_pos_finance/models/his_cash_transfer.py`, `wizard/his_cash_transfer_receive.py` (+ view), `views/his_cash_transfer_views.xml`, `report/his_cash_transfer_report.xml`, `tests/test_transfer.py`; sequence `his.cash.transfer` prefix `VERS/%(year)s/`

**Interfaces:**
- Consumes: Task 3 `his_open`; `company.transfer_account_id`.
- Produces:
  - Model `his.cash.transfer` with the fields of spec §5.5. `from_session_id` and `to_session_id` are optional.
  - `action_send()`, `action_receive(amount: float)`.
  - `pos.session.his_handover(amount: float, note: str) -> int` (transfer id, already sent), `pos.session.his_pending_transfers() -> list[dict]` (id, name, amount_sent), `pos.session.his_receive_transfer(transfer_id: int, amount: float) -> None`.
  - Report action `his_pos_finance.action_report_cash_transfer`.
  - `his.cash.transfer.his_discrepancy_ids` (One2many on `transfer_id`).

- [ ] **Step 1: Tests.**

```python
def test_handover_from_till(self):
    s = self._open_session(self.cafeteria, cashbox=1000)
    self._sell_cash(s, 5000)
    tid = s.his_handover(4000, "")
    t = self.env["his.cash.transfer"].browse(tid)
    self.assertEqual((t.state, t.to_journal_id.code), ("sent", "CFIN"))
    self.assertEqual(s.cash_register_balance_end, 2000)
    t.with_user(self.finance).action_receive(4000)
    self.assertEqual(t.state, "received")
    self.assertEqual(self._balance("581000"), 0)
    self.assertEqual(self._balance("530001"), 4000)


def test_receive_less_opens_handover_form(self):
    t = self._sent_handover(4000)
    t.with_user(self.finance).action_receive(3950)
    f = t.his_discrepancy_ids
    self.assertEqual((f.kind, f.amount, f.journal_id.code), ("handover", -50, "CFIN"))
    self.assertEqual(self._balance("581000"), 0)


def test_invalid_handover_amount(self):  # Review Focus 4
    s = self._open_session(self.cafeteria, cashbox=1000)
    for bad in (0, -5, 1000.01):
        with self.assertRaises(UserError):
            s.his_handover(bad, "")
    self.assertFalse(self.env["his.cash.transfer"].search([]))


def test_injection_received_at_till(self):
    s = self._open_session(self.cafeteria, cashbox=0)
    t = self._backend_transfer("CFIN", "CCAF", 2000)
    s.his_receive_transfer(t.id, 2000)
    self.assertEqual(s.cash_register_balance_end, 2000)


def test_only_finance_receives_handover(self):
    with self.assertRaises(AccessError):
        self._sent_handover(100).with_user(self.pos_manager).action_receive(100)


def test_slip_renders(self):
    pdf, _ = self.env["ir.actions.report"]._render_qweb_html(
        "his_pos_finance.action_report_cash_transfer", self._sent_handover(100).ids
    )
    self.assertIn(b"VERS/", pdf)
```

- [ ] **Step 2: Implement.**
  - From a till (`his_handover`): the target is the company's CFIN journal. Amount must be > 0 and ≤ the session's `cash_register_balance_end`; check this before anything is written. Post a session statement line `-amount` with counterpart 581000, then create the transfer in state `sent` with `sent_by` = user.
  - Back-end send: an `account.move` in the source journal, 581000 ↔ the source 530 account.
  - Receive:
    - target is a till: a statement line in the target's open session (raise if none), counterpart 581000;
    - otherwise: a move in the target journal, 530 ↔ 581000;
    - `received ≠ sent`: post 581000 ↔ 476000 for the residual, then `his_open("handover", to_journal, expected=sent, counted=received, provisional_move=that move, transfer_id=…)`.
  - Rights:
    - receiving into CFIN, and any back-end send: `group_finance`;
    - receiving into CDIR: `group_purchase_director` or `group_finance_head`;
    - receiving into a till: the POS user of that session.
  - Slip: QWeb with name, date, from, to, amount sent, amount received, sent by, received by, two signature lines "Remis par" and "Reçu par" (source in English: "Handed over by" / "Received by").
  - Views: list, form with Send, Receive and Print buttons. Search filter "Not received". Menu next to Cash Discrepancies.

- [ ] **Step 3: Run the test command.** Expected: 0 failed.

- [ ] **Step 4: Commit** `[ADD] his_pos_finance : versements entre caisses via 581 et bordereau`.

---

### Task 6: Transfers on the till

**Files:**
- Create: `his_pos_finance/static/src/app/cash_transfer_buttons.js/.xml`, `static/src/app/handover_dialog.js/.xml`; manifest assets `point_of_sale._assets_pos`
- Modify: `pos.config` / session loader only if a field must reach the till (`his_float_amount`)

**Interfaces:**
- Consumes: `his_handover`, `his_pending_transfers`, `his_receive_transfer` (Task 5); `pos.config.his_float_amount` (Task 1).

- [ ] **Step 1: Implement.**
  - Two items in the till's top-right menu, visible to any tapped-in cashier: "Hand over to Finance" and "Receive cash".
  - "Hand over to Finance" opens a dialog proposing `expected cash − his_float_amount` (never below 0), editable. It calls `his_handover`, then prints the slip via the report action.
  - "Receive cash" lists `his_pending_transfers()`; confirming one asks for the counted amount and calls `his_receive_transfer`.
  - Server errors show as the standard error dialog.

- [ ] **Step 2: Verify in the tour of Task 8** (one tour covers the till).

- [ ] **Step 3: Commit** `[ADD] his_pos_finance : versement et reception d'especes depuis la caisse`.

---

### Task 7: Finance and Direction cash box counts

**Files:**
- Create: `his_pos_finance/models/his_cash_count.py`, `views/his_cash_count_views.xml` (kanban "Cash Boxes" on `account.journal` codes CFIN/CDIR + count form), `tests/test_count.py`

**Interfaces:**
- Consumes: Task 3 `his_open`; `account.journal.his_holder_id`.
- Produces:
  - Model `his.cash.count`: `journal_id`, `kind` ∈ opening/closing, `expected` (computed at create from posted move lines on `journal_id.default_account_id`, company), `counted`, `difference`, `note`, `user_id`, `date`.
  - `account.journal.his_count_state` ∈ none/opened/closed for today.
  - `account.journal.action_his_count(kind: str)` opens the count form.
  - `his.cash.count.his_discrepancy_ids` (One2many on `count_id`).

- [ ] **Step 1: Tests.**

```python
def test_count_without_gap(self):
    c = self._count("CFIN", "opening", counted=self._balance("530001"))
    self.assertFalse(c.his_discrepancy_ids)


def test_count_gap_needs_note_and_opens_form(self):
    with self.assertRaises(ValidationError):
        self._count("CFIN", "closing", counted=self._balance("530001") - 20, note="")
    c = self._count("CFIN", "closing", counted=self._balance("530001") - 20, note="Piece manquante")
    f = c.his_discrepancy_ids
    self.assertEqual((f.kind, f.amount), ("count", -20))
    self.assertEqual(f._his_reviewer_group(), "his_purchase.group_purchase_director")
    self.assertEqual(self._balance("476000"), 20)


def test_count_rights(self):
    with self.assertRaises(AccessError):
        self._count("CFIN", "opening", counted=0, user=self.cashier_user)
```

- [ ] **Step 2: Implement.**
  - A constraint requires `note` when there is a gap.
  - On create with a gap, post a move in the box's journal (530 ↔ 476000) and call `his_open("count", …, count_id=…, holder_id=journal.his_holder_id or user)`.
  - Who may count: the holder, or `group_finance` (CFIN), `group_finance_head` / director (CDIR).
  - Kanban: one card per box, showing today's state, with Open count and Close count buttons. Menu "Cash Boxes" under Accounting.

- [ ] **Step 3: Run the test command.** Expected: 0 failed.

- [ ] **Step 4: Commit** `[ADD] his_pos_finance : comptage quotidien des caisses Finance et Direction`.

---

### Task 8: Manager authorisation on the till + tour

**Files:**
- Create: `his_pos_finance/models/pos_order_line.py`, `static/src/app/authorization_dialog.js/.xml`, `static/src/app/authorization_patches.js`, `static/tests/tours/pos_finance_tour.js`, `tests/test_tour.py`; order-line fields shown in the back-end order form (`views/pos_order_views.xml`)

**Interfaces:**
- Produces: `pos.order.line.his_authorized_by_id` (Many2one hr.employee), `his_authorization_reason` (Char), `his_authorization_kind` (Selection price/discount/refund); all loaded and synced by the POS data service (add them to `_load_pos_data_fields` if that list is explicit in 19).

- [ ] **Step 1: Implement the dialog.**
  - Fields: manager select (employees with `_role === "manager"`), PIN, reason (required).
  - The PIN is checked like `pos_hr/static/src/app/utils/select_cashier_mixin.js` `checkPin` (`Sha1.hash(pin) === employee._pin`).
  - It resolves to `{employee, reason}` or `null`.
  - If the current cashier is already a manager: reason only, employee = cashier.

- [ ] **Step 2: Patch only the cashier's UI actions.**
  - `OrderSummary.setLinePrice`, replacing pos_hr's Access Denied: dialog, then `super`, then set the fields, kind `price`.
  - `pos.setDiscountFromUI(line, value)`: kind `discount`.
  - `TicketScreen.onDoRefund`: kind `refund`, written on every refund line.
  - Never patch `setUnitPrice` / `setDiscount` on the line model.

- [ ] **Step 3: Write the tour and its Python runner** (`HttpCase`, `start_tour("/pos/ui?config_id=…", "his_pos_finance_tour", login=<cafeteria counter user>)`, cashier tapped in with a basic PIN, manager with PIN 9999). Steps:
  1. The cashier opens the till.
  2. Sells a product, changes its price: the dialog appears; manager + PIN + reason "Prix affiche errone"; the order is paid.
  3. **Review Focus 1:** at the Copy Center till, a copy product whose bulk price applies (≥ the threshold in `copy_bulk_pricing.js`) is paid with no dialog. On the Restaurant till, a meal on credits for a student with credits is served at 0 DA with no dialog. If one till per tour is simpler, split this into a second tour with the same runner.
  4. "Hand over to Finance" for a set amount.
  5. Close with a gap and empty notes: the button is disabled. Type notes, close.
  - The runner then asserts in Python: one line with `his_authorization_kind == "price"` and the reason; one transfer `sent`; one closing discrepancy; and the session is closed (CI fact: a tour must not leave a session open).

- [ ] **Step 4: Run the test command.** Expected: 0 failed, tour passes.

- [ ] **Step 5: Commit** `[ADD] his_pos_finance : autorisation du responsable (PIN + motif) sur prix, remise, remboursement`.

---

### Task 9: Reporting

**Files:**
- Create: `his_pos_finance/data/his_metabase_dashboard_data.xml`, `docs/pos-finance-metabase.md`
- Modify: discrepancy and transfer views (pivot and graph), `his_pos_finance/README.md`

- [ ] **Step 1: Views.**
  - Discrepancy pivot (rows journal, then holder; columns month; measures count and `amount`) and graph.
  - Filters: "Open" (state ≠ closed), "This month".
  - A server-computed list "Tills closed without hand over": closed sessions of the last 30 days with no transfer from them. Expose it as a filter on `pos.session`: a boolean `his_no_handover` with a search method.

- [ ] **Step 2: Metabase.** Add a record `dashboard_cash` (`his.metabase.dashboard`, name "Cash Control", code `cash`, groups `his_purchase_finance.group_finance`) in the same `noupdate` style as `his_metabase/data/his_metabase_dashboard_data.xml`. `docs/pos-finance-metabase.md` gives the 4 SQL questions to create in Metabase:
  1. gaps per cashier and per month;
  2. open forms by age and state;
  3. handovers not received;
  4. authorised overrides per cashier.

- [ ] **Step 3: Test** that `his_no_handover` finds a closed session without a transfer and skips one with a transfer (add it to `test_transfer.py`). Run the test command. Expected: 0 failed.

- [ ] **Step 4: Commit** `[ADD] his_pos_finance : suivi des ecarts et tableau de bord Metabase`.

---

### Task 10: Translations, full CI replay, push, PR, final review

- [ ] **Step 1:** Export `fr.po` for `his_pos_finance`, `his_stock_mdm` and `his_role_catalogue` (pitfall from 2026-10-20: the export can lose terms, so diff before writing). Translate every new term; slip signature lines "Remis par" / "Reçu par".
- [ ] **Step 2:** Lint as CI does: `ruff format --check`, `ruff check`, `pylint --rcfile=.pylintrc his_pos_finance his_stock_mdm`, eslint on the new JS.
- [ ] **Step 3:** Full CI replay (all MODULES, fresh base, the 3 CI steps). Expected: the result line `0 failed, 0 error(s)`, and the test count is higher than the previous run.
- [ ] **Step 4:** Commit `[I18N] his_pos_finance : traductions`, push `feature/pos-finance`, open ONE PR against `main` (title `[ADD] Points de vente : controles Finance (his_pos_finance)`, body listing rollout: close tills before install, Finance Head role to a staging login, holders on CFIN/CDIR).
- [ ] **Step 5:** One fresh reviewer on the whole branch, thorough on till code and access rights. Fix the real findings, re-run, push.
