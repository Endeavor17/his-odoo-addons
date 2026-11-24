# Finance controls on the points of sale

Date: 2026-11-24. Source: Finance's corrected point-of-sale procedure
(`Procedure_PDV.docx`, "Procédure de gestion comptable et de contrôle des
points de vente", still a working version) and Mohamed's decisions of
2026-11-24. Follows `2026-11-22-purchase-finance-controls-design.md`
(`his_purchase_finance`, merged in PR #86 and #87).

## 1. Why

Finance wants the three points of sale (Copy Center, Cafeteria, Restaurant)
and its own two cash boxes (Finance, Direction) under one set of rules:

- each activity has its own journals and accounts;
- every cash gap is declared, explained, reviewed and decided by Finance
  before it becomes a loss or a gain;
- money moves between boxes against a slip both sides confirm;
- refunds, price changes and discounts are authorised and justified;
- Finance can follow repeat gaps per cashier and per box.

Today a cashier does all of this alone. Cashiers sit on pos_hr's "advanced"
list, which the till treats as a manager. Odoo books every closing gap straight
to the cash journal's loss or profit account, and nothing tracks it afterwards.

Asking Finance the 20 open questions would take about 15 days. Mohamed decided
to build on our own recommendations instead.

## 2. Decisions (Mohamed, 2026-11-24)

| # | Decision |
|---|----------|
| 1 | **Closing with a gap:** the cashier closes, and an explanation is required. The gap goes **provisionally to 476**, and a discrepancy form opens automatically: cashier → POS manager → Finance. Finance's "final close" means deciding the form and posting the regularisation (476 → 657 / 757, or a correction). Why: Odoo allows one open session per till, so a literal "only the Finance head closes" would stop sales the next morning. |
| 2, 4, 7 | The approvers, the Finance head's deputy and the cash box holders are not named yet. Build on roles and fields, and assign people later. |
| 3 | Gaps of 1 to 5 DA: POS manager review plus Finance review (§6.2 wins over §6.3). |
| 5 | The Finance head gets a personal Odoo login. |
| 6 | The Finance and Direction cash boxes follow **the same pattern** as the tills: opening and closing counts, and the same discrepancy form. |
| 8 | The Direction validates the gaps of the Finance cash box. Mohamed confirmed (2026-11-24) that this means **the Director does the review step** on a Finance-box form, and Finance then decides and posts as on any form. No rule stops a box holder from acting on their own box's form. |
| 9 | An opening needs the POS manager **only when** the counted float differs from the previous close. Mohamed confirmed (2026-11-24) that this means **review afterwards**: the cashier opens alone with a required explanation, and the POS manager reviews the gap form. No PIN at opening, so the till never waits. |
| 10 | Refund, price change, discount: **POS manager PIN on the till plus a required reason.** This reverses the 2026-10-27 "the cashier does it alone". |
| 11 | The automatic Copy Center black-and-white print discount (PR #81) counts as authorised. |
| 12 | Handover to Finance **every evening**. A fixed float stays in the till. A printed slip is counted by two people, and both the amount sent and the amount received are confirmed. |
| 13 | Cash put into a till comes only from the Finance box, through 581. |
| 14 | Surprise counts stay on paper, attached to the form if they find a gap. Nothing to build. |
| 15 | Goods the Cafeteria resells as bought → **700200**. |
| 16 | 476 is used as is. |
| 17 | 411100 / 411200 / 411300 are for invoiced customers only. Counter sales don't use them. |
| 18 | Cash only (no card, no cheque). Meal plans → 701300 at sale. |
| 19 | VAT stays at 9% everywhere (`his_pos_tva`) until Finance gives rates per product family. |
| 20 | Journal codes VGEN / VCOP / VCAF / VRES (sales) and CDIR / CFIN / CCOP / CCAF / CRES (cash). Odoo allows 5 characters at most. |

## 3. What Odoo 19 already does (read in the `odoo:19.0` image, 2026-11-24)

- **Closing gap:** `pos.session._post_statement_difference` posts the gap as a
  cash statement line whose counterpart is the cash journal's
  `loss_account_id` (shortage) or `profit_account_id` (surplus). If those two
  accounts are 476000, the provisional entry of §7.1 happens with no code.
- **"Maximum difference" (`set_maximum_difference`, `amount_authorized_diff`)
  is checked only in the closing popup** (`closing_popup.js`,
  `hasUserAuthority`). The server never checks it. `_cannot_close_session` is
  the hook meant for server-side checks. It runs in `close_session_from_ui`.
- **Closing call order from the popup:** `post_closing_cash_details(counted)`,
  then `update_closing_control_state_session(notes)`, which stores
  `closing_notes`, then `close_session_from_ui`. So `closing_notes` is already
  set when `_cannot_close_session` runs.
- **Opening:** `_set_opening_control_data` stores the counted float as
  `cash_register_balance_start` and only posts a chatter message about the
  difference. **No accounting entry:** an overnight gap disappears from the
  books.
- **Till roles (pos_hr):** an employee whose user is in `group_pos_manager`,
  or who is on the config's `advanced_employee_ids`, gets `_role = "manager"`.
  "basic" gives `"cashier"`, "minimal" gives `"minimal"`.
  - The cash in/out button shows only for `"manager"`, and its server side also
    needs `group_pos_manager` or `account.group_account_invoice`.
  - `restrict_price_control` blocks price changes for non-managers.
  - Nothing restricts refunds or discounts, except that "minimal" loses the
    "−" key.
  - PINs are checked in the browser against hashes (`get_barcodes_and_pin_hashed`).
- **Cash in/out** (`try_cash_in_out`) creates a statement line in the session
  with no counterpart (it lands in the journal's suspense account).
- **Income account of a till sale:**
  `pos.order.line._prepare_base_line_for_taxes_computation` takes the product's
  income account (from its category), then applies the order's fiscal position
  `map_account`. A till's default fiscal position can therefore send the same
  product to a different account per till. Fiscal positions are not used
  anywhere in the repo today.

## 4. Approaches

**A. The gap at closing.**
- (a) Block the close until Finance acts. The till can't sell the next
  morning, so this is ruled out.
- (b) Close without posting anything and hold the gap off the books until
  Finance decides. Odoo posts it inside the close itself, so this means
  rewriting `_validate_session`. Heavy, and fragile on upgrades.
- **(c) chosen:** let Odoo post the gap to 476 (journal loss and profit
  accounts = 476000), then open a form that Finance closes by posting 476 →
  final account. Setup does most of it, and it matches §7.1 and §7.2 exactly.

**B. Finance and Direction cash boxes ("same pattern").**
- (a) Make them POS configs with no products. Ruled out: supplier payments from
  these boxes are `account.payment` on the cash journal and are not session
  statement lines. The session's expected cash would ignore them.
- **(b) chosen:** a daily count record on the cash journal. The expected amount
  is the account balance at that moment. A gap opens the same discrepancy
  form. Same pattern for the user: open count, close count, explanation,
  form. Different mechanism, so that the payments are counted.

**C. Authorising refunds, price changes and discounts.**
- (a) Native only: move cashiers to "basic" and turn on
  `restrict_price_control`. That covers prices only, gives no reason field,
  and shows "Access denied" with no way to get a manager.
- **(b) chosen:** cashiers move to "basic" (native, which also hides the cash
  in/out button). Our own till dialog asks a manager to pick their name, type
  their PIN and give a reason, and records all three on the order line.

**D. Handover to Finance.**
- (a) The native cash-out with a reason. Managers only, no receiving side, no
  slip.
- **(b) chosen:** a transfer record, sent from the till and received in the
  back end, with a printed slip and accounting through 581.

## 5. Design

One new module, **`his_pos_finance`**. It depends on `point_of_sale`,
`pos_hr`, `his_stock_mdm` (tills, cashier sync), `his_purchase_finance`
(`group_finance`, account-creation pattern) and `his_purchase` (Direction
group). Add it to the CI `MODULES` list.

### 5.1 Accounts, journals, fiscal positions (hook, idempotent, like `his_purchase_finance/hooks.py`)

Create the missing accounts. The l10n_dz chart already has some of them; CI
loads the generic chart.

| Code | Label | Type |
|---|---|---|
| 530000 / 530001 / 530100 / 530200 / 530300 | Caisse – Direction / Département Finance / Copy Center / Cafétéria / Restaurant | liquidity (cash) |
| 581000 | Virements internes | current asset (company `transfer_account_id`) |
| 476000 | Écarts de caisse à régulariser | current asset, reconcilable |
| 657000 / 757000 | Autres charges / produits exceptionnels | expense / income |
| 700100 / 700200 / 700300 | Ventes de marchandises – Copy Center / Cafétéria / Restaurant | income |
| 701200 / 701300 | Ventes de produits finis – Cafétéria / Restaurant | income |
| 706000 / 706100 / 706200 | Prestations de services – Société / Autres / Copy Center | income |
| 411000 / 411100 / 411200 / 411300 | Clients – Général / Copy Center / Cafétéria / Restaurant | receivable |
| 445600 / 445720 | TVA déductible / collectée – Global | tax accounts, assigned to the 9% taxes of `his_pos_tva` |

700300 is our call. The procedure has no account for drinks the Restaurant
resells, and it sells them since 2026-10-27.

Journals:
- sales VGEN, VCOP, VCAF, VRES;
- cash CDIR, CFIN, CCOP, CCAF, CRES, each on its 530 account, with
  `loss_account_id` and `profit_account_id` set to 476000.

Each till gets:
- its sales journal (`pos.config.journal_id`) and its invoice journal (the
  same one);
- a cash payment method on its cash journal (CCOP / CCAF / CRES);
- `cash_control` on and `set_maximum_difference` off;
- a default fiscal position "Revenue – <till>" that maps only income accounts:

| Till | Fiscal position maps |
|---|---|
| Copy Center | resale goods → 700100, services → 706200 |
| Cafeteria | resale goods → 700200, prepared products → 701200 |
| Restaurant | resale goods → 700300, meals → 701300 |

Base income per category: Copy Center supplies and Cafeteria and Restaurant
resale categories → 700xxx; print, copy and scan categories → 706200; meal
and menu products → 701300; Cafeteria prepared products → 701200.
**Meal plans → 701300** whichever till sells them. The Copy Center sells
top-ups, so the Copy Center position must not map 701300.

411 per activity: accounts created, **no automatic routing** (decision 17
leaves it to invoiced customers, and Finance sets the customer).

Setup runs in a hook and must refuse, with a clear message, while a till
session is open. Same rule as `his_pos_tva`: "close the tills before `-i`".

### 5.2 Till roles

In `his_stock_mdm`'s `_his_sync_tills`, cashiers go to **`basic_employee_ids`**
instead of `advanced_employee_ids`. POS managers (`group_pos_manager`, the
"POS Supervisor" role = *responsable du point de vente*) stay managers on
every till. Native effects:
- no cash in/out button for cashiers;
- `restrict_price_control = True` on the three tills.

The comment in `_his_sync_tills` ("ils font les entrees et sorties d'especes
et ferment la caisse") changes accordingly. Update
`his_stock_mdm/tests/test_caisses_postes.py`.

**Cashiers must still close.** pos_hr shows "Close Register" only to a
manager or to the user who opened the session
(`pos_hr/static/src/app/components/navbar/navbar.xml`). Our tills are opened
by a shared counter account, so a "basic" cashier would lose the button that
decision 1 relies on. Patch the navbar so that any cashier tapped in on the
till sees it.

**Tills may not pay out cash** (§4.1): `try_cash_in_out` refuses on the three
tills for everyone. Cash only leaves a till through a handover (5.5).

### 5.3 Authorisation on the till

When a cashier with role `"cashier"` does one of the following, a dialog opens:
- changes a line price;
- applies a manual discount (line or order);
- starts a refund from the ticket screen.

The dialog has three fields:
- a manager to pick, from the till's `"manager"` employees;
- that manager's PIN, checked like pos_hr's own login, in the browser against
  the hash;
- a reason, required.

On success the action goes through. The line stores `his_authorized_by_id`
(hr.employee), `his_authorization_reason` and `his_authorization_kind`
(price / discount / refund). These fields are sent with the order and are
visible on the order in the back end. A manager acting on the till is not
asked (their own name is recorded, reason still required).

The Copy Center rule discount, the 0 DA meal-on-credits flow and pricelists
set prices and discounts in code, not through the cashier's buttons. **They
must not trigger the dialog.** Hook the UI actions (numpad price and discount
modes, discount button, refund button), never the order-line setters.

`shortcut: enforced in the browser, like pos_hr's own PIN login; a server-side
check is impossible without telling coded prices from manual ones. Upgrade if
an audit asks for it.`

### 5.4 Discrepancy form (`his.cash.discrepancy`)

One record per gap, whatever its size (compare amounts with the currency,
any non-zero). Fields follow §8:

| Field | Content |
|---|---|
| `name` | sequence `ECART/2026/0001` |
| `date` | date and time of the count |
| `kind` | `opening`, `closing`, `handover`, `count` |
| `journal_id` | the cash box (CCOP, CCAF, CRES, CFIN, CDIR) |
| `session_id` | optional |
| `transfer_id` / `count_id` | optional |
| `holder_id` | res.users: the cashier's user, or the box holder |
| `holder_employee_id` | the till cashier who tapped in, when known |
| `expected`, `counted`, `amount` | `amount` signed, counted − expected |
| `nature` | computed: shortage / surplus |
| `tier` | computed: minor / significant / important / major, from four company settings (defaults 5, 2,000, 5,000 DA) |
| `explanation` | the holder's written explanation, required |
| `manager_note` | the reviewer's observations |
| `finance_decision` | accepted / refused / investigating |
| `finance_note` | Finance's notes |
| `provisional_move_id` | the 476 entry |
| `regularisation_move_id` | the final entry |
| `closed_date` | date of the final close |
| `state` | `to_review` → `finance` → `direction` (major tier only) → `closed` |

Chatter, with attachments for supporting documents and surprise-count reports.

**Where forms come from:**
- **Closing** (till): after the session closes with `cash_register_difference
  ≠ 0`. The provisional entry is the statement line Odoo just posted. The
  explanation comes from `closing_notes`.
- **Opening** (till): in `_set_opening_control_data`, when counted ≠ expected.
  Odoo posts nothing here, so **we post the provisional entry ourselves**:
  530x ↔ 476000, in the cash journal, as a statement line in the session. The
  explanation comes from `opening_notes`.
  - Keep `cash_register_balance_start` at the previous close's counted amount.
    Don't let Odoo overwrite it with the new count. `_compute_cash_balance`
    adds every statement line on top of `balance_start`, so the gap must be
    carried by the statement line alone, or it is counted twice.
  - Make sure the native opening chatter message still shows the difference.
- **Handover** and **count**: see 5.5 and 5.6.

**Required explanation:** `_cannot_close_session` returns an error when there
is a cash gap and `closing_notes` is empty. The closing and opening popups
also make the notes field required when a gap shows. Sessions closed from the
back end still get a form; the explanation is then filled on the form before
it can move on.

**Circuit and rights:**

| Step | Who | Action |
|---|---|---|
| `to_review` | POS manager (`group_pos_manager`). On a CFIN form: the Director. On a CDIR form: the Finance head. | comments, then sends to Finance |
| `finance` | minor and significant: any Finance user (`group_finance`); important and major: Finance head | decides accepted, refused or investigating |
| `direction` | Director (`his_purchase.group_purchase_director`) | approves or sends back |
| `closed` | | regularisation posted |

At the `finance` step:
- **Refused** sends the form back to `to_review` with the note.
- **Investigating** keeps it at `finance`; 476 stays open.
- **Accepted** asks for the counterpart account, with defaults 657000 for a
  shortage and 757000 for a surplus. Finance may pick another one to cover
  §6.5: 70x for an unrecorded sale, another 530 for a transfer error, an
  expense for an authorised outflow that wasn't recorded. Then:
  - minor, significant or important tier: the regularisation entry
    476000 ↔ counterpart is posted in a miscellaneous journal and reconciled
    with the provisional line, and the form closes;
  - major tier: the form goes to `direction` first, and the Director's
    approval posts and closes it.

Decision 3 (1–5 DA) is covered: the POS manager reviews and a Finance user
posts. Our call (§6.2 governs levels, §6.3 is read as "Finance posts"): any
Finance user may close minor and significant forms; the Finance head closes
important and major ones.

**New group: Finance Head** (`his_pos_finance.group_finance_head`, implies
`his_purchase_finance.group_finance`), with a new role "Finance Head" in
`his_role_catalogue`. The cashier and the POS manager can never post or edit
the amounts. Amounts and moves are read-only after creation.

`shortcut: manual journal entries on 476000 are not blocked; only the form
generates them. Add a constraint if Finance asks.`

### 5.5 Transfers between cash boxes (`his.cash.transfer`)

Fields:
- `name` sequence;
- `from_journal_id`, `to_journal_id`;
- `amount_sent`, `amount_received`;
- `sent_by`, `received_by`, `sent_at`, `received_at`;
- `state` draft → sent → received.

Accounting through 581000 (the company transfer account):
- **Sent:** 581000 ↔ the sending box.
- **Received:** the receiving box ↔ 581000, for the amount received.
- If received ≠ sent, the 581 residual moves to 476 and a `handover`
  discrepancy form opens on the receiving box.

On a till side, the movement is a **statement line in the open session**,
counterpart 581000, so the session's expected cash is right. In the back end
it is a plain journal entry.

| Direction | Created where | Received where |
|---|---|---|
| Till → Finance (evening handover) | till: a "Hand over to Finance" button for cashiers and managers, amount proposed as expected cash − the till's fixed float (`pos.config.his_float_amount`) | back end by a Finance user (`group_finance`) after the two-person count |
| Finance → till (cash injection, decision 13) | back end by Finance | till: "Receive cash" lists pending transfers to this till and confirms the amount |
| Finance ↔ Direction | back end | back end |

**The slip** is a QWeb PDF from the transfer: boxes, amount sent, amount
received, both names, date, two signature lines. It can be printed at `sent`
and reprinted at `received`.

A daily handover is expected (decision 12), but a missing one does not block
anything. The reporting (5.7) shows tills closed without a handover.

### 5.6 Finance and Direction cash box counts (`his.cash.count`)

Holder per box: `account.journal.his_holder_id` (res.users). Names come later
(decision 7).

A count record has: `journal_id`, `kind` (opening / closing), `expected` (the
account balance of the box's 530 at that moment, posted lines), `counted`,
`difference`, `note`, `user_id`, `date`. A difference ≠ 0 requires the note
and opens a `count` discrepancy form, with a provisional entry 530 ↔ 476
posted at once.

Menu: "Cash boxes", one card per box showing today's state (not opened /
opened / closed) with Open and Close buttons. The holder and Finance users can
count.

`shortcut: a missing daily count is shown, not enforced; enforce if Finance
asks.`

Supplier payments from these boxes are ordinary payments on CFIN and CDIR.
The `his_purchase_finance` payment controls apply unchanged.

### 5.7 Reporting

- Discrepancy list, pivot and graph views, grouped by box, cashier, month,
  tier and state. Count and sum, which covers §6.6.
- Transfers not yet received, and tills closed without a handover.
- Metabase: a POS-finance dashboard following `his_metabase`'s numbering
  pattern:
  - gaps per cashier and per month;
  - open forms by age and state;
  - handovers not yet received;
  - authorised overrides per cashier.

## 6. Non-goals

- VAT by product family (decision 19). Stays at 9%.
- Routing invoiced customers to 411100 / 411200 / 411300.
- Blocking manual entries on 476.
- Surprise counts in Odoo (decision 14).
- Card or cheque payment methods.
- Server-side enforcement of manager authorisations.
- Recording lines deleted from an order before payment. They are not a sale
  yet. Our call; Mohamed can reverse it.
- Automatic escalation of repeat gaps to the Direction. Finance sees them in
  the reports and can send any form on.
- A POS manager per till: the POS Supervisor still sees every till.

## 7. Rollout

- Close every till before installing. The hook refuses otherwise.
- Existing cashiers move from "advanced" to "basic" at the next
  `_his_sync_tills`. Run it in the hook.
- Staging: give the Finance Head role to a test login (the staging Finance
  test login is `comptable`). The real Finance head needs a login (decision 5).
- Fill `his_holder_id` on CFIN and CDIR once Finance names the holders.

## 8. Testing

Python tests (`post_install`), covering:
- account and journal setup on the generic chart;
- a close with a shortage or a surplus creates a form, the explanation is
  required, and the provisional line is on 476;
- an opening gap creates a form and a 476 line, and the session's expected
  cash stays right;
- tiers and the rights per step;
- the regularisation entry, reconciled with the provisional line;
- a refused form goes back;
- the major tier needs the Director;
- transfers sent and received, the mismatch form, and the session statement
  line on the till side;
- cash in/out is refused on tills;
- the count gap form;
- the `_his_sync_tills` basic list.

One till tour covers: a cashier closes with a gap and no notes (blocked),
then with notes (closed, form created); a cashier changes a price (dialog,
manager PIN, reason recorded). Known CI facts apply: the generic chart, and a
till tour must not leave a session open.

## 9. Left to the builder

- The exact product categories per income account. `his_stock_mdm`'s
  `categ_copy_*` and `categ_cafe_*` give a clear split; check where meal and
  menu products and Cafeteria prepared items sit.
- Which l10n_dz accounts already exist on staging, and their exact codes
  (6 digits, padded).
- How the till dialog plugs into Odoo 19's numpad and ticket screen, as long
  as coded price and discount changes are left alone.
- French labels in `i18n/fr.po`, with English sources.
