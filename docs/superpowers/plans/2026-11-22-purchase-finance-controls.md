# Finance Controls on Purchasing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finance confirms every purchase order, validates suppliers, holds non-matching bills and blocks unsafe payments, on top of `his_purchase`.

**Architecture:** Request hold and the 10 choice reasons go into `his_purchase` (19.0.2.2.0). Everything Finance owns lives in a new module `his_purchase_finance` (depends `his_purchase`, `account`, `purchase_stock`), with one file per concern under `models/`.

**Tech Stack:** Odoo 19 Community, pinned image `odoo:19.0@sha256:dd9013e6…`, TransactionCase tests.

**Spec:** `docs/superpowers/specs/2026-11-22-purchase-finance-controls-design.md`

## Global Constraints

- English source strings, French in `i18n/fr.po` for every new term (model names, field labels, selections, messages). Python comments in French, unaccented ASCII.
- Commits: author `Endeavor <mohamed.bounouaa@outlook.com>`, no `Co-Authored-By`.
- `QUOTE_THRESHOLD = 100_000` (company currency, excl. tax), `QUOTES_REQUIRED = 3`, `DAYS_TO_CONFIRM = 2` working days.
- Journal codes `AGEN`, `ACOP`, `ACAF`, `ARES` (Odoo caps codes at 5 characters).
- Rating bands: satisfactory ≥ 3.5, to watch ≥ 2.5, failing < 2.5.
- Rights tests: `Form` under the role, `self.env.invalidate_all()` before acting as the role.
- New fields on models the POS loads (`res.partner`) must be readable by a plain POS user or carry `groups=`.
- Lint like CI: `ruff check .`, `ruff format --check .`, `pylint --rcfile=.pylintrc <modules>`.

## Review Focus

1. Order in a foreign currency: the 100,000 DA rule uses the amount converted to company currency. Test in Task 4.
2. Order line in cartons, bill line in units: price and quantity compare in the order line's unit. Test in Task 6.
3. Partial receipts and two bills: the second bill is held only if the cumulative invoiced quantity exceeds what was received. Test in Task 6.
4. Credit note (`in_refund`) on an order: never held for quantity. Test in Task 6.
5. The order partner is a contact of the supplier company: status and documents are read on the commercial partner. Test in Task 4.

---

### Task 1: Request on hold + 10 choice reasons (`his_purchase`)

**Files:**
- Modify: `his_purchase/models/his_purchase_request.py` (STATES, OPEN_STATES, `action_approve`, `_his_reject`, new `_his_hold`, `_his_step`)
- Modify: `his_purchase/models/purchase_order.py` (CRITERIA)
- Modify: `his_purchase/wizard/his_purchase_request_reject.py` + views (field `mode`: `reject`/`hold`)
- Modify: `his_purchase/views/his_purchase_request_views.xml` (Put on Hold button, statusbar, buttons visible in `on_hold`)
- Modify: `his_purchase/wizard/his_purchase_choice.py` (note required for `usual_supplier`/`other`)
- Modify: `his_purchase/__manifest__.py` (19.0.2.2.0), `his_purchase/i18n/fr.po`
- Test: `his_purchase/tests/test_request.py`, `his_purchase/tests/test_order.py`

**Interfaces:**
- Produces: state `on_hold`; `HisPurchaseRequest.action_open_hold()`; `HisPurchaseRequest._his_hold(reason: str)`; `CRITERIA` with keys `lowest_price, payment_terms, earliest_delivery, quality, warranty, reliability, availability, usual_supplier, only_supplier, other`; `NOTE_REQUIRED_CRITERIA = {"usual_supplier", "other"}` in `purchase_order.py`.

- [ ] **Step 1: Tests** — `test_hold_from_submitted_notifies_requester` (state `on_hold`, a message containing the reason, follow-up `his_step` False), `test_approve_and_reject_from_hold`, `test_only_approver_can_hold` (AccessError/UserError for requester), `test_choice_note_required_for_other` (wizard with `criterion="other"` and no note raises UserError).
- [ ] **Step 2: Implement.** `on_hold` goes after `submitted` in STATES and into OPEN_STATES. Approve/reject accept `("submitted", "on_hold")`. `_his_step` returns None for `on_hold`. The reject wizard's `action_reject` dispatches on `mode`.
- [ ] **Step 3: Run** the his_purchase tests (see Task 8 command, `-u his_purchase`). Expected: all pass.
- [ ] **Step 4: Commit** `[IMP] his_purchase : demande en attente et 10 motifs de choix`.

### Task 2: Module scaffold, Finance group, accounts and journals

**Files:**
- Create: `his_purchase_finance/{__init__.py,__manifest__.py,hooks.py}`, `security/his_purchase_finance_security.xml`, `security/ir.model.access.csv`, `i18n/fr.po`, `tests/__init__.py`, `tests/common.py`, `tests/test_setup.py`
- Modify: `.github/workflows/ci.yml` (MODULES += `his_purchase_finance`), `his_role_catalogue/data/his_privilege_heading.xml` + `his_role_catalogue/__manifest__.py` depends + its test list

**Interfaces:**
- Produces: group `his_purchase_finance.group_finance` (privilege `res_groups_privilege_finance`, implies `purchase.group_purchase_user`, `account.group_account_invoice`, `account.group_validate_bank_account`; `account.group_account_user` implies it). `hooks.setup_accounts(env, company)` (idempotent), `post_init_hook(env)`. `ACCOUNTS: list[tuple[code, name, account_type, reconcile]]`, `JOURNALS: list[tuple[code, name]]`.
- `tests/common.py`: `HisFinanceCase(HisPurchaseCase)` adding `cls.finance` (user, group_finance), `cls.supplier_a..c` set to `validated` in sudo, and helper `_sent_order(request=None, supplier=None, price=…)`.

- [ ] **Step 1: Tests** — `test_setup_creates_missing_accounts_once` (call twice, 4 journals with those codes, account 381200 exists, the count is unchanged on the second call), `test_accountant_is_finance` (a user with `account.group_account_user` has `group_finance`).
- [ ] **Step 2: Implement.** The hook skips with `_logger.warning` when the company has no `chart_template`. It searches `account.account` by `code` with `company_ids` and the journal by `code`/company.
- [ ] **Step 3: Run, commit** `[ADD] his_purchase_finance : groupe Finance, comptes et journaux d'achat`.

### Task 3: Supplier file and bank trust

**Files:**
- Create: `his_purchase_finance/models/res_partner.py`, `models/his_supplier_document.py`, `models/account_payment.py`, `views/res_partner_views.xml`
- Test: `tests/test_supplier_file.py`

**Interfaces:**
- Produces: `res.partner.his_supplier_status` (Selection `waiting|reserve|validated|refused`, default `waiting`, `groups="base.group_user"`), `his_supplier_status_reason`, `his_supplier_document_ids`; `res.partner._his_supplier_blockers() -> list[str]` (empty when the commercial partner is validated with no expired or non-compliant document); `his.supplier.document.status` (`valid|to_refresh|expired|non_compliant`, non-stored compute).

- [ ] **Step 1: Tests** — `test_only_finance_sets_status`, `test_reason_required_for_reserve_and_refused`, `test_buyer_creates_supplier_waiting_only`, `test_document_status` (expired yesterday → expired; expires in 10 days → to_refresh; tax certificate received 7 months ago → to_refresh; flagged → non_compliant), `test_blockers_read_on_commercial_partner` (contact of a validated company with an expired doc → blocker), `test_payment_to_untrusted_bank_refused` (outbound supplier payment with an untrusted `partner_bank_id` → UserError at `action_post`; trusted → posted; no bank → posted).
- [ ] **Step 2: Implement.** The write guard raises only when the value actually changes and the user is not Finance or sudo. Create guard: a non-Finance user may only create with `waiting`.
- [ ] **Step 3: Run, commit** `[ADD] his_purchase_finance : dossier fournisseur et compte bancaire de confiance`.

### Task 4: Send to Finance, Finance confirms, Return to Buyer

**Files:**
- Create: `his_purchase_finance/models/purchase_order.py`, `wizard/his_finance_return.py` (+ views), `views/purchase_order_views.xml`
- Modify (by inheritance): `his.purchase.choice` (in `his_purchase_finance/wizard/his_purchase_choice.py`)
- Test: `tests/test_send_confirm.py`

**Interfaces:**
- Consumes: `_his_supplier_blockers()` (Task 3), `_his_confirm_checks`, `_his_competitors`, `_his_action_choice` (his_purchase).
- Produces: `purchase.order.action_his_send_to_finance()`, `purchase.order._his_mark_sent()`, `purchase.order._his_quote_count() -> int`, `purchase.order._his_amount_company() -> float`, `purchase.order.action_his_return(reason)`, fields `his_sent_to_finance_on`, `his_sent_to_finance_by_id`; follow-up step key `finance_confirm`.

- [ ] **Step 1: Tests** — `test_send_always_asks_reason` (single offer: returns the choice wizard action), `test_quote_rule_below_threshold` (90,000: no note needed), `test_quote_rule_above_threshold_needs_note` (150,000 with 2 quotes and no note → UserError; with a note → sent, chatter contains "Exception to the 3-quote rule"), `test_three_quotes_no_note`, `test_foreign_currency_converted` (EUR order whose converted amount ≥ 100,000 DA needs a note), `test_contract_order_skips_wizard`, `test_buyer_cannot_confirm`, `test_confirm_requires_sent`, `test_confirm_blocked_by_supplier_status` (waiting, reserve, refused, expired doc), `test_finance_confirms_then_routed_approval` (two_step: state `to approve`, approved by the manager), `test_buyer_cannot_edit_sent_order`, `test_return_to_buyer_clears_choice`, `test_finance_activity_created`.
- [ ] **Step 2: Implement.** The choice wizard override: when `self.env.context.get("his_send_to_finance")`, validate the note rules and the quote rule, write the choice, call `_his_mark_sent()` instead of `button_confirm`. `button_confirm` override: not Finance and not su → UserError; Finance → check sent + blockers, then super. Locked fields when sent: `partner_id, currency_id, order_line`. `_his_step` override: draft/sent + sent → `finance_confirm` step (owner = active Finance users, `DAYS_TO_CONFIRM`), else super.
- [ ] **Step 3: Run, commit** `[ADD] his_purchase_finance : commande confirmee par la Finance, regle des 3 devis`.

### Task 5: Service done

**Files:**
- Create: `his_purchase_finance/wizard/his_service_done.py` (+ views), `models/his_purchase_request.py`
- Modify: `models/purchase_order.py`, `views/purchase_order_views.xml`, request form inheritance view
- Test: `tests/test_service_done.py`

**Interfaces:**
- Produces: fields `his_service_done_by_id`, `his_service_done_on`, `his_service_period`, `his_service_note`, `his_has_services`; `purchase.order._his_certify_service(period: str, note: str)`; `his.purchase.request.action_open_service_done()`; hook `purchase.order._his_recheck_bills()` (defined in Task 6; Task 5 calls it if present via the Task 6 override, so Task 5 alone calls a no-op defined here).

- [ ] **Step 1: Tests** — `test_requester_certifies_service` (service line `qty_received` = ordered, fields set), `test_outsider_cannot_certify`, `test_manager_certifies_order_without_request`.
- [ ] **Step 2: Implement**, access check before the sudo write.
- [ ] **Step 3: Run, commit** `[ADD] his_purchase_finance : attestation de service fait`.

### Task 6: Bill check, payment block, proof

**Files:**
- Create: `his_purchase_finance/models/account_move.py`, `wizard/account_payment_register.py`, `wizard/his_bill_decision.py` (+ views), `views/account_move_views.xml`
- Modify: `models/account_payment.py` (proof on supplier payments)
- Test: `tests/test_bill_check.py`

**Interfaces:**
- Consumes: `his_service_done_on` (Task 5).
- Produces: `account.move.his_check_state`, `his_check_reason`, `his_first_check_clean`, `his_first_check_done`; `account.move._his_is_checked_bill() -> bool`; `account.move._his_mismatches() -> list[str]`; `account.move._his_run_check()`; `action_his_check_again()`, `action_open_release()`, `action_open_refuse()`; `purchase.order._his_recheck_bills()`.

- [ ] **Step 1: Tests** — `test_clean_bill_validated`, `test_price_mismatch_held`, `test_tax_mismatch_held`, `test_over_receipt_held`, `test_unlinked_line_held`, `test_service_not_certified_held`, `test_held_bill_payment_refused` (register wizard `_create_payments` raises; `payment_state == "blocked"`), `test_release_needs_reason_and_unblocks`, `test_refuse_needs_reason`, `test_check_again_after_receipt`, `test_service_done_rechecks`, `test_first_check_flag_kept`, `test_uom_cartons` (order 1 carton of 12 at 1,200; bill 12 units at 100 → validated), `test_partial_receipts_two_bills`, `test_refund_not_held_for_quantity`, `test_proof_required_in_wizard`, `test_manual_supplier_payment_needs_attachment`, `test_bill_without_order_not_checked`.
- [ ] **Step 2: Implement.** Check in `_post` (after super) for `_his_is_checked_bill()` moves. The quantity check uses `purchase_line_id.qty_invoiced > qty_received` (compare with the line UoM rounding), only for `in_invoice`. The price compares `bill price_unit` converted to the order line's UoM (`product_uom_id._compute_price`) after discount, with `currency.compare_amounts`. Blocking: write `payment_state="blocked"` when not validated, and for validated, if blocked, set `not_paid` and `env.add_to_compute`. The `button_draft` override resets to `waiting`.
- [ ] **Step 3: Run, commit** `[ADD] his_purchase_finance : rapprochement facture, blocage et preuve de paiement`.

### Task 7: Supplier rating

**Files:**
- Create: `his_purchase_finance/models/his_supplier_rating.py`, `views/his_supplier_rating_views.xml`
- Modify: `models/res_partner.py` (score + label), `models/purchase_order.py` (`action_his_rate`)
- Test: `tests/test_rating.py`

**Interfaces:**
- Produces: `his.supplier.rating` (`order_id, partner_id, side, purchase_* criteria, finance_* criteria, note, score`); `res.partner.his_rating_score`, `his_rating_label` (`satisfactory|watch|failing`).

- [ ] **Step 1: Tests** — `test_one_rating_per_side`, `test_score_average_and_label` (purchase side all 4 → 4.0 satisfactory; a second order with a finance rating of 2 → average 3.0 watch), `test_criteria_bounds` (6 → ValidationError).
- [ ] **Step 2: Implement, run, commit** `[ADD] his_purchase_finance : evaluation fournisseur`.

### Task 8: KPIs, translations, full verification

**Files:**
- Create: `docs/metabase/purchase-finance-kpis.sql`
- Modify: `his_purchase_finance/i18n/fr.po`, `his_purchase/i18n/fr.po`

- [ ] **Step 1:** Write the 6 queries (spec §6.11) and run each against the local test base: no SQL error.
- [ ] **Step 2:** Export `.pot` for both modules and check every msgid is in `fr.po` (run `his_access_base` language test with `-u his_access_base,his_purchase,his_purchase_finance`).
- [ ] **Step 3:** Lint like CI. Full CI replay on a fresh base: `-i MODULES,VENDORED --test-enable`, expected `0 failed, 0 error(s) of N tests`.
- [ ] **Step 4:** Commit, push, open the PR to main.

Local test command (worktree mounted at `/mnt/ws`, base copied from `ci`):
`odoo.sh -d <copy> --stop-after-init -u his_purchase_finance --test-enable --test-tags /his_purchase_finance`
