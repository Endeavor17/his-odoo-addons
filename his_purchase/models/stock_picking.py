# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        res = super()._action_done()
        # Reception complete : la demande d'achat passe a « Terminee ». En sudo :
        # le magasinier receptionne sans aucun droit sur les demandes d'achat.
        self.purchase_id.sudo()._his_requests()._his_update_progress()
        return res
