# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "HIS - Metabase Dashboards",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "Each workflow manager opens their Metabase dashboard inside their Odoo app",
    "description": """
One record per dashboard (code, Metabase number, allowed groups), one page that
shows a server-signed static-embedding URL, one menu per app. The Metabase site
and key are the system parameters his_metabase.site_url and
his_metabase.secret_key, set per server and never committed.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "maintenance_university",
        "helpdesk_mgmt",
        "point_of_sale",
        "his_purchase",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/his_metabase_dashboard_data.xml",
        "views/his_metabase_dashboard_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "his_metabase/static/src/**/*",
        ],
    },
    "installable": True,
}
