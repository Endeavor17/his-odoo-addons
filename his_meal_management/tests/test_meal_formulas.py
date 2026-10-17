"""The caterer's formulas: what they are, and which till sells them.

Pack 300 and Pack 600 are combos the cafeteria serves on credits only; the
restaurant formula is a single product. See the plan of 2026-10-15
(docs/superpowers/plans/2026-10-15-formules-repas.md) for the decisions.
"""

from odoo.tests import TransactionCase, tagged

from ..hooks import lier_categories_pos, taguer_produits


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
