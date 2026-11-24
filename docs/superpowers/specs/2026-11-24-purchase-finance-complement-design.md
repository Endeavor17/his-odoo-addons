# Finance controls on purchasing: what the first pass missed

Date: 2026-11-24. Source: a full re-read of Finance's purchasing procedure
(`Procedure_Achats_Systeme_Information_version_fin.docx`, PROC-ACH, working
version) against `2026-11-22-purchase-finance-controls-design.md` and the
`his_purchase_finance` code on main (`97262ec`). Mohamed asked to build what
is missing, with the defaults sent to Finance by mail the same day, and not to
wait for Finance: if they want a change, they ask.

## 1. Why

The 2026-11-22 pass compared the new version of the procedure with the old
one and asked questions about the changes. It never traced each requirement
to the code. The re-read found requirements that were never decided and never
built. The worst is a control hole: a vendor bill with no purchase order is
never checked, so it can be posted and paid freely, around every other
control.

## 2. Decisions

Mohamed, 2026-11-24: build the missing parts with our defaults; Finance can
ask for changes later. The defaults sent to Finance:

| # | Point | Default |
|---|-------|---------|
| 1 | Finance / Treasury roles | One "Finance" profile (the existing `group_finance`, implied by the Accountant role) does everything. No Treasury role. Every action is traced. Nothing to build. |
| 2 | Supplier documents | Green only with the required documents present and not expired or non-compliant. Company: RC, NIF, NIS, tax existence certificate, RIB, manager's ID. Individual: NIF, NIS, ID, RIB. Licence checked by Finance case by case (not enforced). A NIF is registered once. |
| 3 | Stock accounting flow | Not built here (see non-goals). Odoo 19 posts no entry per receipt or issue; it books the purchase at the bill and the stock variation at closing (periodic method, account 603). Proposed to Finance; their accountant confirms. |
| 4 | Withholding tax | None set up (no foreign supplier known). Nothing to build. |
| 5 | Delegation grid (missing) | Until it arrives, Finance approves 3-quote exceptions (by confirming the order, as today), down payments, and changes to a confirmed order. |

## 3. Goals, non-goals, anti-goals

Goals
- No vendor bill can be paid without Finance's check, with or without an
  order.
- The bill check covers what §7.1 lists: supplier, payment terms, and any
  open anomaly on the order, on top of price, taxes, quantities and service
  done.
- No supplier is paid unless its file is green.
- A supplier file goes green only with its required documents; no two
  suppliers share a NIF.
- Receipts record refused quantities with a reason; refusing anything opens
  an anomaly.
- Anomalies follow the procedure's circuit (§6.4): declared, fixed by the
  buyer, approved by Finance, closed by Finance.
- The paper original of a bill is traced (§7.3).
- Cash payments above 1,000,000 DA incl. tax carry a VAT warning (§8.2).
- Requests carry priority, estimated taxes and total incl. tax (Step 1).
- Every order sent to Finance carries the supplier's quote file; quotes are
  compared in a table on the order (§3.1, §3.2).
- Only Finance changes a confirmed order or authorises a down payment.
- Returns waiting for a credit note are visible with an estimated amount
  (§8.4.3).
- A purchase file is closed only when complete (§9.3).
- Payments carry a cheque or bank reference (§8.3).

Non-goals
- The stock accounting flow (decision 3): a separate accounting project once
  Finance agrees on the method. The accounts already exist.
- Withholding tax (decision 4).
- Delivery-note-only purchases (open point 5) and asset fields on receipts
  (open point 8): still open. Note for point 8: `his_patrimoine` already
  tracks the serial (`stock.lot`) and the room; only the commissioning date
  and the user responsible are missing.
- A Treasury role or a separate Finance head for purchases (decision 1).
- Supplier suspension by the Direction (§9.2): the rating label and Finance's
  "refused" status cover it for now.
- Unbilled receipts (FNP, §7.5): core Odoo has the accrued-expense wizard
  (`account.accrued.orders.wizard`). No supplier chase for missing invoices.
- Automated expiry alerts by cron (unchanged from the first spec).

Anti-goals (a failure even if it works)
- Rent or electricity bills that Finance cannot pay at all. They go on hold,
  and one Release with a reason frees them.
- A receipt that the storekeeper cannot validate because of the new fields.
- Breaking the existing circuit: Send to Finance, confirmation, routed
  approval, service done, the `his_finance_confirms` switch (off = old
  behaviour, everywhere this spec adds a block).
- A buyer able to change a confirmed order's quantities or prices.

## 4. Current state (main `97262ec`)

- `his_purchase_finance` (spec of 2026-11-22): Send to Finance, Finance
  confirms, supplier file (4 statuses, `his.supplier.document` with computed
  status), bill check on posting (`account.move._his_mismatches`,
  `his_check_state`, payment blocked unless `validated`, Release / Refuse /
  Check Again), service done, proof in the register wizard, rating, accounts
  and journals hook, KPI SQL.
- The bill check only runs on bills with at least one line linked to an order
  line (`_his_is_checked_bill`). Others have no `his_check_state`.
- `account.payment.action_post` refuses an untrusted bank account and a
  missing proof. It does not look at the supplier's status.
- `_his_supplier_blockers` refuses status != validated and expired or
  non-compliant documents. A supplier with no document at all can be
  validated.
- `purchase.order` lock (`_his_locked_orders`): only while sent and not
  confirmed, and in "to approve". A confirmed order (`purchase`) is open to
  the buyer again.
- NIF is the core `vat` field (`his_partner_dz` adds RC, NIS, AI, NIN; no
  uniqueness).
- Odoo 19 facts checked in the pinned image:
  - Purchase down payments are order lines with `is_downpayment`, created from
    a bill line. A down-payment bill line is linked to that order line.
  - Stock moves post an entry only when a location has a
    `valuation_account_id`; receipts from Vendors post nothing.
  - `account.accrued.orders.wizard` exists in Community.

## 5. Approaches

**A. Extend `his_purchase_finance`, request fields in `his_purchase`
(chosen).** Everything Finance owns already lives there, with its tests and
the `his_finance_confirms` switch. Request priority and tax estimate belong to
the requester's form, which `his_purchase` owns.

**B. A third module (`his_purchase_anomaly`...).** One more module to install
on staging and prod and to add to CI, for features that all hang on the
same bill check and the same switch. Rejected.

**C. OCA (`purchase_exception`, `base_tier_validation`).** Not needed for this
size, and they would duplicate the circuit we have. Rejected.

## 6. Design

All blocks below are skipped when `company.his_finance_confirms` is off,
except where stated.

### 6.1 Bills without a purchase order

- Every vendor bill (`in_invoice`) is checked at posting, linked to an order
  or not. `_his_is_checked_bill` becomes: `in_invoice`, or `in_refund` with a
  line linked to an order line (unchanged for refunds: money coming back
  needs no hold).
- A bill with no line linked to an order gets one mismatch: "No purchase
  order: Finance must release this bill with a reason". It goes on hold, as
  any other mismatch. Release, Refuse, Check Again work unchanged.
- Down payments: a bill line linked to an order line with `is_downpayment`
  gives the mismatch "Down payment on <order>: needs Finance's
  authorisation". Release is that authorisation. The quantity rule skips
  down-payment lines.

### 6.2 Bill check additions (§7.1)

Added to `_his_mismatches`, per order linked to the bill:
- the bill's commercial partner differs from the order's commercial partner;
- the bill's payment terms differ from the order's (only when the order has
  payment terms);
- the order has an open anomaly (6.5): "Anomaly <ref> is open on <order>".

Closing the anomaly re-checks the order's bills on hold, as service done does
today (`_his_recheck_bills`).

### 6.3 Payment needs a green supplier (§8.1)

`account.payment.action_post`, for outbound supplier payments: refused when
the commercial partner's `his_supplier_status` is not `validated`. This also
covers the register wizard. Applies only when the switch is on.

### 6.4 Supplier file: required documents, unique NIF (§4.1)

- New partner field `his_documents_exempt` (boolean, "Public body or
  utility: no documents required"), tracked, writable by Finance only.
- Required document types: company (`is_company`): `rc`, `nif`, `nis`,
  `tax_certificate`, `rib`, `id_card`. Individual: `nif`, `nis`, `id_card`,
  `rib`. Exempt: none.
- Setting `his_supplier_status = validated` is refused while a required type
  has no document in status `valid` or `to_refresh`. The message lists the
  missing types.
- `_his_supplier_blockers` (order confirmation) adds missing required types,
  so a supplier validated before this change is caught at its next order.
- NIF uniqueness: a Python constraint on `vat` for commercial partners
  (`is_company` or with no parent): two different commercial partners of the
  same company cannot share a NIF (spaces ignored). A Python constraint, not
  SQL, so that duplicates already in a database do not stop the upgrade; they
  are caught at the next edit.

### 6.5 Anomalies (§6.4)

New model `his.purchase.anomaly` (mail thread, activities), sequence
`ANO/####`:
- `order_id` (required), `picking_id`, `move_id` (bill), `partner_id`
  (related to the order's partner, stored), `company_id`.
- `kind`: shortage, damage, non-compliance, invoice or price discrepancy,
  service not compliant, other.
- `description` (required), `declared_by_id`, `declared_on`.
- `solution`: replacement, return, complementary delivery, correction, credit
  note, other; `solution_note`. Set by the buyer.
- `finance_note` (Finance's assessment of the financial, accounting and tax
  impact).
- `state`: `declared` → `proposed` (buyer sets the solution) → `approved`
  (Finance) → `executed` (buyer: carried out with the supplier) → `closed`
  (Finance, after checking the supporting documents); `cancelled` (Finance,
  with a note: declared by mistake). My call: the `executed` step hands the
  to-do back to Finance, which otherwise never learns the fix was done.
- Who declares: purchase users, stock users (the receiver), the requester or
  department head of the order's request, Finance. Who proposes: purchase
  users. Who approves, closes, cancels: Finance.
- Follow-up through `his.purchase.followup.mixin`: declared → buyer of the
  order (`user_id`, or purchase manager); proposed → Finance users; approved →
  buyer (execute with the supplier, due in 5 working days); executed →
  Finance users (close); no escalation chain. My call: 2 working days for
  every step but execution.
- Declaring an anomaly re-checks the order's posted, unpaid bills that are
  `validated`: they go on hold. The first-check flag is set once and is not
  touched. My call: the procedure says any anomaly blocks the payment of the
  operation concerned (control principle 6), so the whole order's bills are
  held, including the accepted part. Closing or cancelling the anomaly
  re-checks them automatically, so Finance has no extra click.
- Open = not closed and not cancelled. An open anomaly holds the order's
  bills (6.2).
- Entry points: a "Declare Anomaly" button on the order, on the receipt, on
  the bill, on the request form (requesters cannot read orders: the wizard
  lists the request's confirmed orders in sudo, as the service-done wizard
  does), and in the service-done wizard ("Not compliant" opens an anomaly of
  kind "service not compliant" instead of confirming). A smart button on the
  order lists its anomalies.

### 6.6 Receipts: refused quantities (§6.1)

- On `stock.move`: `his_qty_refused` (float) and `his_refusal_reason` (char),
  shown on incoming receipts linked to an order.
- Accepted = the quantity received (`quantity`); refused goods are not
  received. Remaining = the backorder, as today: core asks the receiver
  whether to create one. My call: no custom backorder logic. A backorder
  means a replacement is expected; "No backorder" means it is not.
- At validation: a refused quantity needs a reason; each receipt with refused
  quantities gets one anomaly of kind "non-compliance", listing the refused
  lines and reasons, declared by the receiver (created in sudo: the
  storekeeper has no purchase rights).
- Stock users write these two fields; they are not locked by the order lock.

### 6.7 Paper original (§7.3)

On vendor bills: `his_original_received_on` (date), `his_original_holder_id`
(user), `his_original_state` (`missing` default, `compliant`,
`not_compliant`), `his_original_note`. Tracked, set by Finance. Not blocking.
A filter "Original missing" on vendor bills.

### 6.8 Cash payment above 1,000,000 DA (§8.2)

- Register wizard: a computed warning shown when the journal is of type
  `cash`, the partner is a supplier and one of the bills has
  `amount_total_signed` above 1,000,000 in company currency: "VAT on this
  bill is not deductible if paid in cash (Finance Act 2023, art. 23)". Not
  blocking.
- When such a payment is created, a note is posted on the bill.
- Threshold as a module constant `CASH_VAT_LIMIT = 1_000_000`.

### 6.9 Request: priority and tax estimate (`his_purchase`, Step 1)

- `priority` selection: normal, urgent. Shown as a star; tracked.
- On request lines: `estimated_tax` computed from the product's purchase
  taxes (`supplier_taxes_id`, company-filtered) on `estimated_subtotal`; 0
  without a product. On the request: `estimated_tax` and
  `estimated_amount_total` (stored, beside `estimated_amount`).

### 6.10 Quote file and comparison table (§3.1, §3.2)

- Send to Finance requires at least one attachment on the order (the
  supplier's quote or offer), except for framework-contract orders. Message:
  "Attach the supplier's quote before sending to Finance."
- When the order has competing offers, Send to Finance posts a comparison
  table in the chatter: supplier, total excl. tax, total incl. tax, delivery
  date, payment terms, quote attached (yes/no), with the chosen one marked.
  The table is the "tableau comparatif joint au dossier".

### 6.11 Confirmed orders: only Finance changes them (decision 5)

- Extend the lock: on a confirmed order (`purchase`), non-Finance users
  cannot change partner, currency or payment terms, cannot cancel it, and
  cannot create, delete, or change `product_id`, `product_qty`,
  `price_unit`, `discount`, `tax_ids` on its lines. Other line fields
  (received quantities, dates, descriptions) stay open, so receiving, manual
  service receipts and his_purchase's own updates keep working.
- Exception: down-payment lines (`is_downpayment`, and their section line)
  that core creates on the order when a down-payment bill is encoded. The
  Invoicing Clerk encodes bills too; the bill then goes on hold (6.1) and
  Finance's Release is the authorisation.
- Changes Finance makes are tracked by core's chatter and stand on their own
  (decision 5): no new routed approval and no new quote rule. My call.

### 6.12 Returns waiting for a credit note (§8.4.3)

- On order lines: `his_qty_to_refund` = max(0, `qty_invoiced` −
  `qty_received`) for goods; `his_amount_to_refund` on the order (stored,
  company currency, net price × quantity).
- Filter "Credit note due" on purchase orders.

### 6.13 Closing the purchase file (§9.3)

- **Close File** button (Finance) on confirmed orders. Refused unless:
  no receipt still open (not done or cancelled) and, for services, service
  done; nothing left to bill (`invoice_status` not `to invoice`); every bill paid
  (`paid` or `in_payment`) or no amount due; no open anomaly; both ratings
  given (purchase side and finance side). The message lists what is missing.
- Sets `his_closed_on` and `his_closed_by_id`, locks the order (`button_done`
  if core allows it at that point), posts a message.
- Filter "Ready to close" (computed `his_ready_to_close`, not stored; the
  filter uses a search method).

### 6.14 Payment reference (§8.3)

- Register wizard and payment: `his_bank_reference` ("Cheque or bank
  reference"), required for outbound supplier payments from a bank journal,
  copied to the payment and shown in the supplier payment list.

## 7. Access

| Who | Can |
|-----|-----|
| Finance (`group_finance`) | everything below, plus approve / close / cancel anomalies, set the exempt flag, original fields, Close File |
| Buyer (`purchase.group_purchase_user`) | declare and propose on anomalies |
| Receiver (`stock.group_stock_user`) | refused quantities, declare an anomaly from a receipt |
| Requester / department head | declare an anomaly on its request's orders, "Not compliant" in service done |

`his.purchase.anomaly` gets record rules: Finance and purchase users see all;
stock users see those they declared or on receipts; requesters those on their
requests' orders. No model is open to all users (repo policy test).

## 8. Deployment

- Upgrade `his_purchase` and `his_purchase_finance` (staging: auto `-u`).
- After the upgrade, Finance must add documents before validating new
  suppliers; already-green suppliers missing documents are blocked at their
  next order confirmation. Flag public bodies and utilities as exempt.
- Bills posted from now on without an order go on hold.

## 9. Tests

One test per rule above, through `Form` or the role's user, following the
existing `his_purchase_finance/tests/common.py` fixture. Plus: the switch off
restores the old behaviour for 6.1, 6.3, 6.4, 6.10, 6.11; the receipt
validates without refused quantities (no anomaly); existing tests keep
passing (their fixtures may need documents and quote attachments).

## 10. Left to the builder

- View placement, wording (English source + `fr.po`).
- Anomaly kind for refused receipt lines (my call: non-compliance).
- Whether Close File calls `button_done` (lock) or only stamps.
- NIF uniqueness scope: within the company.
- Whether the RFQ PDF that Odoo attaches when the buyer emails it counts as
  the quote file (my call: no; the attachment must not be a "Request for
  Quotation" report generated by Odoo, so the check looks for any attachment
  whose name does not start with the RFQ report's name).
- The exact comparison-table layout.
