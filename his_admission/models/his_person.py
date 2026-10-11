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

    _inherit = "his.person"

    # --- Etat civil, ce que his_person_core ne portait pas encore ------------

    genre = fields.Selection(
        selection=[("male", "Male"), ("female", "Female")],
        string="Gender",
    )
    date_naissance = fields.Date(string="Date of Birth")
    commune_naissance = fields.Char(string="Municipality of Birth")
    wilaya_naissance = fields.Char(string="Wilaya of Birth")
    numero_identite = fields.Char(
        string="National ID Number",
        copy=False,
        help="Number of the national ID document.",
    )
    date_expiration_identite = fields.Date(string="ID Document Expiry")
    # Texte libre et non Selection : le classeur y trouve « bonne sante » dans
    # 135 cas sur 152, puis douze descriptions medicales toutes differentes
    # (« a subi une operation au cerveau, doit sortir de classe parfois »).
    # Une Selection perdrait exactement l'information qui compte.
    etat_sante = fields.Char(string="Health Status")
    adresse_residence = fields.Char(string="Home Address")

    # --- Famille -------------------------------------------------------------

    pere_nom = fields.Char(string="Father's Name")
    pere_profession = fields.Char(string="Father's Occupation")
    pere_telephone = fields.Char(string="Father's Phone")
    pere_email = fields.Char(string="Father's Email")

    mere_nom = fields.Char(string="Mother's Surname")
    mere_prenom = fields.Char(string="Mother's First Name")
    mere_profession = fields.Char(string="Mother's Occupation")

    # Le tuteur n'est pas toujours un parent — le classeur en cite qui sont la
    # mere, le pere, ou un tiers. D'ou le champ relation, en texte libre.
    tuteur_nom = fields.Char(string="Guardian's Full Name")
    tuteur_relation = fields.Char(string="Relationship to Student")
    tuteur_telephone = fields.Char(string="Guardian's Phone")
    tuteur_email = fields.Char(string="Guardian's Email")
    tuteur_adresse = fields.Char(string="Guardian's Address")
