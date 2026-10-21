# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Patrimoine - Groupe HIS-HTC-IRA",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Biens durables (mobilier, informatique, climatisation...) suivis par numero de serie, salle par salle",
    "description": """
Spec : docs/superpowers/specs/2026-10-20-investment-purchases-and-fixed-assets-design.md.

- Categories Patrimoine (mobilier, informatique, reseau, climatisation,
  vehicules, cuisine) : stockable, un numero de serie PAT-000001 par bien,
  valorisation periodique (la facture reste en charge, le comptable reclasse).
- Un emplacement par batiment (maintenance_university) sous Patrimoine, hors de
  WH/Stock ; les salles se creent a la main dessous et se comptent chaque annee.
- Reception : les biens arrivent dans WH/Stock/À affecter (une regle de
  rangement ne peut viser qu'un enfant de WH/Stock), puis un transfert interne
  les place dans leur salle.
- Inventaire ▸ Patrimoine : biens, salles, comptage annuel (feuille standard) ;
  la cloture annuelle reste celle de his_stock_mdm.
- Etiquettes : rapport standard des numeros de serie.
- Import initial : tools/import_patrimoine.py.
- Hors perimetre : reforme, amortissement.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "his_stock_mdm",
        "maintenance_university",
    ],
    "data": [
        "data/ir_sequence_data.xml",
        "data/product_category_data.xml",
        "data/stock_location_data.xml",
        "views/patrimoine_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
