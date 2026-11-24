# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    # Procedure §4.3 : annulation, modification, remboursement autorises et
    # motives. Renseignes par la caisse (code PIN du responsable + motif).
    his_authorized_by_id = fields.Many2one("hr.employee", string="Authorized By", readonly=True)
    his_authorization_reason = fields.Char(string="Authorization Reason", readonly=True)
    his_authorization_kind = fields.Selection(
        [("price", "Price Change"), ("discount", "Discount"), ("refund", "Refund")],
        string="Authorization",
        readonly=True,
    )

    @api.model
    def _load_pos_data_fields(self, config):
        return [
            *super()._load_pos_data_fields(config),
            "his_authorized_by_id",
            "his_authorization_reason",
            "his_authorization_kind",
        ]
