# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "POS - Perimetre des clients",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Ecarte des caisses les contacts qui ne sont que des candidats au recrutement",
    "description": """
Le POS charge TOUS les contacts de la societe (pos.config.get_limited_partners_loading,
les 100 premiers par nombre de commandes puis par nom), sans verifier qu'il
s'agit de clients. Or hr_recruitment cree un contact par candidat : l'import
Campus+ de 249 enseignants a rempli 93 des 100 places, dans les trois caisses.

Un contact est ecarte du chargement ET de la recherche en caisse quand il :
  - est le contact d'un hr.applicant,
  - n'a aucune commande POS,
  - n'est pas le contact d'un utilisateur,
  - n'est pas le contact professionnel d'un employe,
  - ne porte aucune fiche personne d'un autre type que « candidat ».

Etudiants, employes et enseignants (porteurs d'une fiche personne) restent donc
visibles — la recherche par carte repas en caisse ne fonctionne que sur les
contacts charges — ainsi que quiconque a deja achete quelque chose.

Aucun contact n'est archive ni supprime : l'email et le telephone des
candidatures vivent sur ces contacts.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
        "hr_recruitment",
        "his_person_core",
    ],
    "installable": True,
}
