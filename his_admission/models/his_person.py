# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisPerson(models.Model):
    """Etat civil et famille : sur la personne, pas sur le dossier.

    Le classeur repetait ces colonnes sur chaque ligne d'inscription. Une
    reinscription y recopiait donc le nom du pere et le telephone du tuteur,
    avec la divergence que toute recopie finit par produire.

    Les parents ne changent pas d'une inscription a l'autre : ces champs
    appartiennent a l'humain, pas au parcours.
    """
    _inherit = 'his.person'

    # --- Etat civil, ce que his_person_core ne portait pas encore ------------

    genre = fields.Selection(
        selection=[('male', "Masculin"), ('female', "Feminin")],
        string="Genre",
    )
    date_naissance = fields.Date(string="Date de naissance")
    commune_naissance = fields.Char(string="Commune de naissance")
    wilaya_naissance = fields.Char(string="Wilaya de naissance")
    numero_identite = fields.Char(
        string="Numero d'identite nationale", copy=False,
        help="Numero de la piece d'identite nationale.",
    )
    date_expiration_identite = fields.Date(string="Expiration de la piece d'identite")
    # Texte libre et non Selection : le classeur y trouve « bonne sante » dans
    # 135 cas sur 152, puis douze descriptions medicales toutes differentes
    # (« a subi une operation au cerveau, doit sortir de classe parfois »).
    # Une Selection perdrait exactement l'information qui compte.
    etat_sante = fields.Char(string="Etat de sante")
    adresse_residence = fields.Char(string="Adresse de residence")

    # --- Famille -------------------------------------------------------------

    pere_nom = fields.Char(string="Nom du pere")
    pere_profession = fields.Char(string="Profession du pere")
    pere_telephone = fields.Char(string="Telephone du pere")
    pere_email = fields.Char(string="Email du pere")

    mere_nom = fields.Char(string="Nom de la mere")
    mere_prenom = fields.Char(string="Prenom de la mere")
    mere_profession = fields.Char(string="Profession de la mere")

    # Le tuteur n'est pas toujours un parent — le classeur en cite qui sont la
    # mere, le pere, ou un tiers. D'ou le champ relation, en texte libre.
    tuteur_nom = fields.Char(string="Nom complet du tuteur")
    tuteur_relation = fields.Char(string="Lien avec l'etudiant")
    tuteur_telephone = fields.Char(string="Telephone du tuteur")
    tuteur_email = fields.Char(string="Email du tuteur")
    tuteur_adresse = fields.Char(string="Adresse du tuteur")
