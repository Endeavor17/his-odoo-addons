# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models

PURCHASE_DOMAINS = [
    ("general", "General"),
    ("pos", "Points of Sale"),
]


class HrDepartment(models.Model):
    _inherit = "hr.department"

    his_purchase_domain = fields.Selection(
        PURCHASE_DOMAINS,
        string="Purchase Domain",
        default="general",
        required=True,
        help="Points of Sale (Cafeteria, Restaurant, Copy Center): orders approved by the purchase "
        "manager or the executive director. General: by the executive director only.",
    )
