# Meal Formulas (Pack 300, Pack 600, Restaurant) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two generic meals ("Meal 300", "Meal 600") with the real formulas the caterer serves: two cafeteria packs where the cashier picks the dish and a small bottle, and one restaurant formula. All three are eaten on subscription credits only.

**Architecture:** The packs are Odoo 19 **combo products** priced at 0 DA and carrying `meal_credit_cost` (0.5 / 1). A product priced 0 with a credit cost is already, on the server, "a meal eaten on credits" (`pos.order.line._his_is_credit_meal`). So the existing rule that demands a scanned student with enough credits makes the packs subscription-only with no new server rule. The children of a combo (dish, bottle) are ordinary lines at 0 DA. The bottle is a stocked product, so core POS takes it out of stock. The restaurant formula is a plain product, with no choice. Only three things need code: which till shows which formula, the till's "nothing to pay" test (it must accept combo children), and the "value" wording on a 0 DA formula.

**Tech Stack:** Odoo 19 (`odoo:19.0`), `point_of_sale` combos (`product.combo`, `product.combo.item`), Owl patches, Python `TransactionCase` / `TestPointOfSaleHttpCommon` tours.

**Spec:** the decisions are recorded in the "Decisions" section below, taken with Mohamed on 2026-10-15. There is no separate spec document.

## Decisions (Mohamed, 2026-10-15)

| # | Decision |
|---|---|
| D1 | The packs are bought **only through subscriptions**. No walk-in cash sale of a formula. |
| D2 | Plans keep their prices: Pack 300 is 1,500 / 6,000 / 18,000; Pack 600 is 3,000 / 12,000 / 36,000. Already in `meal_plans.xml`, nothing changes. |
| D3 | **Pack 300** (cafeteria): *Pizza (5 slices)* **or** *Cheeseburger + fries*, plus a small bottle. Costs 0.5 credit. |
| D4 | **Pack 600** (cafeteria): *Rice box + crispy + cheese sauce* **or** *Fries box + crispy + cheese sauce*, plus a small bottle. Costs 1 credit. |
| D5 | **Restaurant formula**: salad + main dish + dessert. The dish changes daily and is **not** chosen in Odoo. One product, costs 1 credit. |
| D6 | Drink = **small bottles only** (juices, water, sodas), no large bottles, no cans. Staff keep this list in Odoo. |
| D7 | All POS products are taxed 9 % included (`his_pos_tva`, merged). A 0 DA formula carries no tax. VAT was collected when the plan was sold. |

**Pending, defaulted (do not block on them):**
- "cheese" in the caterer's sheet is labelled **"Cheeseburger + fries"**. Renaming is a one-field edit in the UI.
- The restaurant formula has **no bottle**. Adding one later means turning it into a combo, as in Task 1.

## Facts verified in Odoo 19 core (do not re-derive)

- Tapping a combo product calls `PosStore.addLineToCurrentOrder`, which runs `handleComboProduct` and opens `ComboConfiguratorPopup` (`point_of_sale/static/src/app/services/pos_store.js:1110`). Our `serveStudentMeal` already calls `addLineToCurrentOrder`, so the popup opens on the credit path with no extra code. If the cashier cancels the popup, no line is added.
- Child prices come from `computeComboItems` (`models/utils/compute_combo_items.js`): `price = combo.base_price * parentLstPrice / Σ base_price`. With the parent at 0, every child is 0. **If every combo's `base_price` is 0, this is `0/0 = NaN`.** `base_price` is the minimum `lst_price` of the combo's items. On staging **every drink is priced 0 DA** (checked 2026-10-15). So the dish items must carry a non-zero list price. They never show on the grid, so that price is never charged.
- The POS loads combo item products even when they are **not** `available_in_pos` (`point_of_sale/models/product_template.py:90-100`). The dish choices therefore stay off the grid and cannot be sold for cash.
- `available_in_pos` cannot be switched off on a product that is inside a combo (`_check_combo_inclusions`). Leave the dish choices at `False` from creation.
- A combo product must have at least one combo (`product/models/product_template.py:489`). A combo must have at least one item and no duplicate products.
- Invoices turn a combo parent into a **section line** (`pos_order.py:231`). Our `_get_invoice_lines_values` already returns early on `display_type`.
- Real drink data on staging cannot be filtered automatically. Sizes live in the names ("PM"/"GM", "33 CL", "0,5L"), the Format attribute is mostly empty, and cans and bottles share sizes. **The drink combo is built by staff in the UI, not seeded** (Task 4).
- Existing `taguer_produits` (`his_meal_management/hooks.py:47`) forces the "Meals" tab onto **every** product with `meal_credit_cost > 0`. Unchanged, it would put the cafeteria packs on the Restaurant till. Task 1 changes it.
- `pos_categ_repas` ("Meals") is linked today to **both** Restaurant and Cafeteria (`hooks.py` `RATTACHEMENTS`).

## Global Constraints

- Code and data sources are in **English**. Every new translatable term gets its French in `his_meal_management/i18n/fr.po` (`his_access_base/tests/test_langue_interface.py` fails otherwise).
- Python comments are French or English like the surrounding file. No accents in Python. Commit messages are in French, following the `[ADD]` / `[FIX]` / `[IMP]` style of `git log`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. The author stays `Endeavor <mohamed.bounouaa@outlook.com>`.
- Module version: `his_meal_management` `19.0.3.13.0` → **`19.0.3.14.0`**, with migration `migrations/19.0.3.14.0/post-migration.py`.
- No change to the credit engine (`_consume_meal_credit`, `_grant_meal_credits`, `_apply_meal_credits` flow). If a test seems to need one, stop and report.
- Local tests: Git Bash needs `MSYS_NO_PATHCONV=1`. Use `--without-demo=True`, never `=all`. Use a dedicated test base (`his_test`), keep it clean, and use `--http-port=8199`.

## Review Focus

1. **The cashier cancels the combo window** after confirming the serve dialog. Expected: no line, no error, and the student keeps their credits. Pinned by the tour in Task 3 (cancel step).
2. **Every item of every combo priced 0** (staff reprice a dish choice to 0). Expected: the till must not show `NaN`. Pinned by `test_every_dish_choice_has_a_price` (Task 1), with a comment on the dish choices' list price saying why.
3. **A student short of credits taps Pack 600** (0.5 left, or no plan at all). Expected: refused, nothing debited. Pinned by `test_a_formula_without_enough_credits_is_refused` (Task 2).
4. **A formula plus a paid item** (a pack and a cash juice). Expected: the payment screen shows for the juice, the pack costs credits, and the juice costs money. Pinned by `test_a_formula_next_to_a_paid_juice` (Task 2) and the mixed tour (Task 3).
5. **The wrong till**: the Restaurant shows the packs, or the Cafeteria shows the restaurant formula. Expected: each till sees only its own. Pinned by `test_each_till_sees_its_own_formulas` (Task 1).

---

### Task 1: The formulas as data, each on its own till

**Files:**
- Create: `his_meal_management/data/meal_formulas.xml`
- Create: `his_meal_management/migrations/19.0.3.14.0/post-migration.py`
- Create: `his_meal_management/tests/test_meal_formulas.py`
- Modify: `his_meal_management/__manifest__.py` (version, data list)
- Modify: `his_meal_management/hooks.py` (`RATTACHEMENTS`, `taguer_produits`)
- Modify: `his_meal_management/data/meal_plans.xml` (stale tax comment, archive generic meals)
- Modify: `his_meal_management/tests/__init__.py`
- Modify: `his_meal_management/i18n/fr.po`
- Modify: `his_meal_management/README.md` §8

**Interfaces:**
- Produces XML IDs used by Tasks 2 to 4: `his_meal_management.product_pack_300`, `product_pack_600` (product.template, type `combo`), `product_formule_restaurant` (product.template), `product_choix_pizza`, `product_choix_cheeseburger`, `product_choix_box_riz`, `product_choix_box_frites` (**product.product**), `combo_plat_300`, `combo_plat_600` (product.combo), `pos_categ_formules` (pos.category "Meal Packs").

- [ ] **Step 1: Write the failing tests**

`his_meal_management/tests/test_meal_formulas.py`:

```python
"""The caterer's formulas: what they are, and which till sells them.

Pack 300 and Pack 600 are combos the cafeteria serves on credits only; the
restaurant formula is a single product. See the plan of 2026-10-15
(docs/superpowers/plans/2026-10-15-formules-repas.md) for the decisions.
"""

from odoo.tests import TransactionCase, tagged

from ..hooks import lier_categories_pos, taguer_produits


@tagged("post_install", "-at_install")
class TestMealFormulasData(TransactionCase):
    def test_formulas_are_eaten_on_credits_only(self):
        """Priced 0 with a credit cost: the server's own definition of a credit meal."""
        for xmlid, kind, cost in (
            ("product_pack_300", "combo", 0.5),
            ("product_pack_600", "combo", 1.0),
            ("product_formule_restaurant", "consu", 1.0),
        ):
            formula = self.env.ref(f"his_meal_management.{xmlid}")
            self.assertEqual(formula.type, kind, xmlid)
            self.assertEqual(formula.list_price, 0.0, f"{xmlid} could be sold for cash")
            self.assertEqual(formula.meal_credit_cost, cost, xmlid)
            self.assertTrue(formula.available_in_pos, xmlid)

    def test_dish_choices_never_reach_the_grid(self):
        """On the grid they would be sold for cash, alone, outside any formula."""
        for xmlid in (
            "product_choix_pizza",
            "product_choix_cheeseburger",
            "product_choix_box_riz",
            "product_choix_box_frites",
        ):
            self.assertFalse(self.env.ref(f"his_meal_management.{xmlid}").available_in_pos, xmlid)

    def test_every_dish_choice_has_a_price(self):
        """The till prorates a combo by its items' prices: all at 0 is 0/0 = NaN."""
        for xmlid in ("combo_plat_300", "combo_plat_600"):
            self.assertGreater(self.env.ref(f"his_meal_management.{xmlid}").base_price, 0, xmlid)

    def test_generic_meals_are_retired(self):
        for xmlid in ("product_meal_300", "product_daily_meal"):
            self.assertFalse(self.env.ref(f"his_meal_management.{xmlid}").active, xmlid)

    def test_each_till_sees_its_own_formulas(self):
        lier_categories_pos(self.env)
        taguer_produits(self.env)
        formules = self.env.ref("his_meal_management.pos_categ_formules")
        repas = self.env.ref("his_meal_management.pos_categ_repas")
        cafeteria = self.env.ref("his_stock_mdm.pos_config_cafeteria")
        restaurant = self.env.ref("his_stock_mdm.pos_config_restaurant")

        self.assertIn(formules, cafeteria.iface_available_categ_ids)
        self.assertNotIn(repas, cafeteria.iface_available_categ_ids)
        self.assertIn(repas, restaurant.iface_available_categ_ids)
        self.assertNotIn(formules, restaurant.iface_available_categ_ids)
        # taguer_produits used to force "Meals" onto every credit meal, which
        # would have put the packs on the Restaurant till.
        for xmlid in ("product_pack_300", "product_pack_600"):
            self.assertEqual(self.env.ref(f"his_meal_management.{xmlid}").pos_categ_ids, formules, xmlid)
        self.assertEqual(self.env.ref("his_meal_management.product_formule_restaurant").pos_categ_ids, repas)
```

Add `test_meal_formulas` to `his_meal_management/tests/__init__.py` (keep alphabetical order):

```python
from . import (
    test_meal_balance_screen,
    test_meal_credit_invoice,
    test_meal_credits,
    test_meal_formulas,
    test_meal_population,
)
```

- [ ] **Step 2: Run them to make sure they fail**

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo -d his_test -u his_meal_management \
  --test-tags /his_meal_management:TestMealFormulasData --stop-after-init --without-demo=True --http-port=8199 2>&1 | tail -30
```
Expected: errors `ValueError: External ID not found ... product_pack_300`.

- [ ] **Step 3: Write the data**

`his_meal_management/data/meal_formulas.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <!-- The cafeteria's own tab. The packs do not go under "Meals": that tab is
         the Restaurant's, and sharing it put each till's formulas on the other.
         Outside noupdate, like pos_categ_repas: which tab exists is a module
         decision. -->
    <record id="pos_categ_formules" model="pos.category">
        <field name="name">Meal Packs</field>
        <field name="sequence">4</field>
    </record>

    <data noupdate="1">

        <!-- What the caterer serves (sheet received 2026-10-15). Eaten on
             subscription credits ONLY: every formula is priced 0, and a product
             priced 0 with a credit cost is, on the server, a meal that needs a
             scanned student with the credits for it
             (pos.order.line._his_is_credit_meal). A walk-in therefore cannot
             buy one - there is no price to pay.

             The dish choices are product.product so the combo items can ref()
             them directly. They are kept OFF the grid (available_in_pos False):
             the till still loads them as combo items, but they cannot be sold
             alone. Their list price is NOT what anyone pays - a child of a
             combo priced 0 is always 0 - it only keeps the till's proration
             (compute_combo_items.js: base_price * parent / sum of base_price)
             away from 0/0 = NaN. Every drink on staging is priced 0, so the
             dish must carry the non-zero one. Do not set it to 0. -->

        <record id="product_choix_pizza" model="product.product">
            <field name="name">Pizza (5 slices)</field>
            <field name="type">consu</field>
            <field name="list_price">300.0</field>
            <field name="available_in_pos" eval="False"/>
            <field name="purchase_ok" eval="False"/>
        </record>
        <record id="product_choix_cheeseburger" model="product.product">
            <field name="name">Cheeseburger + fries</field>
            <field name="type">consu</field>
            <field name="list_price">300.0</field>
            <field name="available_in_pos" eval="False"/>
            <field name="purchase_ok" eval="False"/>
        </record>
        <record id="product_choix_box_riz" model="product.product">
            <field name="name">Rice box + crispy + cheese sauce</field>
            <field name="type">consu</field>
            <field name="list_price">600.0</field>
            <field name="available_in_pos" eval="False"/>
            <field name="purchase_ok" eval="False"/>
        </record>
        <record id="product_choix_box_frites" model="product.product">
            <field name="name">Fries box + crispy + cheese sauce</field>
            <field name="type">consu</field>
            <field name="list_price">600.0</field>
            <field name="available_in_pos" eval="False"/>
            <field name="purchase_ok" eval="False"/>
        </record>

        <record id="combo_plat_300" model="product.combo">
            <field name="name">Pack 300 - dish</field>
            <field name="combo_item_ids" eval="[
                Command.create({'product_id': ref('product_choix_pizza')}),
                Command.create({'product_id': ref('product_choix_cheeseburger')}),
            ]"/>
        </record>
        <record id="combo_plat_600" model="product.combo">
            <field name="name">Pack 600 - dish</field>
            <field name="combo_item_ids" eval="[
                Command.create({'product_id': ref('product_choix_box_riz')}),
                Command.create({'product_id': ref('product_choix_box_frites')}),
            ]"/>
        </record>

        <!-- The drink is a second combo, "Small bottle", that staff build and
             add to both packs in the UI (Point of Sale > Products > Combo
             Choices): which bottles qualify cannot be read from the catalogue
             (sizes live in the names, cans and bottles share them). Until it
             exists the packs serve the dish alone. -->

        <record id="product_pack_300" model="product.template">
            <field name="name">Pack 300 (pizza or cheeseburger, with a drink)</field>
            <field name="type">combo</field>
            <field name="list_price">0.0</field>
            <field name="meal_credit_cost">0.5</field>
            <field name="combo_ids" eval="[Command.set([ref('combo_plat_300')])]"/>
            <field name="available_in_pos" eval="True"/>
            <field name="pos_categ_ids" eval="[Command.set([ref('pos_categ_formules')])]"/>
            <field name="purchase_ok" eval="False"/>
        </record>
        <record id="product_pack_600" model="product.template">
            <field name="name">Pack 600 (rice or fries box, with a drink)</field>
            <field name="type">combo</field>
            <field name="list_price">0.0</field>
            <field name="meal_credit_cost">1.0</field>
            <field name="combo_ids" eval="[Command.set([ref('combo_plat_600')])]"/>
            <field name="available_in_pos" eval="True"/>
            <field name="pos_categ_ids" eval="[Command.set([ref('pos_categ_formules')])]"/>
            <field name="purchase_ok" eval="False"/>
        </record>

        <!-- The day's dish changes too often to be a choice in Odoo: one
             product, one tap. -->
        <record id="product_formule_restaurant" model="product.template">
            <field name="name">Restaurant meal (salad + main dish + dessert)</field>
            <field name="type">consu</field>
            <field name="list_price">0.0</field>
            <field name="meal_credit_cost">1.0</field>
            <field name="available_in_pos" eval="True"/>
            <field name="pos_categ_ids" eval="[Command.set([ref('pos_categ_repas')])]"/>
            <field name="purchase_ok" eval="False"/>
        </record>

    </data>
</odoo>
```

In `his_meal_management/__manifest__.py`, set `"version": "19.0.3.14.0"` and add `"data/meal_formulas.xml",` right after `"data/meal_plans.xml",` (it refs `pos_categ_repas` from that file).

In `his_meal_management/data/meal_plans.xml`:
- Replace the paragraph starting `Taxes are cleared deliberately.` with:
  ```
  Taxes: his_pos_tva puts 9 % INCLUDED on every POS product, plans included
  (2026-10-15), so a plan at 12 000 still takes exactly 12 000. A meal served
  on credits is at 0 and carries none: the VAT was collected on the plan.
  ```
- In `product_meal_300` and `product_daily_meal`, add `<field name="active" eval="False"/>` with the comment `<!-- Retired 2026-10-15 for the formulas in meal_formulas.xml; kept for the ledger lines that point at it. -->`. This only reaches fresh installs (noupdate). Existing bases get it from the migration.

- [ ] **Step 4: Wire the tills (`hooks.py`)**

Replace `RATTACHEMENTS` and its comment's last paragraph:

```python
# Les REPAS (onglet Meals) sont ceux du Restaurant ; la Cafeteria a ses propres
# formules (onglet Meal Packs, 2026-10-15). Partager « Meals » mettait la
# formule du Restaurant a la Cafeteria et les packs au Restaurant.
RATTACHEMENTS = [
    ("his_meal_management.pos_categ_repas", "his_stock_mdm.pos_config_restaurant"),
    ("his_meal_management.pos_categ_formules", "his_stock_mdm.pos_config_cafeteria"),
    ("his_meal_management.pos_categ_recharges", "his_stock_mdm.pos_config_copy_center"),
]
```

In `taguer_produits`, a meal already carrying **either** meal tab keeps it. Replace the loop with:

```python
    formules = env.ref("his_meal_management.pos_categ_formules", raise_if_not_found=False)
    rayons_repas = repas | formules if formules else repas

    for champ, rayon, rayon_a_retirer in (("meal_credits", recharges, repas), ("meal_credit_cost", repas, recharges)):
        for produit in Template.search([(champ, ">", 0)]):
            commandes = []
            # Un repas range sous les formules de la Cafeteria y reste : lui
            # imposer « Meals » le mettrait aussi au Restaurant.
            deja_range = champ == "meal_credit_cost" and produit.pos_categ_ids & rayons_repas
            if rayon not in produit.pos_categ_ids and not deja_range:
                commandes.append((4, rayon.id))
            # Un produit qui porte les deux champs est a la fois forfait et
            # repas : on ne lui retire alors rien.
            porte_les_deux = produit.meal_credits > 0 and produit.meal_credit_cost > 0
            if not porte_les_deux and rayon_a_retirer in produit.pos_categ_ids:
                commandes.append((3, rayon_a_retirer.id))
            if commandes:
                produit.write({"available_in_pos": True, "pos_categ_ids": commandes})
```

`his_meal_management/migrations/19.0.3.14.0/post-migration.py`:

```python
"""Les formules du traiteur remplacent « Meal 300 » et « Meal 600 » (2026-10-15).

Les produits sont en noupdate : le fichier de donnees n'archive les deux repas
generiques que sur une base neuve, d'ou cette migration. On ecrit `active`
directement et non par action_archive : celle-ci refuse tant qu'une caisse est
ouverte, et une caisse ouverte se contente de les garder jusqu'a son
rechargement.

L'onglet « Meals » quitte la Cafeteria : il est desormais celui du Restaurant,
la Cafeteria a « Meal Packs ». Le hook n'enleve jamais un onglet, d'ou le
retrait ici.
"""

from odoo import SUPERUSER_ID, api
from odoo.addons.his_meal_management.hooks import lier_categories_pos, taguer_produits


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in ("product_meal_300", "product_daily_meal"):
        produit = env.ref(f"his_meal_management.{xmlid}", raise_if_not_found=False)
        if produit:
            produit.write({"active": False})

    repas = env.ref("his_meal_management.pos_categ_repas", raise_if_not_found=False)
    cafeteria = env.ref("his_stock_mdm.pos_config_cafeteria", raise_if_not_found=False)
    if repas and cafeteria and repas in cafeteria.iface_available_categ_ids:
        cafeteria.write({"iface_available_categ_ids": [(3, repas.id)]})

    lier_categories_pos(env)
    taguer_produits(env)
```

- [ ] **Step 5: French translations**

Export the module's terms and add the French to `his_meal_management/i18n/fr.po` for every new `msgid`:

| English source | French |
|---|---|
| Meal Packs | Formules |
| Pizza (5 slices) | Pizza (5 tranches) |
| Cheeseburger + fries | Cheeseburger + frites |
| Rice box + crispy + cheese sauce | Box riz + crispy + sauce fromage |
| Fries box + crispy + cheese sauce | Box frites + crispy + sauce fromage |
| Pack 300 - dish | Pack 300 - plat |
| Pack 600 - dish | Pack 600 - plat |
| Pack 300 (pizza or cheeseburger, with a drink) | Pack 300 (pizza ou cheeseburger, avec boisson) |
| Pack 600 (rice or fries box, with a drink) | Pack 600 (box riz ou frites, avec boisson) |
| Restaurant meal (salad + main dish + dessert) | Repas restaurant (salade + plat + dessert) |

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo -d his_test --i18n-export=/tmp/meal.po \
  --modules=his_meal_management --language=fr_FR --stop-after-init --http-port=8199
docker compose exec odoo cat /tmp/meal.po > /tmp/meal_export.po
```
Copy the new `#: model:` blocks into `fr.po` with the `msgstr` above. Do not overwrite the existing file with the export.

- [ ] **Step 6: Run the tests until they pass**

Same command as Step 2. Expected: `0 failed, 0 error(s) of 5 tests`. Then run the language test:

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo -d his_test -u his_meal_management \
  --test-tags /his_access_base:TestLangueInterface --stop-after-init --without-demo=True --http-port=8199 2>&1 | tail -15
```
Expected: `0 failed`.

- [ ] **Step 7: README §8**

In `his_meal_management/README.md` §8, replace the table and the "Taxes are cleared deliberately" paragraph with:

```markdown
| Product | Price | Credits | Till |
|---|---|---|---|
| Plans 300: 6 / 25 / 80 meals | 1 500 / 6 000 / 18 000 | grants 3 / 12.5 / 40 | Copy Center |
| Plans 600: 6 / 25 / 80 meals | 3 000 / 12 000 / 36 000 | grants 6 / 25 / 80 | Copy Center |
| Pack 300 (combo: pizza or cheeseburger, + bottle) | 0 | costs 0.5 | Cafeteria |
| Pack 600 (combo: rice or fries box, + bottle) | 0 | costs 1 | Cafeteria |
| Restaurant meal (salad + main dish + dessert) | 0 | costs 1 | Restaurant |

**The formulas are priced 0 on purpose**: they are bought only through a plan
(2026-10-15), and a product at 0 with a credit cost is, on the server, a meal that
needs a scanned student with the credits for it. The dish choices inside the packs
carry a list price only so the till's combo proration never divides 0 by 0; nobody
pays it.

**The drink is a combo staff maintain**: create "Small bottle" under Point of Sale >
Products > Combo Choices with the bottles allowed (small bottles only, no cans), then
add it to both packs' Combo Choices. The bottle chosen leaves stock.

Taxes: `his_pos_tva` puts 9 % included on every POS product, plans included; a meal on
credits is at 0 and carries none. **Set the company currency to DZD before going live.**
```

- [ ] **Step 8: Commit**

```bash
git add his_meal_management
git commit -m "[ADD] his_meal_management : formules Pack 300, Pack 600 et Restaurant

Les deux repas generiques cedent la place aux formules du traiteur : deux
combos Cafeteria (plat au choix + petite bouteille) et une formule
Restaurant, a 0 DA, payables en credits seulement. Chaque caisse a son
onglet.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The server takes credits for a formula, and only for it

No production code is expected here. These tests **pin** that the existing engine already does the right thing with combos. The only code change is the invoice wording on a 0 DA formula.

**Files:**
- Modify: `his_meal_management/tests/test_meal_credit_invoice.py` (move `_sync` into a module-level `sync_order`)
- Modify: `his_meal_management/tests/test_meal_formulas.py` (add `TestMealFormulasServer`)
- Modify: `his_meal_management/models/pos_order.py` (`_get_invoice_lines_values`)
- Modify: `his_meal_management/i18n/fr.po`

**Interfaces:**
- Consumes: XML IDs from Task 1.
- Produces: `sync_order(env, session, cash, partner, lines, uuid, to_invoice=True) -> pos.order` in `tests/test_meal_credit_invoice.py`, where `lines` is a list of `(product, qty, price_unit, discount)`.

- [ ] **Step 1: Extract the sync helper**

In `tests/test_meal_credit_invoice.py`, move the body of `TestTheCreditMealInvoice._sync` to a module-level function, unchanged except for the parameters, and keep `_sync` as a one-line call:

```python
def sync_order(env, session, cash, partner, lines, uuid, to_invoice=True):
    """An order through the till's own entry point.

    `lines` is a list of (product, qty, price_unit, discount). A meal on
    credits comes with no payment line at all: that is what the till sends
    now that it skips the payment screen, and core must accept it.
    """
    total = sum(qty * price * (1 - discount / 100) for _p, qty, price, discount in lines)
    payload = {
        "company_id": env.company.id,
        "session_id": session.id,
        "partner_id": partner.id if partner else False,
        "uuid": uuid,
        "to_invoice": to_invoice,
        # ... the rest of the existing payload, with self.cash -> cash ...
    }
    env["pos.order"].sync_from_ui([payload])
    return env["pos.order"].search([("uuid", "=", uuid)])
```

(The `# ...` line stands for the existing `lines`, `payment_ids`, `amount_*` and `last_order_preparation_change` keys, copied verbatim. Only `self.cash` becomes `cash`.)

```python
    def _sync(self, partner, lines, uuid):
        return sync_order(self.env, self.session, self.cash, partner, lines, uuid)
```

Run the existing class to prove nothing moved:

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo -d his_test -u his_meal_management \
  --test-tags /his_meal_management:TestTheCreditMealInvoice --stop-after-init --without-demo=True --http-port=8199 2>&1 | tail -15
```
Expected: `0 failed`. If the archived `product_daily_meal` / `product_meal_300` refs now fail in this class, point `meal_600` and `meal_300` at two products created in `setUpClass` instead (`list_price` 600 / 300, `meal_credit_cost` 1 / 0.5, `taxes_id` cleared), as `TestTheCreditMealTill` does.

- [ ] **Step 2: Write the failing server tests**

Append to `tests/test_meal_formulas.py`:

```python
from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError

from .test_meal_credit_invoice import sync_order
from .test_meal_credits import make_person


@tagged("post_install", "-at_install")
class TestMealFormulasServer(AccountTestInvoicingCommon):
    """A formula is a combo: the parent costs the credits, the children cost nothing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("point_of_sale.group_pos_manager") | cls.env.ref(
            "his_meal_management.group_meal_officer"
        )
        ref = cls.env.ref
        cls.pack_300 = ref("his_meal_management.product_pack_300").product_variant_id
        cls.pack_600 = ref("his_meal_management.product_pack_600").product_variant_id
        cls.restaurant = ref("his_meal_management.product_formule_restaurant").product_variant_id
        cls.pizza = ref("his_meal_management.product_choix_pizza")
        cls.box_riz = ref("his_meal_management.product_choix_box_riz")
        cls.bottle = cls.env["product.product"].create(
            {"name": "Test Ifri PM", "type": "consu", "is_storable": True, "list_price": 50.0, "available_in_pos": True}
        )
        cls.juice = cls.env["product.product"].create(
            {
                "name": "Test Jus",
                "type": "consu",
                "list_price": 100.0,
                "available_in_pos": True,
                "taxes_id": [Command.clear()],
            }
        )
        cls.cash = cls.env["pos.payment.method"].create(
            {
                "name": "Especes",
                "receivable_account_id": cls.company_data["default_account_receivable"].id,
                "journal_id": cls.company_data["default_journal_cash"].id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {"name": "Formula Cafeteria", "payment_method_ids": [Command.set(cls.cash.ids)]}
        )
        cls.config.open_ui()
        cls.session = cls.config.current_session_id
        cls.plan = ref("his_meal_management.product_plan_weekly").product_variant_id  # 6 credits

    def _student(self, name):
        partner = make_person(self.env, name).partner_id
        partner.sudo()._grant_meal_credits(self.plan)
        return partner

    def _sync(self, partner, lines, uuid):
        return sync_order(self.env, self.session, self.cash, partner, lines, uuid, to_invoice=False)

    def test_pack_600_takes_one_credit_and_its_bottle_leaves_stock(self):
        student = self._student("Formula Amine")
        order = self._sync(
            student,
            [(self.pack_600, 1, 0.0, 0.0), (self.box_riz, 1, 0.0, 0.0), (self.bottle, 1, 0.0, 0.0)],
            "formula-0001",
        )
        self.assertEqual(order.state, "paid")
        self.assertEqual(student.meal_credits_remaining, 5.0, "the dish or the bottle took a credit too")
        ledger = self.env["his.meal.transaction"].search([("pos_order_id", "=", order.id)])
        self.assertEqual(ledger.product_id, self.pack_600)
        self.assertIn(self.bottle, order.picking_ids.move_ids.product_id, "the bottle never left stock")

    def test_pack_300_takes_half_a_credit_and_two_take_two_halves(self):
        student = self._student("Formula Lina")
        self._sync(student, [(self.pack_300, 2, 0.0, 0.0), (self.pizza, 2, 0.0, 0.0)], "formula-0002")
        self.assertEqual(student.meal_credits_remaining, 5.0)

    def test_the_restaurant_formula_takes_one_credit(self):
        student = self._student("Formula Karim")
        self._sync(student, [(self.restaurant, 1, 0.0, 0.0)], "formula-0003")
        self.assertEqual(student.meal_credits_remaining, 5.0)

    def test_a_formula_without_a_student_is_refused(self):
        """D1: no walk-in. A formula at 0 is a credit meal, and a credit meal needs a card."""
        with self.assertRaises(UserError):
            self._sync(False, [(self.pack_600, 1, 0.0, 0.0), (self.box_riz, 1, 0.0, 0.0)], "formula-0004")

    def test_a_formula_without_enough_credits_is_refused(self):
        broke = make_person(self.env, "Formula Sans Pack").partner_id
        with self.assertRaises(UserError):
            self._sync(broke, [(self.pack_600, 1, 0.0, 0.0), (self.box_riz, 1, 0.0, 0.0)], "formula-0005")
        self.assertFalse(self.env["his.meal.transaction"].search([("partner_id", "=", broke.id)]))

    def test_a_formula_next_to_a_paid_juice(self):
        student = self._student("Formula Nour")
        order = self._sync(
            student,
            [(self.pack_600, 1, 0.0, 0.0), (self.box_riz, 1, 0.0, 0.0), (self.juice, 1, 100.0, 0.0)],
            "formula-0006",
        )
        self.assertEqual(student.meal_credits_remaining, 5.0)
        self.assertEqual(sum(order.payment_ids.mapped("amount")), 100.0)

    def test_an_invoiced_formula_does_not_claim_a_value_of_zero(self):
        """A 0 DA formula is worth its credits, not "0,00 DA"."""
        student = self._student("Formula Facture")
        order = sync_order(self.env, self.session, self.cash, student, [(self.restaurant, 1, 0.0, 0.0)], "formula-0007")
        label = order.account_move.invoice_line_ids.filtered(lambda l: l.product_id == self.restaurant).name
        self.assertIn("Paid with 1 meal credit(s)", label)
        self.assertNotIn("value", label)
```

Note: these lines are sent without a `combo_parent_id` link. The server does not read the link (`_apply_meal_credits` looks at products and prices only). The real parent/child payload is exercised by the tour in Task 3.

- [ ] **Step 3: Run them to make sure only the invoice test fails**

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo -d his_test -u his_meal_management \
  --test-tags /his_meal_management:TestMealFormulasServer --stop-after-init --without-demo=True --http-port=8199 2>&1 | tail -30
```
Expected: `test_an_invoiced_formula_does_not_claim_a_value_of_zero` FAILS (the label says `value 0,00`). The other six PASS. If any other test fails, stop: that is a real gap in the engine. Report it rather than patching around it.

- [ ] **Step 4: Drop the value when the meal has no price**

In `his_meal_management/models/pos_order.py`, `_get_invoice_lines_values`, replace the `note = _(...)` assignment with:

```python
        credits = f"{pos_line.product_id.meal_credit_cost * pos_line.qty:g}"
        price = pos_line.product_id.lst_price
        # A formula is priced 0 (eaten on credits only): "value 0,00 DA" would
        # say it is worth nothing.
        if order.currency_id.is_zero(price):
            note = _("Paid with %(credits)s meal credit(s)", credits=credits)
        else:
            note = _(
                "Paid with %(credits)s meal credit(s), value %(value)s",
                credits=credits,
                value=order.currency_id.format(price * pos_line.qty),
            )
```

Add to `fr.po`:

```
#. module: his_meal_management
#. odoo-python
#: code:addons/his_meal_management/models/pos_order.py:0
msgid "Paid with %(credits)s meal credit(s)"
msgstr "Payé avec %(credits)s crédit(s) repas"
```

- [ ] **Step 5: Run the whole module's tests**

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo -d his_test -u his_meal_management \
  --test-tags /his_meal_management --stop-after-init --without-demo=True --http-port=8199 2>&1 | grep -E "failed|ERROR|FAIL" | tail -20
```
Expected: `0 failed, 0 error(s)`. Read the `skipped` count: the tours are skipped here (no websocket). Task 3 runs them.

- [ ] **Step 6: Commit**

```bash
git add his_meal_management
git commit -m "[IMP] his_meal_management : tests serveur des formules, libelle sans valeur a 0 DA

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The till serves a formula (combo window, no payment screen)

**Files:**
- Modify: `his_meal_management/static/src/app/product_screen.js`
- Modify: `his_meal_management/static/src/app/pos_order.js`
- Modify: `his_meal_management/static/src/app/pos_store.js` (customer note)
- Create: `his_meal_management/static/tests/tours/meal_formula_tour.js`
- Modify: `his_meal_management/tests/test_meal_formulas.py` (add `TestMealFormulasTill`)
- Modify: `his_meal_management/i18n/fr.po`

**Interfaces:**
- Consumes: `PosStore.serveStudentMeal(product, line = null)` (existing), and core's `addLineToCurrentOrder` combo path.
- Produces: tours `his_meal_formula_tour`, `his_meal_formula_cancel_tour`, `his_meal_formula_walkin_tour`.

- [ ] **Step 1: Write the tours**

`his_meal_management/static/tests/tours/meal_formula_tour.js`:

```js
/** @odoo-module */

import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ComboPopup from "@point_of_sale/../tests/pos/tours/utils/combo_popup_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

// A formula served the way a cashier does it: student, formula, serve dialog,
// combo window (dish then bottle), Payment -> straight to the receipt.
// tests/test_meal_formulas.py reads the order back.

function openWithStudent() {
    return [
        Chrome.startPoS(),
        Dialog.confirm("Open Register"),
        ProductScreen.clickPartnerButton(),
        ProductScreen.clickCustomer("AAA Tour Formule"),
    ].flat();
}

const serve = { content: "Serve on credits", trigger: ".his_serve_meal_confirm", run: "click" };
const confirmCombo = { content: "Confirm the combo", trigger: ".modal footer button.confirm", run: "click" };

registry.category("web_tour.tours").add("his_meal_formula_tour", {
    steps: () =>
        [
            openWithStudent(),
            ProductScreen.clickDisplayedProduct("Tour Pack 600"),
            serve,
            ComboPopup.select("Tour Box Riz"),
            ComboPopup.select("Tour Ifri PM"),
            confirmCombo,
            ProductScreen.selectedOrderlineHas("Tour Pack 600", "1"),
            ProductScreen.clickPayButton(false),
            ReceiptScreen.isShown(),
            {
                content: "The ticket lists what was inside",
                trigger: ".pos-receipt:contains('Tour Box Riz'):contains('Tour Ifri PM')",
            },
            {
                content: "The ticket does not claim a value of zero",
                trigger: ".pos-receipt .customer-note:contains('Paid with 1 meal credit(s) per meal'):not(:contains('value'))",
            },
        ].flat(),
});

// Review Focus 1: the combo window closed without choosing.
registry.category("web_tour.tours").add("his_meal_formula_cancel_tour", {
    steps: () =>
        [
            openWithStudent(),
            ProductScreen.clickDisplayedProduct("Tour Pack 600"),
            serve,
            { content: "Close the combo window", trigger: ".modal .btn-close", run: "click" },
            ProductScreen.orderIsEmpty(),
        ].flat(),
});

// D1: no student, no formula.
registry.category("web_tour.tours").add("his_meal_formula_walkin_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Tour Pack 600"),
            { content: "The till asks for the card", trigger: ".modal:contains('No student')" },
            Dialog.confirm(),
            ProductScreen.orderIsEmpty(),
        ].flat(),
});
```

Append to `tests/test_meal_formulas.py`:

```python
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged("post_install", "-at_install")
class TestMealFormulasTill(TestPointOfSaleHttpCommon):
    """A formula clicked through on a real till."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plan = cls.env["product.product"].create(
            {"name": "Tour Pack", "type": "service", "list_price": 3000.0, "meal_credits": 6}
        )
        new = cls.env["product.product"].create
        box_riz = new({"name": "Tour Box Riz", "type": "consu", "list_price": 600.0})
        box_frites = new({"name": "Tour Box Frites", "type": "consu", "list_price": 600.0})
        cls.bottle = new(
            {"name": "Tour Ifri PM", "type": "consu", "is_storable": True, "list_price": 0.0, "available_in_pos": True}
        )
        Combo = cls.env["product.combo"]
        dish = Combo.create(
            {
                "name": "Tour dish",
                "combo_item_ids": [Command.create({"product_id": p.id}) for p in (box_riz, box_frites)],
            }
        )
        drink = Combo.create({"name": "Tour drink", "combo_item_ids": [Command.create({"product_id": cls.bottle.id})]})
        cls.pack = cls.env["product.template"].create(
            {
                "name": "Tour Pack 600",
                "type": "combo",
                "list_price": 0.0,
                "meal_credit_cost": 1.0,
                "combo_ids": [Command.set([dish.id, drink.id])],
                "available_in_pos": True,
                "taxes_id": [Command.clear()],
            }
        )
        cls.student = make_person(cls.env, "AAA Tour Formule").partner_id
        cls.student.sudo()._grant_meal_credits(plan)

    def _run(self, tour):
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour(tour)
        return self.env["pos.order"].search([("config_id", "=", self.main_pos_config.id)], order="id desc", limit=1)

    def test_a_formula_is_served_on_credits_with_its_choices(self):
        order = self._run("his_meal_formula_tour")
        self.assertEqual(order.state, "paid")
        self.assertFalse(order.payment_ids, "a formula on credits was recorded as paid by something")
        self.assertEqual(self.student.meal_credits_remaining, 5.0)
        parent = order.lines.filtered(lambda l: l.product_id.product_tmpl_id == self.pack)
        self.assertEqual(parent.combo_line_ids.product_id.mapped("name"), ["Tour Box Riz", "Tour Ifri PM"])
        self.assertIn(self.bottle, order.picking_ids.move_ids.product_id)

    def test_closing_the_combo_window_serves_nothing(self):
        self._run("his_meal_formula_cancel_tour")
        self.assertEqual(self.student.meal_credits_remaining, 6.0)

    def test_a_walk_in_cannot_take_a_formula(self):
        self._run("his_meal_formula_walkin_tour")
        self.assertEqual(self.student.meal_credits_remaining, 6.0)
```

The bottle is priced 0 here on purpose. It reproduces staging, where every drink is at 0, while the dish choices carry the price (see "Facts").

- [ ] **Step 2: Run the tours to make sure they fail**

Tours are SKIPPED by the stock `odoo:19.0` image (no Chrome, no `python3-websocket`), and the summary still says "0 failed". Use the local image that has both:

```bash
MSYS_NO_PATHCONV=1 docker run --rm --network his-odoo-addons_default \
  -v "$PWD":/mnt/extra-addons -v "$PWD/config/odoo.conf":/etc/odoo/odoo.conf:ro \
  odoo19-chromium-ws odoo -d his_test -u his_meal_management \
  --test-tags /his_meal_management:TestMealFormulasTill --stop-after-init --without-demo=True --http-port=8199 2>&1 | tail -40
```
Stop the `odoo` service first (`docker compose stop odoo`), since two Odoo processes on one base during `-u` fail with "could not serialize access". Before each run, clear stale asset bundles:
`docker compose exec db psql -U odoo -d his_test -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'"`.
Expected: three FAILS, **not skips**. Read the `skipped` count. The walk-in tour fails because the formula goes to `super` and opens the combo window. The main tour fails because the payment screen opens (a combo child is not a credit meal) or because the note carries `value`.

- [ ] **Step 3: Implement**

`product_screen.js`: replace the `if` with:

```js
        const variant = product.product_variant_ids?.[0];
        // A formula has no cash price (D1, 2026-10-15): it is only ever eaten on
        // credits, so without a student it still goes to serveStudentMeal,
        // which asks for the card instead of opening the combo window.
        const creditOnly = variant?.meal_credit_cost > 0 && this.pos.currency.isZero(variant.lst_price);
        if (variant?.meal_credit_cost > 0 && (this.pos.getOrder()?.getPartner() || creditOnly)) {
            return this.pos.serveStudentMeal(variant);
        }
```
Update the comment above `addProductToOrder` to say a formula (combo) goes the same way and that core's `addLineToCurrentOrder` opens its combo window.

`pos_order.js`: replace the `every(...)` predicate with:

```js
                this.lines.every((line) => {
                    // A dish or a bottle chosen inside a formula: it is the
                    // formula, its parent, that the credits pay for.
                    const meal = line.combo_parent_id ? line.combo_parent_id.product_id : line.product_id;
                    return (
                        meal.meal_credit_cost > 0 &&
                        this.currency.isZero(line.price_unit * (1 - (line.discount || 0) / 100))
                    );
                })
```
Add one line to the comment: "A combo's children (dish, bottle) at 0 DA belong to the formula above them."

`pos_store.js`, in `confirm`: replace the `line?.setCustomerNote(...)` call with:

```js
                const credits = product.meal_credit_cost;
                line?.setCustomerNote(
                    this.currency.isZero(product.lst_price)
                        ? // A formula is priced 0: "value 0,00 DA" would say it is worth nothing.
                          _t("Paid with %(credits)s meal credit(s) per meal", { credits })
                        : _t("Paid with %(credits)s meal credit(s) per meal, value %(value)s", {
                              credits,
                              value: this.env.utils.formatCurrency(product.lst_price),
                          })
                );
```

`fr.po`:

```
#. module: his_meal_management
#. odoo-javascript
#: code:addons/his_meal_management/static/src/app/pos_store.js:0
msgid "Paid with %(credits)s meal credit(s) per meal"
msgstr "Payé avec %(credits)s crédit(s) repas par repas"
```

- [ ] **Step 4: Run the tours and the existing ones until they pass**

Same command as Step 2, with `--test-tags /his_meal_management:TestMealFormulasTill,/his_meal_management:TestTheCreditMealTill`.
Expected: `0 failed, 0 error(s)` and **0 skipped** for these 6 tests. The three existing `TestTheCreditMealTill` tours must still pass, since they pin the plain-meal path.

- [ ] **Step 5: Look at it (`verify-ui-by-rendering`)**

On the local stack (`docker compose up -d`, base `his_dev`, after `-u his_meal_management`):
1. Open `/pos/ui` for the Cafeteria in Chrome, **also with `?debug=assets`** (Owl prop validation only fires there).
2. Check: the "Meal Packs" tab shows Pack 300 and Pack 600, and no "Meals" tab. On the Restaurant, "Meals" shows the restaurant formula and no packs.
3. With a student who has credits, tap Pack 600: serve dialog, combo window, the dish lines under the pack, Payment, then the receipt listing dish and bottle.
4. Screenshot each step. Console must be clean. Read the server log for QWeb/XML errors.

- [ ] **Step 6: Commit**

```bash
git add his_meal_management
git commit -m "[IMP] his_meal_management : la caisse sert une formule (fenetre combo, sans ecran de paiement)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Ship to staging and hand over the drink list

**Files:** none in the repo. These are operations on staging, `169.58.77.161`, base `his_dev`.

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin feature/formules-repas
```
Mohamed opens the PR (`gh` is not installed here). CI must be green: lint, tests (≥ 400 run), and the result line read.

- [ ] **Step 2: After the merge, upgrade staging**

The merge deploys the image (about 6 min, check the staging container serves the new `sha-`). The upgrade is manual and targeted. Ask the staging Claude, or run it by SSH using the procedure in the `his-prod-staging-split` memory (`odoo-upgrade` with `his_meal_management` only: stop Odoo, `compose run -l traefik.enable=false --pull never`, `-u his_meal_management`, start Odoo). Back up the base first.

- [ ] **Step 3: Check the migration did its job**

```sql
SELECT name->>'en_US', active, list_price FROM product_template
 WHERE id IN (SELECT res_id FROM ir_model_data WHERE module='his_meal_management'
   AND name IN ('product_meal_300','product_daily_meal','product_pack_300','product_pack_600','product_formule_restaurant'));
```
Expected: the two generic meals have `active = f`, and the three formulas exist with `list_price = 0`. Then open the Cafeteria and Restaurant tills (reload them) and check the tabs as in Task 3 Step 5.

- [ ] **Step 4: Build "Small bottle" with Mohamed**

In Point of Sale > Products > Combo Choices: create **Small bottle**, add the small bottles (the "PM" waters, 24/25/33 CL sodas, 0,5L, small juices; no "GM", no 1L+, no cans), then add it to the Combo Choices of Pack 300 and Pack 600. Leave the list to the cafeteria staff afterwards. This is D6, and README §8 says how.

- [ ] **Step 5: Mohamed's recette**

He serves one Pack 300, one Pack 600 and one restaurant formula to a test student, then checks the ticket, the credits left, and that the bottle left stock (Inventory > Moves).

---

## Self-review notes

- D1 → Task 1 (price 0) + Task 2 `test_a_formula_without_a_student_is_refused` + Task 3 walk-in tour. D2 → unchanged data. D3/D4 → Task 1 combos. D5 → Task 1 restaurant product. D6 → Task 4 Step 4 + README. D7 → Task 1 comment fix.
- Names used across tasks: `sync_order`, `pos_categ_formules`, `product_pack_300/600`, `product_formule_restaurant`, `product_choix_*`, `combo_plat_300/600` match everywhere.
- The server needs no new credit rule. If Task 2 Step 3 shows otherwise, the plan stops there by design.
