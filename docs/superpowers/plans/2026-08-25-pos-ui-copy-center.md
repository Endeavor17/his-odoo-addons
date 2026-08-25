# POS Theme Layer and Copy Center Job Builder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the three HIS points of sale a branded, touch-first POS interface, and replace the Copy Center's multi-popup product hunt with a single job-builder dialog.

**Architecture:** Two new modules. `his_pos_ui` carries the shared theme as CSS custom properties scoped by a class on the POS root element, driven by one selection field on `pos.config`. `his_pos_copy_center` depends on it and adds a dialog that maps four dimension chips to one tagged `product.template`, then adds an ordinary order line. No new models, no new RPCs, no new dependencies.

**Tech Stack:** Odoo 19.0 Community, OWL 2, SCSS compiled by Odoo's asset pipeline, `point_of_sale._assets_pos` bundle, `odoo.tests` (`TransactionCase`, `HttpCase` for POS tours).

**Spec:** `docs/superpowers/specs/2026-08-25-pos-ui-copy-center-design.md`

## Global Constraints

- **Odoo 19.0 Community.** No Enterprise-only modules (`pos_restaurant` is Community; `pos_self_order` is not used).
- **No new Python or JS dependency.** No CSS framework, no component library, no build step beyond Odoo's own asset pipeline.
- **Nothing in the browser computes money.** Price displayed = price read from the loaded product. The order line carries the product; the server prices it.
- **`his_meal_management` and `his_stock_mdm` are not modified.** MDM rule 6 (`product_template_attribute_line._check_mdm_categ_eligible`) is obeyed, never amended.
- **Source strings English, wrapped in `_t()`**; French `i18n/fr.po` shipped. Product and attribute names stay French — they are data.
- **Licence `LGPL-3`, author `Abdo Chabouti`**, matching every existing module manifest.
- **Version string `19.0.1.0.0`** for both new modules.
- **A theme that is unset must leave POS looking and behaving exactly as stock.**
- **Dev loop:** `docker compose restart odoo` picks up Python changes; asset changes need `--dev=assets` or a module upgrade. DB is `his_dev`.

---

### Task 1: `his_pos_ui` module skeleton and the theme field

**Files:**
- Create: `his_pos_ui/__init__.py`
- Create: `his_pos_ui/__manifest__.py`
- Create: `his_pos_ui/models/__init__.py`
- Create: `his_pos_ui/models/pos_config.py`
- Create: `his_pos_ui/views/pos_config_views.xml`
- Create: `his_pos_ui/tests/__init__.py`
- Test: `his_pos_ui/tests/test_pos_theme.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `pos.config.his_pos_theme`, a `fields.Selection` with keys `copy_center`, `restaurant`, `cafeteria`, default `False`. Task 2 reads it in JS as `pos.config.his_pos_theme`. Task 6 sets it on the Copy Center config.

- [ ] **Step 1: Write the failing test**

```python
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPosTheme(TransactionCase):
    """The theme is a label on the till, and nothing more.

    It must be optional, because an unthemed POS has to keep looking exactly
    like stock Odoo - that fallback is what makes the whole CSS-only design
    safe.
    """

    def test_theme_is_optional(self):
        config = self.env['pos.config'].create({'name': "Untouched Till"})
        self.assertFalse(
            config.his_pos_theme,
            "A new point of sale must carry no theme, so it renders as stock Odoo.",
        )

    def test_theme_accepts_the_three_points_of_sale(self):
        config = self.env['pos.config'].create({'name': "Themed Till"})
        for theme in ('copy_center', 'restaurant', 'cafeteria'):
            config.his_pos_theme = theme
            self.assertEqual(config.his_pos_theme, theme)

    def test_theme_reaches_the_browser(self):
        """POS reads pos.config with an empty field list, which means *all*
        fields. This test pins that behaviour: if a future Odoo starts
        whitelisting pos.config fields, the theme silently stops arriving in
        the browser and every till goes back to looking stock. Better to fail
        here than to debug CSS that was never given a class to hang on.
        """
        config = self.env['pos.config'].create({
            'name': "Loaded Till",
            'his_pos_theme': 'copy_center',
        })
        fields = self.env['pos.config']._load_pos_data_fields(config)
        loaded = config.read(fields, load=False)[0]
        self.assertEqual(loaded.get('his_pos_theme'), 'copy_center')
```

- [ ] **Step 2: Run the test and watch it fail**

Run:
```bash
docker compose run --rm -T odoo odoo -d his_dev -i his_pos_ui --test-enable --test-tags /his_pos_ui --stop-after-init --max-cron-threads=0
```
Expected: FAIL — the module does not exist yet, so Odoo reports it cannot find `his_pos_ui`.

- [ ] **Step 3: Create the module skeleton**

`his_pos_ui/__init__.py`:
```python
from . import models
```

`his_pos_ui/models/__init__.py`:
```python
from . import pos_config
```

`his_pos_ui/__manifest__.py`:
```python
{
    'name': 'HIS POS Interface',
    'version': '19.0.1.0.0',
    'summary': 'Branded, touch-first interface shared by the HIS points of sale',
    'description': """
HIS POS Interface
=================
The interface may be redesigned; the transaction may not.

* A point of sale wears a theme, chosen on its own configuration. Unset means
  stock Odoo: the fallback is what makes a CSS-only theme safe to install.
* The theme is CSS scoped under a class on the POS root element. No component
  is patched to apply styling, so no styling decision can break a sale.
* Touch sizing and the entry wallpaper reuse variables Odoo already exposes
  (--btn-height-size, --homeMenu-bg-image) rather than overriding rules.
""",
    'author': 'Abdo Chabouti',
    'category': 'Sales/Point of Sale',
    'license': 'LGPL-3',

    'depends': ['point_of_sale'],

    'data': [
        'views/pos_config_views.xml',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'his_pos_ui/static/src/**/*',
        ],
    },

    'installable': True,
}
```

- [ ] **Step 4: Add the theme field**

`his_pos_ui/models/pos_config.py`:
```python
from odoo import fields, models


class PosConfig(models.Model):
    """Which face this till wears.

    Deliberately a plain Selection and not a many2one to a theme model: there
    are three points of sale, they are named in the MDM, and a table whose rows
    would each need a matching stylesheet is a table that lies about how
    configurable it is.
    """

    _inherit = 'pos.config'

    his_pos_theme = fields.Selection(
        [
            ('copy_center', "Copy Center"),
            ('restaurant', "Restaurant"),
            ('cafeteria', "Cafétéria"),
        ],
        string="HIS Theme",
        help="Appearance of this point of sale. Leave empty to keep the stock "
             "Odoo interface.",
    )
```

- [ ] **Step 5: Expose the field in the backend form**

`his_pos_ui/views/pos_config_views.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <record id="view_pos_config_form_his_theme" model="ir.ui.view">
        <field name="name">pos.config.form.his.theme</field>
        <field name="model">pos.config</field>
        <field name="inherit_id" ref="point_of_sale.pos_config_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//block[@name='pos_interface_section']" position="inside">
                <setting string="HIS Theme" help="Branded appearance for this point of sale">
                    <field name="his_pos_theme"/>
                </setting>
            </xpath>
        </field>
    </record>
</odoo>
```

If `pos_interface_section` does not exist in this Odoo build, find the real anchor before guessing:
```bash
docker exec his-odoo-addons-db-1 psql -U odoo -d his_dev -tAc \
  "select arch_db from ir_ui_view where model='pos.config' and type='form' limit 1" | head -60
```

- [ ] **Step 6: Run the tests and watch them pass**

Run:
```bash
docker compose run --rm -T odoo odoo -d his_dev -i his_pos_ui --test-enable --test-tags /his_pos_ui --stop-after-init --max-cron-threads=0
```
Expected: PASS, 3 tests.

- [ ] **Step 7: Commit**

```bash
git add his_pos_ui
git commit -m "[ADD] his_pos_ui : champ de theme sur le point de vente"
```

---

### Task 2: The theme reaches the DOM

**Files:**
- Create: `his_pos_ui/static/src/app/chrome.xml`
- Test: manual, in the browser — a class either lands on the root element or it does not, and no unit test tells you that more cheaply than looking.

**Interfaces:**
- Consumes: `pos.config.his_pos_theme` from Task 1.
- Produces: the CSS hooks every later task styles against — `.his-pos` on every themed till, plus one of `.his-theme-copy_center` / `.his-theme-restaurant` / `.his-theme-cafeteria`.

- [ ] **Step 1: Read the stock template before inheriting it**

Run:
```bash
docker exec his-odoo-addons-odoo-1 cat \
  /usr/lib/python3/dist-packages/odoo/addons/point_of_sale/static/src/app/pos_app.xml
```
Expected: the `point_of_sale.Chrome` template whose root is `<div class="pos dvh-100 d-flex flex-column">`. Confirm that root before writing an xpath against it.

- [ ] **Step 2: Add the theme class**

`his_pos_ui/static/src/app/chrome.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates id="template" xml:space="preserve">
    <t t-name="his_pos_ui.Chrome" t-inherit="point_of_sale.Chrome" t-inherit-mode="extension">
        <xpath expr="//div[hasclass('pos')]" position="attributes">
            <attribute name="t-attf-class">{{ this.pos.config.his_pos_theme ? 'his-pos his-theme-' + this.pos.config.his_pos_theme : '' }}</attribute>
        </xpath>
    </t>
</templates>
```

An unthemed till gets an empty string, so it keeps exactly the classes stock Odoo gave it.

- [ ] **Step 3: Verify in the browser**

```bash
docker compose restart odoo
```
Set the Copy Center till's HIS Theme to *Copy Center* in the backend, open its POS, and in devtools confirm the root element reads
`class="pos dvh-100 d-flex flex-column his-pos his-theme-copy_center"`.

Then set the theme back to empty, reload, and confirm `his-pos` is gone. That second check is the one that matters: it proves the fallback.

- [ ] **Step 4: Commit**

```bash
git add his_pos_ui/static/src/app/chrome.xml
git commit -m "[ADD] his_pos_ui : classe de theme sur la racine du POS"
```

---

### Task 3: Design tokens and the themed working screens

**Files:**
- Create: `his_pos_ui/static/src/scss/tokens.scss`
- Create: `his_pos_ui/static/src/scss/pos.scss`

**Interfaces:**
- Consumes: the `.his-pos` / `.his-theme-*` classes from Task 2.
- Produces: the custom properties every later task and every later POS module styles against — `--his-surface`, `--his-surface-raised`, `--his-border`, `--his-text`, `--his-text-muted`, `--his-accent`, `--his-accent-contrast`, `--his-wallpaper`.

- [ ] **Step 1: Define the tokens**

`his_pos_ui/static/src/scss/tokens.scss`:
```scss
// One accent per point of sale, and a shared neutral surface underneath.
//
// The wallpapers are dark, warm photographs. They earn their place on the
// entry screen and nowhere else: behind a working product grid they destroy
// the legibility of every price on screen. So the working surface is a calm
// near-neutral, and the accent is spent on exactly one thing - the primary
// action.

.his-pos {
    --his-surface: #f4f5f7;
    --his-surface-raised: #ffffff;
    --his-border: #d8dbe0;
    --his-text: #1c2024;
    --his-text-muted: #5b6470;
    --his-accent: #2f6feb;
    --his-accent-contrast: #ffffff;
    --his-wallpaper: none;

    // Odoo sizes every POS button from this one variable. Raising it is the
    // whole touch-target change: no button rule is overridden.
    --btn-height-size: 64px;

    // Consumed by point_of_sale's own login_screen.scss.
    --homeMenu-bg-color: #{'var(--his-wallpaper-color)'};
    --homeMenu-bg-image: #{'var(--his-wallpaper)'};
}

.his-theme-copy_center {
    --his-accent: #2f6feb;          // ink blue - administrative, not appetising
    --his-wallpaper-color: #10233f;
    --his-wallpaper: url('/his_pos_ui/static/src/img/copy_center.webp');
}

.his-theme-restaurant {
    --his-accent: #2f8f4e;          // herb green - does not compete with food
    --his-wallpaper-color: #14301f;
    --his-wallpaper: url('/his_pos_ui/static/src/img/restaurant.webp');
}

.his-theme-cafeteria {
    --his-accent: #b3701c;          // espresso amber - the crema in the cup
    --his-wallpaper-color: #33220f;
    --his-wallpaper: url('/his_pos_ui/static/src/img/cafeteria.webp');
}
```

- [ ] **Step 2: Apply the tokens to the working screens**

`his_pos_ui/static/src/scss/pos.scss`:
```scss
// Styling only. Nothing here changes what a click does.

.his-pos {
    background-color: var(--his-surface);
    color: var(--his-text);

    .btn-primary {
        background-color: var(--his-accent);
        border-color: var(--his-accent);
        color: var(--his-accent-contrast);
    }

    // Money is read at a glance across a counter, so it gets size, weight and
    // tabular figures - digits that do not shift width as the total changes.
    .order-summary,
    .total {
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.01em;
    }

    .product-card {
        background-color: var(--his-surface-raised);
        border: 1px solid var(--his-border);
        border-radius: 0.75rem;
    }

    .numpad button {
        font-size: 1.25rem;
        font-variant-numeric: tabular-nums;
    }
}
```

- [ ] **Step 3: Check the result against the real screens**

```bash
docker compose restart odoo
```
Open the themed POS with `--dev=assets` active, or upgrade the module so SCSS recompiles:
```bash
docker compose run --rm -T odoo odoo -d his_dev -u his_pos_ui --stop-after-init --max-cron-threads=0
```
Confirm: buttons are visibly taller, the primary action carries the accent, totals are tabular. Then confirm an unthemed till is untouched.

- [ ] **Step 4: Check contrast, do not assume it**

For each theme, check `--his-text` on `--his-surface` and `--his-accent-contrast` on `--his-accent` in devtools' contrast picker. Body text must reach 4.5:1, large text and UI boundaries 3:1. Adjust the token, not the rule, if a pair falls short.

- [ ] **Step 5: Commit**

```bash
git add his_pos_ui/static/src/scss
git commit -m "[ADD] his_pos_ui : jetons de design et habillage des ecrans de travail"
```

---

### Task 4: The entry screen

**Files:**
- Create: `his_pos_ui/static/src/scss/login.scss`
- Create: `his_pos_ui/static/src/img/README.md`

**Interfaces:**
- Consumes: `--his-wallpaper`, `--his-wallpaper-color` from Task 3.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Confirm which variables the stock login screen reads**

```bash
docker exec his-odoo-addons-odoo-1 cat \
  /usr/lib/python3/dist-packages/odoo/addons/point_of_sale/static/src/app/screens/login_screen/login_screen.scss
```
Expected: `.login-overlay` sets its background from `var(--homeMenu-bg-color, ...)` and `var(--homeMenu-bg-image, ...)`. Task 3 already points both at the theme, so the wallpaper needs no template override — only a scrim.

- [ ] **Step 2: Add the scrim and the entry typography**

`his_pos_ui/static/src/scss/login.scss`:
```scss
// The wallpaper is a photograph, so the text over it needs a floor it can
// stand on. The scrim lives in CSS rather than baked into the image: contrast
// stays tunable without re-exporting an asset, and one image serves any future
// light variant.

.his-pos .login-overlay {
    position: relative;

    &::before {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(
            180deg,
            rgba(0, 0, 0, 0.35) 0%,
            rgba(0, 0, 0, 0.65) 100%
        );
        pointer-events: none;
    }

    // Everything the cashier reads sits above the scrim.
    > * {
        position: relative;
        z-index: 1;
        color: #fff;
    }

    .timer-hours {
        font-variant-numeric: tabular-nums;
    }
}
```

- [ ] **Step 3: Record what the image folder needs**

`his_pos_ui/static/src/img/README.md`:
```markdown
# Wallpapers

One per point of sale, named for the theme that loads it:

| File | Theme |
|---|---|
| `copy_center.webp` | `copy_center` |
| `restaurant.webp` | `restaurant` |
| `cafeteria.webp` | `cafeteria` |

Long edge 1920px, WebP. They are decorative: no alt text, no meaning carried.

A missing file is not a failure. `tokens.scss` sets `--his-wallpaper-color`
alongside the image, so an absent wallpaper degrades to the theme's deep tone
and the entry screen still looks deliberate.
```

- [ ] **Step 4: Verify both paths**

Open a themed POS's login screen with no image files present and confirm it shows the theme's deep tone with legible white text. Drop the images in, reload, and confirm the photograph appears behind the same legible text.

- [ ] **Step 5: Commit**

```bash
git add his_pos_ui/static/src/scss/login.scss his_pos_ui/static/src/img/README.md
git commit -m "[ADD] his_pos_ui : ecran d'entree, voile et repli sans image"
```

---

### Task 5: `his_pos_copy_center` skeleton and the copy dimension fields

**Files:**
- Create: `his_pos_copy_center/__init__.py`
- Create: `his_pos_copy_center/__manifest__.py`
- Create: `his_pos_copy_center/models/__init__.py`
- Create: `his_pos_copy_center/models/product_template.py`
- Create: `his_pos_copy_center/views/product_template_views.xml`
- Create: `his_pos_copy_center/tests/__init__.py`
- Test: `his_pos_copy_center/tests/test_copy_products.py`

**Interfaces:**
- Consumes: `his_pos_ui` (dependency only).
- Produces: on `product.template` — `copy_service` (`photocopie`/`impression`), `copy_format` (`a4`/`a3`), `copy_color` (`bw`/`color`), `copy_sides` (`recto`/`duplex`). Task 7's JS reads all four off loaded products.

- [ ] **Step 1: Write the failing test**

```python
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCopyProducts(TransactionCase):
    """Tagging a copy product must not fight the MDM.

    his_stock_mdm forbids the Format attribute on copy categories, which is why
    these dimensions are plain fields on the template rather than attributes.
    The last test here is the one that guards that decision: if someone later
    'improves' this into attributes, it fails loudly.
    """

    def test_a_copy_product_carries_its_dimensions(self):
        product = self.env['product.template'].create({
            'name': "Photocopie A4 N&B Recto",
            'type': 'consu',
            'list_price': 10.0,
            'available_in_pos': True,
            'copy_service': 'photocopie',
            'copy_format': 'a4',
            'copy_color': 'bw',
            'copy_sides': 'recto',
        })
        self.assertEqual(product.copy_service, 'photocopie')
        self.assertEqual(product.copy_format, 'a4')

    def test_an_ordinary_product_is_untouched(self):
        product = self.env['product.template'].create({'name': "Stylo"})
        self.assertFalse(product.copy_service)
        self.assertFalse(product.copy_format)

    def test_tagging_does_not_trip_the_mdm_rule(self):
        """The whole reason these are fields and not attributes."""
        product = self.env['product.template'].create({
            'name': "Photocopie A3 Couleur Recto-verso",
            'type': 'consu',
            'list_price': 30.0,
            'copy_service': 'photocopie',
            'copy_format': 'a3',
            'copy_color': 'color',
            'copy_sides': 'duplex',
        })
        # No ValidationError: nothing here creates an attribute line.
        self.assertTrue(product.id)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker compose run --rm -T odoo odoo -d his_dev -i his_pos_copy_center --test-enable --test-tags /his_pos_copy_center --stop-after-init --max-cron-threads=0
```
Expected: FAIL — module not found.

- [ ] **Step 3: Create the skeleton**

`his_pos_copy_center/__init__.py`:
```python
from . import models
```

`his_pos_copy_center/models/__init__.py`:
```python
from . import product_template
```

`his_pos_copy_center/__manifest__.py`:
```python
{
    'name': 'HIS POS Copy Center',
    'version': '19.0.1.0.0',
    'summary': 'One dialog to price a copy job, instead of one popup per dimension',
    'description': """
HIS POS Copy Center
===================
A copy is priced by its dimensions - copies, format, colour, sides - and stock
POS makes the cashier answer one popup per dimension, per document.

* The dimensions are plain fields on the product, not attributes. his_stock_mdm
  forbids the Format attribute on the copy categories (MDM rule 6), and its own
  error text prescribes the alternative: a distinct product per physical
  variation. This module labels those products so a till can find them.
* The builder resolves one product and adds one ordinary order line. It reads a
  price, it never computes one.
* A product carrying no copy_service is invisible to the builder and behaves
  exactly as it does today.
""",
    'author': 'Abdo Chabouti',
    'category': 'Sales/Point of Sale',
    'license': 'LGPL-3',

    'depends': ['his_pos_ui'],

    'data': [
        'views/product_template_views.xml',
    ],

    'demo': [
        'demo/copy_products.xml',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'his_pos_copy_center/static/src/**/*',
        ],
    },

    'installable': True,
}
```

- [ ] **Step 4: Add the fields**

`his_pos_copy_center/models/product_template.py`:
```python
from odoo import fields, models


class ProductTemplate(models.Model):
    """The dimensions a copy is priced by, as labels on the product.

    Not attributes, and not by choice: his_stock_mdm's MDM rule 6 permits the
    Format attribute only on the cafe, restaurant and menage categories, and
    enforces it with a ValidationError. Its message prescribes what to do
    instead - "une variation physique doit etre portee par une fiche produit
    distincte" - so A4 N&B Recto and A3 Couleur Recto-verso are separate
    products, and these fields are how the till recognises which is which.

    Nothing here prices anything. The price is the product's own.
    """

    _inherit = 'product.template'

    copy_service = fields.Selection(
        [('photocopie', "Photocopie"), ('impression', "Impression")],
        string="Copy Service",
        help="Marks this product as a copy service the Copy Center job builder "
             "can offer. Leave empty for every other product.",
    )
    copy_format = fields.Selection(
        [('a4', "A4"), ('a3', "A3")], string="Copy Format")
    copy_color = fields.Selection(
        [('bw', "N&B"), ('color', "Couleur")], string="Copy Colour")
    copy_sides = fields.Selection(
        [('recto', "Recto"), ('duplex', "Recto-verso")], string="Copy Sides")
```

- [ ] **Step 5: Expose the fields in the product form**

`his_pos_copy_center/views/product_template_views.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <record id="view_product_template_form_copy" model="ir.ui.view">
        <field name="name">product.template.form.copy.center</field>
        <field name="model">product.template</field>
        <field name="inherit_id" ref="product.product_template_form_view"/>
        <field name="arch" type="xml">
            <xpath expr="//page[@name='general_information']" position="inside">
                <group string="Copy Center" name="his_copy_center">
                    <field name="copy_service"/>
                    <field name="copy_format" invisible="not copy_service"/>
                    <field name="copy_color" invisible="not copy_service"/>
                    <field name="copy_sides" invisible="not copy_service"/>
                </group>
            </xpath>
        </field>
    </record>
</odoo>
```

- [ ] **Step 6: Run the tests and watch them pass**

```bash
docker compose run --rm -T odoo odoo -d his_dev -i his_pos_copy_center --test-enable --test-tags /his_pos_copy_center --stop-after-init --max-cron-threads=0
```
Expected: PASS, 3 tests.

- [ ] **Step 7: Commit**

```bash
git add his_pos_copy_center
git commit -m "[ADD] his_pos_copy_center : dimensions de copie portees par le produit"
```

---

### Task 6: Demo products, because the catalogue is empty

**Files:**
- Create: `his_pos_copy_center/demo/copy_products.xml`

**Interfaces:**
- Consumes: the four fields from Task 5.
- Produces: eight demo photocopy products, used by the Task 8 tour. The Copy Center `pos.config` also gets `his_pos_theme = copy_center` here.

- [ ] **Step 1: Confirm the catalogue really is empty**

```bash
docker exec his-odoo-addons-db-1 psql -U odoo -d his_dev -tAc \
  "select count(*) from product_template pt join product_category pc on pt.categ_id=pc.id where pc.complete_name like '%Copy%'"
```
Expected: `0`. This is why demo data exists — a tour cannot shop in an empty shop.

- [ ] **Step 2: Write the demo data**

`his_pos_copy_center/demo/copy_products.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <data noupdate="1">
        <!-- Demo only. The real catalogue belongs to whoever runs the MDM, not
             to this module: it ships the shape of a copy product, not a price
             list anyone should sell from.

             Eight products - the full A4/A3 x N&B/Couleur x Recto/Recto-verso
             grid for Photocopie - so the builder has something to resolve
             against and the tour has something to buy. -->

        <record id="product_copy_a4_bw_recto" model="product.template">
            <field name="name">Photocopie A4 N&amp;B Recto</field>
            <field name="type">consu</field>
            <field name="list_price">10.0</field>
            <field name="available_in_pos" eval="True"/>
            <field name="copy_service">photocopie</field>
            <field name="copy_format">a4</field>
            <field name="copy_color">bw</field>
            <field name="copy_sides">recto</field>
        </record>
        <record id="product_copy_a4_bw_duplex" model="product.template">
            <field name="name">Photocopie A4 N&amp;B Recto-verso</field>
            <field name="type">consu</field>
            <field name="list_price">15.0</field>
            <field name="available_in_pos" eval="True"/>
            <field name="copy_service">photocopie</field>
            <field name="copy_format">a4</field>
            <field name="copy_color">bw</field>
            <field name="copy_sides">duplex</field>
        </record>
        <record id="product_copy_a4_color_recto" model="product.template">
            <field name="name">Photocopie A4 Couleur Recto</field>
            <field name="type">consu</field>
            <field name="list_price">40.0</field>
            <field name="available_in_pos" eval="True"/>
            <field name="copy_service">photocopie</field>
            <field name="copy_format">a4</field>
            <field name="copy_color">color</field>
            <field name="copy_sides">recto</field>
        </record>
        <record id="product_copy_a4_color_duplex" model="product.template">
            <field name="name">Photocopie A4 Couleur Recto-verso</field>
            <field name="type">consu</field>
            <field name="list_price">70.0</field>
            <field name="available_in_pos" eval="True"/>
            <field name="copy_service">photocopie</field>
            <field name="copy_format">a4</field>
            <field name="copy_color">color</field>
            <field name="copy_sides">duplex</field>
        </record>
        <record id="product_copy_a3_bw_recto" model="product.template">
            <field name="name">Photocopie A3 N&amp;B Recto</field>
            <field name="type">consu</field>
            <field name="list_price">20.0</field>
            <field name="available_in_pos" eval="True"/>
            <field name="copy_service">photocopie</field>
            <field name="copy_format">a3</field>
            <field name="copy_color">bw</field>
            <field name="copy_sides">recto</field>
        </record>
        <record id="product_copy_a3_bw_duplex" model="product.template">
            <field name="name">Photocopie A3 N&amp;B Recto-verso</field>
            <field name="type">consu</field>
            <field name="list_price">30.0</field>
            <field name="available_in_pos" eval="True"/>
            <field name="copy_service">photocopie</field>
            <field name="copy_format">a3</field>
            <field name="copy_color">bw</field>
            <field name="copy_sides">duplex</field>
        </record>
        <record id="product_copy_a3_color_recto" model="product.template">
            <field name="name">Photocopie A3 Couleur Recto</field>
            <field name="type">consu</field>
            <field name="list_price">80.0</field>
            <field name="available_in_pos" eval="True"/>
            <field name="copy_service">photocopie</field>
            <field name="copy_format">a3</field>
            <field name="copy_color">color</field>
            <field name="copy_sides">recto</field>
        </record>
        <record id="product_copy_a3_color_duplex" model="product.template">
            <field name="name">Photocopie A3 Couleur Recto-verso</field>
            <field name="type">consu</field>
            <field name="list_price">140.0</field>
            <field name="available_in_pos" eval="True"/>
            <field name="copy_service">photocopie</field>
            <field name="copy_format">a3</field>
            <field name="copy_color">color</field>
            <field name="copy_sides">duplex</field>
        </record>
    </data>
</odoo>
```

- [ ] **Step 3: Load the demo data and verify**

```bash
docker compose run --rm -T odoo odoo -d his_dev -u his_pos_copy_center --stop-after-init --max-cron-threads=0
docker exec his-odoo-addons-db-1 psql -U odoo -d his_dev -tAc \
  "select name->>'en_US', list_price from product_template where copy_service is not null order by list_price"
```
Expected: the eight photocopy products.

If the database was created without demo data, these records will not load. Check with:
```bash
docker exec his-odoo-addons-db-1 psql -U odoo -d his_dev -tAc \
  "select demo from ir_module_module where name='base'"
```
If it reports `f`, create the products by hand in the backend for testing rather than forcing demo mode on an existing database.

- [ ] **Step 4: Commit**

```bash
git add his_pos_copy_center/demo
git commit -m "[ADD] his_pos_copy_center : produits de demo pour le builder"
```

---

### Task 7: The job builder dialog

**Files:**
- Create: `his_pos_copy_center/static/src/app/copy_job_dialog.js`
- Create: `his_pos_copy_center/static/src/app/copy_job_dialog.xml`
- Create: `his_pos_copy_center/static/src/app/copy_job_dialog.scss`
- Create: `his_pos_copy_center/static/src/app/control_buttons.js`
- Create: `his_pos_copy_center/static/src/app/control_buttons.xml`

**Interfaces:**
- Consumes: `copy_service`/`copy_format`/`copy_color`/`copy_sides` on loaded products (Task 5); `--his-accent` and friends (Task 3).
- Produces: a control button carrying class `js_copy_job`, and a dialog whose primary action carries class `js_copy_job_add` — both are what the Task 8 tour clicks.

- [ ] **Step 1: Read how the existing HIS control button does it**

```bash
cat his_meal_management/static/src/app/control_buttons.js
cat his_meal_management/static/src/app/control_buttons.xml
```
That patch is the house pattern for adding a POS control button: follow it rather than inventing a second way.

- [ ] **Step 2: Write the dialog component**

`his_pos_copy_center/static/src/app/copy_job_dialog.js`:
```javascript
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Component, useState } from "@odoo/owl";

// One dialog instead of one popup per dimension.
//
// It resolves a product and adds an ordinary order line. It never computes a
// price: the figure on screen is read off the product POS already loaded, so
// the total the cashier reads and the total the server charges cannot drift
// apart - there is only ever one number.
export class CopyJobDialog extends Component {
    static template = "his_pos_copy_center.CopyJobDialog";
    static components = { Dialog };
    static props = {
        pos: Object,
        close: Function,
    };

    setup() {
        this.pos = this.props.pos;
        this.state = useState({
            service: "photocopie",
            format: "a4",
            color: "bw",
            sides: "recto",
            copies: 1,
        });
    }

    get products() {
        return this.pos.models["product.product"].filter((p) => p.copy_service);
    }

    get availableServices() {
        return [...new Set(this.products.map((p) => p.copy_service))];
    }

    // The one product matching all four chips, or nothing.
    get matchedProduct() {
        return this.products.find(
            (p) =>
                p.copy_service === this.state.service &&
                p.copy_format === this.state.format &&
                p.copy_color === this.state.color &&
                p.copy_sides === this.state.sides
        );
    }

    get unitPrice() {
        const product = this.matchedProduct;
        return product ? product.lst_price : 0;
    }

    get total() {
        return this.unitPrice * this.state.copies;
    }

    get formattedUnitPrice() {
        return this.pos.env.utils.formatCurrency(this.unitPrice);
    }

    get formattedTotal() {
        return this.pos.env.utils.formatCurrency(this.total);
    }

    pick(dimension, value) {
        this.state[dimension] = value;
    }

    isPicked(dimension, value) {
        return this.state[dimension] === value;
    }

    addCopies(n) {
        this.state.copies = Math.max(1, this.state.copies + n);
    }

    setCopies(ev) {
        const value = parseInt(ev.target.value, 10);
        this.state.copies = Number.isFinite(value) && value > 0 ? value : 1;
    }

    // Returns true when a line was added, so the caller knows whether to close
    // or to leave the dialog standing for a correction.
    async addLine() {
        const product = this.matchedProduct;
        if (!product) {
            this.pos.env.services.dialog.add(AlertDialog, {
                title: _t("No such copy"),
                body: _t(
                    "No product is configured for %(format)s / %(color)s / %(sides)s. " +
                        "Tell the Copy Center manager: this is a catalogue gap, not your mistake.",
                    {
                        format: this.state.format.toUpperCase(),
                        color: this.state.color === "bw" ? _t("N&B") : _t("Couleur"),
                        sides:
                            this.state.sides === "recto"
                                ? _t("Recto")
                                : _t("Recto-verso"),
                    }
                ),
            });
            return false;
        }

        if (!product.lst_price) {
            this.pos.env.services.dialog.add(AlertDialog, {
                title: _t("No price"),
                body: _t(
                    "%s carries no price, so it cannot be sold. Set its price before using it.",
                    product.display_name
                ),
            });
            return false;
        }

        await this.pos.addLineToCurrentOrder(
            {
                product_tmpl_id: product.product_tmpl_id,
                product_id: product,
                qty: this.state.copies,
            },
            {}
        );
        return true;
    }

    async onAddAndClose() {
        if (await this.addLine()) {
            this.props.close();
        }
    }

    // A job is several documents, so the form resets and stays open. Each
    // document is one ordinary order line; there is no job header.
    // ponytail: no his.copy.job model. Add one only if a saved, referenced
    // multi-document job turns out to be a real need.
    async onAddAnother() {
        if (await this.addLine()) {
            this.state.copies = 1;
        }
    }
}
```

- [ ] **Step 3: Write the dialog template**

`his_pos_copy_center/static/src/app/copy_job_dialog.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates id="template" xml:space="preserve">
    <t t-name="his_pos_copy_center.CopyJobDialog">
        <Dialog title="'Copy job'" size="'md'">
            <div class="his-copy-job">

                <t t-if="availableServices.length > 1">
                    <div class="his-copy-job-row">
                        <span class="his-copy-job-label">Service</span>
                        <div class="his-copy-job-chips">
                            <button t-foreach="availableServices" t-as="service" t-key="service"
                                class="btn his-chip"
                                t-att-class="{ 'his-chip-on': isPicked('service', service) }"
                                t-on-click="() => this.pick('service', service)">
                                <t t-esc="service"/>
                            </button>
                        </div>
                    </div>
                </t>

                <div class="his-copy-job-row">
                    <span class="his-copy-job-label">Format</span>
                    <div class="his-copy-job-chips">
                        <button class="btn his-chip" t-att-class="{ 'his-chip-on': isPicked('format', 'a4') }"
                            t-on-click="() => this.pick('format', 'a4')">A4</button>
                        <button class="btn his-chip" t-att-class="{ 'his-chip-on': isPicked('format', 'a3') }"
                            t-on-click="() => this.pick('format', 'a3')">A3</button>
                    </div>
                </div>

                <div class="his-copy-job-row">
                    <span class="his-copy-job-label">Colour</span>
                    <div class="his-copy-job-chips">
                        <button class="btn his-chip" t-att-class="{ 'his-chip-on': isPicked('color', 'bw') }"
                            t-on-click="() => this.pick('color', 'bw')">N&amp;B</button>
                        <button class="btn his-chip" t-att-class="{ 'his-chip-on': isPicked('color', 'color') }"
                            t-on-click="() => this.pick('color', 'color')">Couleur</button>
                    </div>
                </div>

                <div class="his-copy-job-row">
                    <span class="his-copy-job-label">Sides</span>
                    <div class="his-copy-job-chips">
                        <button class="btn his-chip" t-att-class="{ 'his-chip-on': isPicked('sides', 'recto') }"
                            t-on-click="() => this.pick('sides', 'recto')">Recto</button>
                        <button class="btn his-chip" t-att-class="{ 'his-chip-on': isPicked('sides', 'duplex') }"
                            t-on-click="() => this.pick('sides', 'duplex')">Recto-verso</button>
                    </div>
                </div>

                <div class="his-copy-job-row his-copy-job-copies">
                    <span class="his-copy-job-label">Copies</span>
                    <div class="his-copy-job-stepper">
                        <button class="btn his-step" t-on-click="() => this.addCopies(-1)">−</button>
                        <input type="number" min="1" class="his-copy-count"
                            t-att-value="state.copies" t-on-change="setCopies"/>
                        <button class="btn his-step" t-on-click="() => this.addCopies(1)">+</button>
                    </div>
                </div>

                <div class="his-copy-job-total">
                    <t t-if="matchedProduct">
                        <span class="his-copy-job-calc">
                            <t t-esc="state.copies"/> × <t t-esc="formattedUnitPrice"/>
                        </span>
                        <span class="his-copy-job-amount" t-esc="formattedTotal"/>
                    </t>
                    <t t-else="">
                        <span class="his-copy-job-missing">No product for this combination</span>
                    </t>
                </div>
            </div>

            <t t-set-slot="footer">
                <button class="btn btn-secondary btn-lg" t-on-click="onAddAnother">
                    Add another document
                </button>
                <button class="btn btn-primary btn-lg js_copy_job_add" t-on-click="onAddAndClose">
                    Add to order
                </button>
            </t>
        </Dialog>
    </t>
</templates>
```

- [ ] **Step 4: Style the dialog**

`his_pos_copy_center/static/src/app/copy_job_dialog.scss`:
```scss
// Chips are the whole interaction, so they are sized for a fingertip and their
// selected state is unmistakable across a counter.

.his-copy-job {
    display: flex;
    flex-direction: column;
    gap: 1rem;

    .his-copy-job-row {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .his-copy-job-label {
        flex: 0 0 5.5rem;
        color: var(--his-text-muted, #5b6470);
        font-weight: 600;
    }

    .his-copy-job-chips {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
    }

    .his-chip {
        min-height: 56px;
        min-width: 6rem;
        border: 2px solid var(--his-border, #d8dbe0);
        border-radius: 0.75rem;
        background: var(--his-surface-raised, #fff);
        font-size: 1.05rem;
        font-weight: 600;
    }

    .his-chip-on {
        border-color: var(--his-accent, #2f6feb);
        background: var(--his-accent, #2f6feb);
        color: var(--his-accent-contrast, #fff);
    }

    .his-copy-job-stepper {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .his-step {
        min-width: 56px;
        min-height: 56px;
        font-size: 1.5rem;
        border: 2px solid var(--his-border, #d8dbe0);
        border-radius: 0.75rem;
    }

    .his-copy-count {
        width: 6rem;
        height: 56px;
        text-align: center;
        font-size: 1.5rem;
        font-variant-numeric: tabular-nums;
        border: 2px solid var(--his-border, #d8dbe0);
        border-radius: 0.75rem;
    }

    .his-copy-job-total {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        border-top: 1px solid var(--his-border, #d8dbe0);
        padding-top: 0.75rem;
    }

    .his-copy-job-calc {
        color: var(--his-text-muted, #5b6470);
        font-variant-numeric: tabular-nums;
    }

    .his-copy-job-amount {
        font-size: 1.75rem;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }

    .his-copy-job-missing {
        color: #b42318;
        font-weight: 600;
    }
}
```

- [ ] **Step 5: Add the control button that opens it**

`his_pos_copy_center/static/src/app/control_buttons.js`:
```javascript
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { CopyJobDialog } from "./copy_job_dialog";

patch(ControlButtons.prototype, {
    // Hidden unless this till actually sells copies, so the button never opens
    // onto an empty form.
    get hasCopyProducts() {
        return this.pos.models["product.product"].some((p) => p.copy_service);
    },

    clickCopyJob() {
        this.dialog.add(CopyJobDialog, { pos: this.pos });
    },
});
```

`his_pos_copy_center/static/src/app/control_buttons.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates id="template" xml:space="preserve">
    <t t-name="his_pos_copy_center.ControlButtons" t-inherit="point_of_sale.ControlButtons" t-inherit-mode="extension">
        <xpath expr="//SelectPartnerButton" position="after">
            <button t-if="hasCopyProducts and !props.showRemainingButtons"
                class="btn btn-primary btn-lg border-0 js_copy_job"
                t-on-click="() => this.clickCopyJob()">
                <i class="fa fa-copy me-1" role="img" aria-label="Copy job" title="Copy job"/>
                Copy job
            </button>
        </xpath>
    </t>
</templates>
```

- [ ] **Step 6: Try it by hand before automating it**

```bash
docker compose run --rm -T odoo odoo -d his_dev -u his_pos_copy_center --stop-after-init --max-cron-threads=0
docker compose restart odoo
```
Open the Copy Center POS. Confirm, in order:
1. the *Copy job* button is present;
2. picking A4 / Couleur / Recto shows `1 × 40,00` and a matching total;
3. setting copies to 24 shows `24 × 40,00` and `960,00`;
4. *Add to order* produces one order line of quantity 24 at that price;
5. picking a combination with no product shows the missing-combination message and adds nothing.

- [ ] **Step 7: Commit**

```bash
git add his_pos_copy_center/static
git commit -m "[ADD] his_pos_copy_center : dialogue de composition d'un travail de copie"
```

---

### Task 8: The tour that proves it

**Files:**
- Create: `his_pos_copy_center/static/tests/tours/copy_job_tour.js`
- Create: `his_pos_copy_center/tests/test_copy_job_tour.py`
- Modify: `his_pos_copy_center/__manifest__.py` — add the `web.assets_tests` bundle

**Interfaces:**
- Consumes: `js_copy_job` and `js_copy_job_add` from Task 7; the demo products from Task 6.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Find the house pattern for POS tours**

```bash
docker exec his-odoo-addons-odoo-1 sh -c \
  "ls /usr/lib/python3/dist-packages/odoo/addons/point_of_sale/static/tests/tours/ && \
   sed -n 1,40p /usr/lib/python3/dist-packages/odoo/addons/point_of_sale/static/tests/tours/*.js | head -60"
```
Use whatever helper module the stock tours import (`utils/product_screen_util`, `utils/common`, and friends) rather than hand-rolling selectors.

- [ ] **Step 2: Write the tour**

`his_pos_copy_center/static/tests/tours/copy_job_tour.js`:
```javascript
import { registry } from "@web/core/registry";
import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";

registry.category("web_tour.tours").add("his_copy_job_tour", {
    steps: () => [
        Chrome.startPoS(),
        Dialog.confirm("Open Register"),
        {
            content: "Open the copy job builder",
            trigger: ".js_copy_job",
            run: "click",
        },
        {
            content: "Pick A4 colour recto",
            trigger: ".his-copy-job",
            run: () => {},
        },
        {
            content: "Choose Couleur",
            trigger: ".his-copy-job button:contains('Couleur')",
            run: "click",
        },
        {
            content: "Set 24 copies",
            trigger: ".his-copy-count",
            run: "edit 24",
        },
        {
            content: "The total is read, never computed",
            trigger: ".his-copy-job-amount",
            run: () => {},
        },
        {
            content: "Add the job to the order",
            trigger: ".js_copy_job_add",
            run: "click",
        },
        ProductScreen.selectedOrderlineHas("Photocopie A4 Couleur Recto", "24"),
    ],
});
```

Selector helpers move between Odoo versions. If `selectedOrderlineHas` does not exist in this build, read the util file listed in Step 1 and use the one that does — do not invent a helper name.

- [ ] **Step 3: Register the tour bundle**

In `his_pos_copy_center/__manifest__.py`, extend `assets`:
```python
    'assets': {
        'point_of_sale._assets_pos': [
            'his_pos_copy_center/static/src/**/*',
        ],
        'web.assets_tests': [
            'his_pos_copy_center/static/tests/tours/**/*',
        ],
    },
```

- [ ] **Step 4: Write the Python side of the tour**

`his_pos_copy_center/tests/test_copy_job_tour.py`:
```python
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.common import CommonPosTest


@tagged('post_install', '-at_install')
class TestCopyJobTour(CommonPosTest):
    """The builder, driven the way a cashier drives it.

    The assertion that matters is the last one: the order line carries the
    product the chips described, at the quantity typed. If that holds, the
    dialog is a face over the catalogue and nothing more - which is the whole
    design.
    """

    def test_copy_job_adds_one_line(self):
        config = self.env.ref('his_stock_mdm.pos_config_copy_center')
        config.write({'his_pos_theme': 'copy_center'})
        config.with_user(self.env.user).open_ui()
        self.start_pos_tour("his_copy_job_tour", login="accountman", pos_config=config)
```

`CommonPosTest` and `start_pos_tour` are the Odoo 19 helpers. Confirm both before running:
```bash
docker exec his-odoo-addons-odoo-1 sh -c \
  "grep -n 'def start_pos_tour\|class CommonPosTest' /usr/lib/python3/dist-packages/odoo/addons/point_of_sale/tests/common.py"
```
If the helper is named differently in this build, follow whatever `point_of_sale`'s own tour tests do.

- [ ] **Step 5: Run the tour**

```bash
docker compose run --rm -T odoo odoo -d his_dev -u his_pos_copy_center --test-enable --test-tags /his_pos_copy_center --stop-after-init --max-cron-threads=0
```
Expected: PASS. A tour failure prints the step it died on — fix the selector, not the assertion.

- [ ] **Step 6: Commit**

```bash
git add his_pos_copy_center/static/tests his_pos_copy_center/tests his_pos_copy_center/__manifest__.py
git commit -m "[ADD] his_pos_copy_center : tour POS du builder de copies"
```

---

### Task 9: Documentation and the repository index

**Files:**
- Create: `his_pos_ui/README.md`
- Create: `his_pos_copy_center/README.md`
- Modify: `README.md` — the module table

**Interfaces:**
- Consumes: everything above.
- Produces: nothing.

- [ ] **Step 1: Write `his_pos_ui/README.md`**

Follow the house style set by `his_meal_management/README.md`: state the governing idea first as a block quote, then an ownership table saying what the module owns and what it does not, then the deviations it assumes. The governing idea here:

> **The interface may be redesigned; the transaction may not.**

Cover: the theme field and why it is a Selection rather than a model; why the theme is CSS behind a class and never a patched component; the two Odoo variables reused (`--btn-height-size`, `--homeMenu-bg-image`) and why reusing them beat overriding rules; the wallpaper fallback; and the RTL ceiling (`pos_app.scss` forces `direction: ltr`).

- [ ] **Step 2: Write `his_pos_copy_center/README.md`**

Same style. The governing idea:

> **The dimensions are fields, not attributes, and `his_stock_mdm` decided that.**

Cover: MDM rule 6 and the exact constraint that forbids `Format` on copy categories; why that makes A4 N&B Recto a distinct product; how the four fields tag those products; that the builder reads a price and never computes one; the missing-combination message being a catalogue gap rather than a cashier error; and the `ponytail:` note that there is no `his.copy.job` model yet.

- [ ] **Step 3: Update the repository module table**

In the root `README.md`, add two rows and retire the "Point de Vente avancé — Autre intervenant" placeholder line for the part now covered:

```markdown
| [`his_pos_ui`](his_pos_ui/) | POS — habillage partagé, identité par point de vente, ergonomie tactile | Développé |
| [`his_pos_copy_center`](his_pos_copy_center/) | POS Copy Center — composition d'un travail de copie en un écran | Développé |
```

- [ ] **Step 4: Commit**

```bash
git add README.md his_pos_ui/README.md his_pos_copy_center/README.md
git commit -m "[DOC] POS : README des deux modules d'interface"
```

---

## What this plan does not do

Recorded so the next person does not think they were forgotten:

- **Restaurant and Cafétéria flows.** Their own specs. The meal plans (Weekly, Monthly, Semester, Daily Meal) are already modelled and tested in `his_meal_management`; what they lack is UI, and that belongs to the Restaurant spec.
- **A `his.copy.job` model.** Marked with a `ponytail:` comment in Task 7. Add it only if a saved, referenced, multi-document job becomes a real requirement.
- **Print spooling.** The builder prices copies. It does not receive files or talk to a printer.
- **RTL layout.** `.pos` forces `direction: ltr` in stock Odoo. Arabic strings translate; the layout does not mirror.
- **The three wallpaper images.** They must be dropped into `his_pos_ui/static/src/img/`. Every theme degrades to a solid tone until they are.
