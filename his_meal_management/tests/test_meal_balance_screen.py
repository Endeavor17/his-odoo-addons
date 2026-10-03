from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from .test_meal_credits import card_uid, make_person


@tagged("post_install", "-at_install")
class TestMealBalanceScreen(TransactionCase):
    """The desk's balance screen: a card or a name finds the student, and the
    figures shown add up."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.person = make_person(cls.env, "Balance Screen Student")
        cls.student = cls.person.partner_id
        cls.env["his.meal.card"].create({"partner_id": cls.student.id, "code": card_uid(71)})
        cls.plan = cls.env["product.product"].create(
            {
                "name": "Balance Screen Plan",
                "type": "service",
                "list_price": 6000.0,
                "meal_credits": 12,
                "meal_validity_days": 30,
            }
        )
        cls.desk = cls.env["res.users"].create(
            {
                "name": "Meal Desk",
                "login": "his_meal_balance_desk",
                "group_ids": [(6, 0, [cls.env.ref("his_meal_management.group_meal_cashier").id])],
            }
        )

    def test_a_card_a_name_or_a_matricule_finds_the_student(self):
        Partner = self.env["res.partner"].with_user(self.desk)
        # A contact with no his.person holds no wallet, so it is never offered.
        self.env["res.partner"].create({"name": "Balance Screen Visitor"})
        for query in (card_uid(71), "balance screen", self.person.matricule_affiche):
            found = Partner.search_meal_holders(query)
            self.assertEqual([holder["id"] for holder in found], [self.student.id], query)
        self.assertEqual(found[0]["matricule"], self.person.matricule_affiche)
        self.assertEqual(Partner.search_meal_holders("  "), [])

    def test_used_and_left_add_up_to_the_plan(self):
        self.student._grant_meal_credits(self.plan)
        self.student._consume_meal_credit(1.5)
        balance = self.student.with_user(self.desk).get_meal_balance()
        self.assertEqual(
            (balance["credits_total"], balance["credits_used"], balance["credits"]),
            (12, 1.5, 10.5),
        )

    def test_nobody_else_can_search(self):
        outsider = self.env["res.users"].create(
            {
                "name": "Not the Meal Desk",
                "login": "his_meal_balance_outsider",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            self.env["res.partner"].with_user(outsider).search_meal_holders("Balance Screen")
