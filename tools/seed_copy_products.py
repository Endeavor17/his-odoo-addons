"""Cree ou met a jour les services de copie du Copy Center depuis la grille reelle.

Source : tools/seed/copy_services.csv (affiche « TARIFS Photocopie &
Impression » et feuille du comptoir, 2026-10-29). 16 services + la rame vendue
au comptoir, chacun relie au papier qu'il sort du stock.

Les articles papier (Papier A4 80g, Papier Luxe...) viennent de l'import du
catalogue (tools/import_seed_catalogue.py) : les lancer AVANT ce script. S'il
en manque un, le script s'arrete sans rien ecrire et les nomme.

Rejouable : un service deja present (meme service, papier, couleur, faces ; ou
meme nom pour la rame) est mis a jour, jamais duplique.

Usage :
    docker compose run --rm -T odoo odoo shell -d <base> --no-http \
        < tools/seed_copy_products.py
"""

import csv
import os

GRID_PATH = os.environ.get("COPY_PATH", "/mnt/extra-addons/tools/seed/copy_services.csv")

Product = env["product.template"]
PaperProduct = env["product.product"]

with open(GRID_PATH, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

papers = {}
missing = []
for name in sorted({row["Papier_Consomme"] for row in rows}):
    paper = PaperProduct.search([("name", "=", name), ("is_storable", "=", True)], limit=1)
    if paper:
        papers[name] = paper
    else:
        missing.append(name)
if missing:
    raise SystemExit("Articles papier absents (importer le catalogue d'abord) : %s" % ", ".join(missing))


def categ(xmlid):
    return env.ref(xmlid, raise_if_not_found=False)


# Une caisse peut restreindre son catalogue (limit_categories) : les copies ont
# leur propre categorie POS, autorisee sur la caisse plutot que de lever la
# restriction, qui est un choix de gestion.
PosCateg = env["pos.category"]
pos_copies = PosCateg.search([("name", "=", "Copies & Prints")], limit=1) or PosCateg.create(
    {"name": "Copies & Prints"}
)
pos_fournitures = categ("his_stock_mdm.pos_categ_fournitures")

created = updated = 0
for row in rows:
    service = row["Service"] or False
    vals = {
        "name": row["Nom"],
        "type": "service",
        "list_price": float(row["Prix"]),
        "available_in_pos": True,
        "sale_ok": True,
        "purchase_ok": False,
        "copy_service": service,
        "copy_paper": row["Papier"] or False,
        "copy_color": row["Couleur"] or False,
        "copy_sides": row["Faces"] or False,
        "copy_bulk_price": float(row["Prix_Plus_20"] or 0),
        "copy_paper_product_id": papers[row["Papier_Consomme"]].id,
        "copy_sheets_per_unit": float(row["Feuilles"]),
    }
    if service:
        domain = [
            ("copy_service", "=", service),
            ("copy_paper", "=", vals["copy_paper"]),
            ("copy_color", "=", vals["copy_color"]),
            ("copy_sides", "=", vals["copy_sides"]),
        ]
        target = categ(
            "his_stock_mdm.categ_copy_photocopie" if service == "photocopie" else "his_stock_mdm.categ_copy_impression"
        )
        vals["pos_categ_ids"] = [(6, 0, [pos_copies.id])]
    else:
        # La rame vendue au comptoir : un article de bureau comme les autres.
        domain = [("name", "=", row["Nom"])]
        target = categ("his_stock_mdm.categ_copy_bureautique")
        if pos_fournitures:
            vals["pos_categ_ids"] = [(6, 0, [pos_fournitures.id])]
    if target:
        vals["categ_id"] = target.id
    existing = Product.with_context(active_test=False).search(domain, limit=1)
    if existing:
        existing.write(vals)
        updated += 1
    else:
        Product.create(vals)
        created += 1

config = env.ref("his_stock_mdm.pos_config_copy_center", raise_if_not_found=False) or env["pos.config"].search(
    [("name", "ilike", "Copy")], limit=1
)
if config:
    if not config.his_pos_theme:
        config.his_pos_theme = "copy_center"
    if config.limit_categories and pos_copies not in config.iface_available_categ_ids:
        config.iface_available_categ_ids = [(4, pos_copies.id)]

env.cr.commit()
print("Services de copie : %s crees, %s mis a jour" % (created, updated))
print("Caisse : %s" % (config.display_name if config else "aucune trouvee"))
