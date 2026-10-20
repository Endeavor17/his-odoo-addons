# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Patrimoine - Groupe HIS-HTC-IRA",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Biens durables (mobilier, informatique, climatisation...) suivis par numero de serie, salle par salle",
    "description": """
Spec : docs/superpowers/specs/2026-10-20-investment-purchases-and-fixed-assets-design.md.
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
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
