# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Evaluation du fournisseur a la cloture de l'achat (procedure Finance, etape 9).

Achats et Finance notent chacun leurs criteres de 1 a 5. La procedure parle
d'une note ponderee sans donner les poids : moyenne simple, et seuils
Satisfaisant / A surveiller / Defaillant choisis ici (3,5 et 2,5).
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .common import is_finance

SIDES = [("purchase", "Purchasing"), ("finance", "Finance")]
CRITERIA = {
    "purchase": [
        "purchase_delay",
        "purchase_quality",
        "purchase_compliance",
        "purchase_quantity",
        "purchase_responsiveness",
        "purchase_warranty",
        "purchase_price",
    ],
    "finance": [
        "finance_admin",
        "finance_invoicing",
        "finance_bank",
        "finance_payment_terms",
        "finance_anomalies",
    ],
}
SATISFACTORY = 3.5
WATCH = 2.5


class HisSupplierRating(models.Model):
    _name = "his.supplier.rating"
    _description = "Supplier Rating"
    _order = "id desc"

    order_id = fields.Many2one("purchase.order", string="Purchase Order", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one(
        "res.partner", string="Supplier", related="order_id.partner_id.commercial_partner_id", store=True, index=True
    )
    side = fields.Selection(SIDES, string="Rated By", required=True, default=lambda self: self._default_side())
    purchase_delay = fields.Integer(string="Delivery Delays")
    purchase_quality = fields.Integer(string="Quality")
    purchase_compliance = fields.Integer(string="Compliance")
    purchase_quantity = fields.Integer(string="Quantities")
    purchase_responsiveness = fields.Integer(string="Responsiveness")
    purchase_warranty = fields.Integer(string="Warranty")
    purchase_price = fields.Integer(string="Price Competitiveness")
    finance_admin = fields.Integer(string="Administrative and Tax Compliance")
    finance_invoicing = fields.Integer(string="Invoicing")
    finance_bank = fields.Integer(string="Bank Details")
    finance_payment_terms = fields.Integer(string="Payment Terms")
    finance_anomalies = fields.Integer(string="Handling of Anomalies")
    note = fields.Text(string="Observations")
    score = fields.Float(string="Score", compute="_compute_score", store=True, digits=(3, 2))

    _order_side_uniq = models.Constraint("UNIQUE(order_id, side)", "This order already has a rating from this side.")

    @api.model
    def _default_side(self):
        return "finance" if self.env.user.has_group("his_purchase_finance.group_finance") else "purchase"

    @api.depends(*CRITERIA["purchase"], *CRITERIA["finance"], "side")
    def _compute_score(self):
        for rating in self:
            marks = [rating[name] for name in CRITERIA.get(rating.side, [])]
            rating.score = sum(marks) / len(marks) if marks else 0.0

    @api.constrains(*CRITERIA["purchase"], *CRITERIA["finance"], "side")
    def _check_marks(self):
        for rating in self:
            if any(not 1 <= rating[name] <= 5 for name in CRITERIA[rating.side]):
                raise ValidationError(_("Rate every criterion from 1 (very poor) to 5 (excellent)."))

    @api.model_create_multi
    def create(self, vals_list):
        ratings = super().create(vals_list)
        if ratings.filtered(lambda r: r.side == "finance") and not is_finance(self.env):
            raise AccessError(_("Only Finance can give the Finance rating."))
        return ratings


class ResPartner(models.Model):
    _inherit = "res.partner"

    his_rating_score = fields.Float(string="Supplier Score", compute="_compute_his_rating", digits=(3, 2))
    his_rating_label = fields.Selection(
        [("satisfactory", "Satisfactory"), ("watch", "To Watch"), ("failing", "Failing")],
        string="Supplier Rating",
        compute="_compute_his_rating",
    )

    def _compute_his_rating(self):
        Rating = self.env["his.supplier.rating"].sudo()
        for partner in self:
            scores = Rating.search([("partner_id", "=", partner.commercial_partner_id.id)]).mapped("score")
            score = sum(scores) / len(scores) if scores else 0.0
            partner.his_rating_score = score
            if not scores:
                partner.his_rating_label = False
            elif score >= SATISFACTORY:
                partner.his_rating_label = "satisfactory"
            elif score >= WATCH:
                partner.his_rating_label = "watch"
            else:
                partner.his_rating_label = "failing"


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def action_his_rate(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Rate Supplier"),
            "res_model": "his.supplier.rating",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }
