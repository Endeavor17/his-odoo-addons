# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Achats - Groupe HIS-HTC-IRA",
    "version": "19.0.1.2.1",
    "category": "Supply Chain/Purchase",
    "summary": "Demande d'achat, relances, choix fournisseur, commande mensuelle et documents algeriens",
    "description": """
Ajoute autour des achats standard d'Odoo les regles du Groupe
(docs/superpowers/specs/2026-10-15-purchasing-design.md) :

- demande d'achat interne, approuvee par le chef de departement ;
- reponse du fournisseur sur chaque demande de prix (un refus n'est jamais une
  offre a 0 DA) et choix du fournisseur trace, fige a la confirmation ;
- approbation de toute commande, routee : directeur executif pour les achats
  generaux, responsable achats ou directeur pour les achats des points de vente ;
- relances et escalade a chaque etape, relance automatique des fournisseurs,
  recapitulatif hebdomadaire ;
- commande mensuelle generee sur un contrat-cadre annuel, besoins ponctuels
  ajoutes a la prochaine commande ou commandes tout de suite ;
- Demande de proforma, Fiche de choix fournisseur, Bon de commande et Bon de
  reception.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "purchase_stock",
        "purchase_requisition",
        "his_partner_dz",
    ],
    "data": [
        "security/his_purchase_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/mail_activity_type_data.xml",
        "data/ir_cron_data.xml",
        "report/his_purchase_report_templates.xml",
        "report/his_purchase_reports.xml",
        "data/mail_template_data.xml",
        "wizard/his_purchase_request_source_views.xml",
        "wizard/his_purchase_request_reject_views.xml",
        "wizard/his_purchase_choice_views.xml",
        "views/his_purchase_request_views.xml",
        "views/purchase_order_views.xml",
        "views/purchase_requisition_views.xml",
        "views/hr_department_views.xml",
        "views/res_config_settings_views.xml",
        "views/his_purchase_menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
