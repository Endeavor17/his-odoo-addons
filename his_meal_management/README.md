# his_meal_management — Cards, Meal Wallet and Point of Sale

Prepaid meal credits for the Groupe HIS-HTC-IRA, driven from two points of sale:
the **student centre sells the plans**, the **restaurant consumes the credits**.

The governing idea is small and worth stating first:

> **Credits belong to the person, never to the card.** The card carries an
> identifier and nothing else. A lost card is replaced without losing a single
> credit, because nothing of value was ever stored on it.

---

## 1. What this module owns, and what it does not

| | Owner |
|---|---|
| Person, matricule, the sequence that issues it | `his_person_core` — **not here** |
| Employee ↔ person link | `his_hr_base` — **not here** |
| Cards, wallet, subscriptions, ledger, POS behaviour | **here** |
| Academic attributes (rank, speciality, faculties) | **here**, added onto `his.person` |

Academic fields live here rather than in the socle because the socle holds what
*every* person has. A rank and a faculty are academic facts, and today this is
the module that needs them. If a future Scolarité module needs them too, that is
the moment to propose moving them down — not before.

**The wallet stays on `res.partner`** deliberately: the card mirrors its code
onto `res.partner.barcode`, Odoo's own barcode rule resolves a partner, and the
POS sells to a partner. Since every `his.person` carries one by delegation,
`person.meal_credits_remaining` resolves for free with nothing extra to define.

**No wallet without an identity.** A card and a subscription both refuse a
partner that carries no `his.person`, so a plain contact — or a walk-in customer
— can never hold a balance.

---

## 2. Models

| Model | Purpose |
|---|---|
| `his.meal.card` | The physical badge. Code, state, what it replaced |
| `his.meal.subscription` | One purchase of one plan: window + counters |
| `his.meal.transaction` | Append-only ledger. One line per movement |
| `his.faculty` | Faculty referential, six real codes |
| `his.person` *(inherit)* | Rank, speciality, faculties, and the badge takeover |
| `res.partner` *(inherit)* | The wallet itself |
| `product.template` *(inherit)* | A plan is a product carrying a credit count |
| `pos.config` *(inherit)* | Which product is the student meal |
| `pos.order` *(inherit)* | Where credits actually move |
| `his.meal.adjust.wizard` | The only sanctioned manual correction |

---

## 3. The badge — one number, four readers

`his_person_core` declared `numero_carte` as a plain `Char` and said in its own
README that it had to move into a dedicated model **before the wallet stored
money**. This module is that handover.

```
his.meal.card (the active row)        ← the single source
      │  compute + inverse
      ▼
his.person.numero_carte               ← the referential's badge field
      │  stored related
      ▼
hr.employee.barcode                   ← attendance clock, cashier login
      │  mirror
      ▼
res.partner.barcode                   ← what the POS scan resolves
```

Every link is a stored relation or a maintained mirror — never two fields copied
into one another, because those always drift, and drifting here would mean *a
card the till accepts and the attendance reader refuses*.

**Writing a badge issues a card.** `_inverse_numero_carte` retires the previous
card as `replaced` and creates the new one, which is the half a single `Char`
could not do: it is what lets anyone answer *"which card was valid when that meal
was served"*.

Two database constraints hold the story up: `unique(numero_carte)` on the person
and `UNIQUE(code)` on the card — one badge, one person — plus a Python check that
a person holds at most one **active** card.

`_sync_partner_barcode()` maintains the partner mirror on create, write **and
unlink**. The unlink half was a real leak: four people stayed scannable by cards
that had been deleted.

---

## 4. Scanning — the whole POS integration is two data records

`data/barcode_rule.xml` is the entire hardware integration. An RFID reader that
types digits and presses Enter *is* a barcode scanner as far as Odoo is
concerned.

| Rule | Sequence | Pattern | For |
|---|---|---|---|
| Student RFID Card | 15 | ten digit-atoms + `$` | Manufacturer UIDs |
| Student Meal Card | 39 | `HIS` | Printed cards |

**Sequence 15 is deliberate.** Rules are tried in order and the first match wins.
The stock nomenclature has a Lot rule at 80 and a catch-all Product rule at 90
matching `.*` — which otherwise swallows every UID and sends the POS hunting for
a product that does not exist.

> ### Do not "tidy" the RFID pattern
>
> It is written out longhand on purpose. Odoo parses barcodes **twice, with two
> different implementations**:
>
> ```
> Python  barcode_nomenclature.py   re.match(pattern, code[:len(pattern)])
> JS      barcode_parser.js         code.match('^' + pattern)
> ```
>
> The Python side truncates the code to the *pattern's own length* first. A
> seven-character shorthand therefore only ever compares the first seven digits
> and never matches; a ten-character one truncates a 13-digit EAN to ten digits
> and hijacks real product barcodes. Spelled out, the pattern is longer than any
> barcode, so the truncation is a no-op and the trailing `$` correctly rejects
> 8- and 13-digit codes.

Because the card mirrors onto `res.partner.barcode`, a scan sets the customer
through Odoo's own code paths. **No custom JavaScript identifies the student.**

---

## 5. The wallet

### A subscription is one purchase

`his.meal.subscription` carries its own validity window and its own counters —
`credits_total`, `credits_used`, computed `credits_remaining`, and a computed
`state` of `active` / `exhausted` / `expired` / `cancelled`.

`product_id` is empty on a manual correction: those credits came from an
officer's decision, not from a plan anyone bought.

### Spending order

`_usable_subscriptions()` returns what may be eaten today — not cancelled,
credits left, inside the window — ordered by `date_end` ascending. **Credits
about to be lost are spent before the ones that keep**, which is what a person
would choose.

### The safety story

```sql
CHECK (credits_used >= 0 AND credits_used <= credits_total)
CHECK (credits_total > 0)
CHECK (date_end >= date_start)
```

A negative balance is rejected by **Postgres itself**, so no bug, race or manual
write anywhere in Odoo can produce one.

`_consume_meal_credit()` takes `SELECT … FOR UPDATE` on the person's
subscriptions first. Without it, two cashiers scanning the same card at the same
instant could both read "1 credit left" and both serve a meal. It flushes before
locking so pending writes reach the locked rows, then invalidates so counters are
re-read at their committed values.

---

## 6. Where credits actually move

**On the server, in `pos.order._process_saved_order()`** — never in the browser.
A cashier with the developer console open still cannot invent a credit.

```
plan line   (product.meal_credits > 0)   →  _grant_meal_credits()   →  +credits
meal line   (the configured meal, at price 0)  →  _consume_meal_credit()  →  −1 each
```

A **student meal is the free one**. The same product sold at its real price is a
paying walk-in customer and must not touch anyone's balance — that is what the
`float_is_zero` check on `price_unit` is for.

`_already_applied()` makes the whole thing idempotent by looking for an existing
ledger line on the order: POS orders re-sync, and credits must move exactly once.

An order carrying a plan or a student meal with **no customer** is refused
outright — the cashier is told to scan the card.

> **Refunds are a deliberate no-op on credits.** A negative quantity produces an
> empty range and a non-positive meal count, so refunding a plan leaves the
> subscription standing and refunding a meal gives no credit back. An officer
> settles both with the correction wizard. Marked in the source with a
> `ponytail:` comment — handle it properly only if refunds turn out to be common.

### At the till

The **Student Meal** button is a convenience, not a control. It shows the cashier
who the student is and what they have left, then drops a zero-priced line. The
credit itself is taken server-side on validation, so nothing in the browser can
be tricked into serving a meal the student cannot pay for.

`get_meal_balance()` feeds it, and returns `matricule_affiche` — the displayed
form without the check digit, because nobody copies this number by hand; it is
read off a card.

---

## 7. The ledger

`his.meal.transaction` is **append-only, in Python, not by convention**:

```python
def write(self, vals):  raise UserError("… cannot be edited. Post a correction instead.")
def unlink(self):       raise UserError("… cannot be deleted.")
```

Every grant and every meal writes one line naming the student, card, plan,
cashier, session, point of sale, and **the balance it left behind**. Nobody —
officer included — can edit or delete one. That immutability is also what forces
the direction of a merge: the record holding the wallet has to survive.

---

## 8. Meal plans are ordinary products

A product with `meal_credits > 0` **is** a meal plan. There is no separate plan
model to keep in sync, so price, POS sellability, invoicing and accounting are
all stock Odoo.

| Plan | Price | Credits | Valid |
|---|---|---|---|
| Weekly | 3 000 | 6 (5 paid + 1 free) | 7 days |
| Monthly | 12 000 | 25 (20 + 5) | 30 days |
| Semester | 36 000 | 80 (60 + 20) | 180 days |
| Daily Meal | 600 | 0 | — |

Taxes are cleared deliberately: a plan sold at 12 000 must land 25 credits and
take exactly 12 000, and the student meal must stay at zero when paid with a
credit. **Set the company currency to DZD before going live.**

Validity counts from the day of purchase and is inclusive: a 7-day plan bought
today is usable today through day 7, not day 8 — hence `date_end = today +
validity − 1`.

---

## 9. Corrections

**Meals → Configuration → Correct Credits** is the only sanctioned way to change
a balance by hand. It exists so corrections leave the same audit trail as
everything else: nobody edits `credits_used` directly, and every correction
carries a reason and the name of whoever made it.

Taking credits back reuses the same guarded path as a real meal, so a correction
can no more push a student negative than a cashier can.

---

## 10. Roles

| Group | Implies | Can |
|---|---|---|
| **Restaurant Cashier** | — | Read cards, subscriptions, ledger, people |
| **Meal Officer** | Cashier | Issue and replace cards, edit subscriptions, correct credits, manage plans and faculties |

Neither can **delete a ledger line** — `perm_unlink = 0` for both, and the model
refuses it anyway.

The Officer has `perm_create = 0` on subscriptions: credits are only born from a
POS sale or the correction wizard, never typed in by hand.

The Officer deliberately holds **no write access to `his.person`**. The officer
issues cards; the referential issues identities. That is why the card's
constraint refuses an unregistered contact rather than the officer being handed
broader rights.

> **These groups do not include POS access.** A cashier also needs
> `point_of_sale.group_pos_user`, or they will see the Meals menus and be unable
> to open a till. This is the most common setup mistake.

---

## 11. Configuration

Set **Student Meal Product** on the *restaurant* point of sale; leave it empty on
the one that sells plans. Without it the button reports "Not configured".

`post_init_hook` wires `his_stock_mdm`'s Restaurant config to the Daily Meal
automatically, with two guards: `his_stock_mdm` being absent is a normal install,
and an already-filled field is never overwritten. Because hooks only run at
**install**, migration `19.0.2.2.0` calls the same function so existing databases
get it too.

> **Do not add `meal_product_id` to `_get_special_products()`.** It looks right —
> `pos_discount` does exactly that — and it is a trap here. See the comment in
> `models/pos_config.py` for why.

`ir_sequence.xml` issues `HIS-CARD-000001` codes for **printed** cards only. RFID
cards never use it: their code is the UID burned in by the manufacturer.

A daily cron refreshes subscription `state` so lists and filters show reality.
It is **cosmetic** — consumption checks the dates directly, so a missed run can
never let an expired plan be eaten.

---

## 12. Gotchas

- **Leading zeros.** RFID UIDs look like `0007197786`. Excel and most CSV editors
  turn that into `7197786` and the badge never matches. Force the column to text.
- **Identity and a card are not credits.** A recognised student with an empty
  wallet still cannot eat. Someone must sell them a plan.
- **Students should not be users.** They are a `his.person` plus a card. They
  never log in; they get scanned.
- **`res.partner.barcode` is read by core Odoo in three places** — the POS loads
  it, the customer list searches it, the product screen resolves scans through
  it. Removing the mirror silently breaks every scan.
- **Multiple plans stack.** Nothing currently stops selling a monthly plan to
  someone mid-week; both run side by side and drain soonest-expiry first.

---

## 13. Install and test

```bash
docker compose run --rm odoo odoo -d <db> -i his_meal_management --stop-after-init

docker compose run --rm odoo odoo -d <db> -u his_meal_management \
  --test-enable --test-tags /his_meal_management --stop-after-init
```

On Git Bash, prefix with `MSYS_NO_PATHCONV=1`. Python changes need
`docker compose restart odoo`; view and data changes need `-u`.

**Migrations** — run in order, each idempotent:

| Version | Does |
|---|---|
| `19.0.1.1.0` | early wallet groundwork |
| `19.0.2.0.0` | moves identity to `his.person`, drops the orphaned columns |
| `19.0.2.1.0` | issues a card for every badge recorded before the handover |
| `19.0.2.2.0` | points the Restaurant till at the student meal |

`tests/test_meal_credits.py` covers credit grant and spend, expiry, the
impossible negative balance, card lifecycle and replacement, the append-only
ledger, POS behaviour at both tills, the identity boundary, RFID parsing, and the
full badge chain from card to employee.

**Depends on** `base`, `product`, `point_of_sale`, `his_person_core`.
