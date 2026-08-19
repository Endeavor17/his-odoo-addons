# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Socle RH - Groupe HIS-HTC-IRA",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': "Rattache hr.employee au referentiel Personnes (his.person)",
    'description': """
Relie chaque employe a sa fiche his.person et y miroite son matricule
institutionnel. Le champ matricule_institutionnel de hr.employee devient un
miroir en lecture seule : la source est his_person_core, jamais l'employe.

Reprise de donnees incluse : les matricules deja attribues sur hr.employee
(par maintenance_university) sont captures avant redefinition du champ, puis
rattaches a des fiches his.person portant exactement la meme valeur.
    """,
    'author': "Groupe HIS-HTC-IRA",
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'his_person_core',
    ],
    'data': [
        'data/hr_contract_type_data.xml',
        'views/hr_employee_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
