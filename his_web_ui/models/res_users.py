from odoo import api, models


class ResUsers(models.Model):
    """Where a user lands when they sign in.

    web_responsive states only half the rule. Its compute clears the flag for
    anyone holding a Home Action:

        self.filtered("action_id").is_redirect_home = False

    and never sets it, so the field falls back to the Boolean default of False
    and every user has to tick a box to get the app grid. Here the app grid is
    the institution's landing page, so the other half is stated explicitly.

    This is why the module owns a compute override rather than an `ir.default`
    record: on a stored computed field a default is at the mercy of whether the
    compute runs and assigns, whereas this is deterministic — no Home Action
    means the grid, a Home Action means that action, every time.

    Someone who unticks the box for themselves keeps their choice: the compute
    only re-fires when `action_id` changes.
    """

    _inherit = 'res.users'

    @api.depends('action_id')
    def _compute_redirect_home(self):
        super()._compute_redirect_home()
        self.filtered(lambda user: not user.action_id).is_redirect_home = True
