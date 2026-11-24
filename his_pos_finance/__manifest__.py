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
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/his_role_data.xml",
        "views/res_config_settings_views.xml",
        "views/his_cash_discrepancy_views.xml",
        "report/his_cash_transfer_report.xml",
        "views/his_cash_transfer_views.xml",
        "views/his_cash_count_views.xml",
        "views/pos_order_views.xml",
        "views/pos_session_views.xml",
        "data/his_metabase_dashboard_data.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "his_pos_finance/static/src/app/**/*",
        ],
        "web.assets_tests": [
            "his_pos_finance/static/tests/tours/**/*",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
}
