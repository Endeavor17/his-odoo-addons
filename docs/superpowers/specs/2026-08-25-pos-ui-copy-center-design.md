# POS Frontend — Theme Layer and Copy Center Job Builder

Design for the Point of Sale user interface of the Groupe HIS-HTC-IRA.

The governing idea, stated first:

> **The interface may be redesigned; the transaction may not.** Every screen in
> this design ends by writing an ordinary POS order line carrying an ordinary
> product variant. Price, tax, stock and accounting stay stock Odoo. Nothing in
> the browser computes money.

---

## 1. Scope and decomposition

Three points of sale exist (`his_stock_mdm/data/pos_config_data.xml`):
Cafétéria, Restaurant, Copy Center. Their flows differ enough that one spec
covering all three would be three specs in a trench coat. This document covers:

| Phase | Deliverable | Status |
|---|---|---|
| 1 | `his_pos_ui` — shared theme tokens, per-POS identity, touch sizing | this spec |
| 2 | `his_pos_ui` — branded entry / session-open, scan-first identification | this spec |
| 3 | `his_pos_copy_center` — copy job builder | this spec |
| 4 | Restaurant flow (courses, meal-credit banner) | **its own spec, later** |
| 5 | Cafétéria flow (quick-serve grid) | **its own spec, later** |

Copy Center goes first deliberately: it is the flow stock Odoo serves worst, so
it is the one that proves the architecture. If a job builder can sit on top of
product variants without inventing a pricing engine, the other two are easy.

## 2. Module architecture

Two modules, following the repository's one-module-one-domain convention.

```
his_pos_ui              theme tokens, POS identity, entry screen, touch sizing
    ^
    |
his_pos_copy_center     job builder popup, copy-service configuration
```

`his_pos_ui` depends on `point_of_sale` only. It knows nothing about copies,
meals or coffee — it knows how a HIS till should look and how a person is
identified at one. Restaurant and Cafétéria will depend on it without ever
loading Copy Center code.

`his_meal_management` is **not modified**. Its Student Meal control button
inherits the theme through the shared tokens, because it is styled with the
Bootstrap classes the theme already retunes.

### Why not one module

A single module gated by `pos.config` flags would ship every flow's JavaScript
to every till and would become the monolith this repository has so far avoided.
The cost of the split is one extra manifest.

## 3. The theme layer

### 3.1 How a till knows which theme it wears

A selection field on `pos.config`:

```python
his_pos_theme = fields.Selection([
    ('copy_center', "Copy Center"),
    ('restaurant', "Restaurant"),
    ('cafeteria', "Cafétéria"),
], string="HIS Theme")
```

Empty means stock Odoo appearance. Nothing breaks when it is unset; that is the
fallback the whole design leans on.

The field reaches the browser with no loader code. `pos.load.mixin`'s
`_load_pos_data_read` calls `read(fields)` where `pos.config` supplies no field
whitelist, and an empty list makes Odoo read every readable field. This is the
same reason `his_meal_management.meal_product_id` is readable from
`control_buttons.js` today without a `_load_pos_data_fields` override.

### 3.2 How the theme reaches the DOM

`point_of_sale.Chrome` renders the root `<div class="pos dvh-100 ...">`. A
single template inheritance adds a theme class to it, so everything else is CSS
scoped under `.his-theme-copy_center`, and so on.

No component is patched to apply styling. A theme that is only CSS cannot break
a transaction.

### 3.3 Tokens, not a restyle

Odoo's POS already exposes the two variables that matter most, and the design
uses them rather than overriding rules:

| Variable | Stock value | What we do |
|---|---|---|
| `--btn-height-size` | `54px` | raise to `64px` — finger targets without touching a single button rule |
| `--homeMenu-bg-image` | an `hr_attendance` SVG | point at the POS's own wallpaper |
| `--homeMenu-bg-color` | `$o-gray-200` | the theme's deep tone, so a missing image still looks deliberate |

On top of those, `his_pos_ui` defines its own custom properties per theme —
surface, elevated surface, text, muted text, accent, accent-contrast — and
restyles only what the token cannot reach: order lines, the numpad, the product
grid card, and the navbar.

### 3.4 Palette

The wallpapers are dark, warm and photographic. They cannot sit behind a working
grid without turning it to mush, so:

- **Wallpaper appears on entry, lock and session-open screens only.** Working
  screens are a calm near-neutral surface.
- **Every wallpaper carries a CSS scrim**, a gradient overlay applied in CSS
  rather than baked into the image, so contrast is tunable without re-exporting
  and one asset serves any future light variant.
- **One saturated accent per point of sale**, used for the primary action and
  nothing else:

| Point of sale | Accent | Rationale |
|---|---|---|
| Copy Center | ink blue | the toner and paper register; reads as administrative, not appetising |
| Restaurant | herb green | picks up the salad wallpaper without competing with food colour |
| Cafétéria | espresso amber | warm, matches the crema in the wallpaper |

Contrast targets: WCAG AA (4.5:1) for body text, 3:1 for large text and UI
boundaries — checked against the actual surface token, not assumed.

### 3.5 Typography and density

System font stack retained. A till is not the place to pay for a webfont round
trip on a cold session. What changes is scale and rhythm: order line amounts and
the total rise to a tabular-numeric display size, secondary metadata drops in
weight and contrast, and vertical padding grows to match the 64px target height.

### 3.6 Assets

Three wallpapers, exported as WebP with a JPEG fallback, long edge 1920px,
committed under `his_pos_ui/static/src/img/`. They are decorative and carry
empty alt text.

**Open item:** the three reference images were pasted into a chat and are not
files in this repository. Before Phase 1 can close, they must either be dropped
into that folder or replaced by licensed equivalents. The build is not blocked —
the colour tokens stand alone and the missing image degrades to
`--homeMenu-bg-color` by design.

## 4. The entry experience

Stock POS opens on a login overlay that is functional and anonymous. The change
is identity, not mechanics:

- the institution's mark and the point of sale's own name, so a cashier can see
  at a glance which till they are standing at;
- the POS wallpaper behind a scrim;
- the existing clock and session controls, restyled, not rebuilt.

**Scan-first identification.** `his_meal_management` already ships a barcode rule
that resolves a card to a `res.partner`. At Copy Center, identifying a person is
a convenience and never a gate: a walk-in pays cash and is nobody. So the scan
is offered, the resolved person is shown by name, and no flow blocks on its
absence. This is the opposite of the Restaurant, where a credit cannot move
without a person — one more reason those are separate specs.

## 5. The Copy Center job builder

### 5.1 The problem it solves

A copy is priced by dimensions, not by product identity: 24 copies, A4, colour,
recto-verso. Stock POS makes the cashier click a product, answer a variant popup
per attribute, then set quantity on the numpad — several popups per document,
repeated for every document in a job.

**The dimensions cannot be product attributes here, and that is decided by
`his_stock_mdm`, not by us.** Its MDM rule 6 is enforced as a hard
`ValidationError` in `product_template_attribute_line._check_mdm_categ_eligible`:
an attribute may only be used on the categories listed in its
`allowed_categ_ids`. `Variante` is permitted on `categ_copy_impression` and
`categ_copy_photocopie`; **`Format` is not permitted on any copy category** — it
is restricted to café, restaurant and ménage. A Photocopie template carrying
Format/Colour/Sides as three attributes would refuse to save.

The MDM states the alternative in the text of that very error: *"une variation
physique doit être portée par une fiche produit distincte."* So under this
governance, **A4 N&B Recto and A3 Couleur Recto-verso are distinct product
templates**, each with its own price and its own cost. That is the catalogue
this design must serve, and arguing with it would mean amending another module's
governance to satisfy a UI.

The builder therefore resolves a **product**, not a variant.

### 5.2 What it is

A dialog, launched from a control button, not a router screen. It borrows the
POS dialog service, leaves the router alone, and keeps the surface small enough
to delete if it disappoints.

```
  Service    [ Photocopie ] [ Impression ]
  Format     [    A4     ] [    A3     ]
  Colour     [   N&B     ] [  Couleur  ]
  Sides      [  Recto    ] [ Recto-verso ]

  Copies         [ − ]   24   [ + ]

  ────────────────────────────────────
  24 × 12,00 DA                288,00 DA

  [ Add another document ]   [ Add to order ]
```

Large chips, one tap per dimension, a stepper big enough for a finger, and the
running total visible before anything is committed.

### 5.3 How a chip finds its product

Four selection fields on `product.template`, owned by `his_pos_copy_center`:

```python
copy_service = fields.Selection([('photocopie', ...), ('impression', ...)])
copy_format  = fields.Selection([('a4', "A4"), ('a3', "A3")])
copy_color   = fields.Selection([('bw', "N&B"), ('color', "Couleur")])
copy_sides   = fields.Selection([('recto', "Recto"), ('duplex', "Recto-verso")])
```

They tag an existing product with the dimensions it already represents. They add
no attribute, create no variant, and touch no MDM rule — a product is simply
labelled with what it is, so the till can find it by description instead of by
name. A product carrying no `copy_service` is invisible to the builder and
behaves exactly as it does today.

This is deliberately a *lookup*, not a model: the four fields are how a Copy
Center manager declares "this template is the A4 colour recto-verso photocopy",
and the builder does nothing more than find the one product matching four
chips.

### 5.4 What it does not do

It calls the same `addLineToCurrentOrder` any product click uses, with quantity
set to the number of copies.

The displayed price is read from the product POS already loaded. It is a preview
of what the order line will say, not a calculation. If the two could ever
disagree, the price would have two sources of truth and one of them would be
JavaScript — precisely the mistake `his_meal_management` documents avoiding for
credits.

"Add another document" commits the current line and resets the form, so a job of
five documents is five ordinary order lines. There is **no job model** in this
phase. A `ponytail:` marker records the decision: if a saved multi-document job
header with its own reference turns out to be a real need, that is the moment to
add `his.copy.job`, not before.

Bureautique, Flexy top-ups and scan-only services stay ordinary product taps.
They have no dimensions worth a builder.

### 5.5 Language

Source strings are written in English and wrapped in `_t()`, with a French
`i18n/fr.po` shipped alongside. This matches `his_meal_management`, whose POS
strings are already English `_t()` calls, and it lets a till switch language per
user without a code change. The service and attribute names the cashier actually
taps — Photocopie, Impression, A4, Couleur — are **product and attribute data**,
not interface strings, so they read in French because that is how
`his_stock_mdm` created them. Nothing translates them and nothing should.

## 6. Data flow

```
pos.config.his_pos_theme ──► Chrome root class ──► CSS tokens          (styling only)

card scan ──► existing barcode rule ──► res.partner ──► order.setPartner  (optional)

builder chips ──► copy_service/format/color/sides ──► product.template
                                              │
                                              ▼
                                    addLineToCurrentOrder(product, copies)
                                              │
                                              ▼
                             stock POS order pipeline ──► server
```

No new RPC and no new model in any of the three phases. The builder reads only
models POS has already loaded into the browser.

## 7. Error handling

| Situation | Behaviour |
|---|---|
| `his_pos_theme` unset | stock Odoo appearance, no error |
| wallpaper file missing | falls back to `--homeMenu-bg-color` |
| no product matches the chosen combination | dialog naming the exact missing combination, so it reads as the configuration gap it is, not as cashier error |
| matched product carries no price | refuse to add the line and say so; never add a zero-priced line by accident |
| service products absent from this till | builder button hidden entirely rather than opening onto an empty form |

The theme cannot fail loudly by construction: it is CSS behind a class that may
be absent. The builder fails by refusing, never by guessing.

## 8. Testing

- **Python** — `pos.config.his_pos_theme`; the four `product.template` copy
  fields; and the guarantee that tagging a copy product does **not** trip
  `his_stock_mdm`'s MDM rule 6. Follows the existing `TransactionCase` style in
  `his_meal_management/tests/`.
- **JS tours** — Odoo's POS tour framework, two paths: a job built and added to
  the order with the expected line and quantity, and the missing-product refusal.
- **Demo data** — the copy categories are empty in `his_dev`; the tour cannot
  run against an empty catalogue, so `his_pos_copy_center` ships `demo/` products
  covering the eight photocopy combinations. Demo data only: the real catalogue
  belongs to whoever runs the MDM, not to this module.
- **Not tested** — appearance. No screenshot or snapshot suite. Contrast ratios
  are checked once, by hand, against the tokens.

## 9. Known ceilings

Recorded rather than solved:

- **RTL.** `pos_app.scss` sets `direction: ltr` on `.pos`. Arabic strings will
  translate; the layout will not mirror. Changing that is an Odoo-wide fight and
  is out of scope here.
- **No print spooler.** The builder prices copies; it does not receive files,
  queue jobs or talk to a printer. Nothing in this design forecloses that later.
- **Refunds.** Inherited stock POS behaviour, untouched.

## 10. Non-goals

No new dependency. No CSS framework. No component library. No design-token build
step — plain SCSS compiled by Odoo's existing asset pipeline, because that is
already installed and already works.
