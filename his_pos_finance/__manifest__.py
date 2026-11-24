# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Points de vente - Controles Finance",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Journaux par activite, fiche d'ecart de caisse, versements a la Finance, autorisation du responsable",
    "description": """
Controles du Departement Finance sur les caisses
(docs/superpowers/specs/2026-11-24-pos-finance-controls-design.md).
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "pos_hr", "his_stock_mdm", "his_purchase_finance", "his_purchase", "his_pos_tva", "his_metabase"],
    "data": [
        "security/his_pos_finance_security.xml",
        "data/his_role_data.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "his_pos_finance/static/src/app/**/*",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
}
