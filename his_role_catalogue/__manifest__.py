# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "HIS Business Role Catalogue",
    "version": "19.0.1.1.0",
    "category": "Technical",
    "summary": "The starting list of HIS business roles: tills, meals, stock, purchase, accounting, HR, helpdesk, maintenance, hygiene",
    "description": """
Le catalogue de depart des roles metier (MDM des roles, 2026-10-27).

Un role par vrai metier, defini une fois : l'administrateur des droits les
choisit sur les postes, jamais des groupes Odoo bruts. Les donnees sont en
noupdate : ses corrections dans Parametres > Utilisateurs > Roles metier
survivent aux mises a jour.

Hors perimetre pour l'instant (modules beta) : CRM/admissions, production de
contenu, Campus+ et recrutement.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "account",
        "hr",
        "helpdesk_mgmt",
        "his_access_base",
        "his_helpdesk_identity_bridge",
        "his_hygiene",
        "his_meal_management",
        "his_person_core",
        "his_purchase",
        "his_stock_mdm",
        "maintenance_university",
    ],
    "data": [
        "data/his_role_data.xml",
        "data/his_privilege_heading.xml",
    ],
    "installable": True,
}
