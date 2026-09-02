# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Socle Personnes - Groupe HIS-HTC-IRA",
    'version': '19.0.1.2.0',
    'category': 'Technical',
    'summary': "Identite unique des personnes du groupe et matricule institutionnel",
    'description': """
Source unique de verite du matricule institutionnel (HIS-AAAA-NNNNNN-C) et de la
fiche personne, pour tous les types : employes, enseignants, etudiants, candidats.

Ce module possede la SEULE sequence autorisee a emettre un matricule. Aucun autre
module ne doit en creer une seconde ni ecrire directement dans le champ.
    """,
    'author': "Groupe HIS-HTC-IRA",
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'security/his_person_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/res_partner_category_data.xml',
        'views/his_person_views.xml',
        'views/his_engagement_views.xml',
    ],
    'installable': True,
}
