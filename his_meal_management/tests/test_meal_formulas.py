"""The caterer's formulas: what they are, and which till sells them.

Pack 300 and Pack 600 are combos the cafeteria serves on credits only; the
restaurant formula is a single product. See the plan of 2026-10-15
(docs/superpowers/plans/2026-10-15-formules-repas.md) for the decisions.
"""

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..hooks import lier_categories_pos, taguer_produits
from .test_meal_credit_invoice import sync_order
from .test_meal_credits import make_person


@tagged("post_install", "-at_install")
class TestMealFormulasData(TransactionCase):
    def test_formulas_are_eaten_on_credits_only(self):
        """Priced 0 with a credit cost: the server's own definition of a credit meal."""
        for xmlid, kind, cost in (
            ("product_pack_300", "combo", 0.5),
            ("product_pack_600", "combo", 1.0),
            ("product_formule_restaurant", "consu", 1.0),
        ):
            formula = self.env.ref(f"his_meal_management.{xmlid}")
            self.assertEqual(formula.type, kind, xmlid)
            self.assertEqual(formula.list_price, 0.0, f"{xmlid} could be sold for cash")
            self.assertEqual(formula.meal_credit_cost, cost, xmlid)
            self.assertTrue(formula.available_in_pos, xmlid)

    def test_dish_choices_never_reach_the_grid(self):
        """On the grid they would be sold for cash, alone, outside any formula."""
        for xmlid in (
            "product_choix_pizza",
            "product_choix_cheeseburger",
            "product_choix_box_riz",
            "product_choix_box_frites",
        ):
            self.assertFalse(self.env.ref(f"his_meal_management.{xmlid}").available_in_pos, xmlid)

    def test_every_dish_choice_has_a_price(self):
        """The till prorates a combo by its items' prices: all at 0 is 0/0 = NaN."""
        for xmlid in ("combo_plat_300", "combo_plat_600"):
            self.assertGreater(self.env.ref(f"his_meal_management.{xmlid}").base_price, 0, xmlid)

    def test_generic_meals_are_retired(self):
        for xmlid in ("product_meal_300", "product_daily_meal"):
            self.assertFalse(self.env.ref(f"his_meal_management.{xmlid}").active, xmlid)

    def test_each_till_sees_its_own_formulas(self):
        lier_categories_pos(self.env)
        taguer_produits(self.env)
        formules = self.env.ref("his_meal_management.pos_categ_formules")
        repas = self.env.ref("his_meal_management.pos_categ_repas")
        cafeteria = self.env.ref("his_stock_mdm.pos_config_cafeteria")
        restaurant = self.env.ref("his_stock_mdm.pos_config_restaurant")

        self.assertIn(formules, cafeteria.iface_available_categ_ids)
        self.assertNotIn(repas, cafeteria.iface_available_categ_ids)
        self.assertIn(repas, restaurant.iface_available_categ_ids)
        self.assertNotIn(formules, restaurant.iface_available_categ_ids)
        # taguer_produits used to force "Meals" onto every credit meal, which
        # would have put the packs on the Restaurant till.
        for xmlid in ("product_pack_300", "product_pack_600"):
            self.assertEqual(self.env.ref(f"his_meal_management.{xmlid}").pos_categ_ids, formules, xmlid)
        self.assertEqual(self.env.ref("his_meal_management.product_formule_restaurant").pos_categ_ids, repas)


@tagged("post_install", "-at_install")
class TestMealFormulasServer(AccountTestInvoicingCommon):
    """A formula is a combo: the parent costs the credits, the children cost nothing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("point_of_sale.group_pos_manager") | cls.env.ref(
            "his_meal_management.group_meal_officer"
        )
        ref = cls.env.ref
        cls.pack_300 = ref("his_meal_management.product_pack_300").product_variant_id
        cls.pack_600 = ref("his_meal_management.product_pack_600").product_variant_id
        cls.restaurant = ref("his_meal_management.product_formule_restaurant").product_variant_id
        cls.pizza = ref("his_meal_management.product_choix_pizza")
        cls.box_riz = ref("his_meal_management.product_choix_box_riz")
        cls.bottle = cls.env["product.product"].create(
            {"name": "Test Ifri PM", "type": "consu", "is_storable": True, "list_price": 50.0, "available_in_pos": True}
        )
        cls.juice = cls.env["product.product"].create(
            {
                "name": "Test Jus",
                "type": "consu",
                "list_price": 100.0,
                "available_in_pos": True,
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
            {"name": "Formula Cafeteria", "payment_method_ids": [Command.set(cls.cash.ids)]}
        )
        cls.config.open_ui()
        cls.session = cls.config.current_session_id
        cls.plan = ref("his_meal_management.product_plan_weekly").product_variant_id  # 6 credits

    def _student(self, name):
        partner = make_person(self.env, name).partner_id
        partner.sudo()._grant_meal_credits(self.plan)
        return partner

    def _sync(self, partner, lines, uuid):
        return sync_order(self.env, self.session, self.cash, partner, lines, uuid, to_invoice=False)

    def test_pack_600_takes_one_credit_and_its_bottle_leaves_stock(self):
        student = self._student("Formula Amine")
        order = self._sync(
            student,
            [(self.pack_600, 1, 0.0, 0.0), (self.box_riz, 1, 0.0, 0.0), (self.bottle, 1, 0.0, 0.0)],
            "formula-0001",
        )
        self.assertEqual(order.state, "paid")
        self.assertEqual(student.meal_credits_remaining, 5.0, "the dish or the bottle took a credit too")
        ledger = self.env["his.meal.transaction"].search([("pos_order_id", "=", order.id)])
        self.assertEqual(ledger.product_id, self.pack_600)
        self.assertIn(self.bottle, order.picking_ids.move_ids.product_id, "the bottle never left stock")

    def test_pack_300_takes_half_a_credit_and_two_take_two_halves(self):
        student = self._student("Formula Lina")
        self._sync(student, [(self.pack_300, 2, 0.0, 0.0), (self.pizza, 2, 0.0, 0.0)], "formula-0002")
        self.assertEqual(student.meal_credits_remaining, 5.0)

    def test_the_restaurant_formula_takes_one_credit(self):
        student = self._student("Formula Karim")
        self._sync(student, [(self.restaurant, 1, 0.0, 0.0)], "formula-0003")
        self.assertEqual(student.meal_credits_remaining, 5.0)

    def test_a_formula_without_a_student_is_refused(self):
        """D1: no walk-in. A formula at 0 is a credit meal, and a credit meal needs a card."""
        with self.assertRaises(UserError):
            self._sync(False, [(self.pack_600, 1, 0.0, 0.0), (self.box_riz, 1, 0.0, 0.0)], "formula-0004")

    def test_a_formula_without_enough_credits_is_refused(self):
        broke = make_person(self.env, "Formula Sans Pack").partner_id
        with self.assertRaises(UserError):
            self._sync(broke, [(self.pack_600, 1, 0.0, 0.0), (self.box_riz, 1, 0.0, 0.0)], "formula-0005")
        self.assertFalse(self.env["his.meal.transaction"].search([("partner_id", "=", broke.id)]))

    def test_a_formula_next_to_a_paid_juice(self):
        student = self._student("Formula Nour")
        order = self._sync(
            student,
            [(self.pack_600, 1, 0.0, 0.0), (self.box_riz, 1, 0.0, 0.0), (self.juice, 1, 100.0, 0.0)],
            "formula-0006",
        )
        self.assertEqual(student.meal_credits_remaining, 5.0)
        self.assertEqual(sum(order.payment_ids.mapped("amount")), 100.0)

    def test_an_invoiced_formula_does_not_claim_a_value_of_zero(self):
        """A 0 DA formula is worth its credits, not "0,00 DA".

        Invoiced only alongside something paid: a formula alone is not invoiced.
        """
        student = self._student("Formula Facture")
        drink = self.env["product.product"].create({"name": "Formula Drink", "type": "consu", "list_price": 100.0})
        order = sync_order(
            self.env,
            self.session,
            self.cash,
            student,
            [(self.restaurant, 1, 0.0, 0.0), (drink, 1, 100.0, 0.0)],
            "formula-0007",
        )
        label = order.account_move.invoice_line_ids.filtered(lambda l: l.product_id == self.restaurant).name
        self.assertIn("Paid with 1 meal credit(s)", label)
        self.assertNotIn("value", label)


@tagged("post_install", "-at_install")
class TestMealFormulasTill(TestPointOfSaleHttpCommon):
    """A formula clicked through on a real till."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Students are hidden from plain users: the till runs as a meal cashier.
        cls.pos_user.group_ids |= cls.env.ref("his_meal_management.group_meal_cashier")
        plan = cls.env["product.product"].create(
            {"name": "Tour Pack", "type": "service", "list_price": 3000.0, "meal_credits": 6}
        )
        # A combo only takes products for sale, and a stocked product for sale
        # needs a price (his_stock_mdm): the bottle has its cash price, and
        # inside the formula it still costs nothing.
        new = cls.env["product.product"].create
        box_riz = new({"name": "Tour Box Riz", "type": "consu", "list_price": 600.0})
        box_frites = new({"name": "Tour Box Frites", "type": "consu", "list_price": 600.0})
        cls.bottle = new(
            {"name": "Tour Ifri PM", "type": "consu", "is_storable": True, "list_price": 50.0, "available_in_pos": True}
        )
        Combo = cls.env["product.combo"]
        dish = Combo.create(
            {
                "name": "Tour dish",
                "combo_item_ids": [Command.create({"product_id": p.id}) for p in (box_riz, box_frites)],
            }
        )
        drink = Combo.create({"name": "Tour drink", "combo_item_ids": [Command.create({"product_id": cls.bottle.id})]})
        cls.pack = cls.env["product.template"].create(
            {
                "name": "Tour Pack 600",
                "type": "combo",
                "list_price": 0.0,
                "meal_credit_cost": 1.0,
                "combo_ids": [Command.set([dish.id, drink.id])],
                "available_in_pos": True,
                "taxes_id": [Command.clear()],
            }
        )
        cls.student = make_person(cls.env, "AAA Tour Formule").partner_id
        cls.student.sudo()._grant_meal_credits(plan)

    def _run(self, tour):
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour(tour)
        return self.env["pos.order"].search([("config_id", "=", self.main_pos_config.id)], order="id desc", limit=1)

    def test_a_formula_is_served_on_credits_with_its_choices(self):
        order = self._run("his_meal_formula_tour")
        self.assertEqual(order.state, "paid")
        self.assertFalse(order.payment_ids, "a formula on credits was recorded as paid by something")
        self.assertEqual(self.student.meal_credits_remaining, 5.0)
        parent = order.lines.filtered(lambda l: l.product_id.product_tmpl_id == self.pack)
        self.assertEqual(parent.combo_line_ids.product_id.mapped("name"), ["Tour Box Riz", "Tour Ifri PM"])
        self.assertIn(self.bottle, order.picking_ids.move_ids.product_id)

    def test_closing_the_combo_window_serves_nothing(self):
        self._run("his_meal_formula_cancel_tour")
        self.assertEqual(self.student.meal_credits_remaining, 6.0)

    def test_a_walk_in_cannot_take_a_formula(self):
        self._run("his_meal_formula_walkin_tour")
        self.assertEqual(self.student.meal_credits_remaining, 6.0)
