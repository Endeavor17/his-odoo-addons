{
    "name": "Hygiene - Groupe HIS-HTC-IRA",
    "version": "19.0.1.0.0",
    "category": "Operations/Maintenance",
    "summary": "Monthly planning of the cleaning team, day clock, areas done, findings and recap",
    "description": """
Spec : docs/superpowers/specs/2026-10-22-hygiene-team-design.md.

- Planning mensuel zones x jours, saisi librement par la responsable.
- Pointage (debut, pause, fin) sur la journee de maintenance_university, par la
  salariee sur son telephone ou par la responsable pour elle.
- Zones = emplacements Patrimoine sous les batiments (aucune autre liste).
- Constats : panne vers la maintenance, salissure vers la responsable.
- Recapitulatif mensuel et vue de chaque salariee sur son propre mois.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "his_patrimoine",
        "maintenance_university",
    ],
    "data": [
        "security/hygiene_security.xml",
        "security/ir.model.access.csv",
        "data/hygiene_data.xml",
        "views/hygiene_config_views.xml",
        "views/hygiene_workday_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
