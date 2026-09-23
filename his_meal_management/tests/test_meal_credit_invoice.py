"""A meal eaten on credits: no payment screen, an invoice, and its email.

Two halves, because the feature has two:

* `TestTheCreditMealInvoice` is the server. The till only sets `to_invoice`; it
  is core that invoices the order and emails the invoice. What this module adds
  is the line on that invoice saying which credits paid for a 0 DA meal - and
  the promise that nothing about the credits themselves moved.

* `TestTheCreditMealTill` drives a real till: Payment on a meal served on
  credits must land on the receipt without ever showing the payment screen,
  and an order with anything to pay must still show it.
"""

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .test_meal_credits import make_person


@tagged("post_install", "-at_install")
class TestTheCreditMealInvoice(AccountTestInvoicingCommon):
    """What the invoice of a meal served on credits says, and who receives it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("point_of_sale.group_pos_manager") | cls.env.ref(
            "his_meal_management.group_meal_officer"
        )
        cls.with_email = make_person(cls.env, "Samira", email="samira.test@his.edu.dz").partner_id
        cls.without_email = make_person(cls.env, "Yacine").partner_id
        cls.plan = cls.env.ref("his_meal_management.product_plan_weekly").product_variant_id
        cls.meal_600 = cls.env.ref("his_meal_management.product_daily_meal").product_variant_id
        cls.meal_300 = cls.env.ref("his_meal_management.product_meal_300").product_variant_id
        cls.cash = cls.env["pos.payment.method"].create(
            {
                "name": "Especes",
                "receivable_account_id": cls.company_data["default_account_receivable"].id,
                "journal_id": cls.company_data["default_journal_cash"].id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Credit Meal Restaurant",
                "payment_method_ids": [Command.set(cls.cash.ids)],
                "invoice_journal_id": cls.company_data["default_journal_sale"].id,
            }
        )
        cls.config.open_ui()
        cls.session = cls.config.current_session_id
        for partner in (cls.with_email, cls.without_email):
            partner.sudo()._grant_meal_credits(cls.plan)

    def _sync(self, partner, lines, uuid):
        """An invoiced order through the till's own entry point.

        `lines` is a list of (product, qty, price_unit, discount). A meal on
        credits comes with no payment line at all: that is what the till sends
        now that it skips the payment screen, and core must accept it.
        """
        total = sum(qty * price * (1 - discount / 100) for _p, qty, price, discount in lines)
        payload = {
            "company_id": self.env.company.id,
            "session_id": self.session.id,
            "partner_id": partner.id,
            "uuid": uuid,
            "to_invoice": True,
            "lines": [
                [
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "qty": qty,
                        "price_unit": price,
                        "discount": discount,
                        "tax_ids": [[6, False, []]],
                        "price_subtotal": qty * price * (1 - discount / 100),
                        "price_subtotal_incl": qty * price * (1 - discount / 100),
                    },
                ]
                for product, qty, price, discount in lines
            ],
            "payment_ids": (
                [[0, 0, {"amount": total, "name": fields.Datetime.now(), "payment_method_id": self.cash.id}]]
                if total
                else []
            ),
            "amount_paid": total,
            "amount_total": total,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "last_order_preparation_change": "{}",
        }
        self.env["pos.order"].sync_from_ui([payload])
        return self.env["pos.order"].search([("uuid", "=", uuid)])

    def _invoice_mails(self, invoice, partner):
        # With his_mail_async installed, PDF and email are left to the "Send
        # invoices automatically" cron: do what it does (minus its commit).
        pending = invoice.filtered("sending_data")
        if pending:
            self.env["account.move.send"]._generate_and_send_invoices(pending, from_cron=True)
        return invoice.message_ids.filtered(lambda message: partner in message.partner_ids)

    def test_a_credit_meal_is_invoiced_at_zero_with_its_credits_stated(self):
        order = self._sync(self.with_email, [(self.meal_600, 1, 0.0, 0.0)], "credit-invoice-0001")
        invoice = order.account_move

        self.assertTrue(invoice, "the order was not invoiced")
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.amount_total, 0.0, "the meal was already paid for when the pack was sold")
        label = invoice.invoice_line_ids.name
        self.assertIn("Paid with 1 meal credit(s)", label)
        self.assertIn(invoice.currency_id.format(600.0), label, "the line does not say what the credit was worth")
        # Invoicing is a document, not a second charge.
        self.assertEqual(self.with_email.meal_credits_remaining, 5.0)
        self.assertEqual(
            self.env["his.meal.transaction"].search_count([("pos_order_id", "=", order.id), ("type", "=", "consume")]),
            1,
        )

    def test_half_credits_and_quantities_are_stated_as_they_are(self):
        order = self._sync(self.with_email, [(self.meal_300, 3, 0.0, 0.0)], "credit-invoice-0002")
        label = order.account_move.invoice_line_ids.name
        self.assertIn("Paid with 1.5 meal credit(s)", label)
        self.assertIn(order.currency_id.format(900.0), label)

    def test_the_invoice_is_emailed_to_a_student_who_has_an_address(self):
        order = self._sync(self.with_email, [(self.meal_600, 1, 0.0, 0.0)], "credit-invoice-0003")
        mails = self._invoice_mails(order.account_move, self.with_email)
        self.assertTrue(mails, "core did not email the invoice")
        self.assertTrue(
            any(name.endswith(".pdf") for name in mails.attachment_ids.mapped("name")),
            "the email went out without the invoice attached",
        )

    def test_a_student_with_no_address_is_invoiced_and_nothing_is_sent(self):
        order = self._sync(self.without_email, [(self.meal_600, 1, 0.0, 0.0)], "credit-invoice-0004")
        self.assertEqual(order.account_move.state, "posted")
        self.assertFalse(self._invoice_mails(order.account_move, self.without_email))

    def test_a_meal_sold_at_its_price_carries_no_credit_line(self):
        order = self._sync(self.with_email, [(self.meal_600, 1, 600.0, 0.0)], "credit-invoice-0005")
        self.assertNotIn("meal credit", order.account_move.invoice_line_ids.name)
        self.assertEqual(order.account_move.amount_total, 600.0)
        self.assertEqual(self.with_email.meal_credits_remaining, 6.0, "a paying customer spent credits")

    def test_a_meal_discounted_to_nothing_says_what_paid_for_it(self):
        """The 100% discount is a credit meal since 19.0.3.6.0; the invoice agrees."""
        order = self._sync(self.with_email, [(self.meal_600, 1, 600.0, 100.0)], "credit-invoice-0006")
        self.assertIn("Paid with 1 meal credit(s)", order.account_move.invoice_line_ids.name)
        self.assertEqual(self.with_email.meal_credits_remaining, 5.0)


@tagged("post_install", "-at_install")
class TestTheCreditMealTill(TestPointOfSaleHttpCommon):
    """Payment on a meal eaten on credits, clicked through the way a cashier does."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plan = cls.env["product.product"].create(
            {"name": "Tour Pack", "type": "service", "list_price": 3000.0, "meal_credits": 6}
        )
        cls.env["product.product"].create(
            {
                "name": "Tour Repas 600",
                "type": "consu",
                "list_price": 600.0,
                "meal_credit_cost": 1.0,
                "available_in_pos": True,
                "taxes_id": [Command.clear()],
            }
        )
        cls.env["product.product"].create(
            {
                "name": "Tour Jus",
                "type": "consu",
                "list_price": 100.0,
                "available_in_pos": True,
                "taxes_id": [Command.clear()],
            }
        )
        # "AAA": the till loads only the first partners it finds, by name.
        cls.with_email = make_person(cls.env, "AAA Tour Email", email="tour.email@his.edu.dz").partner_id
        cls.without_email = make_person(cls.env, "AAA Tour Sans Email").partner_id
        for partner in (cls.with_email, cls.without_email):
            partner.sudo()._grant_meal_credits(plan)

    def _run(self, tour):
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour(tour)
        return self.env["pos.order"].search([("config_id", "=", self.main_pos_config.id)], order="id desc", limit=1)

    def test_payment_on_a_credit_meal_goes_straight_to_the_receipt(self):
        order = self._run("his_meal_credit_payment_email_tour")
        self.assertTrue(order.to_invoice)
        self.assertEqual(order.state, "done", "an invoiced order ends 'done'")
        self.assertFalse(order.payment_ids, "a meal on credits was recorded as paid by something")
        self.assertEqual(order.account_move.amount_total, 0.0)
        self.assertEqual(self.with_email.meal_credits_remaining, 5.0)

    def test_a_student_with_no_email_still_gets_the_invoice_and_the_receipt(self):
        order = self._run("his_meal_credit_payment_no_email_tour")
        self.assertTrue(order.account_move)
        self.assertEqual(self.without_email.meal_credits_remaining, 5.0)

    def test_anything_to_pay_keeps_the_payment_screen(self):
        self._run("his_meal_credit_payment_mixed_tour")
