# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Referentiel academique",
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': "Facultes, rang academique et specialite des enseignants",
    'description': """
Donnees academiques partagees par les modules qui parlent d'enseignants.

Elles etaient portees par his_meal_management, seul module a en avoir besoin a
l'epoque (son propre commentaire annoncait le deplacement « le jour ou un autre
module en aura besoin »). InSite en a besoin : sans ce module il aurait du
dependre du POS et des repas pour lire un rang academique.

Le modele his.faculty, sa table et sa table de relation his_faculty_person_rel
sont repris a l'identique. Les donnees (les six facultes), les droits des
caissiers et le menu restent dans his_meal_management.
    """,
    'author': "Groupe HIS-HTC-IRA",
    'license': 'LGPL-3',
    'depends': [
        'his_person_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/his_person_views.xml',
    ],
    'installable': True,
}
