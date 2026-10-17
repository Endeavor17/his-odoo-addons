# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Toute commande est approuvee (decision du 2026-10-15) : deux niveaux,
    # montant 0, y compris pour une societe creee apres l'installation.
    po_double_validation = fields.Selection(default="two_step")
    po_double_validation_amount = fields.Monetary(default=0)

    his_purchase_officer_id = fields.Many2one(
        "res.users",
        string="Purchasing Officer",
        help="Sources approved purchase requests and chases suppliers.",
    )
    his_purchase_manager_id = fields.Many2one(
        "res.users",
        string="Purchase Manager",
        help="Approves point-of-sale orders; first level of escalation.",
    )
    his_purchase_director_id = fields.Many2one(
        "res.users",
        string="Executive Director",
        help="Approves general orders; last level of escalation.",
    )
