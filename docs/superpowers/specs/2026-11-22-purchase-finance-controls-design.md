# Finance controls on purchasing

Date: 2026-11-22. Source: Finance's corrected purchasing procedure
(`Procedure_Achats_Systeme_Information_version_fin.docx`, PROC-ACH, still a
working version) and Mohamed's decisions of 2026-11-22. Builds on
`2026-10-15-purchasing-design.md` and
`2026-10-20-investment-purchases-and-fixed-assets-design.md`. The
point-of-sale procedure comes after this one.

## 1. Why

Finance wants control over the money side of purchasing. Four things matter
to them: a supplier is checked before HIS commits to it, the order that leaves
is one Finance confirmed, an invoice is paid only when it matches what was
ordered and received, and every payment carries its proof. Today `his_purchase`
covers the purchasing team's side, from the request to the receipt. Nothing
in the repo touches bills or payments (only `his_mail_async` touches
`account.move`).

## 2. Decisions (Mohamed, 2026-11-22)

| # | Decision |
|---|----------|
| 1 | Request approval keeps our logic: the buyer approves usual purchases, the director approves investments. Add a **Put on hold** button next to Approve and Reject. Finance's "the director approves everything" is not adopted. |
| 2 | The buyer prepares the order. **Only Finance confirms it.** |
| 3 | Quotes: below 100,000 DA excl. tax, 1 quote and a reason. From 100,000 DA, 3 quotes, otherwise blocked unless a written reason is given. The choice reasons go from 5 to Finance's 10. |
| 4 | Supplier file: Finance's 4 statuses (orange waiting, red on reserve, green validated, dark red refused), documents with an expiry date, and a payment block when bank details change. A supplier is created orange, so requests for quotes still work. **Only the final order confirmation** is blocked until the supplier is green. |
| 6 | Invoice: our own 3-way match (Community has none). A hold status with a reason, an automatic order/receipt/invoice comparison, zero tolerance. |
| 7 | A "service done" confirmation, signed by the department, is required before payment. |
| 9 | Accounts: setup only. 4 purchase journals and about 30 sub-accounts. We fix Meriem's numbering gaps ourselves. |
| 10 | Payment status and proof, supplier rating 1-5, and the 6 KPIs are accepted as proposed. |

Defaults confirmed by Mohamed the same day:
- **Finance = the Accountant role** (`account.group_account_user`). It confirms
  orders, validates supplier files and releases invoices on hold.
- **Investment orders also go through Finance.** The director approves the
  request, then Finance confirms the order like any other.
- **Existing suppliers start orange.** Every order is blocked at go-live until
  Finance checks each supplier. That is accepted.
- **Missing accounts** follow the 380xxx pattern: 381000, 381200, 381300,
  382000 to 382300.

Still **open**, and not built: 5 (purchases backed only by a delivery note, with
no order) and 8 (asset fields on the receipt, manual class 2 entries).

## 3. Goals, non-goals, anti-goals

Goals
- No order reaches a supplier unless Finance confirmed it and the supplier is
  green, with no expired or non-compliant document.
- No vendor bill linked to an order can be paid until it matches the order and
  the receipt (or the service-done confirmation), or until Finance releases it
  with a written reason.
- No supplier payment goes to a bank account Finance has not trusted.
- Every supplier payment carries a proof file.
- The supplier choice is always justified, and the 3-quote rule is enforced
  from 100,000 DA.

Non-goals
- Delivery-note-only purchases (open point 5), asset fields on receipts
  (open point 8), automated class 2 entries (manual per Finance).
- A budget check. "Budget available" stays Finance's judgement.
- Routing each bill to the right ACH journal automatically. Decision 9 asks
  for setup only, so Finance picks the journal.
- Down payments, credit notes and returns workflows beyond core Odoo.
- Unpaid-invoice accruals (FNP): an accounting closing task, done with core
  reports.
- Expiry alerts by cron. The document status is computed live. Add a cron
  later if Finance asks for one.

Anti-goals (a failure even if it works)
- A buyer able to confirm an order, or to change one after Finance has it.
- A bill on hold that can still be paid through some other screen.
- Finance having to re-enter what the buyer already recorded (the choice and
  its reason).
- Breaking the existing purchasing circuit: routed approval, follow-ups,
  monthly orders, the investment ceiling.

## 4. Current state (main `c570b11`)

- `his.purchase.request`: draft → submitted → approved → sourcing → ordered →
  done (+ cancel). The approver approves or rejects (reject sends it back to
  draft with a reason, `his.purchase.request.reject` wizard).
- `purchase.order.button_confirm` (his_purchase) runs `_his_confirm_checks`
  (supplier answer, NIF/RC, priced lines, quantities). If competing offers
  exist, it opens the `his.purchase.choice` wizard (5 `CRITERIA`), otherwise it
  auto-fills `only_supplier`. Then the core confirms, and routed approval
  follows (`_approval_allowed`: purchase manager, or the director above the
  investment ceiling).
- Follow-up: each model's `_his_step()` gives key, owner, due date and chain.
  The mixin creates and closes the activities.
- Core Odoo 19 facts (checked in the pinned image):
  - `account.journal.code` is `size=5`. "ACH-GEN" does not fit.
  - `res.partner.bank.allow_out_payment` ("trusted") can only be set by
    `account.group_validate_bank_account` or system users. A trusted account's
    number and partner are locked: changing them means un-trusting first.
  - In Community, `_get_method_codes_needing_bank_account()` returns `[]`, so
    **core never blocks a payment to an untrusted account**. We must.
  - `account.move.payment_state` has a `blocked` value. Core refuses to
    register a payment on a blocked bill from the bill
    (`action_force_register_payment`). The value sticks through recomputes.
  - `purchase.order.line.qty_invoiced` counts bill lines of non-cancelled
    moves (drafts included). Services and consumables use a manual
    `qty_received`.
  - The `account.group_account_invoice` group can read and write
    `purchase.order` but not create it.

## 5. Approaches

**A. Everything in `his_purchase`.** One module, already installed everywhere
and upgraded automatically on staging. But every existing his_purchase test
confirms orders as the buyer. They would all need rewriting to go through
Finance, and the module, already 2,000 lines, would also carry bills and
payments.

**B. A new module `his_purchase_finance` on top of `his_purchase`, plus small
edits to `his_purchase` (chosen).** The request hold and the 10 reasons belong
to the purchasing team's circuit, so they go into `his_purchase`. Everything
Finance owns goes into the new module: confirmation, supplier file, bill
check, service done, payment proof, rating, accounts. his_purchase's tests
keep describing the buyer's circuit, with the Finance gate switched off in
their fixture (§6.4). The module
can be installed when Finance is ready. Cost: one more module to install and
add to CI.

**C. OCA modules.** OCA has no 3-way match or supplier-document module for
19.0 (`account_invoice_three_way_match` and `partner_document` are not
ported), and `base_tier_validation` would replace an approval circuit we
already have. Rejected.

## 6. Design

### 6.1 Request on hold (`his_purchase`)

- New state `on_hold` ("On Hold"), between submitted and approved.
- **Put on Hold** button, beside Approve and Reject, for the approver
  (`_his_check_approver`). It opens the reject wizard in hold mode (a `mode`
  field). The reason is required. The requester is notified with the reason,
  as on a rejection.
- From `on_hold`, the approver can **Approve** or **Reject** (same buttons,
  same rules). No separate "resume".
- While on hold there is no follow-up step (no reminders): the request waits
  for information on purpose. `on_hold` counts as open (`OPEN_STATES`), so it
  shows in the weekly digest, and the requester can still send a reminder.

### 6.2 Ten choice reasons (`his_purchase`)

`CRITERIA` becomes Finance's list. The 5 existing keys are kept, so no data
migration is needed:

| key | label |
|-----|-------|
| `lowest_price` | Best price |
| `payment_terms` | Best payment terms |
| `earliest_delivery` | Earliest delivery |
| `quality` | Quality and technical compliance |
| `warranty` | Warranty and after-sales service |
| `reliability` | Supplier reliability and experience |
| `availability` | Product or service availability |
| `usual_supplier` | Usual supplier |
| `only_supplier` | Only supplier or technical exclusivity |
| `other` | Other |

A note is required with `usual_supplier` ("subject to justification") and
`other` ("to be specified").

### 6.3 Send to Finance (`his_purchase_finance`)

- New order fields: `his_sent_to_finance_on` (datetime) and
  `his_sent_to_finance_by_id` (user), both read-only.
- **Send to Finance** button (purchase users, RFQ in draft or sent, not yet
  sent). It runs `_his_confirm_checks()` (the existing checks), then **always**
  opens the choice wizard, even with a single offer, because Finance wants a
  reason every time.
- Wizard rules, on top of the existing "best price must really be the
  cheapest":
  - the reason is required;
  - the note is required for `usual_supplier` and `other`;
  - **quote rule**: amount = order total excl. tax, in company currency. Quotes
    = this offer + competing offers (`_his_competitors()`: priced, not declined
    or unanswered). If the amount is ≥ 100,000 DA and there are fewer than 3
    quotes, a note explaining the exception is required, and it is posted in
    the chatter as "Exception to the 3-quote rule".
- Orders under a framework contract (`requisition_id` set, which includes
  monthly orders) skip the wizard and the quote rule: the contract was the
  competition. Their reason is set to `usual_supplier`, with the note
  "Framework contract <name>".
- On success: choice recorded (as today, frozen), sent fields set, and a
  follow-up step `finance_confirm` ("Confirm purchase order X") assigned to
  every active Finance user, due in 2 working days, with no escalation chain.
- Once sent, only Finance can change the supplier, the currency or the lines.
  Others get "X is with Finance: ask Finance to return it".
- **Return to Buyer** (Finance, sent and not confirmed): a reason is required.
  It clears the sent fields and the recorded choice, and notifies the buyer.
- Constants: `QUOTE_THRESHOLD = 100_000` (company currency), `QUOTES_REQUIRED = 3`,
  `DAYS_TO_CONFIRM = 2`.

### 6.4 Finance confirms

- `button_confirm` is refused (UserError) to anyone outside Finance, except in
  sudo. The core "Confirm Order" buttons are shown only to Finance, and only
  once the order has been sent.
- Additional checks before the existing ones: the order was sent to Finance,
  the supplier is **validated**, and the supplier has no expired or
  non-compliant document.
- A company setting **Finance Confirms Purchase Orders** (`res.company.his_finance_confirms`,
  on by default, in Purchase settings) switches this gate off: the buyer
  confirms as before, with no supplier check. It exists because his_purchase's
  own tests are post-install and run with this module installed (they switch
  it off in their fixture), and it gives a go-live lever if Finance is not
  staffed yet.
- Then the existing flow, unchanged: the his_purchase checks, the choice
  already recorded (so no wizard), core confirmation, routed approval
  (manager or director). Finance confirming does not replace the approval.

### 6.5 Supplier file

On `res.partner`, always read on the commercial partner:

- `his_supplier_status`: `waiting` (orange, the default, including existing
  partners), `reserve` (red), `validated` (green), `refused` (dark red).
  Tracked. A reason (`his_supplier_status_reason`) is required for `reserve`
  and `refused`. Only Finance changes the status. Others can create a partner
  only in `waiting`.
- `his.supplier.document`: partner, type (RC, NIF, NIS, tax existence
  certificate with tax article, RIB, professional licence, manager's ID,
  other), file, received on, expires on, non-compliant flag with note, and a
  computed status:
  - `non_compliant` if flagged;
  - `expired` if past its expiry date;
  - `to_refresh` if it expires within 30 days, or if it is a tax existence
    certificate received more than 6 months ago (Finance's internal alert);
  - `valid` otherwise.

  Purchase users can read and add documents. Finance has full rights.
- A "Supplier File" page on the partner form (purchase and Finance users) shows
  the status, the reason, the documents and the rating.
- **Bank details**: core already lets only `account.group_validate_bank_account`
  trust an account, and locks a trusted account's number. Finance gets that
  group. New rule: **an outbound supplier payment to an untrusted bank account
  is refused at posting** (`account.payment.action_post`), which also covers
  the register-payment wizard. A payment with no bank account (cash, cheque)
  is not affected.

### 6.6 Bill check (3-way match)

On vendor bills and refunds (`in_invoice`, `in_refund`) that have at least one
line linked to an order line:

- `his_check_state`: `waiting` ("Waiting", draft or not yet checked),
  `reserve` ("On Hold"), `validated`, `refused`. `his_check_reason` (text).
  `his_first_check_clean` (boolean, set once at the first check, for the KPI).
- **At posting**, the check runs. It returns a list of mismatches, compared in
  the order's unit and currency, with zero tolerance:
  - price after discount differs from the order line;
  - taxes differ from the order line;
  - quantity: the line's cumulative `qty_invoiced` is above `qty_received`;
  - service lines: the order has no service-done confirmation;
  - a product line not linked to any order line;
  - a currency different from the order's.

  No mismatch: `validated`. Otherwise: `reserve`, with the reason listing the
  mismatches, posted in the chatter.
- `reserve`, `refused` and `waiting` set core's `payment_state = blocked`.
  `validated` unblocks it. Our override of
  `account.payment.register._create_payments` also refuses any bill that is
  not validated, which covers the path from journal items as well.
- Finance buttons: **Check Again** (after a receipt, a credit note or a service
  confirmation), **Release** (reason required: it sets `validated` and logs
  "Released by X: reason" as a match exception), **Refuse** (reason required).
  Resetting to draft brings `waiting` back.
- Bills with no order line are not checked (no `his_check_state`), as today.

### 6.7 Service done

- New order fields: `his_service_done_by_id`, `his_service_done_on`,
  `his_service_period` (text) and `his_service_note` (reservations or
  anomalies). Computed `his_has_services`.
- **Confirm Service Done** wizard (period and note). It is available from the
  request form, to the requester or the head of the request's department, for
  its confirmed orders with service lines. It is also on the order form, for
  purchase managers, for orders without a request.
- Effect (in sudo after the access check): the confirmation fields are set,
  service lines get `qty_received = product_qty`, a chatter message is posted,
  and that order's bills on hold are checked again automatically.

### 6.8 Payment status and proof

- Status: core `payment_state` (not paid, partial, in payment, paid) plus our
  bill hold, which shows as "Blocked". Both columns appear in the vendor bill
  list.
- **Proof**: the register-payment wizard gets a file field (`his_proof`),
  required when paying vendor bills. The file is attached to each payment
  created. A supplier payment posted from the payment form needs at least one
  attachment. The procedure says "Paid" only after the proof is attached.
  Requiring it at payment makes that true from the start.

### 6.9 Supplier rating

- `his.supplier.rating`: order, partner (the commercial partner), side
  (`purchase` or `finance`, from the rater's group), 1-5 integer criteria,
  note, `score` = average of the side's criteria. One rating per order and
  side.
  - Purchasing: delays, quality, compliance, quantities, responsiveness,
    warranty, price.
  - Finance: administrative and tax compliance, invoicing, bank details,
    payment terms, handling of anomalies.
- **Rate Supplier** button on confirmed orders.
- On the partner: `his_rating_score` (average of the scores) and
  `his_rating_label`: satisfactory ≥ 3.5, to watch from 2.5, failing below
  2.5. Finance gave no weights or bands, so these are my call (simple
  average).

### 6.10 Accounts and journals (setup)

A `post_init_hook` (skipped with a log line if the company has no chart) adds
whatever is missing. Nothing is created twice:

- Journals, type purchase: `AGEN` "Purchases - General (ACH-GEN)", `ACOP`
  Copy Center, `ACAF` Cafeteria, `ARES` Restaurant. The codes are 4
  characters because Odoo caps them at 5.
- Accounts (6 digits, l10n_dz): 300000/300100/300200/300300,
  310000/310200/310300, 320000/320100/320200/320300 (stock, current asset);
  380000-380300, 381000/381200/381300, 382000-382300 (stocked purchases);
  600000-600300, 601000/601200/601300, 602000-602300 (consumption, expense);
  401000 stock suppliers, 401200 service suppliers, 404000 asset suppliers
  (payable). French labels as in Finance's tables. On the l10n_dz chart,
  300000, 310000, 380000, 381000, 382000, 401000, 404000, 600000, 601000 and
  602000 already exist (codes padded to 6 digits) and are left alone. There is
  no 320000 (the chart has 321/322/326), so it gets created. CI loads the
  generic chart instead (`try_loading` does not replace one already loaded),
  so the hook must not assume either chart.
- Not done: assigning these accounts to product categories and journals'
  default accounts. That is Finance's configuration, since the procedure says
  the journal must not force an account.

### 6.11 KPIs

Six monthly indicators, as SQL for the existing Purchasing dashboard in
Metabase (`docs/metabase/purchase-finance-kpis.sql`):

1. Requests authorised before commitment: orders confirmed in the month whose
   requests were all approved before `date_approve` (contract orders count as
   authorised).
2. Supplier files compliant before ordering: always 100 % by construction
   (confirmation is blocked otherwise). Shown for the record.
3. Bills compliant at the first check: `his_first_check_clean` among bills
   first checked in the month.
4. Average request processing time: days from request creation to the first
   confirmed order.
5. Compliant receipts: incoming receipts done in the month with neither a
   backorder nor a return.
6. Payments on time: bills fully paid in the month whose last reconciliation
   date ≤ due date.

Building the cards in Metabase and adding the Finance group to the Purchasing
dashboard are deployment steps.

## 7. Access

| Who | Group | Can |
|-----|-------|-----|
| Finance | `his_purchase_finance.group_finance` "Purchase Finance", implied by `account.group_account_user`. Implies `purchase.group_purchase_user`, `account.group_account_invoice` and `account.group_validate_bank_account` | confirm orders, return them, set supplier status, trust bank accounts, check, release or refuse bills, rate (finance side) |
| Buyer | `purchase.group_purchase_user` | send to Finance, add supplier documents, rate (purchasing side) |
| Requester / department head | `his_purchase.group_requester` | confirm service done on their request's orders |
| Approver | (as today) | put a request on hold |

The new privilege goes under the HIS heading (`his_role_catalogue` heading
file). No new catalogue role: the Accountant role already carries
`account.group_account_user`.

## 8. Deployment

- Add `his_purchase_finance` to CI `MODULES`.
- Staging: `odoo-upgrade --install his_purchase_finance` (auto `-u` does not
  install). Prod: install with the rest.
- Give the Accountant role to Finance staff, then have Finance validate each
  active supplier: they are all orange.
- Finance assigns category and journal accounts.
- Metabase: build the 6 cards on the Purchasing dashboard and add Purchase
  Finance to its groups.
- his_purchase's tests are post-install, so they run with this module
  installed; their fixture turns `his_finance_confirms` off.

## 9. Tests (`his_purchase_finance/tests`)

- Send to Finance: always asks for a reason; note rules; the 3-quote rule
  below and above 100,000 DA; the exception is logged; contract orders skip
  it; editing after sending is refused to the buyer; Return to Buyer.
- Confirm: refused to the buyer; refused before sending; refused for an
  orange, red or refused supplier, and for an expired document; allowed for
  Finance; routed approval still applies afterwards.
- Supplier status: only Finance; reason required; a buyer creates suppliers
  in waiting only; document status computation.
- Payment to an untrusted bank account is refused; a trusted one passes.
- Bill check: a clean bill is validated; price, tax, over-receipt, unlinked
  line and missing service confirmation each put it on hold; the register
  wizard refuses it; Release and Refuse need a reason; Check Again after the
  receipt validates it; service done re-checks automatically; the first-check
  flag stays as first set.
- Proof required in the register wizard and on a posted supplier payment.
- Rating: one per side, score, partner average and label.
- Setup hook: creates the missing accounts and journals, is idempotent, and
  skips when there is no chart.
- `his_purchase`: hold from submitted; approve and reject from on hold; no
  reminders while on hold; the 10 reasons.
- Rights tests go through `Form` under the role, and `invalidate_all()`
  before acting as the role.

## 10. Left to the builder

- Exact view placement, and wording of the messages (English source + `fr.po`).
- Whether `to_refresh` documents also deserve a warning at confirmation (not
  required).
- The delegation grid is still missing from Finance's document. If it arrives
  with thresholds per signatory, it becomes an extra check in §6.4.
