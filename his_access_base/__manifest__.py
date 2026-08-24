# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Socle de controle d'acces",
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': "Politique de droits du groupe, attribution par le poste, et les tests qui la tiennent",
    'description': """
Le socle de droits commun a tous les modules du groupe.

Il ne porte aucun metier. Il porte trois choses :

1. La fermeture du socle natif d'Odoo. Un utilisateur interne sans role ne doit
   voir que la messagerie et l'agenda. L'annuaire et les contacts demandent un
   role explicite.

2. L'attribution des roles PAR LE POSTE. hr.job porte les roles Odoo qu'il
   donne ; l'application distingue ce qui vient du poste de ce qui a ete pose a
   la main, et ne reconcilie que le premier.

3. Les tests de politique. C'est la partie qui compte : ils inspectent le
   registre INSTALLE, pas une liste ecrite d'avance. Un module livre demain qui
   ouvrirait un modele a tout le monde les fera echouer sans que personne ait
   eu a y penser. Une politique sans controle pourrit ; celle-ci est tenue.

Aucun autre module ne depend de celui-ci : il s'installe a cote. C'est ce qui
lui permet de surveiller des modules qui ne le connaissent pas.
    """,
    'author': "Groupe HIS-HTC-IRA",
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'contacts',
    ],
    'data': [
        'security/his_access_groups.xml',
        'security/ir.model.access.csv',
        'views/socle_menus.xml',
        'views/hr_job_views.xml',
        'views/revue_acces_views.xml',
    ],
    'installable': True,
}
