# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.exceptions import UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    def try_cash_in_out(self, _type, amount, reason, partner_id, extras):
        # Procedure §4.1 : une caisse ne paie ni achat ni fournisseur ; les
        # especes n'en sortent que par un versement a la Finance.
        raise UserError(_("Cash only leaves a till by a hand over to Finance."))
