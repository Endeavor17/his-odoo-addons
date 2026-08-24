# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "CRM - Referentiel Personnes (pont)",
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': "Cree la fiche personne du candidat au premier contact commercial",
    'description': """
Pont entre le pipeline Admissions et le referentiel Identite.

Quand un lead de l'equipe Ventes atteint « Contact etabli », ce module rapproche
le candidat du referentiel Personnes et, si personne ne correspond, cree sa fiche
et son engagement a l'etat prospect.

Il ne possede AUCUNE logique de rapprochement : il appelle
his.person._find_or_flag_match, exactement comme l'adaptateur Google Sheets.
Il n'emet AUCUN matricule : la sequence partagee de his_person_core s'en charge.
Il ne fait AUCUNE transition d'engagement au-dela de prospect : la suite
appartient a Finance/Admission.

Aucune dependance a hr ni a his_hr_base : un candidat n'est pas un employe.
    """,
    'author': "Groupe HIS-HTC-IRA",
    'license': 'LGPL-3',
    'depends': [
        'his_crm_pipeline',
        'his_person_core',
    ],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'installable': True,
}
