# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.his_meal_management.tests.test_meal_credit_invoice import TestTheCreditMealTill
from odoo.addons.his_pos_finance.hooks import setup_pos_finance
from odoo.addons.pos_hr.tests.test_frontend import TestPosHrHttpCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFinanceTill(TestPosHrHttpCommon):
    def test_cashier_flow(self):
        # La classe de test cree sa propre societe : on y pose comptes et journaux.
        setup_pos_finance(self.env, self.env.company)
        config = self.main_pos_config
        ecart = self.env["account.account"].search(
            [("code", "=", "476000"), ("company_ids", "in", self.env.company.id)], limit=1
        )
        config.payment_method_ids.journal_id.filtered(lambda j: j.type == "cash").write(
            {"loss_account_id": ecart.id, "profit_account_id": ecart.id}
        )
        config.write({"restrict_price_control": True, "cash_control": True, "set_maximum_difference": False})
        # Comme au comptoir : un compte connecte, le caissier tape son nom et son PIN.
        config.with_user(self.pos_admin).open_ui()
        self.start_pos_tour("his_pos_finance_tour", login="pos_admin")

        self.env.invalidate_all()  # le navigateur a ecrit par ses propres requetes
        # la fermeture renvoie au tableau de bord, qui prepare deja la session suivante
        session = config.session_ids.filtered(lambda s: s.state == "closed")
        line = session.order_ids.lines
        self.assertEqual(line.his_authorization_kind, "price")
        self.assertEqual(line.his_authorization_reason, "Prix affiche errone")
        self.assertEqual(line.his_authorized_by_id, self.manager1)
        self.assertEqual(session.his_transfer_ids.state, "sent")
        form = session.his_discrepancy_ids
        self.assertEqual((form.kind, form.amount, form.explanation), ("closing", 1, "Un dinar trouve sous le tiroir"))


# Revue §1 : un prix pose par le code (repas sur credits a 0 DA) ne demande
# pas le PIN. Le tour existant tourne avec la restriction des caisses HIS ; une
# fenetre d'autorisation inattendue le bloquerait. (Les tours de tarif degressif
# du Copy Center echouent deja sur main, sans ce module : signale a part.)
@tagged("post_install", "-at_install")
class TestCreditMealWithApproval(TestTheCreditMealTill):
    allow_inherited_tests_method = True
    test_a_student_with_no_email_gets_the_receipt_and_nothing_is_sent = None
    test_anything_to_pay_keeps_the_payment_screen = None

    def _run(self, tour):
        self.main_pos_config.write({"restrict_price_control": True})
        return super()._run(tour)
