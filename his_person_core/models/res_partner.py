# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Inverse de la delegation. Sert surtout a filtrer : depuis que chaque
    # personne du referentiel porte un res.partner, les selecteurs de contacts
    # d'Odoo proposent employes, etudiants et candidats la ou on attend une
    # adresse ou une societe. Ce champ donne aux vues de quoi les ecarter.
    his_person_ids = fields.One2many(
        'his.person', 'partner_id', string="Fiche personne",
    )
