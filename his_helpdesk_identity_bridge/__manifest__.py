# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Helpdesk - Referentiel Personnes (pont)",
    "version": "19.0.1.0.0",
    "category": "Services/Helpdesk",
    "summary": "Chaque ticket est rattache a une personne du referentiel",
    "description": """
Pont entre le helpdesk OCA (helpdesk_mgmt) et le referentiel Identite.
Un ticket porte la personne (his.person) dont il parle. Le lien est
deterministe : une personne delegue a UN contact, donc choisir l'un pose
l'autre.
Le helpdesk ne cree JAMAIS de personne : un etudiant absent du referentiel
est un defaut du referentiel, corrige a sa source.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "helpdesk_mgmt_crm",
        "his_person_core",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/his_helpdesk_identity_bridge_security.xml",
        "views/helpdesk_ticket_views.xml",
    ],
    "installable": True,
}
