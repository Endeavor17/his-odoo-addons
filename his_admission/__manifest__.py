# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Admission - Dossier candidat",
    'version': '19.0.1.3.0',
    'category': 'Education',
    'summary': "Dossier d'admission, pieces justificatives, eligibilite et exports",
    'description': """
Remplace le classeur Excel de suivi des admissions.

Le dossier d'admission n'est pas un modele de plus : c'est his.engagement, le
parcours date d'une personne, vu par le back-office Admission. Une reinscription
est donc un second engagement sur la meme personne et le meme matricule, et non
un statut comme le classeur le rangeait.

Deux regles serveur remplacent deux defauts du classeur. On ne passe pas a
« Inscrit » avec une piece obligatoire manquante ou des droits non encaisses.
Et l'eligibilite est calculee depuis un bareme configurable, pas recopiee a la
main dans une cellule.

Les huit feuilles secondaires du classeur (Pedagogie, Ministere, service
national, parents, finance, carte etudiant) deviennent des vues filtrees : leur
export XLSX natif rend le fichier attendu par chaque destinataire.
    """,
    'author': "Groupe HIS-HTC-IRA",
    'license': 'LGPL-3',
    'depends': [
        'his_person_core',
        'his_crm_identity_bridge',
    ],
    'data': [
        'security/his_admission_security.xml',
        'security/ir.model.access.csv',
        'data/his_domaine_data.xml',
        'data/his_specialite_data.xml',
        'data/his_document_type_data.xml',
        'views/his_admission_config_views.xml',
        'views/his_engagement_views.xml',
        'views/his_admission_export_views.xml',
        'views/crm_lead_views.xml',
    ],
    'installable': True,
}
