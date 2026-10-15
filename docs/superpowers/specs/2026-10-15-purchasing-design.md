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
| Sourcing tiers by amount (direct / three quotes) | Imports (foreign currency, bank domiciliation, customs): no case yet |
| Supplier answer on each RFQ (quoted / declined / no answer) | Budget control that blocks a request: analytic tagging only, budgets later |
| Documented supplier choice, locked after confirmation | Supplier portal, e-signature |
| Order approval above a threshold (native Odoo) | Stamp duty and cash-payment limits: accounting, not purchasing (see §10) |
| Blanket orders for recurring suppliers (food, consumables) | Composite products: not a purchasing concern |
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
  currency.** That is the right basis only if HIS cannot recover input VAT
  (§11, question 3). It also **skips lines with a zero total**, so a supplier
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
| `his_purchase` | `purchase`, `purchase_stock`, `purchase_requisition`, `hr`, `his_stock_mdm`, `his_partner_dz` | Purchase request, sourcing tiers, supplier answer, supplier choice, reports, groups and rules |

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
| Purchase manager | `purchase.group_purchase_manager` | Approve orders above the amount; authorise exceptions (single source, not-cheapest choice above the amount, split orders) |
| Storekeeper | `stock.group_stock_user` | Receive goods against the order |
| Accountant | `account.group_account_invoice` | Record and check vendor bills |

Separation of duties (default, to confirm): **the person who approves an
order cannot be the one who chose the supplier**. Odoo does not enforce this;
`his_purchase` does, server-side.

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
| `estimated_amount` | Monetary, computed | Sum of line estimates; decides the sourcing tier |
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
| `estimated_price_unit` | ≥ 0; used for the tier only, never sent to suppliers |
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

### 5.2 Sourcing tiers

When the officer clicks « Source », the tier is set from `estimated_amount`
(thresholds stored in settings, values to confirm, §11 question 1):

| Tier | Estimated amount | Rule |
|---|---|---|
| **Direct** | below `direct_purchase_limit` | One RFQ to one supplier. No comparison needed. |
| **Three quotes** | from `direct_purchase_limit` | At least **three** alternative RFQs, or a documented exception (single source: exclusive supplier, urgency, brand imposed) authorised by a purchase manager |
| **Blanket order** | any amount | A call-off from an active blanket order skips comparison: the prices were agreed when the blanket order was set up |

« Source » creates the first RFQ from the request lines (quantities, UoM,
required date as `date_planned`, analytic distribution, link back to the
request line). The other suppliers are added with Odoo's « Create
alternative », which copies the lines.

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
- `declined` and `no_answer` RFQs **cannot be confirmed** and do not count
  towards the three quotes. Marking one sets its line quantities to 0 so the
  comparison ignores it (Odoo already skips zero totals).
- The supplier answer is a business field; the Odoo state (`draft`, `sent`,
  `purchase`, `cancel`) is not repurposed.

### 5.4 Supplier choice — extension of `purchase.order` (confirmation)

On confirmation of an RFQ that belongs to a request in the **three quotes**
tier, a wizard asks:

| Field | Rule |
|---|---|
| `his_choice_criterion` | Selection: `lowest_price`, `earliest_delivery`, `quality`, `single_source`, `other` |
| `his_choice_note` | Required unless the criterion is `lowest_price` **and** this RFQ is the lowest on every line |
| `his_chosen_by_id` | Current user, read-only |
| `his_chosen_on` | Now, read-only |

Rules:
- Confirmation is refused when fewer than three alternatives are `quoted`,
  unless a purchase manager has recorded the single-source exception.
- Choosing an offer that is not the lowest requires a note; above the
  approval amount it also requires a purchase manager.
- After confirmation the choice fields are read-only for everyone. A change
  means cancelling the order and choosing again; both events stay in the
  chatter.
- The competing RFQs are cancelled through Odoo's own warning wizard.

### 5.5 Approval — native

Use Odoo's « Purchase Order Approval » (company setting
`po_double_validation = two_step`, amount `po_double_validation_amount`).
Orders above the amount go to `to approve` and only a purchase manager can
approve them. `his_purchase` adds the separation-of-duties check of §4.

Odoo has one amount per company and one approval level. If HIS needs two
levels (e.g. purchase manager, then director above a higher amount), that is
an addition to decide (§11, question 1).

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

## 6. Replenishment from `his_stock_mdm`

`his_stock_mdm` reorder rules (counters, Restaurant) create draft RFQs through
`purchase_stock` without any request. Default (to confirm): **they bypass the
request but not the controls** — they are treated as the Direct tier, keep the
approval amount, and when a blanket order exists for the product the RFQ is
created against it. They carry no `his_request_id`, which is how reports tell
them apart.

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
  (default; exceptions for individuals, to confirm).
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
| **Fiche de choix fournisseur** | Confirmed order with alternatives | Request reference, requester, department, date; for each supplier: answer, proforma ref and date, HT / VAT / TTC per line and total, promised date; comparison basis (HT or TTC, §11 question 3); chosen supplier, criterion, note; chosen by, approved by, dates; signature boxes for the officer and the approver |
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
  the three-quotes tier formalises it without a committee.
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

1. **Thresholds and approvers.** Amount below which a direct purchase is
   allowed? Amount above which a purchase manager must approve the order? Is
   one approval level enough, or does a director approve above a higher
   amount? Who are the purchase managers?
2. **Companies.** Are HIS, HTC and IRA separate companies in Odoo, or one
   company with cost centres? This decides `company_id` vs analytic only, and
   whose letterhead prints.
3. **Input VAT.** Can HIS deduct the VAT it pays on purchases (question for
   the accountant)? If not, comparison is on TTC (Odoo's native basis); if
   yes, it must be on HT and the comparison view needs an HT ranking.
4. **Recurring purchases.** Which suppliers get blanket orders (food for the
   Restaurant and Cafétéria, paper for the Copy Center, cleaning products)?
   For how long are prices agreed?
5. **Request approval.** Is the department head the right approver for every
   request, including the Restaurant and Cafétéria managers' own requests?
6. **Separation of duties.** Confirm that the approver of an order must not be
   the person who chose the supplier.
7. **Individuals as suppliers.** Can HIS buy from an individual with no RC
   (e.g. a craftsman)? If yes, which identifiers are required instead?

## 12. Acceptance tests

| ID | Test |
|---|---|
| AT-01 | A requester creates a request with one line and a justification; it gets a `DA/` reference and can be submitted. |
| AT-02 | Submitting without justification, required date or line is refused, and the error names what is missing. |
| AT-03 | A requester cannot see another department's requests; a department head sees their department's. |
| AT-04 | An approved request below the direct limit is sourced with one RFQ and confirmed without comparison. |
| AT-05 | An approved request above the direct limit: with two quoted RFQs confirmation is refused; with three it is allowed. |
| AT-06 | An RFQ marked `declined` cannot be confirmed, does not count towards three quotes, and is never highlighted as best price. |
| AT-07 | Suppliers A (20 000 DA) and B (19 000 DA) quoted on the same basis: comparison highlights B; choosing A without a note is refused. |
| AT-08 | After confirmation, the choice criterion and note cannot be changed by anyone. |
| AT-09 | Above the approval amount the order goes to `to approve`; the user who chose the supplier cannot approve it; a purchase manager can. |
| AT-10 | A second order cannot exceed the requested quantity of a request line without a manager's authorisation. |
| AT-11 | A supplier under IFU quotes without VAT; comparison against a VAT-charging supplier uses the same basis (§11, question 3). |
| AT-12 | An order to a supplier without NIF or RC cannot be confirmed. |
| AT-13 | Demande de proforma, Fiche de choix fournisseur and Bon de commande show the same references, suppliers, quantities and amounts as the records; the Demande de proforma shows no prices. |
| AT-14 | A reorder rule creates an RFQ without a request; above the approval amount it still requires approval. |
| AT-15 | Receiving the order creates a stock move valued at the order price without error (precondition 9.1). |
| AT-16 | Every label in a French session comes from `fr.po`; no French string in the Python or XML sources. |
