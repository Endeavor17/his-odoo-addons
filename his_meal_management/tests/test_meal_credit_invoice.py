"""A meal eaten on credits: no payment screen, a ticket, and its email.

Two halves, because the feature has two:

* `TestTheCreditMealInvoice` is the server. A meal eaten on credits is never
  invoiced on its own (decision of 2026-10-17: the plan is an advance payment,
  invoiced and taxed when it is sold; serving the meal is not a sale), so an
  order at 0 DA gets its ticket even with the box ticked, and the back office
  refuses to invoice it. An order with something to pay is still invoiced when
  asked: the meal rides along at 0 DA with a line saying which credits paid for
  it - and nothing about the credits themselves moved.

* `TestTheCreditMealTill` drives a real till: Payment on a meal served on
  credits must land on the receipt without ever showing the payment screen, the
  ticket is emailed rather than an invoice made, and an order with anything to
  pay must still show the payment screen.
"""

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_meal_credits import make_person


def sync_order(env, session, cash, partner, lines, uuid, to_invoice=True):
    """An order through the till's own entry point.

    `lines` is a list of (product, qty, price_unit, discount). A meal on
    credits comes with no payment line at all: that is what the till sends
    now that it skips the payment screen, and core must accept it.
    """
    total = sum(qty * price * (1 - discount / 100) for _p, qty, price, discount in lines)
    payload = {
        "company_id": env.company.id,
        "session_id": session.id,
        "partner_id": partner.id if partner else False,
        "uuid": uuid,
        "to_invoice": to_invoice,
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
            [[0, 0, {"amount": total, "name": fields.Datetime.now(), "payment_method_id": cash.id}]] if total else []
        ),
        "amount_paid": total,
        "amount_total": total,
        "amount_tax": 0.0,
        "amount_return": 0.0,
        "last_order_preparation_change": "{}",
    }
    env["pos.order"].sync_from_ui([payload])
    return env["pos.order"].search([("uuid", "=", uuid)])


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
        # Meals of their own: the module's generic "Meal 300/600" are archived
        # since the formulas (2026-10-15), and an archived product cannot be sold.
        meal = cls.env["product.product"].create
        cls.meal_600 = meal(
            {
                "name": "Test Meal 600",
                "type": "consu",
                "list_price": 600.0,
                "meal_credit_cost": 1.0,
                "taxes_id": [Command.clear()],
            }
        )
        cls.meal_300 = meal(
            {
                "name": "Test Meal 300",
                "type": "consu",
                "list_price": 300.0,
                "meal_credit_cost": 0.5,
                "taxes_id": [Command.clear()],
            }
        )
        cls.drink = meal(
            {
                "name": "Test Drink",
                "type": "consu",
                "list_price": 100.0,
                "taxes_id": [Command.clear()],
            }
        )
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

    def _sync(self, partner, lines, uuid, to_invoice=True):
        return sync_order(self.env, self.session, self.cash, partner, lines, uuid, to_invoice=to_invoice)

    def _ticket_mails(self, order):
        return self.env["mail.mail"].sudo().search([("model", "=", "pos.order"), ("res_id", "=", order.id)])

    def test_the_server_emails_the_ticket_once(self):
        """Recette P-05 : le ticket partait du navigateur, et un rechargement le perdait."""
        order = self._sync(self.with_email, [(self.meal_600, 1, 0.0, 0.0)], "ticket-0001", to_invoice=False)
        mail = self._ticket_mails(order)
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.recipient_ids, self.with_email)
        self.assertEqual(mail.state, "outgoing", "sent inside the till's request instead of queued")
        self.assertIn("Meal credits left", mail.body_html)
        order._his_send_ticket()
        self.assertEqual(len(self._ticket_mails(order)), 1, "a resync sent the ticket twice")

    def test_no_ticket_without_an_address_or_with_an_invoice(self):
        order = self._sync(self.without_email, [(self.meal_600, 1, 0.0, 0.0)], "ticket-0002", to_invoice=False)
        self.assertFalse(self._ticket_mails(order))
        invoiced = self._sync(
            self.with_email, [(self.meal_600, 1, 0.0, 0.0), (self.drink, 1, 100.0, 0.0)], "ticket-0003"
        )
        self.assertTrue(invoiced.account_move)
        self.assertFalse(invoiced.his_ticket_sent, "an invoiced order also got a ticket")

    def _invoice_mails(self, invoice, partner):
        # With his_mail_async installed, PDF and email are left to the "Send
        # invoices automatically" cron: do what it does (minus its commit).
        pending = invoice.filtered("sending_data")
        if pending:
            self.env["account.move.send"]._generate_and_send_invoices(pending, from_cron=True)
        return invoice.message_ids.filtered(lambda message: partner in message.partner_ids)

    def test_a_meal_on_credits_alone_gets_a_ticket_not_an_invoice(self):
        """Ticked box or not: 0 DA invoices were numbered invoices with no sale behind them."""
        order = self._sync(self.with_email, [(self.meal_600, 1, 0.0, 0.0)], "credit-invoice-0001")
        self.assertFalse(order.account_move, "a meal eaten on credits was invoiced at 0 DA")
        self.assertFalse(order.to_invoice)
        self.assertEqual(order.state, "paid")
        self.assertTrue(order.his_ticket_sent, "the student got neither an invoice nor a ticket")
        # Credits move as before.
        self.assertEqual(self.with_email.meal_credits_remaining, 5.0)
        self.assertEqual(
            self.env["his.meal.transaction"].search_count([("pos_order_id", "=", order.id), ("type", "=", "consume")]),
            1,
        )

    def test_the_back_office_refuses_to_invoice_a_meal_on_credits(self):
        """The "Invoice" button and the receipt's QR both end in action_pos_order_invoice."""
        order = self._sync(self.with_email, [(self.meal_600, 1, 0.0, 0.0)], "credit-invoice-0007", to_invoice=False)
        with self.assertRaises(UserError):
            order.action_pos_order_invoice()
        self.assertFalse(order.account_move)

    def test_a_mixed_order_is_invoiced_with_its_credits_stated(self):
        order = self._sync(
            self.with_email, [(self.meal_600, 1, 0.0, 0.0), (self.drink, 1, 100.0, 0.0)], "credit-invoice-0008"
        )
        invoice = order.account_move
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.amount_total, 100.0, "the meal was already paid for when the pack was sold")
        label = invoice.invoice_line_ids.filtered(lambda line: line.product_id == self.meal_600).name
        self.assertIn("Paid with 1 meal credit(s)", label)
        self.assertIn(invoice.currency_id.format(600.0), label, "the line does not say what the credit was worth")
        self.assertEqual(self.with_email.meal_credits_remaining, 5.0)

    def test_half_credits_and_quantities_are_stated_as_they_are(self):
        order = self._sync(
            self.with_email, [(self.meal_300, 3, 0.0, 0.0), (self.drink, 1, 100.0, 0.0)], "credit-invoice-0002"
        )
        label = order.account_move.invoice_line_ids.filtered(lambda line: line.product_id == self.meal_300).name
        self.assertIn("Paid with 1.5 meal credit(s)", label)
        self.assertIn(order.currency_id.format(900.0), label)

    def test_the_invoice_is_emailed_to_a_student_who_has_an_address(self):
        order = self._sync(
            self.with_email, [(self.meal_600, 1, 0.0, 0.0), (self.drink, 1, 100.0, 0.0)], "credit-invoice-0003"
        )
        mails = self._invoice_mails(order.account_move, self.with_email)
        self.assertTrue(mails, "core did not email the invoice")
        self.assertTrue(
            any(name.endswith(".pdf") for name in mails.attachment_ids.mapped("name")),
            "the email went out without the invoice attached",
        )

    def test_a_student_with_no_address_is_invoiced_and_nothing_is_sent(self):
        order = self._sync(
            self.without_email, [(self.meal_600, 1, 0.0, 0.0), (self.drink, 1, 100.0, 0.0)], "credit-invoice-0004"
        )
        self.assertEqual(order.account_move.state, "posted")
        self.assertFalse(self._invoice_mails(order.account_move, self.without_email))

    def test_a_meal_sold_at_its_price_carries_no_credit_line(self):
        order = self._sync(self.with_email, [(self.meal_600, 1, 600.0, 0.0)], "credit-invoice-0005")
        self.assertNotIn("meal credit", order.account_move.invoice_line_ids.name)
        self.assertEqual(order.account_move.amount_total, 600.0)
        self.assertEqual(self.with_email.meal_credits_remaining, 6.0, "a paying customer spent credits")

    def test_a_meal_discounted_to_nothing_says_what_paid_for_it(self):
        """The 100% discount is a credit meal since 19.0.3.6.0; the invoice agrees."""
        order = self._sync(
            self.with_email, [(self.meal_600, 1, 600.0, 100.0), (self.drink, 1, 100.0, 0.0)], "credit-invoice-0006"
        )
        label = order.account_move.invoice_line_ids.filtered(lambda line: line.product_id == self.meal_600).name
        self.assertIn("Paid with 1 meal credit(s)", label)
        self.assertEqual(self.with_email.meal_credits_remaining, 5.0)


@tagged("post_install", "-at_install")
class TestTheCreditMealTill(TestPointOfSaleHttpCommon):
    """Payment on a meal eaten on credits, clicked through the way a cashier does."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Students are hidden from plain users (his_person_core); a till serving
        # meals runs as a meal cashier, or it finds no student to serve.
        cls.pos_user.group_ids |= cls.env.ref("his_meal_management.group_meal_cashier")
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

    def _ticket_mails(self, order):
        return self.env["mail.mail"].search([("model", "=", "pos.order"), ("res_id", "=", order.id)])

    def test_payment_on_a_credit_meal_goes_straight_to_an_emailed_ticket(self):
        """A ticket, not an invoice (loi 04-02, art. 10), and the ticket is emailed."""
        order = self._run("his_meal_credit_payment_email_tour")
        self.assertFalse(order.to_invoice, "a student sale was invoiced without being asked to")
        self.assertFalse(order.account_move)
        self.assertEqual(order.state, "paid")
        self.assertFalse(order.payment_ids, "a meal on credits was recorded as paid by something")
        self.assertEqual(self.with_email.meal_credits_remaining, 5.0)
        mail = self._ticket_mails(order)
        self.assertEqual(mail.recipient_ids, self.with_email)
        self.assertIn("Meal credits left", mail.body_html)

    def test_a_student_with_no_email_gets_the_receipt_and_nothing_is_sent(self):
        order = self._run("his_meal_credit_payment_no_email_tour")
        self.assertFalse(order.account_move)
        self.assertFalse(self._ticket_mails(order))
        self.assertEqual(self.without_email.meal_credits_remaining, 5.0)

    def test_anything_to_pay_keeps_the_payment_screen(self):
        self._run("his_meal_credit_payment_mixed_tour")
