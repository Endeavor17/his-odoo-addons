# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models

from .pos_config import HIDDEN_PARTNER_IDS


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _his_pos_hidden_partner_ids(self):
        return [row[0] for row in self.env.execute_query(HIDDEN_PARTNER_IDS)]

    @api.model
    def get_new_partner(self, config_id, domain, offset):
        # Domaine vide : le coeur repasse par get_limited_partners_loading, deja
        # filtre. Domaine non vide (recherche du caissier) : le coeur cherche
        # dans TOUS les contacts, il faut donc y ajouter la regle ici.
        if domain:
            domain = [*list(domain), ("id", "not in", self._his_pos_hidden_partner_ids())]
        return super().get_new_partner(config_id, domain, offset)
