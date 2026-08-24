# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Synchronisation Personnes - Export Google Sheets",
    'version': '19.0.1.1.0',
    'category': 'Technical',
    'summary': "Importe les etudiants de l'export Sales/Admission vers his.person",
    'description': """
Adaptateur d'import : reprend l'export Google Sheets (CSV/XLSX) des etudiants et
candidats vers le referentiel Personnes.

Sens unique, source -> his_person_core : ce module n'ecrit jamais dans le
fichier source. Il ne fusionne jamais deux fiches automatiquement : au-dessus du
seuil de similarite, la ligne est proposee a un humain qui confirme ou refuse.

L'algorithme de rapprochement n'est pas ici mais sur his.person, pour qu'un
futur adaptateur Uniflow appelle exactement le meme calcul.
    """,
    'author': "Groupe HIS-HTC-IRA",
    'license': 'LGPL-3',
    'depends': [
        'his_person_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/his_person_sync_log_views.xml',
        'views/his_person_import_views.xml',
    ],
    'installable': True,
}
