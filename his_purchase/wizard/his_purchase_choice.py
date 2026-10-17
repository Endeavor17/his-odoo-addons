# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.purchase_order import CRITERIA


class HisPurchaseChoice(models.TransientModel):
    """Pourquoi ce fournisseur : demande seulement s'il y a eu concurrence."""

    _name = "his.purchase.choice"
    _description = "Supplier Choice"

    order_id = fields.Many2one("purchase.order", required=True)
    criterion = fields.Selection(CRITERIA, string="Criterion", required=True)
    note = fields.Text(string="Note")
    is_cheapest = fields.Boolean(string="Cheapest Offer", compute="_compute_offers")
    offer_summary = fields.Text(string="Offers", compute="_compute_offers")

    @api.depends("order_id")
    def _compute_offers(self):
        for wizard in self:
            order = wizard.order_id
            wizard.is_cheapest = order._his_is_cheapest()
            offers = order | order._his_competitors()
            wizard.offer_summary = "\n".join(
                f"{o.partner_id.name}: {o.currency_id.format(o.amount_total)}" for o in offers.sorted("amount_total")
            )

    def action_confirm(self):
        self.ensure_one()
        if self.criterion == "lowest_price" and not self.order_id._his_is_cheapest():
            raise UserError(_("%s is not the cheapest offer: choose another criterion.", self.order_id.name))
        self.order_id.with_context(his_choice_write=True).write(
            {
                "his_choice_criterion": self.criterion,
                "his_choice_note": self.note,
                "his_chosen_by_id": self.env.user.id,
                "his_chosen_on": fields.Datetime.now(),
            }
        )
        return self.order_id.with_context(his_choice_done=True).button_confirm()
