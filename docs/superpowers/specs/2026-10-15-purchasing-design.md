# Purchasing for the Groupe HIS-HTC-IRA

Design for the purchasing flow of the Groupe HIS-HTC-IRA on Odoo 19 Community.

It replaces a first draft that had been written from a recording of another
company's Odoo (an IT reseller buying for a client). HIS buys for its own use
(Cafétéria, Restaurant, Copy Center, maintenance, IT, office supplies), has
**no ad hoc committee**, and runs Community, so the draft's client, resale,
project and committee concepts are dropped.

The governing idea, stated first:

> **Odoo already knows how to buy. We add the HIS rules around it.** A request
> for quotation is a standard draft `purchase.order`, a comparison is Odoo's
> alternative RFQs, approval is Odoo's order approval. The custom code holds
> only what Odoo lacks: the internal purchase request, the supplier's answer,
> the documented choice, Algerian supplier identifiers and the French
> documents.

---

## 1. Scope

| In version 1 | Out of version 1 (and why) |
|---|---|
| Internal purchase request with lines and approval | Ad hoc committee, meeting minutes: no committee at HIS |
| Optional comparison of several quotes (no minimum number) | Imports (foreign currency, bank domiciliation, customs): no case yet |
| Supplier answer on each RFQ (quoted / declined / no answer) | Budget control that blocks a request: analytic tagging only, budgets later |
| Documented supplier choice, locked after confirmation | Supplier portal, e-signature |
| Order approval above a threshold (native Odoo) | Stamp duty and cash-payment limits: accounting, not purchasing (see §10) |
| Reminders and escalation so no request is forgotten (§5.8) | Composite products: not a purchasing concern |
| Recurring monthly orders on a blanket order, plus ad hoc needs (§6) | Quantities computed from consumption: template quantities in v1 |
| Supplier legal identifiers RC, NIF, NIS, AI | |
| Printed documents: Demande de proforma, Fiche de choix fournisseur, Bon de commande, Bon de réception | |

## 2. What Odoo 19 Community already provides (verified in the 19.0 source)

| Need | Native feature | Module |
|---|---|---|
| One RFQ per supplier, with lines, taxes, currency, totals | `purchase.order` in state `draft` / `sent` | `purchase` |
| Send an RFQ by email, print it | « Send by email », RFQ report | `purchase` |
| Ask several suppliers for the same need | **Alternative RFQs** (« Create alternative »), grouped by `purchase.order.group` | `purchase_requisition` |
| Compare offers side by side | « Compare Product Lines »; best price / best unit price / earliest date highlighted (`get_tender_best_lines`) | `purchase_requisition` |
| Pick the winner per line | « Choose » zeroes the quantity on the competing lines | `purchase_requisition` |
| Cancel the losers when the winner is confirmed | Warning wizard on confirmation (« What about the alternative RFQs? ») | `purchase_requisition` |
| Recurring supplier with agreed prices | **Blanket order** (`requisition_type = blanket_order`) | `purchase_requisition` |
| Approval above an amount | « Purchase Order Approval » setting: one company-wide amount, approved by *Purchase / Administrator* | `purchase` |
| Who changed what, when | Chatter tracking on orders | `mail` |
| Receipts and vendor bills from the order | Receipt pickings, bill control on received quantities | `purchase_stock`, `account` |
| Algerian purchase taxes | `l10n_dz_vat_purchase_19`, `_9`, `_0` (and `_depr` variants for depreciable goods) | `l10n_dz` |

Two native behaviours that shape the design:

- **The comparison ranks on `price_total_cc`: tax included, in company
  currency.** Kept as is (decided 2026-10-15: start with 19 % and see; revisit
  the basis only if the accountant says input VAT is recoverable). It also **skips lines with a zero total**, so a supplier
  who declined is never highlighted as cheapest — but nothing stops someone
  from confirming that RFQ. The guard is ours (§5.3).
- **`l10n_dz` ships taxes and a chart of accounts, but no partner fields.**
  RC, NIS and AI do not exist anywhere; NIF can live in the standard `vat`
  field.

## 3. Module architecture

Two modules, so the Algerian identifiers serve sales and invoicing too:

| Module | Depends on | Holds |
|---|---|---|
| `his_partner_dz` | `base`, `account`, `l10n_dz` | RC, NIS, AI on `res.partner` and `res.company`; NIF label on `vat`; supplier tax regime; printing helpers for the legal block |
| `his_purchase` | `purchase`, `purchase_stock`, `purchase_requisition`, `hr`, `his_stock_mdm`, `his_partner_dz` | Purchase request, sourcing, supplier answer, supplier choice, reports, groups and rules |

Before building the request model, check whether OCA `purchase_request` has a
mature 19.0 branch. If it does, vendor it (as was done for `helpdesk_mgmt`)
and put the HIS rules in `his_purchase`; if not, `his_purchase` carries its
own small request model as described in §5.1.

Language rule (2026-10-08): every label is **English in the source** with
`i18n/fr.po` (and `ar.po` when Arabic is switched on). French document titles
below are the `fr.po` values. No module-specific `font-family`.

## 4. Roles

| Role | Odoo group | Can |
|---|---|---|
| Requester | `base.group_user` (any employee with a login) | Create, edit and submit their own requests; see their own requests and the resulting order status |
| Request approver | new `his_purchase.group_request_approver` (department heads) | Approve or reject requests of their department |
| Purchasing officer | `purchase.group_purchase_user` | Turn approved requests into RFQs, record supplier answers, compare, choose, confirm orders below the approval amount |
| Purchase manager | `purchase.group_purchase_manager` | Approve **POS-operations** orders above the amount (§5.5); authorise quantity top-ups (§5.6) |
| Executive director | `purchase.group_purchase_manager` + new `his_purchase.group_purchase_director` | Approves **general** orders above the amount, and may approve POS-operations orders too; last level of escalation (§5.8) |
| Warehouse manager | `stock.group_stock_manager` | Owns the monthly orders (§6.2) |
| Storekeeper | `stock.group_stock_user` | Receive goods against the order |
| Accountant | `account.group_account_invoice` | Record and check vendor bills |

The purchase managers are known but have no Odoo accounts yet: their users
are created and put in the groups at go-live.

No separation of duties (decided 2026-10-15, for flexibility): the person who
chose the supplier **may** approve the order. Both names are recorded and
printed on the Fiche de choix fournisseur.

Authorisation is enforced by groups and record rules, never by hiding buttons
alone.

## 5. Workflow

```
Request (draft) ─submit→ Submitted ─approve→ Approved ─source→ Sourcing ─order→ Ordered → Done
                               └─reject→ Rejected        (any state before Ordered) ─→ Cancelled
```

### 5.1 Purchase request — `his.purchase.request`

Created by the requester. Reference from a sequence, e.g. `DA/2026/00018`.

| Field | Type | Rule |
|---|---|---|
| `name` | Char | Sequence, read-only |
| `requester_id` | `hr.employee` | Default: current user's employee |
| `department_id` | `hr.department` | Default from the employee; drives the approver |
| `company_id` | `res.company` | HIS / HTC / IRA if they are separate companies (§11, question 2) |
| `analytic_distribution` | Json | Cost centre (school, service); copied to order lines |
| `date_required` | Date | When the goods are needed; must not be in the past at submission |
| `justification` | Text | Why the purchase is needed; required at submission |
| `estimated_amount` | Monetary, computed | Sum of line estimates; informative (the approver sees it) |
| `line_ids` | One2many | At least one line to submit |
| `order_ids` | computed | RFQs and orders created from the request; smart button |
| `state` | Selection | `draft`, `submitted`, `approved`, `sourcing`, `ordered`, `done`, `rejected`, `cancelled` |

Request line — `his.purchase.request.line`:

| Field | Rule |
|---|---|
| `product_id` | Optional: a catalogue product (subject to `his_stock_mdm` rules) |
| `description` | Required when there is no product (services, one-off items) |
| `product_qty` | > 0 |
| `product_uom_id` | Required; same category as the product's UoM |
| `estimated_price_unit` | ≥ 0; internal estimate, never sent to suppliers |
| `purchase_line_ids` | Order lines that source this line |
| `qty_ordered` | Computed from confirmed order lines |

Rules:
- Submitting requires a justification, a required date and at least one valid
  line. Missing fields are named in the error.
- After submission the requester can no longer edit; a rejected request goes
  back to `draft` with the rejection reason in the chatter.
- The approver is the department head (`hr.department.manager_id`) unless a
  member of `group_request_approver` acts on the department's behalf.
- A line without a product must get one before it goes on an RFQ (Odoo order
  lines need a product): the officer picks a catalogue product or a generic
  service product per expense category.

### 5.2 Sourcing

**No minimum number of quotes** (decided 2026-10-15): three quotes are good
when they exist, one is acceptable. HIS does not want a rule here, so there
are no amount tiers and no exception workflow.

« Source » creates the first RFQ from the request lines (quantities, UoM,
required date as `date_planned`, analytic distribution, link back to the
request line). If the officer wants to compare, the other suppliers are added
with Odoo's « Create alternative », which copies the lines.

When the products are on an active blanket order (§6), « Source » proposes a
call-off from it instead: supplier and prices are already agreed.

### 5.3 Supplier answer — extension of `purchase.order` (RFQ stage)

| Field | Type | Rule |
|---|---|---|
| `his_request_id` | `his.purchase.request` | Set by « Source »; copied to alternatives |
| `his_supplier_answer` | Selection | `pending` (default), `quoted`, `declined`, `no_answer` |
| `his_quote_ref` | Char | Supplier's proforma number |
| `his_quote_date` | Date | Date on the proforma |
| `his_quote_valid_until` | Date | Validity of the proforma; warn when expired at confirmation |
| `his_answer_note` | Text | Observations (« available from stock », « brand X only ») |

The supplier's promised delivery goes in the **standard `date_planned`** of
each line, so Odoo's « earliest date » highlight keeps working. No separate
lead-time picklist.

Rules:
- `quoted` requires every line to have a positive price, a proforma reference
  and a proforma date. A genuinely free item is a line with price 0 and a
  mandatory note; it does not make the whole RFQ count as zero.
- `declined` and `no_answer` RFQs **cannot be confirmed**. Marking one sets its line quantities to 0 so the
  comparison ignores it (Odoo already skips zero totals).
- The supplier answer is a business field; the Odoo state (`draft`, `sent`,
  `purchase`, `cancel`) is not repurposed.

### 5.4 Supplier choice — extension of `purchase.order` (confirmation)

Kept light, since HIS does not focus on comparison. On confirmation of an RFQ
that has **at least one other `quoted` alternative**, a small wizard asks:

| Field | Rule |
|---|---|
| `his_choice_criterion` | Selection: `lowest_price`, `earliest_delivery`, `quality`, `only_supplier`, `other`; pre-filled with `lowest_price` when this RFQ is the cheapest |
| `his_choice_note` | Optional |
| `his_chosen_by_id` | Current user, read-only |
| `his_chosen_on` | Now, read-only |

With a single RFQ there is no wizard: the criterion is set to `only_supplier`
silently, so the Fiche de choix fournisseur can still be printed.

Rules:
- After confirmation the choice fields are read-only for everyone. A change
  means cancelling the order and choosing again; both events stay in the
  chatter.
- The competing RFQs are cancelled through Odoo's own warning wizard.

### 5.5 Approval — native

Use Odoo's « Purchase Order Approval » (company setting
`po_double_validation = two_step`, amount `po_double_validation_amount`).
Orders above the amount go to `to approve` and only a purchase manager can
approve them. Default amount: **0, every order is approved** — consistent
with monthly orders not skipping approval (§6.2); to raise later if approvals
become a bottleneck (§11, question 1).

**Who approves (decided by Mohamed, 2026-10-15):** the executive director
approves most purchases; the purchase manager approves POS purchases, and the
director may step in there too. Odoo lets any purchase manager approve any
order, so `his_purchase` adds the routing:

| `his_purchase_domain` | Meaning | Who can approve |
|---|---|---|
| `pos` | Supplies for the points of sale: Cafétéria, Restaurant, Copy Center only (goods for sale and their ingredients/consumables) | Purchase manager **or** executive director |
| `general` | Everything else (IT, maintenance, office, furniture, services) | Executive director only |

`his_purchase_domain` is set on the request from the requester's department
(a department setting), editable by the purchasing officer before sourcing,
copied to the RFQs and orders; on a blanket order it is set when the
agreement is created. Reorder-rule RFQs take `pos` when their destination is
a counter or the Restaurant, `general` otherwise.

Odoo still has one approval amount per company; the routing decides who may
approve above it.

### 5.6 No duplicate orders

- A request line's `qty_ordered` cannot exceed `product_qty` on confirmation,
  unless a purchase manager authorises a top-up (logged in the chatter).
- Splitting a line between two suppliers is allowed (Odoo's « Choose » works
  per line); the sum of confirmed quantities still respects the rule above.
- When every line is fully ordered the request moves to `ordered`; when every
  order is received and billed it moves to `done`.

### 5.7 Receipt and bill — native

- Receipt from the order (`purchase_stock`), printed as **Bon de réception**.
- Vendor bills with Odoo's bill control on **received quantities** (setting
  `purchase_method = receive` as the default for stocked products), so the
  accountant pays what was received.

### 5.8 Reminders and escalation

Purchase requests get forgotten at HIS. The rule: **at every step one person
owns the next action, with a due date; when it is missed, the system reminds
them, then escalates.** Nothing depends on someone remembering to check.

**Who owns each step, and by when** (delays in working days, stored in
settings; the 2 / 2 / 5 days were confirmed by Mohamed on 2026-10-15). The
escalation chain is **owner → purchase manager → executive director**; when
the owner is already the purchase manager, the escalation goes straight to
the director.

| Step | Owner | Due | Reminder to the owner | Escalation to |
|---|---|---|---|---|
| Request `submitted` | Department head | 2 days | at due date | Purchase manager, 2 days later; director 2 days after that |
| Request `approved` (not sourced yet) | Purchasing officer | 2 days | at due date | Purchase manager, 2 days later; director 2 days after that |
| RFQ sent, answer `pending` | Purchasing officer | `his_reply_by` (default: sent + 5 days) | « Chase supplier » at reply-by date | Purchase manager, 3 days later |
| Order `to approve`, domain `pos` | Purchase manager | 2 days | at due date | Executive director, 2 days later |
| Order `to approve`, domain `general` | Executive director | 2 days | at due date | — (reminder repeated every 2 days, shown in the weekly digest) |
| Monthly order not confirmed (§6.2) | Warehouse manager | review due date | at due date | Purchase manager, 1 day later |
| Order confirmed, not received by `date_planned` | Purchasing officer | `date_planned` | « Late delivery » the day after | Purchase manager, 3 days later |
| Request not ordered and `date_required` within 5 days | Purchasing officer | — | alert, whatever the state | Purchase manager, at the same time |

**Mechanism — standard Odoo activities, driven by one daily cron:**
- Each transition schedules a `mail.activity` on the owner with the due date
  above (activity types created by the module: « Approve purchase request »,
  « Source purchase request », « Chase supplier », « Late delivery »). Odoo
  emails the owner when the activity is assigned, and it shows in their
  activity menu (clock icon) until done. The activity is marked done
  automatically when the step is completed, and replaced if the owner changes.
- A daily cron (`_cron_purchase_reminders`) finds overdue steps: first a
  reminder email to the owner and a note in the chatter; after the escalation
  delay, an activity and an email to the escalation person. Each reminder is
  counted (`his_reminder_count`) and visible on the request.
- A **weekly digest** (Monday morning) to the purchase managers and the
  executive director: every open
  request with its state, owner, days in state and required date, oldest
  first.
- A **« Remind » button for the requester** on their submitted or approved
  request: posts a message to the current owner and emails them. At most once
  per 24 hours per request; logged in the chatter.

**Chasing suppliers:**
- `his_reply_by` (Date) on the RFQ, printed on the Demande de proforma.
- At the reply-by date the officer gets « Chase supplier »; one click on
  « Send reminder » emails the supplier the « Relance demande de proforma »
  template with the proforma attached again. The cron also **sends it
  automatically** at the reply-by date (decided 2026-10-15), then again every
  3 days while the answer is still `pending`, at most twice; the officer can
  still send one by hand at any time.
- Late deliveries on confirmed orders: Odoo's native **receipt reminder**
  (supplier setting « Receipt Reminder », daily cron « Purchase reminder »)
  emails the supplier N days before the promised date; switch it on for
  regular suppliers. The « Late delivery » activity covers the day after.

**Seeing what is late:**
- `his_state_since` (Datetime) on the request, set at each transition;
  `his_days_in_state` computed; `his_is_late` (Boolean, stored, set by the
  cron) for filtering and red rows in the list.
- Default filter « Late » and a kanban grouped by state for the purchase team.

Emails go through the normal mail queue (the mail cron runs hourly): a
reminder may arrive up to an hour after the cron, which is fine here.

## 6. Recurring monthly supplier and ad hoc needs

Situation today: the stock team has **one supplier who delivers the
Restaurant's needs every month**, and **needs still come up between
deliveries**. Both are handled, with one agreement as the backbone.

### 6.1 The agreement: a blanket order (native)

The monthly supplier gets a **blanket order** (`purchase.requisition`,
`requisition_type = blanket_order`) for **one year** (decided 2026-10-15;
`date_start` / `date_end` on the agreement), with the agreed products, unit prices and total quantities. It is
set up once a year — this is where the supplier and prices are chosen.
Every order placed on it, monthly or ad hoc, still goes through approval
(§5.5).

Thirty days before `date_end`, « Renew agreement » is scheduled on the
purchase manager (reminded and escalated as in §5.8). The monthly cron stops
at `date_end`: no order is created on an expired agreement.

What Odoo does natively when it is confirmed (verified in the 19.0 source):
it creates a vendor price (`product.supplierinfo`) for each line, tied to the
agreement. From then on **any** RFQ for those products — monthly, ad hoc or
from a reorder rule — picks this supplier and this price automatically, and
the agreement shows quantity ordered against quantity agreed.

### 6.2 The monthly order: a recurrence on the blanket order (custom)

`his_purchase` adds to the blanket order:

| Field | Rule |
|---|---|
| `his_recurring` | Boolean: this agreement has a monthly order |
| `his_delivery_day` | Day of the month the supplier delivers: **1** for the Restaurant supplier (start of the month) |
| `his_prepare_days` | How many days before delivery the draft order is created: default **10** |
| `his_owner_id` | Who reviews and sends the monthly order: the **warehouse manager** |
| `his_recurring_qty` (on each line) | Usual monthly quantity |

Timeline for a delivery on the 1st (decided by Mohamed, 2026-10-15: owner =
warehouse manager, delivery to the main warehouse, approval **not** skipped):

| When | What |
|---|---|
| Delivery − 10 days (≈ 21st) | Cron creates the **draft RFQ** on the blanket order with the usual quantities, `date_planned` on the 1st, and schedules « Review monthly order » on the warehouse manager |
| Delivery − 7 days (≈ 24th) | Review due: the warehouse manager adjusts quantities (stock on hand, events, holidays) and confirms |
| Delivery − 5 days (≈ 26th) | Approval due (domain `pos`: purchase manager or executive director, §5.5) |
| After approval | Order sent to the supplier; native receipt reminder before the 1st |

If a step is late, §5.8 reminds and escalates like any other step. The cron
creates one monthly order per agreement per month, never two.

### 6.3 Needs between two deliveries

A need can come from a **purchase request** (Restaurant staff) or a **reorder
rule** (`his_stock_mdm` min/max when stock falls low).

| The product is… | Needed… | What happens |
|---|---|---|
| on the active blanket order | **after** the next monthly order is prepared | « Add to next monthly order »: the request line is linked to the agreement and the cron adds its quantity to the next monthly draft. No separate order, no extra delivery. |
| on the active blanket order | **before** it | « Order now »: a call-off from the blanket order (no comparison: supplier and price already agreed; approval as usual). |
| not on any blanket order | — | Normal request flow (§5.2). |

The purchasing officer picks between the first two from the request (the
system proposes one from the dates).

Reorder rules: for products on the monthly order, keep min/max as a **safety
net** (a low minimum), not as the main supply, or they would compete with
the monthly order. Odoo's replenishment normally adds a need to an existing
draft RFQ of the same supplier rather than opening a new one, so a shortage
noticed while the monthly draft is open lands in it (to verify on staging).
Reorder-rule RFQs carry no `his_request_id`, which is how reports tell them
apart; they go through approval like any other order.

### 6.4 Where the goods go

The monthly delivery is received in the **main warehouse** (decided
2026-10-15), then moved to the Restaurant with the weekly internal transfers
already designed (« Réappro Restaurant », `RESIN`).

## 7. Algerian supplier identifiers — `his_partner_dz`

On `res.partner` (companies) and `res.company`:

| Field | Label (fr.po) | Rule |
|---|---|---|
| `vat` (standard) | NIF | 15 digits for legal persons (format check, to confirm with the accountant) |
| `l10n_dz_rc` | Registre de commerce (RC) | Free text, e.g. `16/00-1234567B21` |
| `l10n_dz_nis` | NIS | Digits |
| `l10n_dz_ai` | Article d'imposition (AI) | Digits |
| `l10n_dz_tax_regime` | Régime fiscal | `real` (charges VAT), `ifu` (flat tax, no VAT), `auto_entrepreneur` (no VAT) |

Rules:
- A supplier must have NIF and RC before an order to it can be confirmed
  (decided 2026-10-15; identifier for individuals: §11, question 4).
- A supplier under `ifu` or `auto_entrepreneur` gets a fiscal position that
  maps the purchase VAT taxes to `l10n_dz_vat_purchase_0` (created by the
  module if `l10n_dz` has none suitable), so its quotes compare correctly
  against VAT-charging suppliers.
- The company's own RC, NIF, NIS, AI print in the header of every purchase
  document.

## 8. Printed documents

All reports are QWeb, values read from the records (one source of truth), dates
in the company's timezone and `dd/mm/yyyy`, amounts in DA.

| Document (fr.po title) | Printed from | Minimum content |
|---|---|---|
| **Demande de proforma** | RFQ | HIS header with legal identifiers; supplier and its RC/NIF; RFQ reference and date; request reference; lines (product, description, quantity, UoM) **without prices**; reply-by date; delivery address; contact of the purchasing officer |
| **Fiche de choix fournisseur** | Confirmed order with alternatives | Request reference, requester, department, date; for each supplier: answer, proforma ref and date, HT / VAT / TTC per line and total, promised date; comparison basis (TTC, Odoo's native ranking); chosen supplier, criterion, note; chosen by, approved by, dates; signature boxes for the officer and the approver |
| **Bon de commande** | Confirmed order | Order number and date; HIS and supplier legal identifiers; delivery address; lines with unit price, VAT rate, HT; totals HT, VAT per rate, TTC; **amount in words**; promised date; payment terms; request reference; signature box |
| **Bon de réception** | Receipt | Receipt number and date, order reference, supplier, lines ordered / received, storekeeper, signature boxes |

The draft's « PV de commission ad hoc » is dropped: there is no committee.

## 9. Preconditions before going live

1. **Stock valuation accounts.** 19 product categories are in `real_time`
   valuation without accounts: the first purchase receipt at real cost will
   fail. Set the `l10n_dz` stock accounts (31x / 60x) on those categories, or
   switch them to periodic valuation, with the accountant.
2. **Purchase taxes on products.** Catalogue products need the right purchase
   tax (19 %, 9 % or exempt); default is `l10n_dz_vat_purchase_19`.
3. **Suppliers.** Supplier lists are the source of truth (`his_stock_mdm`
   rule); import suppliers with their identifiers before the first order.
4. Install `purchase`, `purchase_stock`, `purchase_requisition` on staging,
   tested on a disposable copy first, then the HIS modules.

## 10. Algerian context — what this design does and does not cover

- **Pro formas from several suppliers** before ordering is standard practice;
  the optional comparison records it without a committee or a minimum.
- **Public procurement law** (décret présidentiel 15-247) binds public bodies
  only. HIS is private: the thresholds here are internal policy and can be
  set freely.
- **Stamp duty on cash payments and the obligation to pay by cheque or
  transfer above a threshold** apply to how bills are paid, not to purchasing.
  To be handled in accounting with the accountant; the exact current
  thresholds must come from them, not from this document.
- **Invoice legal mentions** (RC, NIF, NIS, AI, HT/VAT/TTC, amount in words)
  are carried by `his_partner_dz` so vendor bills can be checked against them.

## 11. Open questions for Mohamed

1. **Approval amount.** Default is 0 (every order approved, §5.5). Keep it, or
   approve only above an amount?
2. **Companies.** Are HIS, HTC and IRA separate companies in Odoo, or one
   company with cost centres? This decides `company_id` vs analytic only, and
   whose letterhead prints.
3. **Request approval.** Is the department head the right approver for every
   request, including the Restaurant and Cafétéria managers' own requests?
4. **Individuals as suppliers.** NIF and RC are required for companies. For
   an individual with no RC (e.g. a craftsman), which identifier is required
   instead — national ID number, NIF only, nothing?
5. **Other blanket orders.** Besides the Restaurant's monthly supplier, which
   suppliers get a yearly agreement (Cafétéria, paper for the Copy Center,
   cleaning products)?
6. **Monthly order lead time.** Does the supplier need the order 10 days
   before the 1st, or is less enough?
7. **Input VAT (later).** Start with 19 % and the native TTC comparison; ask
   the accountant whether input VAT is recoverable before the first year-end.

Decided on 2026-10-15:
- Reminder delays 2 / 2 / 5 days; escalation above the purchase manager =
  executive director; supplier reminders sent automatically.
- Executive director approves general purchases; purchase manager or director
  approves POS purchases; POS = Cafétéria, Restaurant, Copy Center only.
- The person who chose the supplier may also approve the order.
- No minimum number of quotes.
- Monthly supplier: yearly agreement, delivery at the start of the month to
  the main warehouse, owned by the warehouse manager, with approval.
- Suppliers need NIF and RC (exception for individuals, question 4).
- Purchase VAT: 19 % by default, comparison on TTC.
- Purchase managers exist but have no Odoo users yet: created at go-live.

## 12. Acceptance tests

| ID | Test |
|---|---|
| AT-01 | A requester creates a request with one line and a justification; it gets a `DA/` reference and can be submitted. |
| AT-02 | Submitting without justification, required date or line is refused, and the error names what is missing. |
| AT-03 | A requester cannot see another department's requests; a department head sees their department's. |
| AT-04 | An approved request is sourced with one RFQ and confirmed without comparison and without the choice wizard; the criterion is `only_supplier`. |
| AT-05 | With two `quoted` alternatives, confirming one opens the choice wizard, pre-filled with `lowest_price` when it is the cheapest. |
| AT-06 | An RFQ marked `declined` cannot be confirmed and is never highlighted as best price. |
| AT-07 | Suppliers A (20 000 DA) and B (19 000 DA) quoted on the same basis: comparison highlights B; choosing A is allowed, with criterion other than `lowest_price`. |
| AT-08 | After confirmation, the choice criterion and note cannot be changed by anyone. |
| AT-09 | With approval amount 0 every order goes to `to approve`; the officer who chose the supplier can approve it if they are a purchase manager. |
| AT-10 | A second order cannot exceed the requested quantity of a request line without a manager's authorisation. |
| AT-11 | A supplier under IFU quotes without VAT; its total is compared TTC against a VAT-charging supplier's. |
| AT-12 | An order to a company supplier without NIF or RC cannot be confirmed. |
| AT-28 | The proforma reminder is emailed automatically at the reply-by date, then every 3 days, at most twice. |
| AT-29 | Thirty days before a blanket order ends, « Renew agreement » is scheduled; no monthly order is created after `date_end`. |
| AT-13 | Demande de proforma, Fiche de choix fournisseur and Bon de commande show the same references, suppliers, quantities and amounts as the records; the Demande de proforma shows no prices. |
| AT-14 | A reorder rule creates an RFQ without a request; above the approval amount it still requires approval. |
| AT-15 | Receiving the order creates a stock move valued at the order price without error (precondition 9.1). |
| AT-16 | Every label in a French session comes from `fr.po`; no French string in the Python or XML sources. |
| AT-17 | Submitting a request schedules « Approve purchase request » on the department head; approving it marks the activity done and schedules « Source purchase request » on the officer. |
| AT-18 | A request left `submitted` past its due date gets a reminder email to the department head; 2 days later the purchase manager gets an activity and an email. Both appear in the chatter. |
| AT-19 | The requester's « Remind » works once, and is refused a second time within 24 hours. |
| AT-20 | An RFQ still `pending` at its reply-by date creates « Chase supplier »; « Send reminder » emails the supplier the relance template. |
| AT-21 | The weekly digest lists every open request, oldest first, with its owner. |
| AT-22 | Confirming a blanket order makes a new RFQ for its products default to that supplier and price. |
| AT-23 | With delivery day 1 and 10 preparation days, the cron creates the monthly draft RFQ 10 days before the 1st, with the usual quantities, assigned to the warehouse manager, and creates only one per month. |
| AT-24 | A request for a blanket-order product needed after the next monthly order is added to that monthly draft; one needed sooner becomes a call-off without comparison. |
| AT-25 | A confirmed monthly order goes through approval like any other order (domain `pos`). |
| AT-26 | A `general` order above the amount can be approved by the executive director and is refused for a purchase manager; a `pos` order can be approved by either. |
| AT-27 | A `pos` order left `to approve` 2 days past due escalates to the executive director. |
