from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _update_last_login(self):
        """Forget the temporary password once it has served (audit S-7).

        The Create Workers wizard keeps it on the employee so a manager can hand
        it over, but it stayed there in clear for as long as the employee lived.
        Called by `_login` as the user who just logged in.
        """
        res = super()._update_last_login()
        self.env["hr.employee"].sudo().search(
            [("user_id", "=", self.env.uid), ("initial_password", "!=", False)]
        ).initial_password = False
        return res
