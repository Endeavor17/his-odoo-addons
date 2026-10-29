# Copy Center: the real catalogue, the real copy grid, and paper that leaves stock

Design for making the Copy Center till sell what the Copy Center actually
sells, at its posted prices, and for making every copy take its paper out of
stock.

The governing idea, stated first:

> **One physical article, one product.** The Copy Center's own sheet is the
> most honest description of what is on its shelves, the supplier lists are the
> most complete description of what can be bought. They are merged, never
> stacked: an article present in both becomes one product carrying the
> counter's name, barcode and price, and the supplier's wording.

Inputs:

- `C:\Users\Mohamed\Downloads\Odoo Knowledge\Inventory - Copy Center.xlsx`
  (three tabs, described in §3).
- The price poster photographed on 2026-10-29 ("TARIFS Photocopie &
  Impression", reproduced in §5).
- `tools/seed/Seed_Catalogue_v2.csv` on `origin/main` (`1d3fe13`): 129 rows in
  `Copy/Articles Bureautique`, all from the supplier lists, none with a barcode.
- The existing module `his_pos_copy_center` (19.0.1.1.0) and its copy-job
  dialog.

---

## 1. Why now

- The Copy Center till sells nothing through its copy dialog today: staging has
  **0 products with `copy_service`**, the eight A4/A3 products exist only as
  demo data with invented prices, and every choice answers "No such copy"
  (recette point P-16).
- The dialog was designed around A4/A3 × B&W/Colour × Single/Double-sided. The
  poster has **no A3**. What changes the price is the **paper** (normal,
  sticker, luxury, A5, Bristol, glossy, photo) and a **volume price above 20
  pages**.
- The 129 Copy Center seed rows are supplier invoice wording ("STYLO ULTRON X2
  NOIR"), with no barcode and no price. The counter cannot scan or sell them.
- Paper is the Copy Center's main consumable and nothing records its use.

## 2. Decisions (Mohamed, 2026-10-29)

1. **The new sheet is taken into account and merged with the inventory
   catalogue.** Inventory keeps every article that can be sold; no article may
   exist twice.
2. **The MDM constraints of `his_stock_mdm` still hold** (§4).
3. **Every row of the sheet is a real Copy Center article**, including chargers,
   Type-C cables, face masks, cosmetics, the graduation hat and the Business
   Results books. None is dropped as out of scope.
4. **A copy job is a counter sale**: the customer arrives with a document, asks
   for copies, pays, leaves. No queue, no job record, no pickup.
5. **Paper tracking is automatic**: selling a copy takes its sheets out of the
   Copy Center's paper stock.
6. **Above 20 pages, every page of the job gets the lower price** (21 B&W prints
   = 21 × 8 DA, not 20 × 10 + 1 × 8).
7. **The discount counts pages across the whole order, B&W prints on normal
   paper only.** Prints of several documents add up; once the order passes 20
   B&W print pages, every B&W print line takes its lower price. Double-sided
   counts two pages a sheet, so 11 double-sided sheets (22 pages) get it.
   **Colour never gets a discount, and photocopies never do** (Mohamed,
   2026-10-29: "discounts only touch printing").
8. **No one cares about the paper brand.** One stock article per paper type:
   A4 copy paper, Luxury, Bristol (all brands received into it).

## 3. The source sheet

| Tab | Rows | What it is | Use |
|---|---|---|---|
| `stock C.C.` | 252 | The counter's list: name, barcode (often), sale price, cost (sometimes), type, POS category | **Reference** for name, barcode, sale price |
| `Products` | 121 | A shelf count sheet: POS family, name, barcode, mostly empty qty/cost/price | Barcode supplement. 50 rows match nothing in `stock C.C.` by name or barcode: they are candidates for the merge like any other row |
| `Stock` | 270 | An older export with legacy `COP-…` references and purchase costs | Purchase cost where `stock C.C.` has none. Its `COP-` references are **discarded** (§4) |

Known defects in the sheet, to surface rather than silently fix:

- 23 rows have no product type.
- Two rows share one barcode (`6975345543281`: Cartouche Golden Rouge and
  Cartouche Golden Vert).
- Many sale prices are empty (books, some binders, cartable…).
- The sheet is Windows-1252 in places (`Cartonn?e`); read it with openpyxl, not
  through a CSV export, so the accents survive.

Measured overlap with the 129 seed rows: **0 exact name matches, 0 barcode
matches** (the seed has no barcodes). A token comparison finds a plausible
counterpart for about 40 rows, many of them false ("Stylo Hausser Noir" ≈
"STYLO ULTRON X2 NOIR"). Automatic matching alone cannot be trusted.

## 4. MDM constraints that bind the merge

From `his_stock_mdm` (README, "Ce que le module applique"):

- **Internal reference mandatory and unique**, minted as opaque `INV-NNNNNN`.
  Semantic codes (`COP-`, `CAF-`, …) are rejected. The pre-assigned codes of
  the prod seed workbook (`Product_Catalogue REVIEW 2026-10-25.xlsx`,
  `INV-000001..001166`) stay attached to the seed row they were given to; new
  articles take codes **after 001166**. The importer must pass `default_code`,
  which it does not yet do, and the reference sequence must then be moved past
  the last code used.
- **Terminal category mandatory.** Copy has five terminal categories:
  Articles Bureautique, Flexy, Impression, Photocopie, Scan.
- **Sale price mandatory when storable and sellable.** A row without a price is
  imported `sale_ok=False` (the existing importer behaviour) and listed for
  someone to price; it never gets an invented price.
- **No Format/Variante attribute on Copy categories** (MDM rule 6). Each colour
  stays its own product, as the supplier-list granularity rule already says.
- **Barcode uniqueness** is enforced by Odoo in Python per company. A duplicated
  barcode is imported on neither row until a person says which one owns it.

## 5. The copy grid

From the sheet's 18 service rows, consistent with the poster wherever both list
a price (every poster price equals the sheet's):

| Service | Paper | Colour | Sides | Price (DA) | ≥ 21 pages |
|---|---|---|---|---|---|
| Photocopy | Normal | B&W | Single | 5 | — |
| Photocopy | Normal | B&W | Double | 10 | — |
| Photocopy | Normal | Colour | Single | 30 | — |
| Photocopy | Normal | Colour | Double | 50 | — |
| Print | Normal | B&W | Single | 10 | 8 |
| Print | Normal | B&W | Double | 15 | 10 |
| Print | Normal | Colour | Single | 30 | — |
| Print | Normal | Colour | Double | 50 | — |
| Print | A5 | B&W | Single | 5 | — |
| Print | A5 | Colour | Single | 15 | — |
| Print | Bristol | B&W | Single | 15 | — |
| Print | Bristol | Colour | Single | 35 | — |
| Print | Sticker | — | Single | 80 | — |
| Print | Glossy | — | Single | 50 | — |
| Print | Luxury | — | Single | 80 | — |
| Print | Photo | — | Single | 50 | — |

The sheet also has the photocopy colour rows and the A5/Bristol/glossy/photo
print rows that the poster does not show; the poster is the public subset, the
sheet is the full offer, and the till sells the full offer.

**The two "+20 pages" rows are not products.** They are a second price carried
by the base product (`copy_bulk_price`: 8 DA on Print B&W single, 10 DA on
Print B&W double). Keeping them as products would create the article twice and
make the cashier choose the price by hand.

**The threshold is per order, so a pricelist cannot do it.** Odoo's
`min_quantity` is checked line by line; decision 7 adds pages across lines. The
rule:

- B&W pages of the order = Σ over lines on a product with `copy_bulk_price`
  set of `qty × pages per unit` (1 single-sided, 2 double-sided).
- More than 20 → every such line is priced at its `copy_bulk_price`; 20 or
  fewer → its list price. Adding or removing a line re-evaluates the whole
  order, both ways.
- The till chooses between two prices stored on the product; it never derives
  one. The README rule ("read a price, never compute one") holds in that sense.
  The server accepts the line price as it does for any POS line.

**Photocopies are outside the rule** (decision 7): no lower price, and their
pages do not count toward the 20. They always sell at 5 / 10 / 30 / 50 DA.

A two-sided copy is **one sheet** of paper and **two pages**. One unit of
"B&W double-sided" is one sheet printed on both sides.

## 6. The copy-job dialog

The dialog stays what it is — one screen, one resolved product, one ordinary
order line, price read from the product, never computed — and changes its
dimensions:

- **Format (A4/A3) is replaced by Paper**: Normal, A5, Bristol, Sticker,
  Glossy, Luxury, Photo. `copy_format` becomes `copy_paper`. No real product
  uses `copy_format` on staging or prod; the demo records and tests move with it.
- **A dimension a product leaves empty is not asked.** Sticker, glossy, luxury
  and photo prints carry no colour, so picking one of those papers hides or
  disables the colour choice.
- **A combination that does not exist cannot be picked**: its chip is disabled
  given the other choices. "No such copy" stays as the last-resort message for
  an incomplete catalogue, not as the normal path.
- **The price shown follows the order.** The dialog's preview shows the price
  the line will carry once added, counting the B&W pages already in the order
  (§5); when adding a document crosses 20 pages, the earlier B&W lines drop to
  their lower price too, visibly on the order.
- Bureautique, Flexy and Scan stay ordinary product tiles.

## 7. Paper leaves stock

Each copy product says what it consumes:

- `copy_paper_product_id`: the storable paper article it uses. One article per
  paper type (decision 8): the seed's and the sheet's A4 reams (Ramos, Target,
  Golden) merge into one "A4 copy paper" article, the three luxury papers into
  one "Luxury paper", the two Bristols into one "Bristol paper"; brands survive
  in the purchase description. Sticker, Glossy, Photo and A5 point at their own
  paper article.
- `copy_sheets_per_unit`: sheets per unit sold, default 1.

When a till order is synced to the server, every order line on a copy product
produces a stock move of `qty × sheets per unit` of its paper article, **from
the till's stock location (`WH/Stock/Copy Center`) to a dedicated consumption
location** ("Consommation Copy Center"), not to Customers: the paper was used,
not sold, and the reports must keep "reams sold over the counter" and "sheets
used by copies" apart. The move belongs to the order's picking so it is
traceable back to the sale.

Where Mohamed sees it:

- **Inventory**: the paper article's stock goes down with every copy sold; its
  replenishment rule on the Copy Center location works on real numbers.
- **A "Paper consumption" view** (stock moves into the consumption location,
  grouped by paper article and by day/week), reachable from the Copy Center /
  Inventory reporting menu.
- **At the inventory count**, the gap between counted and expected paper is the
  waste (jams, misprints), visible as an ordinary inventory adjustment.

Paper is held in **sheets** (the unit copies consume), and a ream is 500 sheets.
Reams are bought and also sold over the counter ("RAME DE PAPIER A4 / 500
FEUILLES RAMOS", 650 DA); selling one ream must take 500 sheets out of stock.

A refunded copy **does not put its paper back**: the sheets were printed.

## 8. The seed and the photos

The pipeline stays the one already in use (`tools/seed/sources/` →
`convertir_listes_seed.py` → `Seed_Catalogue_v2.csv` →
`import_seed_catalogue.py`), and is extended rather than replaced:

1. **Matching, with a human in the loop.** A script pairs each sheet row with
   at most one seed row: barcode first, then normalised name, then a fuzzy
   score. It writes a **review workbook** in `Downloads\Odoo Knowledge\`
   (same style as the 2026-10-25 review workbooks): sure pairs pre-ticked,
   doubtful pairs offered with the candidate, unmatched rows on both sides
   listed. Mohamed or the inventory team ticks "same article / different
   article". The merge follows the ticks.
2. **The merged row** keeps the seed row's pre-assigned `INV-` code when there
   is one, takes the counter name, barcode, sale price and POS category from
   the sheet, the cost from the sheet or the `Stock` tab, and puts the supplier
   wording in the native **Purchase Description** (`description_purchase`), so
   purchase orders still say what the supplier knows. (Not
   `product.supplierinfo.product_name`: that needs a vendor partner and the
   lists do not name one.)
3. **Rows only in the sheet** are added; **seed rows with no counterpart** stay.
4. **The seed gains columns** it never had: sale price, cost, POS availability,
   purchase description. The importer sets `available_in_pos` and `sale_ok`
   when a price exists (the loop the catalogue note describes), and passes
   `default_code`.
5. **The 16 copy services** of §5 become real data (not demo), with their paper
   mapping and the two quantity prices, so a fresh staging or prod database
   sells copies without anyone creating them by hand.
6. **Photos.** Merged rows reuse the existing photo, renamed to the new name
   (the image importer matches on name). New rows get a photo found by barcode
   first, then by name, saved in `tools/seed/images/` with the existing naming
   convention and a source line in a credits CSV, as was done for the menu
   photos. Rows with no photo found go on the "no photo" list.

## 9. Goals, non-goals, anti-goals

**Goals**

- The Copy Center till sells every row of §5 at its posted price, with the
  quantity price applied by itself.
- One product per physical article across the seed and the sheet.
- Every copy sold moves its sheets out of paper stock, and the consumption is
  readable without SQL.
- A fresh database seeded by the pipeline is ready to sell at the Copy Center.

**Non-goals**

- Toner and ink consumption.
- A copy-job record, queue or pickup ticket (decision 4).
- Reading the copier's page counter (option C, not chosen).
- Counted stock quantities: the inventory team enters them later.
- A Metabase card for paper; the Odoo view comes first.

**Anti-goals** (failure even if it technically works)

- The same pen existing twice, with its stock split between two records.
- A cashier choosing between "10 DA" and "8 DA" by hand.
- A copy sold at 0 DA because a price was missing.
- Paper consumption written as a sale to Customers, mixing it with reams sold.
- Any `COP-` reference reaching the database.

## 10. Calls made by Claude (to check while reading)

- `stock C.C.` is the reference tab; `Products` supplements barcodes; `Stock`
  supplies costs, and its rows with no counterpart anywhere go into the review
  workbook pre-ticked "import" (Agenda Journalier, Classeur 500/650/760, Papier
  Photo, Toner…), so a person can untick the ones that no longer exist.
- A5 prints use a dedicated A5 paper article (the sheet's "Papier A5" and
  "Papier Extra Blanc A5" merged), not half an A4 sheet.
- Only B&W prints on normal paper count toward the 20 pages; B&W prints on
  A5 or Bristol do not.
- Merging brands into one paper article is the one place where the supplier-list
  rule "one product per SKU" is set aside, by decision 8. It applies to the
  copy papers only.
- Non-stationery rows (chargers, cables, masks, cosmetics, books, hat) go to
  `Copy/Articles Bureautique`, the only terminal Copy category for goods, rather
  than a new category. Their POS tab follows the sheet's POS category.
- The "+20 pages" rows become a second price on the base product, not products.
- Consumption goes to a dedicated location, not Customers and not the Copy
  Center scrap location ("Pertes Copy Center" stays for real losses).
- A refund does not return paper.
- Supplier wording goes in Purchase Description.
- Built without installing Manufacturing: a kit BoM would do the explosion
  natively but brings a whole app for one consumable.

## 11. Left to the builder

- Where the order-level repricing lives in the POS (order model patch vs line
  hooks), and that it survives reloading an unsent order.

- Where exactly the extra paper moves hook into the POS picking creation in
  Odoo 19, and how they behave for an order synced offline.
- How sheets and reams are expressed in Odoo 19's unit model so that a ream sold
  removes 500 sheets.
- The matching thresholds and the review-workbook layout.
- Which existing tests and tours change with `copy_paper`, and the migration of
  the `copy_format` column.
- Whether stock valuation of paper (AVCO, `real_time`) posts cleanly once costs
  are imported; the catalogue note flags `real_time` categories without
  accounts as a risk to verify, not assume.
