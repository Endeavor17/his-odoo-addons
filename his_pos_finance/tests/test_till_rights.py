# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.his_pos_finance.hooks import post_init_hook
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import HisPosFinanceCase


@tagged("post_install", "-at_install")
class TestTillRights(HisPosFinanceCase):
    def test_cash_in_out_refused_on_tills(self):
        session = self._open_session(self.cafeteria)
        with self.assertRaisesRegex(UserError, "hand over"):
            session.with_user(self.pos_manager).try_cash_in_out(
                "out", 100, "fournisseur", False, {"translatedType": "out"}
            )
        self.assertFalse(session.statement_line_ids)

    def test_install_moves_existing_cashiers_to_basic(self):
        self.cafeteria.module_pos_hr = True
        role = self.env["his.role"].create({"name": "Caisse Cafet", "pos_config_ids": [(6, 0, self.cafeteria.ids)]})
        poste = self.env["hr.job"].create({"name": "Caissier", "role_ids": [(6, 0, role.ids)]})
        rym = self.env["hr.employee"].create({"name": "Rym", "pin": "1234", "job_id": poste.id})
        # etat d'avant le module : caissiere « avancee »
        self.cafeteria.write({"advanced_employee_ids": [(6, 0, rym.ids)], "basic_employee_ids": [(5, 0, 0)]})
        post_init_hook(self.env)
        self.assertIn(rym, self.cafeteria.basic_employee_ids)
        self.assertNotIn(rym, self.cafeteria.advanced_employee_ids)
