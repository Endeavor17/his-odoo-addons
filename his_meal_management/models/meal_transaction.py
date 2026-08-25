from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HisMealTransaction(models.Model):
    """Append-only ledger. One line per credit granted, eaten or corrected.

    Nothing in this module changes a balance without writing here, and nothing
    in the interface can edit or delete a line once written.
    """

    _name = 'his.meal.transaction'
    _description = "Meal Credit Transaction"
    _order = 'date desc, id desc'

    partner_id = fields.Many2one(
        'res.partner', string="Person", required=True, index=True, ondelete='restrict',
    )
    card_id = fields.Many2one('his.meal.card', string="Card", ondelete='set null')
    subscription_id = fields.Many2one(
        'his.meal.subscription', string="Subscription", index=True, ondelete='set null',
    )
    type = fields.Selection(
        [
            ('purchase', "Plan Purchase"),
            ('consume', "Meal Served"),
            ('adjust', "Correction"),
        ],
        required=True, index=True,
    )
    credits = fields.Integer(
        required=True, help="Signed: +25 for a purchase, -1 for a meal.",
    )
    balance_after = fields.Integer(
        required=True, help="The student's total usable credits right after this line.",
    )
    product_id = fields.Many2one('product.product', string="Plan / Meal", ondelete='set null')
    pos_order_id = fields.Many2one('pos.order', string="POS Order", ondelete='set null')
    session_id = fields.Many2one('pos.session', string="POS Session", ondelete='set null')
    config_id = fields.Many2one('pos.config', string="Point of Sale", ondelete='set null')
    user_id = fields.Many2one(
        'res.users', string="Operator", required=True, default=lambda self: self.env.user,
    )
    date = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    note = fields.Char()

    def write(self, vals):
        raise UserError(_("Meal transactions are a permanent record and cannot be edited. "
                          "Post a correction instead."))

    def unlink(self):
        raise UserError(_("Meal transactions are a permanent record and cannot be deleted."))
