from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MealAdjustWizard(models.TransientModel):
    """The only sanctioned way to change a balance by hand.

    It exists so that corrections leave the same audit trail as everything else:
    nobody edits `credits_used` directly, and every correction carries a reason
    and the name of whoever made it.
    """

    _name = 'his.meal.adjust.wizard'
    _description = "Correct Meal Credits"

    # Anyone holding a card, whatever their role. The meal account follows the
    # card, not the matricule institutionnel and not type_personne.
    partner_id = fields.Many2one(
        'res.partner', string="Person", required=True,
        domain=[('meal_card_ids', '!=', False)],
    )
    current_credits = fields.Integer(
        related='partner_id.meal_credits_remaining', string="Credits Now", readonly=True,
    )
    credits = fields.Integer(
        required=True,
        help="Positive to grant credits, negative to take them back.",
    )
    validity_days = fields.Integer(
        string="Valid For (days)", default=30,
        help="Only used when granting credits.",
    )
    reason = fields.Char(required=True, help="Recorded on the ledger line.")

    @api.constrains('credits')
    def _check_credits(self):
        for wizard in self:
            if not wizard.credits:
                raise UserError(_("Enter a number of credits to grant or take back."))

    def action_apply(self):
        self.ensure_one()
        partner = self.partner_id
        if self.credits > 0:
            if self.validity_days <= 0:
                raise UserError(_("Granted credits need a validity of at least one day."))
            partner._add_meal_credits(
                credits=self.credits,
                date_end=fields.Date.context_today(self) + timedelta(days=self.validity_days - 1),
                tx_type='adjust',
                note=self.reason,
            )
        else:
            # Reuses the same guarded path as a real meal, so a correction can
            # no more push a student negative than a cashier can.
            partner._consume_meal_credit(
                qty=-self.credits, tx_type='adjust', note=self.reason,
            )
        return {'type': 'ir.actions.act_window_close'}
