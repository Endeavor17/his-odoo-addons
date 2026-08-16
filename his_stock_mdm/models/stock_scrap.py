# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    # stock.scrap n'a aucun champ libre : `origin` est le document source.
    scrap_note = fields.Char(string="Commentaire")

    # 'product_id' est requis, donc toujours present dans les vals a la
    # creation : sans lui, une declaration creee sans aucun motif ne
    # declencherait pas la contrainte (Odoo ne valide que les champs ecrits).
    @api.constrains('scrap_reason_tag_ids', 'scrap_note', 'product_id')
    def _check_mdm_scrap_reason(self):
        """MDM Phase 7 : motif obligatoire, commentaire obligatoire si « Autre »."""
        autre = self.env.ref('his_stock_mdm.scrap_reason_autre', raise_if_not_found=False)
        for scrap in self:
            if not scrap.scrap_reason_tag_ids:
                raise ValidationError(
                    "Un motif de perte est obligatoire pour permettre le reporting "
                    "par cause.")
            if autre and autre in scrap.scrap_reason_tag_ids and not scrap.scrap_note:
                raise ValidationError(
                    "Le motif « Autre » exige un commentaire décrivant la cause.")
