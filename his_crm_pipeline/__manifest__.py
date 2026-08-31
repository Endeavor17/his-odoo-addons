# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "CRM Ventes/Admissions et Production Contenu",
    'version': '19.0.3.0.0',
    'category': 'Sales/CRM',
    'summary': "Deux pipelines CRM natifs : admissions candidats et production de contenu",
    'description': """
Remplace GoHighLevel par le CRM natif d'Odoo, sans quitter crm.lead.

Deux processus sans rapport partagent le meme modele, separes par equipe :
Ventes/Admissions (parcours candidat, du lead score a la pre-admission) et
Production Contenu (demande de contenu, production par type de livrable,
approbation, publication par marque).

Le verrou d'approbation du contenu est une contrainte serveur : on ne peut pas
atteindre l'etape Approbation tant qu'un livrable demande n'est pas approuve.
C'est ce qui remplace la colonne « Approval Status » du tableur, restee vide
dans presque toutes les lignes reelles.
    """,
    'author': "Groupe HIS-HTC-IRA",
    'license': 'LGPL-3',
    'depends': [
        'crm',
        'mail',
    ],
    'data': [
        'security/his_crm_roles.xml',
        'security/ir.model.access.csv',
        'security/his_crm_security.xml',
        'data/crm_team_data.xml',
        'data/crm_team_member_data.xml',
        'data/his_content_deliverable_type_data.xml',
        'data/crm_stage_data.xml',
        'data/crm_stage_native_data.xml',
        'data/crm_lost_reason_data.xml',
        'data/crm_tag_data.xml',
        'data/ir_cron_data.xml',
        'views/crm_lead_views.xml',
        'views/crm_menus.xml',
        'views/his_dashboard_views.xml',
        # Apres crm_menus.xml : chaque filtre est rattache a l'action de son
        # pipeline, qui doit donc exister au moment du chargement.
        'data/ir_filters_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'his_crm_pipeline/static/src/dashboard/**/*',
        ],
    },
    'installable': True,
}
