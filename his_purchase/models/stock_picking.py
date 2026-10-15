# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        res = super()._action_done()
        # Reception complete : la demande d'achat passe a « Terminee ».
        self.purchase_id.his_request_id._his_update_progress()
        return res
