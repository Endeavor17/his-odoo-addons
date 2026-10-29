# Copy Center: catalogue merge, real copy grid, paper out of stock — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Copy Center till sells the real copy grid at its posted prices (with the order-level B&W discount), every copy takes its paper out of stock, and the Copy Center catalogue is one merged list with no article twice.

**Architecture:** `his_pos_copy_center` grows from a dialog into the Copy Center's whole rule set: product fields (paper, bulk price, paper consumed), a server hook on the POS picking creation that adds paper moves, a POS order patch that applies the bulk price across the order. The catalogue side stays in `tools/`: a new fusion script produces a review workbook and a merged CSV, which the existing converter and importer consume.

**Tech Stack:** Odoo 19 Community (Python, OWL POS), openpyxl through `uv run --with openpyxl` for the workbook scripts, Docker container `his-odoo-addons-odoo-1` for tests.

**Spec:** `docs/superpowers/specs/2026-10-29-copy-center-catalogue-and-paper-design.md` (read it first; section numbers below refer to it).

## Global Constraints

- Branch `feature/copy-center-papier`, worktree `C:\Users\Mohamed\his-odoo-addons\.worktrees\copy-job`. Commits as `Endeavor <mohamed.bounouaa@outlook.com>`, **no `Co-Authored-By` trailer**. Message style `[IMP] …` / `[FIX] …` / `[ADD] …`, French, unaccented.
- UI source strings in **English**, French in `his_pos_copy_center/i18n/fr.po` for every new term (field labels, selection labels, menu, view strings, JS `_t`). Python comments: French, unaccented ASCII. One font, no new CSS font.
- `his_stock_mdm` rules hold: opaque `INV-NNNNNN` codes only (no `COP-`), terminal category, price mandatory when storable + sellable, no Format/Variante attribute on Copy categories, barcode unique.
- Prices (DA, tax included as today): exactly the §5 table. Bulk prices: Print Normal B&W Single **8**, Print Normal B&W Double **10**. Photocopies: never discounted, and their pages do not count.
- Threshold: B&W **print** pages on **normal paper** across the whole order **> 20** → every such line at its bulk price. Pages per unit: 1 single-sided, 2 double-sided. Colour and photocopies: never.
- Paper: one article per type — `Papier A4 80g`, `Papier Luxe`, `Papier Bristol`, `Papier Autocollant`, `Papier Glace`, `Papier Photo`, `Papier A5` — held in sheets (`uom.product_uom_unit`). One copy unit = 1 sheet (double-sided included).
- Consumption location: "Consommation Copy Center", usage `inventory`. Refunds never return paper.
- Module version: `his_pos_copy_center` 19.0.1.1.0 → **19.0.2.0.0**. Write the migration **before** bumping the version.
- Test command (referred to as **`$TEST`** below), on a throwaway copy of the local `ci` base:
  ```bash
  export MSYS_NO_PATHCONV=1
  docker exec his-odoo-addons-db-1 psql -U odoo -d postgres -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='ci'" -c "drop database if exists copyjob" -c "create database copyjob template ci"
  docker exec his-odoo-addons-odoo-1 odoo -d copyjob \
    --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons/.worktrees/copy-job \
    -u his_pos_copy_center --test-enable --test-tags /his_pos_copy_center \
    --http-port 8070 --stop-after-init 2>&1 | tail -40
  ```
  Green means `0 failed` **and** a non-zero test count. If `ci` lacks `his_pos_copy_center`, use `-i` instead of `-u` once.
- Lint before each commit: `~/.local/bin/uvx ruff@0.16.7 check . && ~/.local/bin/uvx ruff@0.16.7 format --check .` from the worktree root.
- POS tours do not run in the `odoo:19.0` image (no browser). JS behaviour is verified in Chrome against a running instance (Task 10) — a clean compile is not verification.

## Review Focus

1. **An order mixing B&W and colour lines crossing 20 pages** — only B&W normal lines reprice; colour lines keep list price. (Task 5, `copyBulkState` test case 3.)
2. **Removing a line or lowering a quantity back under 21 pages** — the earlier lines return to list price. (Task 5, case 4.)
3. **Session closed with "update stock at closing"** — the paper moves are created at closing exactly as at order time, once, not twice. (Task 2, `test_paper_moves_at_session_closing`.)
4. **A copy product whose paper article has no stock** — the sale still goes through, the paper quant goes negative, nothing blocks the till. (Task 2, `test_sale_without_paper_stock_goes_negative`.)
5. **Re-running the importer on staging where the 129 supplier-named products already exist** — they are renamed/updated in place, merged extras archived, nothing duplicated. (Task 8, `--test` case `rejouer_sur_base_existante`.)

---

### Task 1: Copy dimensions follow the real grid

**Files:**
- Modify: `his_pos_copy_center/models/product_template.py`
- Modify: `his_pos_copy_center/models/product_product.py`
- Modify: `his_pos_copy_center/views/product_template_views.xml`
- Create: `his_pos_copy_center/migrations/19.0.2.0.0/pre-migration.py`
- Modify: `his_pos_copy_center/__manifest__.py` (version, after the migration exists)
- Modify: `his_pos_copy_center/tests/test_copy_products.py`, `his_pos_copy_center/tests/test_copy_job_tour.py` (fixtures only), `his_pos_copy_center/demo/copy_products.xml`, `his_pos_copy_center/i18n/fr.po`

**Interfaces:**
- Produces on `product.template`:
  - `copy_paper = fields.Selection([("normal","Normal"),("a5","A5"),("bristol","Bristol"),("sticker","Sticker"),("glossy","Glossy"),("luxury","Luxury"),("photo","Photo")], string="Copy Paper")`
  - `copy_bulk_price = fields.Float("Price above 20 pages", digits="Product Price")` — empty/0 means no bulk price.
  - `copy_format` is **removed**.
- `_load_pos_data_fields` returns the old list minus `copy_format`, plus `copy_paper`, `copy_bulk_price`.

- [ ] **Step 1: Rewrite the tests** in `test_copy_products.py`: replace every `copy_format` with `copy_paper` (`"normal"`), and add:

```python
def test_bulk_price_is_a_second_stored_price(self):
    product = self.env["product.template"].create(
        {
            "name": "Impression N&B Recto",
            "type": "service",
            "list_price": 10.0,
            "copy_service": "impression",
            "copy_paper": "normal",
            "copy_color": "bw",
            "copy_sides": "recto",
            "copy_bulk_price": 8.0,
        }
    )
    self.assertEqual(product.copy_bulk_price, 8.0)
    self.assertEqual(product.list_price, 10.0)
```
  and in `test_the_dimensions_reach_the_till` iterate over `("copy_service", "copy_paper", "copy_color", "copy_sides", "copy_bulk_price")` and `assertNotIn("copy_format", fields)`.
- [ ] **Step 2: Run `$TEST`** — expected FAIL (`copy_paper` unknown).
- [ ] **Step 3: Pre-migration** `migrations/19.0.2.0.0/pre-migration.py`: `migrate(cr, version)` adds column `copy_paper varchar` to `product_template` if missing, sets `copy_paper = 'normal'` where `copy_format = 'a4'`, leaves `a3` rows with `copy_paper` NULL (no such product exists in staging/prod; the demo ones are rewritten). The ORM drops `copy_format` itself.
- [ ] **Step 4: Fields, POS whitelist, form view** (replace the Format field by Paper, add Bulk price under it, visible when `copy_service`), demo XML rewritten to the 16 rows of §5 (same names as Task 6's CSV, `copy_paper` set, `copy_bulk_price` on the two print B&W normal rows, `type` `service`), tour fixtures switched to `copy_paper: "normal"`. Bump manifest version to `19.0.2.0.0`. Update the module docstrings/README §1 where they say "format".
- [ ] **Step 5: fr.po** — add `Copy Paper` → « Papier », `Price above 20 pages` → « Prix au-delà de 20 pages », the seven selection labels (Normal → « Normal », Sticker → « Autocollant », Glossy → « Glacé », Luxury → « Luxe », Photo → « Photo », A5, Bristol), remove the A3/Format entries.
- [ ] **Step 6: Run `$TEST`** — expected PASS, count ≥ 6.
- [ ] **Step 7: Lint, commit** `[IMP] Copy Center : papier et prix au-dela de 20 pages a la place du format`.

### Task 2: Selling a copy takes its paper out of stock

**Files:**
- Create: `his_pos_copy_center/models/stock_picking.py`
- Create: `his_pos_copy_center/data/stock_location_data.xml`
- Create: `his_pos_copy_center/views/paper_consumption_views.xml`
- Modify: `his_pos_copy_center/models/__init__.py`, `models/product_template.py`, `views/product_template_views.xml`, `__manifest__.py` (add the two data files; `stock` comes through `point_of_sale`, no new dependency), `i18n/fr.po`
- Create: `his_pos_copy_center/tests/test_paper_consumption.py`; modify `tests/__init__.py`

**Interfaces:**
- Produces on `product.template`:
  - `copy_paper_product_id = fields.Many2one("product.product", string="Paper Used", domain=[("is_storable", "=", True)])`
  - `copy_sheets_per_unit = fields.Float("Sheets per Unit", default=1.0)`
- Produces record `his_pos_copy_center.loc_consommation_copy_center` (`stock.location`, name "Consommation Copy Center", usage `inventory`, parent = the company's virtual inventory-loss location resolved as in `his_stock_mdm/data/stock_location_data.xml`, `loc_scrap_*`).
- Produces `stock.picking._create_paper_pickings(lines, picking_type, location_dest_id) -> stock.picking` and extends `_create_picking_from_pos_order_lines` to return `super() | paper pickings`.
- Produces action `his_pos_copy_center.action_paper_consumption` (menu "Paper Consumption" under Inventory › Reporting): `stock.move.line` list, domain `location_dest_id = loc_consommation_copy_center`, `state = done`, default group by product then date:week.

Behaviour (the decisions the code must encode):
- Only lines with `qty > 0` and a `copy_paper_product_id` produce paper. Negative lines (refunds) produce nothing.
- Line with `copy_service` set → destination **consumption location**. Line without `copy_service` (the sold ream, Task 6) → the sale's own `location_dest_id`.
- Quantity = Σ `qty × copy_sheets_per_unit`, grouped by (paper product, destination); one picking per destination, type = the till's `picking_type`, source = `picking_type.default_location_src_id`.
- Validate inside `self.env.cr.savepoint()` like the core; on `UserError/ValidationError` log a warning naming the order(s) and leave the picking draft — never block the sale.
- The core's early return when no line is `consu` must not skip paper: call `super()` first, then build paper pickings from the same `lines`.

- [ ] **Step 1: Tests** in `test_paper_consumption.py` (`TestPointOfSaleCommon`/`TestPoSCommon` setup from `point_of_sale.tests.common`, a config whose picking type's source is a fresh internal location with 1000 sheets of a storable `Papier A4 80g`):
  - `test_copy_sale_moves_sheets_to_consumption`: order of 25 × "Impression N&B Recto-verso" (`copy_sheets_per_unit` 1) → quant at source drops by 25; a done move line exists into `loc_consommation_copy_center`; picking `pos_order_id` = the order.
  - `test_two_lines_same_paper_one_move`: 10 + 5 on two copy products using the same paper → one move of 15.
  - `test_ream_sale_goes_to_customer`: product without `copy_service`, `copy_paper_product_id` = paper, `copy_sheets_per_unit` 500, qty 1 → 500 sheets to the order's customer destination, nothing into consumption.
  - `test_refund_returns_no_paper`: refund the first order → paper quant unchanged by the refund.
  - `test_paper_moves_at_session_closing`: config with `update_stock_at_closing` True, two orders, close session → total paper moved equals the sum, exactly one set of moves.
  - `test_sale_without_paper_stock_goes_negative`: source empty, sell 3 → quant −3, order state `paid`/`done`.
  - `test_product_without_paper_moves_nothing`: copy product with no `copy_paper_product_id` → no paper picking.
- [ ] **Step 2: Run `$TEST`** — expected FAIL.
- [ ] **Step 3: Fields + location data + `_create_picking_from_pos_order_lines` override + `_create_paper_pickings`** in `models/stock_picking.py` (`_inherit = "stock.picking"`), reusing `_prepare_picking_vals(partner, picking_type, location_id, location_dest_id)` from core and creating moves directly (`product_uom` = paper `uom_id`, `picked=True`, `_action_confirm`, quantities set, `_action_done`).
- [ ] **Step 4: Form fields** "Paper Used" / "Sheets per Unit" in the Copy Center group (visible under the same `copy_center_visible` condition, so a ream product in Articles Bureautique shows them too). Menu + list view. fr.po: « Papier utilisé », « Feuilles par unité », « Consommation de papier », « Consommation Copy Center ».
- [ ] **Step 5: Run `$TEST`** — PASS.
- [ ] **Step 6: Lint, commit** `[IMP] Copy Center : chaque copie vendue sort son papier du stock`.

### Task 3: A ream is bought in reams, counted in sheets

**Files:**
- Create: `his_pos_copy_center/data/uom_data.xml` (add to manifest)
- Modify: `his_pos_copy_center/tests/test_paper_consumption.py`, `i18n/fr.po`

**Interfaces:**
- Produces `his_pos_copy_center.uom_rame_500`: `uom.uom` name "Ream (500 sheets)", `relative_uom_id` = `uom.product_uom_unit`, `relative_factor` 500.
- Task 6 adds it to the paper articles' `uom_ids` and as the purchase unit of their vendor lines.

- [ ] **Step 1: Test** `test_ream_receipt_counts_500_sheets`: a receipt move of 2 `uom_rame_500` of `Papier A4 80g` → quant +1000 Units.
- [ ] **Step 2: Run `$TEST`** — FAIL.
- [ ] **Step 3: Data file.** Check in the container (`grep -n relative_factor /usr/lib/python3/dist-packages/odoo/addons/uom/models/uom_uom.py`) that this is how Odoo 19 expresses it; if a purchase line refuses the unit, record why in the commit message and fall back to `product.supplierinfo` with `product_uom_id`.
- [ ] **Step 4: `$TEST`** — PASS. **Step 5:** commit `[IMP] Copy Center : la rame de 500 feuilles`.

### Task 4: The copy dialog asks paper, hides what does not apply, refuses impossible combinations

**Files:**
- Modify: `his_pos_copy_center/static/src/app/copy_job_dialog.js`, `copy_job_dialog.xml`, `copy_job_dialog.scss`
- Modify: `his_pos_copy_center/static/tests/tours/copy_job_tour.js`, `tests/test_copy_job_tour.py`, `i18n/fr.po`, `README.md` §3–4

**Interfaces:**
- Consumes `copy_paper`, `copy_bulk_price` (Task 1) and `copyBulkState(order)` (Task 5 — until Task 5 lands, the preview uses `lst_price`).
- `state` = `{ service, paper: "normal", color: "bw", sides: "recto", copies: 1 }` (no `format`).
- `isAvailable(dimension, value) -> boolean`: true iff some copy product matches `value` on `dimension` and the current choice on every **other** dimension that the candidate product sets (a product's empty dimension matches anything).
- `asks(dimension) -> boolean`: false when every product matching the other current choices leaves `dimension` empty (Sticker/Glossy/Luxury/Photo → colour not asked).
- `matchedProduct`: as today, but a product's empty dimension matches any choice.
- `pick(dimension, value)` re-snaps any other dimension whose current value became unavailable to its first available value.

- [ ] **Step 1: Tour** `his_copy_job_tour` rewritten on the §5 fixtures (create the 16 products in `setUpClass` from the same list Task 6 uses — import it from a tiny helper `tests/copy_grid.py` exposing `COPY_GRID`, list of dicts): pick Print → Sticker, assert `.js_copy_color` absent, assert `.js_copy_duplex` has `disabled`, set 3 copies, add, `selectedOrderlineHas("Impression Papier Autocollant", "3")`. Keep `his_copy_job_missing_tour` by archiving one product in its test.
- [ ] **Step 2: Implement** the getters above; paper chips row replaces the A4/A3 sheet buttons (keep `his-chip` styling; class `js_copy_paper_<value>`); disabled chips get `disabled` + `his-off`. Strings `_t`/template in English: "Paper", "Normal", "A5", "Bristol", "Sticker", "Glossy", "Luxury", "Photo".
- [ ] **Step 3: fr.po** for every new string; README §3 table: "a combination that does not exist is disabled; 'No such copy' remains for a catalogue gap".
- [ ] **Step 4:** Python suite still green (`$TEST`); tours run where a browser exists (CI skips them, say so in the commit body). Browser check is Task 10.
- [ ] **Step 5: Commit** `[IMP] Copy Center : le dialogue suit la grille reelle (papier, choix impossibles grises)`.

### Task 5: Above 20 B&W pages in the order, every B&W page takes the lower price

**Files:**
- Create: `his_pos_copy_center/static/src/app/copy_bulk_pricing.js`
- Create: `his_pos_copy_center/static/src/app/pos_order_patch.js`
- Modify: `his_pos_copy_center/static/src/app/copy_job_dialog.js` (preview), `README.md` (§3 "It reads a price, it never computes one" → explain the two stored prices), `i18n/fr.po`
- Create: `his_pos_copy_center/static/tests/tours/copy_bulk_tour.js`, `his_pos_copy_center/tests/test_copy_bulk_tour.py`

**Interfaces:**
- `export const BULK_THRESHOLD_PAGES = 20;`
- `export function isBulkEligible(product) -> boolean`: `copy_service === "impression" && copy_color === "bw" && copy_paper === "normal"`.
- `export function pagesOf(line) -> number`: `line.qty × (copy_sides === "duplex" ? 2 : 1)`, 0 when not eligible.
- `export function copyBulkState(lines) -> { pages: number, active: boolean }`: `active` iff Σ `pagesOf` > `BULK_THRESHOLD_PAGES`.
- `export function bulkUnitPrice(product, active) -> number|null`: `active && product.copy_bulk_price ? copy_bulk_price : null` (null = leave the line's normal price).
- `PosOrder.prototype.hisApplyCopyBulkPrices()`: for each eligible line, `setUnitPrice(bulk ?? product's normal price for that qty via getPrice(pricelist, qty, …))`; idempotent.
- Called after: `PosStore.addLineToOrder` (patch, after super), `PosOrderLine.setQuantity` (patch, after super, via `this.order_id`), `PosOrder.removeOrderline` (patch, after super). Guard against recursion (setUnitPrice does not call setQuantity — verify; if it does, use a flag).

Cases the tour pins (order built through the dialog):
1. 20 × Print B&W Single → 10 DA each.
2. +1 × Print B&W Single on a second line (21 pages) → both lines 8 DA.
3. + 5 × Print Colour Single → stays 30 DA; B&W lines stay 8.
4. Remove the second B&W line → back to 20 pages → first line 10 DA.
5. 11 × Print B&W Double (22 pages) alone → 10 DA (its bulk price).
6. 15 × Photocopy B&W Single + 6 × Print B&W Single → only 6 print pages count → photocopy 5 DA, print 10 DA; then 30 × Photocopy B&W alone → 5 DA (photocopies never discount).

- [ ] **Step 1: Write `copy_bulk_tour.js`** with the six cases above (assert with `ProductScreen.selectedOrderlineHas(name, qty, price)` / `Order.hasLine`), and its `HttpCase` runner using the `COPY_GRID` fixtures.
- [ ] **Step 2: Implement `copy_bulk_pricing.js`** (pure, no POS imports) and `pos_order_patch.js`.
- [ ] **Step 3: Dialog preview**: unit price shown = `bulkUnitPrice(product, copyBulkState([...order lines, candidate]).active) ?? product.lst_price`; when the candidate tips the order over 20 pages, show the line "Earlier B&W pages drop to the lower price" (English source, French in fr.po).
- [ ] **Step 4: `$TEST`** green (Python); the tour is exercised in Task 10.
- [ ] **Step 5: Commit** `[IMP] Copy Center : au-dela de 20 pages N&B dans la commande, toutes les pages au prix reduit`.

### Task 6: The real copy services and paper articles exist on a fresh database

**Files:**
- Create: `tools/seed/copy_services.csv`
- Modify: `tools/seed_copy_products.py` (rewritten: reads the CSV, no example prices)
- Read only: `his_pos_copy_center/tests/copy_grid.py` (Task 4). Tests cannot read `tools/`, so `COPY_GRID` stays a literal copy; Task 8's `--test` checks the CSV and `COPY_GRID` agree.
- Modify: `his_pos_copy_center/README.md` §5

**Interfaces:**
- `copy_services.csv` columns: `Nom,Service,Papier,Couleur,Faces,Prix,Prix_Plus_20,Papier_Consomme,Feuilles` — 16 rows exactly the §5 table, `Papier_Consomme` one of the seven paper names in Global Constraints; plus one row `Rame Papier A4 500 feuilles` (Service empty, Prix 650, Papier_Consomme `Papier A4 80g`, Feuilles 500).
- Names (French, as the counter writes them): `Photocopie N&B Recto`, `Photocopie N&B Recto-verso`, `Photocopie Couleur Recto`, `Photocopie Couleur Recto-verso`, `Impression N&B Recto`, `Impression N&B Recto-verso`, `Impression Couleur Recto`, `Impression Couleur Recto-verso`, `Impression A5 N&B`, `Impression A5 Couleur`, `Impression Bristol N&B`, `Impression Bristol Couleur`, `Impression Papier Autocollant`, `Impression Papier Glace`, `Impression Papier Luxe`, `Impression Papier Photo`.
- `seed_copy_products.py`: idempotent on `(copy_service, copy_paper, copy_color, copy_sides)` (or name for the ream); creates `type="service"`, `sale_ok`, `available_in_pos`, `pos_categ_ids` = Copy Center POS category (create if missing, as today), `categ_id` = Photocopie/Impression (ream: Articles Bureautique), links `copy_paper_product_id` by exact name and **fails loudly** listing missing paper articles (they come from the catalogue import, Task 8); on an existing product it updates prices and mapping.

- [ ] **Step 1:** write the CSV; **Step 2:** rewrite the script; **Step 3:** run it on `copyjob` after creating the seven paper articles by hand in `odoo shell`, check 17 products and their mapping with a `search_read`; **Step 4:** commit `[ADD] Copy Center : la grille de copie reelle en donnees de seed`.

### Task 7: Fusion script and review workbook

**Files:**
- Create: `tools/fusion_copy_center.py`
- Output (not committed): `C:\Users\Mohamed\Downloads\Odoo Knowledge\Copy Center FUSION REVIEW 2026-10-29.xlsx`
- Output (committed): `tools/seed/sources/copy_center_fusion.csv`, `tools/seed/sources/inventory_copy_center.xlsx` (copy of the source workbook, audit trail like the other sources)

**Interfaces:**
- `python tools/fusion_copy_center.py review <source.xlsx> <seed.csv> <catalogue_review.xlsx> <out_review.xlsx>`
- `python tools/fusion_copy_center.py build <review.xlsx> <out_fusion.csv>`
- `python tools/fusion_copy_center.py --test` (internal asserts, like `convertir_listes_seed.py --test`)
- Run all three with `~/.local/bin/uv run --no-project -q --with openpyxl python -I tools/fusion_copy_center.py …`.
- `copy_center_fusion.csv` columns: `Reference,Nom,Ancien_Noms,Categorie_Suggeree,Type,Code_Barres,Prix_Vente,Cout,Description_Achat,Categorie_POS,Groupe_Papier,Source,Ligne`. `Ancien_Noms` = seed names merged into this row, joined by ` | `.

Rules:
- Rows read: `stock C.C.` (reference), `Products` (barcode supplement; rows not matched become candidates), `Stock` (cost; unmatched rows go to a tab pre-ticked import). Ignore empty names; strip names; read with openpyxl only.
- Exclude the 18 copy/print **service** rows (they are Task 6's CSV) and the two "+20 pages" rows.
- Matching order: barcode equal → name normalised (NFKD, ascii, lowercase, alnum tokens) equal → token Jaccard ≥ 0.75 = SAME pre-ticked; 0.4–0.75 = `?` with candidate; below = no candidate. One seed row pairs with at most one sheet row (greedy by score).
- `PAPER_GROUPS` constant: the seven paper articles, each with name regexes covering both sides — e.g. `Papier A4 80g`: `rame .*a4`, `^papier noir/blanc$`; `Papier Luxe`: `luxe|prisma|ivo(i)?ry|premium 120`; `Papier Bristol`: `bristol`; `Papier Autocollant`: `autocollant` (not `impression`); `Papier Glace`: `glac`; `Papier Photo`: `papier photo`; `Papier A5`: `papier (extra blanc )?a5`. Every matching row (sheet and seed) collapses into the group row; group rows are storable, unit sheet, category Articles Bureautique.
- Workbook tabs: `Pairs` (sheet row, candidate, score, **Decision** SAME/DIFF/?), `Paper groups` (member rows, Decision IN/OUT pre-ticked IN), `Sheet only`, `Seed only`, `Stock tab only` (Decision IMPORT/DROP pre-ticked IMPORT), `To fix` (duplicate barcodes — both rows imported **without** barcode until fixed; empty type; empty/0 price → sale_ok False).
- `build`: `?` counts as DIFF and is listed in the build report; prints counts per decision.
- References: a merged row keeps the seed row's `INV-` from `Product_Catalogue REVIEW 2026-10-25.xlsx` (looked up by seed name); if it merges several seed rows, the smallest code wins, the others are retired (listed in the report, never reused). New rows: `INV-001167` upward in (category, name) order. Any `COP-…` value is discarded.
- Type: `Storable` unless the sheet says Service; category: `Copy/Articles Bureautique` for everything not paper or service (spec §10).
- `Description_Achat`: the merged seed names (supplier wording).

- [ ] **Step 1: `--test` asserts** first: normalisation; barcode beats name; one seed row never pairs twice; `PAPER_GROUPS` sends "RAME EXTRA A4 80G TARGET", "RAME DE PAPIER A4 / 500 FEUILLES – RAMOS", "Papier Noir/Blanc" to `Papier A4 80g` and "Impression Papier Autocollant" nowhere; duplicate barcode `6975345543281` yields two rows with empty barcode and two `To fix` entries; a `COP-ABU-AGRF` reference never reaches output; new references start at `INV-001167`.
- [ ] **Step 2:** run `--test` — FAIL; implement; run — PASS.
- [ ] **Step 3:** run `review` on the real files; open the workbook and report the counts (pairs SAME/?/none, sheet only, seed only, stock-tab only, to fix).
- [ ] **Step 4:** run `build` on the untouched workbook → `copy_center_fusion.csv`. Commit script + CSV + source copy: `[ADD] Seed : fusion du catalogue Copy Center (feuille du comptoir + listes fournisseur)`. The workbook goes to Mohamed for ticking; re-running `build` on his ticks is the only step after that.

### Task 8: Converter and importer take the merged Copy Center rows

**Files:**
- Modify: `tools/convertir_listes_seed.py`
- Modify: `tools/import_seed_catalogue.py`
- Regenerate: `tools/seed/Seed_Catalogue_v2.csv`

**Interfaces:**
- Converter: when `sources/copy_center_fusion.csv` exists, the `BUREAUTIQUE` rows from the supplier lists are **not** emitted; the fusion rows are, with the new optional columns `Reference,Prix_Vente,Cout,Description_Achat,Categorie_POS,Ancien_Noms,Groupe_Papier` (empty for every other row; existing columns unchanged).
- Importer, per row:
  - lookup order: `default_code == Reference` → name `== Nom` → any of `Ancien_Noms`. Found → **update** (name, barcode, prices, description_purchase, pos categ, `available_in_pos`/`sale_ok`) instead of skipping; extra products found through other `Ancien_Noms` are archived if they have no positive quant, else reported.
  - create passes `default_code=Reference` when set.
  - `Prix_Vente > 0` → `list_price`, `sale_ok=True`, `available_in_pos=True`, `pos_categ_ids` from `Categorie_POS` (Articles Bureautique → `his_stock_mdm.pos_categ_fournitures`; unknown POS category → create under the same parent and report). `Cout` → `standard_price`.
  - `Groupe_Papier` rows: `uom_ids` += `his_pos_copy_center.uom_rame_500` when the module is installed.
  - After the run, move `product.internal.reference` (the MDM sequence) past the highest `INV-` used — via `sequence.sudo().write({"number_next_actual": n + 1})` (the PostgreSQL sequence, **not** the column; see the catalogue note on `ir_sequence_028`).
- Converter `--test` gains `rejouer_sur_base_existante` (a pure check that every fusion row with `Ancien_Noms` keeps them) and the `COPY_GRID` / `copy_services.csv` agreement check.

- [ ] **Step 1:** converter `--test` cases; FAIL; implement; PASS; regenerate the seed CSV and `git diff --stat` it (expect ~129 Bureautique rows replaced by the fusion rows, nothing else moved).
- [ ] **Step 2:** importer on `copyjob` twice in a row: first run creates, second run reports 0 created / N updated / 0 duplicates; then `seed_copy_products.py` (Task 6) succeeds with all seven papers found. Then on a copy of staging-like data (the 129 supplier-named products present): renamed in place, extras archived, `search_count` of each barcode = 1.
- [ ] **Step 3:** commit `[IMP] Seed : l'import met a jour par reference et anciens noms, passe le prix et la reference`.

### Task 9: Photos

**Files:**
- Rename: `tools/seed/images/<seed name>.<ext>` → `<merged Nom>.<ext>` for merged rows (`git mv`, same naming convention: `/ * "` → `∕ ∗ ʺ`, `%`/`'` → `_`)
- Add: `tools/seed/images/<Nom>.jpg` for new rows found
- Create: `tools/seed/images_copy_center_credits.csv` (`Nom,Code_Barres,Source_URL,Licence_ou_Origine`)
- Update: the "no photo" list next to it (`SANS PHOTO copy center.csv`)

- [ ] **Step 1:** list rows of `copy_center_fusion.csv` without an image (`import_images_catalogue.py` dry run on `copyjob`).
- [ ] **Step 2:** for each, search by barcode then by name (WebSearch / WebFetch), keep a product shot, resize to 640 px inside the `odoo:19.0` image (Pillow is there, not on the PC), record the source line. No photo of a person, no logo-only image.
- [ ] **Step 3:** `import_images_catalogue.py` dry run reports 0 ambiguous; commit `[ADD] Photos du catalogue Copy Center`.

### Task 10: Rehearsal, browser check, docs

**Files:**
- Modify: `his_pos_copy_center/README.md` (sections 3–6 to the new behaviour, paper consumption, seeding order), `his_pos_copy_center/__manifest__.py` description

- [ ] **Step 1: Fresh base** like CI (`-i l10n_dz,point_of_sale,his_person_core,his_academic_base`, the two `tools/*.py` shells, then `-i his_stock_mdm,his_pos_copy_center,his_meal_management`), then converter → importer → `seed_copy_products.py` → images import. Paper stock: receive 2 reams of `Papier A4 80g` into Copy Center.
- [ ] **Step 2: Browser** (Chrome tools, `http://localhost:8070`, Copy Center till as a Copy Center cashier): run the six cases of Task 5 by hand; sticker greys out duplex and hides colour; screenshot each; close the session; open Inventory › Reporting › Paper Consumption and check the sheets equal the copies sold; paper on hand = 1000 − sold.
- [ ] **Step 3: Full module test run** with `$TEST` plus `-u his_stock_mdm --test-tags /his_stock_mdm,/his_pos_copy_center,/his_access_base` (language test) — all green, counts non-zero.
- [ ] **Step 4:** README + manifest description, lint, commit `[DOC] Copy Center : grille, papier, ordre de seed`; push; open the PR to `main` with `gh pr create` (body: what changed, the review workbook to tick, rehearsal evidence).
