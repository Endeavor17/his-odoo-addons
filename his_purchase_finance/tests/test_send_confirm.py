# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from dateutil.relativedelta import relativedelta
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import HisFinanceCase


@tagged("post_install", "-at_install")
class TestSendConfirm(HisFinanceCase):
    # Commande de test : 2 toners. 45 000 l'unite = 90 000 HT ; 75 000 = 150 000 HT.

    def test_send_always_asks_reason(self):
        order = self._offer()
        action = order.with_user(self.officer).action_his_send_to_finance()
        self.assertEqual(action["res_model"], "his.purchase.choice")
        self.assertTrue(action["context"]["his_send_to_finance"])
        self.assertFalse(action["context"]["default_criterion"], "une seule offre : pas de « meilleur prix » d'office")
        self.assertFalse(order.his_sent_to_finance_on)

    def test_quote_rule_below_threshold(self):
        order = self._offer(price=45000)
        self._send(order, criterion="quality", note="")
        self.assertTrue(order.his_sent_to_finance_on)
        self.assertEqual(order.his_choice_criterion, "quality")
        self.assertEqual(order.his_supplier_answer, "quoted")

    def test_quote_rule_above_threshold_needs_note(self):
        order = self._offer(price=75000)
        self._alternative(order, self.supplier_b, 76000)
        with self.assertRaises(UserError):
            self._send(order, criterion="lowest_price", note="")
        self._send(order, criterion="lowest_price", note="Only two suppliers stock this model.")
        self.assertTrue(order.his_sent_to_finance_on)
        self.assertIn("Exception to the 3-quote rule", "".join(order.message_ids.mapped("body")))

    def test_three_quotes_no_note(self):
        order = self._offer(price=75000)
        self._alternative(order, self.supplier_b, 76000)
        self._alternative(order, self.supplier_c, 77000)
        self._send(order, criterion="lowest_price", note="")
        self.assertTrue(order.his_sent_to_finance_on)

    def test_declined_offer_is_not_a_quote(self):
        order = self._offer(price=75000)
        self._alternative(order, self.supplier_b, 76000)
        alt_c = self._alternative(order, self.supplier_c, 77000)
        alt_c.his_supplier_answer = "declined"
        self.assertEqual(order._his_quote_count(), 2)

    def test_foreign_currency_converted(self):
        eur = self.env.ref("base.EUR")
        eur.active = True
        self.env["res.currency.rate"].create(
            {
                "currency_id": eur.id,
                "rate": 0.5,
                "name": fields.Date.today() - relativedelta(days=1),
                "company_id": self.company.id,
            }
        )
        order = self._offer(price=30000)
        order.currency_id = eur
        order.order_line.price_unit = 30000
        # 60 000 EUR = 120 000 dans la devise de la societe : la regle s'applique.
        self.assertTrue(order._his_needs_quote_exception())
        with self.assertRaises(UserError):
            self._send(order, note="")

    def test_contract_order_skips_wizard(self):
        agreement = self.env["purchase.requisition"].create(
            {
                "requisition_type": "blanket_order",
                "vendor_id": self.supplier_a.id,
                "date_start": date(2026, 9, 1),
                "date_end": date(2027, 8, 31),
                "line_ids": [(0, 0, {"product_id": self.tomatoes.id, "product_qty": 1200, "price_unit": 120})],
            }
        )
        agreement.action_confirm()
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.supplier_a.id,
                "requisition_id": agreement.id,
                "order_line": [(0, 0, {"product_id": self.tomatoes.id, "product_qty": 1000, "price_unit": 120})],
            }
        )
        self.assertTrue(order.with_user(self.officer).action_his_send_to_finance())
        self.assertEqual(order.his_choice_criterion, "usual_supplier")
        self.assertIn(agreement.name, order.his_choice_note)

    def test_buyer_cannot_confirm(self):
        order = self._offer()
        self._send(order)
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            order.with_user(self.officer).button_confirm()
        with self.assertRaises(UserError):
            order.with_user(self.manager).button_confirm()

    def test_confirm_requires_sent(self):
        order = self._offer()
        with self.assertRaises(UserError):
            order.with_user(self.finance).button_confirm()

    def test_confirm_blocked_by_supplier_file(self):
        order = self._offer()
        self._send(order)
        for status in ("waiting", "reserve", "refused"):
            self.supplier_a.sudo().write({"his_supplier_status": status, "his_supplier_status_reason": "RC missing"})
            with self.assertRaises(UserError):
                order.with_user(self.finance).button_confirm()
        self.supplier_a.sudo().his_supplier_status = "validated"
        doc = self.env["his.supplier.document"].create(
            {
                "partner_id": self.supplier_a.id,
                "doc_type": "rc",
                "expires_on": fields.Date.today() - relativedelta(days=1),
            }
        )
        with self.assertRaises(UserError):
            order.with_user(self.finance).button_confirm()
        doc.unlink()
        order.with_user(self.finance).button_confirm()
        self.assertIn(order.state, ("to approve", "purchase"))

    def test_finance_confirms_then_routed_approval(self):
        order = self._offer()
        self._send(order)
        order.with_user(self.finance).button_confirm()
        self.assertEqual(order.state, "to approve", "Finance confirme ; l'approbation routee suit")
        order.with_user(self.manager).button_approve()
        self.assertEqual(order.state, "purchase")

    def test_buyer_cannot_edit_sent_order(self):
        order = self._offer()
        self._send(order)
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            order.order_line.with_user(self.officer).price_unit = 1
        with self.assertRaises(UserError):
            order.with_user(self.officer).partner_id = self.supplier_b
        # Les champs hors commande (notes de reponse) restent libres.
        order.with_user(self.officer).his_answer_note = "Delivery Monday."

    def test_return_to_buyer_clears_choice(self):
        order = self._offer()
        self._send(order)
        self.env["his.finance.return"].with_user(self.finance).create(
            {"order_id": order.id, "reason": "Wrong VAT on the pro forma."}
        ).action_return()
        self.assertFalse(order.his_sent_to_finance_on)
        self.assertFalse(order.his_choice_criterion)
        self.assertIn("Wrong VAT on the pro forma.", "".join(order.message_ids.mapped("body")))
        order.order_line.with_user(self.officer).price_unit = 8000
        with self.assertRaises(UserError):
            self.env["his.finance.return"].with_user(self.officer).create(
                {"order_id": order.id, "reason": "x"}
            ).action_return()

    def test_finance_activity_created(self):
        order = self._offer()
        self._send(order)
        self.assertEqual(order.his_step, "finance_confirm")
        self.assertIn(self.finance, order.activity_ids.user_id)
        order.with_user(self.finance).button_confirm()
        self.assertNotEqual(order.his_step, "finance_confirm")

    def test_switch_off_buyer_confirms(self):
        self.company.his_finance_confirms = False
        order = self._offer()
        self.assertTrue(order.with_user(self.officer).his_can_confirm)
        order.with_user(self.officer).button_confirm()
        self.assertIn(order.state, ("to approve", "purchase"))
