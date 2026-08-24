# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisPerson(models.Model):
    _inherit = 'his.person'

    # selection_add plutot qu'une modification de his_person_core : le socle
    # d'identite est deja fusionne et sert trois autres modules. Etendre la
    # liste depuis ici laisse le socle intact et fait apparaitre la valeur
    # exactement la ou elle a un sens — sur une base ou le CRM est installe.
    #
    # ondelete : source_system est requis et sans defaut, « set default » y
    # laisserait un champ vide sur un champ obligatoire. A la desinstallation du
    # pont, les fiches nees du CRM basculent donc en « Saisie manuelle » : leur
    # provenance reelle reste lisible dans external_ref et dans le chatter.
    source_system = fields.Selection(
        selection_add=[('odoo_crm', "Odoo CRM")],
        ondelete={'odoo_crm': lambda recs: recs.write({'source_system': 'manual'})},
    )
