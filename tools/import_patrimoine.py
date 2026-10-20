"""Etiquetage initial des biens existants (bureaux, portables, climatiseurs...).

Run via `odoo shell -d <base> < tools/import_patrimoine.py`, fichier choisi par
PATRIMOINE_CSV (modele : tools/seed/patrimoine_template.csv). Colonnes :
building_code, room, category_xmlid, default_code, product_name, serial.
Un numero vide recoit le suivant (PAT-000001...). Le travail est fait par
stock.lot._his_import_patrimoine (his_patrimoine, teste) : une ligne refusee
n'annule pas les autres, et un numero deja importe est ignore.
"""

import csv
import os

CSV_PATH = os.environ.get("PATRIMOINE_CSV", "/mnt/extra-addons/tools/seed/patrimoine_template.csv")

with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

created, rejected = env["stock.lot"]._his_import_patrimoine(rows)  # noqa: F821 - env fourni par odoo shell
env.cr.commit()  # noqa: F821
print(f"OK {created} / REJECTED {len(rejected)}")
for reason in rejected:
    print("  " + reason)
