# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Campus+ - Referentiel Personnes (pont)",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Recruitment',
    'summary': "Rattache les candidats enseignants Campus+ au referentiel Identite",
    'description': """
Pont entre le recrutement enseignant Campus+ et le referentiel Identite.

Jusqu'ici l'API Campus+ creait un hr.applicant, et hr_recruitment un contact nu,
sans fiche personne ni controle de doublon. Ce module rapproche le candidat du
referentiel quand il atteint l'etape « Select » (campus_hiring_state = invited,
parametre campus_identity.trigger_state) :

  - il appelle his.person._find_or_flag_match, comme les autres ponts ; il ne
    possede AUCUNE logique de rapprochement ;
  - une correspondance probable est proposee a un humain, jamais rattachee ;
  - le candidat entre en « candidat », SANS matricule ; il devient
    « enseignant » et recoit son matricule a l'embauche.

Pas de his.engagement : ses etats (prospect -> inscrit) decrivent l'admission
d'un etudiant. Pour un enseignant, c'est le hr.applicant qui porte le parcours.

n8n n'est pas modifie : /json/2 refuse les methodes prefixees par « _ », le
rapprochement se fait donc cote serveur.
    """,
    'author': "Groupe HIS-HTC-IRA",
    'license': 'LGPL-3',
    'depends': [
        'campus_teacher_management',
        'his_person_core',
        'his_hr_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_applicant_views.xml',
    ],
    'post_init_hook': '_campus_identity_backfill',
    'installable': True,
}
