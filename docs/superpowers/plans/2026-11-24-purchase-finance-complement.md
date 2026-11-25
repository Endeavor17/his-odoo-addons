# Purchase Finance Complement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the purchase-procedure requirements the first pass missed: bills without an order on hold, a wider bill check, green supplier at payment, required supplier documents, anomalies, refused quantities, paper originals, cash VAT warning, request priority and tax, quote file and comparison table, confirmed-order lock, credit notes due, file closure, payment reference.

**Architecture:** Everything Finance owns extends `his_purchase_finance` (new model `his.purchase.anomaly`, new fields and checks on existing models); request priority and tax estimate go into `his_purchase`. Every new block respects `res.company.his_finance_confirms` (off = old behaviour).

**Tech Stack:** Odoo 19 Community, Python, XML views, `fr.po`.

**Spec:** `docs/superpowers/specs/2026-11-24-purchase-finance-complement-design.md`

## Global Constraints

- English source strings, French in each module's `i18n/fr.po`; code comments in French, unaccented ASCII.
- Every new block is skipped when `company.his_finance_confirms` is off (spec §6), except 6.7, 6.8, 6.9, 6.12, 6.14 (informational).
- Write from code in `sudo()` only after an explicit access check, as the module does today; fields written only by the workflow go in `SUDO_ONLY_FIELDS` or an equivalent guard.
- No model readable by all internal users (repo policy test in `his_access_base`).
- Tests: `post_install`, `-at_install`, on `HisFinanceCase`; rights tests through the role's user (`with_user`) and `Form`, `invalidate_all()` before acting as the role.
- Constants: `CASH_VAT_LIMIT = 1_000_000`; anomaly steps due in 2 working days, execution in 5.
- Commits as `Endeavor <mohamed.bounouaa@outlook.com>`, no Co-Authored-By trailer.
- Bump `his_purchase` and `his_purchase_finance` versions (patch → minor).

## Review Focus

1. A supplier validated before this change with no documents: its next order confirmation must be refused with the missing types listed; its existing bills stay payable only if green. Test in Task 2.
2. A refund (`in_refund`) with no order line: must NOT go on hold. Test in Task 3.
3. The storekeeper (stock user only, no purchase rights) validating a receipt with a refused quantity: must succeed and create the anomaly. Test in Task 5.
4. Receiving goods and confirming a service on a confirmed order after the lock widens: must still work for the storekeeper and the requester. Test in Task 6.
5. A down-payment bill encoded by an Invoicing Clerk (`account.group_account_invoice`, not Finance) on a confirmed order: must not hit the lock, and the bill must go on hold. Test in Task 6.

---

### Task 0: Local test harness

- [ ] Copy `.worktrees/pos-finance/.superpowers/sdd/2026-11-24-pos-finance-controls/odoo.sh` to `.superpowers/sdd/2026-11-24-achats-complement/odoo.sh`, pointing at this worktree, base `ac_base`, runs `ac_run_*`, installing `his_purchase_finance` and running `-u his_purchase,his_purchase_finance`. Not committed.
- [ ] Build the base: `odoo.sh base`. Expected: `BASE-DONE`.
- [ ] Baseline: `odoo.sh run "" "/his_purchase_finance,/his_purchase"`. Expected: `0 failed`, with a non-zero test count.

### Task 1: Request priority and tax estimate (`his_purchase`, spec 6.9)

**Files:** Modify `his_purchase/models/his_purchase_request.py`, `his_purchase/views/` (request form and list), `his_purchase/i18n/fr.po`, `his_purchase/__manifest__.py`. Test: `his_purchase/tests/test_request_estimate.py` (+ `tests/__init__.py`).

**Interfaces — Produces:** `his.purchase.request.priority` Selection `[("0", "Normal"), ("1", "Urgent")]`, default `"0"`, tracked; `his.purchase.request.line.estimated_tax` Monetary (stored, computed); `his.purchase.request.estimated_tax`, `estimated_amount_total` Monetary (stored).

- [ ] Tests:
  - `test_tax_estimate_from_product_taxes`: toner with `supplier_taxes_id = tva19`, qty 2, estimated price 1000 → line `estimated_tax == 380`, request `estimated_amount == 2000`, `estimated_amount_total == 2380`.
  - `test_no_product_no_tax`: line without product, price 500 → `estimated_tax == 0`, total 500.
  - `test_priority_default_and_tracked`: new request priority `"0"`; writing `"1"` posts a tracking value.
- [ ] Run: `odoo.sh run "-u his_purchase" "/his_purchase:TestRequestEstimate"`. Expected: FAIL (fields missing).
- [ ] Implement: line tax = `product.supplier_taxes_id.filtered(company)` `.compute_all(estimated_price_unit, currency, product_qty, product)` → `total_included - total_excluded`. Priority widget on form and list.
- [ ] Run the same command. Expected: PASS.
- [ ] Commit `[IMP] his_purchase : priorite et TVA estimee sur la demande`.

### Task 2: Supplier file and payment to a green supplier (spec 6.3, 6.4)

**Files:** Modify `his_purchase_finance/models/res_partner.py`, `models/account_payment.py`, `views/res_partner_views.xml`, `tests/common.py`. Test: `tests/test_supplier_file.py` (extend), `tests/test_bill_check.py` (payment case).

**Interfaces — Produces:**
- `res.partner.his_documents_exempt` Boolean, tracked, Finance-only write (same guard as `his_supplier_status`).
- `res.partner._his_missing_documents() -> list[str]` (labels of required types with no `valid`/`to_refresh` document; `[]` when exempt). Required: company `["rc", "nif", "nis", "tax_certificate", "rib", "id_card"]`, individual `["nif", "nis", "id_card", "rib"]`.
- `_his_supplier_blockers()` also lists missing documents.
- Fixture: `HisFinanceCase` sets `his_documents_exempt = True` before `his_supplier_status = "validated"` on suppliers a, b, c, ifu.

- [ ] Tests:
  - `test_validate_refused_without_documents`: Finance sets `validated` on `supplier_bare` → `ValidationError` naming "Trade Register (RC)".
  - `test_validate_with_documents`: add the 6 company documents → validated.
  - `test_individual_required_set`: an individual needs NIF, NIS, ID, RIB only.
  - `test_exempt_needs_none` and `test_exempt_finance_only` (buyer writing the flag → `AccessError`).
  - `test_old_green_supplier_blocked_at_confirm`: supplier written `validated` in sudo with `his_documents_exempt=False` and no documents (bypass via `with_context(his_skip_documents=True)` is NOT allowed: write it with SQL `UPDATE res_partner SET his_supplier_status='validated'` then `invalidate_all()`) → Finance `button_confirm` raises `UserError` listing the missing types.
  - `test_nif_unique`: two companies with `vat="000016001234567"` and `"000016 001234567"` → `ValidationError`; a contact under the first company with the same vat is accepted.
  - `test_payment_refused_supplier_not_green`: a supplier in `reserve`, outbound supplier payment with proof → `action_post` raises `UserError`; switch off → posts.
- [ ] Run `odoo.sh run "" "/his_purchase_finance"`. Expected: the new tests FAIL.
- [ ] Implement: `@api.constrains("his_supplier_status", "his_documents_exempt")` raising when `validated` and `_his_missing_documents()` (only with the switch on); document unlink / non-compliant flag does NOT re-check (blockers catch it at the next order). NIF constraint on `vat` for `commercial_partner_id == self`, same company or no company, spaces stripped, Python `@api.constrains`. Payment check in `action_post` next to the bank check, on `payment.partner_id.commercial_partner_id`.
- [ ] Run `odoo.sh run "" "/his_purchase_finance"`. Expected: `0 failed`.
- [ ] Commit `[IMP] his_purchase_finance : pieces exigees, NIF unique, paiement a un fournisseur valide`.

### Task 3: Bill check — no order, down payment, supplier, payment terms (spec 6.1, 6.2)

**Files:** Modify `his_purchase_finance/models/account_move.py`, `views/account_move_views.xml`. Test: `tests/test_bill_check.py`.

**Interfaces — Produces:** `account.move._his_is_checked_bill()` = `in_invoice` (switch on), or `in_refund` with an order line; `_his_mismatches()` adds the new messages; Task 4 adds the anomaly mismatch through `_his_order_mismatches(order) -> list[str]` (new hook, called once per linked order, returns `[]` here).

- [ ] Tests:
  - `test_bill_without_order_on_hold`: bill to `supplier_a`, one line "Rent", posted by Finance → `his_check_state == "reserve"`, reason contains "No purchase order", `payment_state == "blocked"`; Release with reason → `validated`.
  - `test_refund_without_order_not_checked`: `in_refund` without order line → `his_check_state` False.
  - `test_switch_off_bill_without_order_free`: switch off → no check state.
  - `test_down_payment_on_hold`: confirmed order, bill line linked to an `is_downpayment` order line (create the order line in sudo with `is_downpayment=True, product_qty=0, price_unit=3000`, and the bill line with `purchase_line_id`) → reserve, reason contains "Down payment".
  - `test_bill_other_supplier`: bill partner `supplier_b` on an order to `supplier_a` → reserve.
  - `test_bill_other_payment_terms`: order with 30-day terms, bill with immediate → reserve; same terms → validated.
- [ ] Run `odoo.sh run "" "/his_purchase_finance:TestBillCheck"`. Expected: the new tests FAIL.
- [ ] Implement in `_his_mismatches`: no product line linked → single issue; down-payment lines skip price and quantity rules and add their own issue; per linked order (`invoice_line_ids.purchase_line_id.order_id`): commercial partner and `invoice_payment_term_id` vs `payment_term_id` (only if the order has one), then `_his_order_mismatches(order)`. Add a "No purchase order" filter in the vendor bill search view.
- [ ] Run. Expected: `0 failed` on `/his_purchase_finance`.
- [ ] Commit `[IMP] his_purchase_finance : factures sans commande, acomptes, fournisseur et conditions controles`.

### Task 4: Anomalies (spec 6.5, 6.2 anomaly hold)

**Files:** Create `his_purchase_finance/models/his_purchase_anomaly.py`, `wizard/his_anomaly_declare.py`, `views/his_purchase_anomaly_views.xml`, `data/ir_sequence.xml`, `security/his_purchase_anomaly_rules.xml`. Modify `models/__init__.py`, `wizard/__init__.py`, `models/account_move.py` (`_his_order_mismatches`), `models/purchase_order.py` (smart button count, `action_his_declare_anomaly`), `models/purchase_order_service.py` (request button), `wizard/his_service_done.py` (`compliant` Boolean, default True), `security/ir.model.access.csv`, `__manifest__.py`, views of order / picking / bill / request. Test: `tests/test_anomaly.py`.

**Interfaces — Produces:**
- Model `his.purchase.anomaly` (`mail.thread`, `mail.activity.mixin`, `his.purchase.followup.mixin`): `name` (sequence `his.purchase.anomaly`, prefix `ANO/`), `order_id` (required), `picking_id`, `move_id`, `partner_id` (related `order_id.partner_id`, stored), `company_id`, `kind` Selection `shortage|damage|non_compliance|invoice|service|other`, `description` (required), `declared_by_id`, `declared_on`, `solution` Selection `replacement|return|complement|correction|credit_note|other`, `solution_note`, `finance_note`, `state` `declared|proposed|approved|executed|closed|cancelled`.
- Methods: `action_propose()` (purchase user, needs `solution`), `action_approve()`, `action_execute()` (purchase user), `action_close()`, `action_cancel()` (Finance; cancel needs `finance_note`). Each raises `UserError` from a wrong state, `AccessError` for a wrong role.
- `@api.model _his_declare(order, kind, description, picking=None, bill=None) -> his.purchase.anomaly`: access check (purchase user, stock user, Finance, or `order._his_may_certify_service(user)`), creates in sudo, re-checks the order's posted bills not paid (`_his_run_check`).
- `purchase.order.his_open_anomaly_ids` (computed, sudo), `his_anomaly_count`.
- Closing or cancelling calls `order.invoice_ids._his_recheck_bills()` (existing helper on account.move; check its name in `account_move.py:214`).
- Wizard `his.anomaly.declare`: `order_ref` Selection built in sudo from context `his_order_ids` (pattern of `his.service.done`), `kind`, `description`; `action_declare()` calls `_his_declare`.
- Service-done wizard: `compliant=False` → `_his_declare(order, "service", note or period)` instead of `_his_certify_service`; `note` required then.

- [ ] Tests:
  - `test_circuit`: buyer declares on a confirmed order → `declared`, buyer has an activity; buyer proposes with `solution="credit_note"` → `proposed`, Finance activity; Finance approves → buyer activity; buyer executes → Finance activity; Finance closes → no activity left.
  - `test_wrong_roles`: buyer `action_approve` → `AccessError`; Finance `action_propose` without solution → `UserError`.
  - `test_open_anomaly_holds_bill`: validated bill, then declare → bill `reserve`, reason contains `ANO/`; close → bill `validated`; `his_first_check_clean` unchanged.
  - `test_requester_declares_from_request`: `requester` opens the request button, wizard lists the order, declares → anomaly exists, requester cannot read `purchase.order` directly (`AccessError` on `read`).
  - `test_service_not_compliant`: service order, requester runs the service-done wizard with `compliant=False` → anomaly kind `service`, `his_service_done_on` still empty.
  - `test_outsider_cannot_declare`: `outsider` → `AccessError`.
  - `test_cancel_needs_note`.
- [ ] Run `odoo.sh run "" "/his_purchase_finance:TestAnomaly"`. Expected: FAIL (model missing).
- [ ] Implement. Record rules: Finance and purchase users all; stock users `[("declared_by_id", "=", user.id)]` or `picking_id` set; requesters `[("declared_by_id", "=", user.id)]`. ACL: purchase user rwc, Finance rwcu, stock user r+c, requester r. `_his_step()` per state as the spec lists, owner buyer = `order_id.user_id or company.his_purchase_manager_id`, Finance = `order_id._his_finance_users()`; register the model in the daily follow-up cron if the cron iterates a fixed model list (check `his_purchase` cron data).
- [ ] Run `odoo.sh run "" "/his_purchase_finance"`. Expected: `0 failed`.
- [ ] Commit `[ADD] his_purchase_finance : anomalies d'achat (declaration, solution, validation Finance)`.

### Task 5: Refused quantities on receipts (spec 6.6)

**Files:** Create `his_purchase_finance/models/stock_move.py` (+ `stock.picking` override). Modify `models/__init__.py`, `views/` (picking form, operations tab), `__manifest__.py` (depends `stock` already through `purchase_stock`). Test: `tests/test_receipt_refusal.py`.

**Interfaces — Consumes:** `his.purchase.anomaly._his_declare` (Task 4). **Produces:** `stock.move.his_qty_refused` Float (digits "Product Unit"), `his_refusal_reason` Char.

- [ ] Tests:
  - `test_refused_needs_reason`: 2 toners ordered, quantity 1, refused 1 without reason → `button_validate` raises `UserError`.
  - `test_refusal_opens_anomaly`: as `storekeeper` (new user, `stock.group_stock_user` only), refused 1 with reason "Box crushed", validate with no backorder → one anomaly, kind `non_compliance`, `picking_id` set, description contains "Box crushed"; the order's bills are held while open.
  - `test_no_refusal_no_anomaly`.
- [ ] Run `odoo.sh run "" "/his_purchase_finance:TestReceiptRefusal"`. Expected: FAIL.
- [ ] Implement: check in `stock.picking.button_validate` (before super) for incoming pickings with `purchase_id`; after `_action_done`, one `_his_declare` per picking in sudo with `declared_by_id` = the user. Fields shown in the operations list only when `picking_type_code == "incoming"`.
- [ ] Run `odoo.sh run "" "/his_purchase_finance"`. Expected: `0 failed`.
- [ ] Commit `[IMP] his_purchase_finance : quantites refusees a la reception`.

### Task 6: Orders — quote file, comparison table, confirmed lock, credit note due, Close File (spec 6.10–6.13)

**Files:** Modify `his_purchase_finance/models/purchase_order.py`, `views/purchase_order_views.xml`, `tests/common.py` (`_offer` attaches a quote file). Create `wizard` none. Test: `tests/test_order_controls.py`.

**Interfaces — Produces:**
- `_his_check_quote_file()` raises `UserError("Attach the supplier's quote before sending to Finance.")` unless an `ir.attachment` on the order whose name does not start with the RFQ report's `print_report_name` prefix ("Request for Quotation"); skipped for framework-contract orders.
- `_his_post_comparison()` posts an HTML table: supplier, total excl. tax, total incl. tax, delivery date (`date_planned`), payment terms, quote attached, chosen marker; called by `_his_mark_sent` when `_his_competitors()` is not empty.
- Lock: `LOCKED_WHEN_CONFIRMED = {"partner_id", "currency_id", "payment_term_id"}`, `LOCKED_LINE_FIELDS = {"product_id", "product_qty", "price_unit", "discount", "tax_ids"}`; `button_cancel` on a `purchase` order refused to non-Finance; line create/unlink refused on `purchase` orders, except lines with `is_downpayment` or whose section is a down-payment section.
- `purchase.order.line.his_qty_to_refund` Float (stored, `max(0, qty_invoiced - qty_received)` for non-service, non-downpayment lines); `purchase.order.his_amount_to_refund` Monetary (stored, company currency); search filter "Credit note due".
- `his_closed_on` Datetime, `his_closed_by_id`; `_his_close_blockers() -> list[str]`; `action_his_close_file()` (Finance) raises with the list, else stamps, posts, calls `button_done()`; `his_ready_to_close` Boolean computed with `_search_his_ready_to_close`; filter "Ready to close".

- [ ] Tests:
  - `test_send_needs_quote_file`; `test_rfq_report_not_a_quote`; `test_contract_order_needs_no_file`.
  - `test_comparison_posted`: order with 2 competitors → a chatter message containing the three supplier names.
  - `test_buyer_cannot_change_confirmed`: officer writes `order_line.product_qty` → `UserError`; officer `button_cancel` → `UserError`; Finance can.
  - `test_receipt_and_service_after_lock` (Review Focus 4): storekeeper validates the receipt; requester confirms a service → both succeed.
  - `test_clerk_down_payment` (Review Focus 5): user with `account.group_account_invoice` only creates the down-payment order line through the bill (sudo-free path as core does) → no `UserError`; the posted bill is on hold.
  - `test_credit_note_due`: receive 2, bill 2, return 1 → `his_qty_to_refund == 1`, amount = net price; in filter.
  - `test_close_file`: blockers listed while unpaid and unrated; after receipt, bill paid with proof, both ratings → closed, `state == "done"`; anomaly open → blocked.
- [ ] Run `odoo.sh run "" "/his_purchase_finance:TestOrderControls"`. Expected: FAIL.
- [ ] Implement; update `_offer` in `tests/common.py` to attach `quote.pdf`.
- [ ] Run `odoo.sh run "" "/his_purchase_finance,/his_purchase"`. Expected: `0 failed`.
- [ ] Commit `[IMP] his_purchase_finance : devis joint, tableau comparatif, commande confirmee verrouillee, cloture du dossier`.

### Task 7: Bills and payments — original, cash VAT warning, bank reference (spec 6.7, 6.8, 6.14)

**Files:** Modify `models/account_move.py`, `models/account_payment.py`, `wizard/account_payment_register.py`, `views/account_move_views.xml` (+ payment list/form, register wizard view). Test: `tests/test_bill_payment_extras.py`.

**Interfaces — Produces:** `account.move.his_original_state` Selection `missing|compliant|not_compliant` (default `missing`, tracked), `his_original_received_on`, `his_original_holder_id`, `his_original_note`; `account.payment.register.his_cash_vat_warning` Char (computed), `his_bank_reference` Char; `account.payment.his_bank_reference` Char; `CASH_VAT_LIMIT = 1_000_000`.

- [ ] Tests:
  - `test_original_default_missing_and_filter`.
  - `test_cash_warning`: bill of 1,190,000 incl. tax, wizard with a cash journal → warning set; bank journal → empty; after paying in cash a message on the bill mentions "not deductible".
  - `test_bank_reference_required`: bank journal, no reference → `UserError`; with "CHQ 004512" → payment carries it. Cash journal → not required.
- [ ] Run `odoo.sh run "" "/his_purchase_finance:TestBillPaymentExtras"`. Expected: FAIL.
- [ ] Implement; reference passed to payments through `_create_payment_vals_from_wizard` / `_create_payment_vals_from_batch`.
- [ ] Run `odoo.sh run "" "/his_purchase_finance"`. Expected: `0 failed`.
- [ ] Commit `[IMP] his_purchase_finance : original papier, alerte TVA especes, reference de paiement`.

### Task 8: Translations, lint, full CI replay, push

- [ ] Export `.pot` for `his_purchase` and `his_purchase_finance` (see `local-tour-image` notes: `--entrypoint odoo`, `-o /mnt/ws/...`), add every new msgid to `i18n/fr.po` in French; check no existing msgid disappeared (`git diff` of fr.po).
- [ ] `ruff check .`, `ruff format --check .` (whole repo, includes .md), pylint on the two modules.
- [ ] Full CI replay (detached container, script pattern `ci_replay.sh` of the pos-finance worktree). Expected: `0 failed, 0 error(s)` with the test count above the 2026-11-24 baseline (1116).
- [ ] Commit `[I18N] Achats Finance complement : traductions`; push `feature/achats-finance-complement`; open the PR to main (no attribution line).
- [ ] One fresh reviewer on the whole branch (access and money paths first); fix what is real, re-run the affected tests, push.
