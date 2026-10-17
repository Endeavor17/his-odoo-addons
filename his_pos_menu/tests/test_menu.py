"""Les menus cash : celui du traiteur au Restaurant, celui de la Cafeteria a la Cafeteria."""

from odoo import Command
from odoo.tests import TransactionCase, tagged

from ..hooks import taxer_plats

# Le PDF du 2026-10-14, ligne a ligne : xmlid -> prix TTC.
MENU = {
    "vegetarian_salad": 100,
    "pasta_rice_salad": 200,
    "caesar_salad": 250,
    "vegetable_soup": 100,
    "chorba_hrira": 250,
    "lentil_soup": 150,
    "poutine": 600,
    "creamy_chicken": 300,
    "chicken_escalope": 300,
    "crispy_chicken": 300,
    "chicken_leg": 300,
    "chicken_balls": 350,
    "chicken_tenders_box": 500,
    "merguez": 350,
    "mchermel_steak": 550,
    "liver_kebda": 400,
    "rice_bulgur": 200,
    "french_fries": 150,
    "mashed_potatoes": 200,
    "pasta": 200,
    "sauteed_vegetables": 250,
    "tagliatelle": 300,
    "gratin": 300,
}

# La feuille « MENU CAFETERIA » (2026-10-17), sans les Pockets non chiffrees.
CAFETERIA = {
    "pizza_plain": 300,
    "pizza_three_cheese": 350,
    "pizza_meat": 350,
    "pizza_chicken": 350,
    "pizza_marina": 350,
    "pizza_vegetarian": 350,
    "pizza_turquoise": 400,
    "pizza_chef": 600,
    "pizza_mega_four_seasons": 1200,
    "pizza_mini_mega": 900,
    "burger_classic_cheese": 250,
    "burger_beef_cheese": 300,
    "burger_big_chicken_cheese": 300,
    "burger_big_beef_cheese": 450,
    "burger_forest": 400,
    "burger_crispy": 250,
    "sandwich_brioche_chicken": 350,
    "sandwich_brioche_meat": 400,
    "sandwich_brioche_kebda": 350,
    "sandwich_house_chicken": 300,
    "sandwich_house_meat": 300,
    "sandwich_house_kebda": 350,
    "sandwich_baker_chicken": 350,
    "sandwich_baker_meat": 350,
    "sandwich_baker_kebda": 400,
    "sandwich_baker_crispy": 400,
    "souffle_chicken": 80,
    "souffle_tuna": 80,
    "fajita": 150,
    "hot_dog": 200,
    "panini_chicken": 200,
    "panini_tuna": 200,
    "panini_three_cheese": 200,
    "box_fries": 500,
    "box_rice": 600,
    "box_fries_crispy": 550,
    "box_rice_crispy": 650,
    "extra_gruyere": 100,
    "extra_cheddar": 100,
    "extra_camembert": 100,
    "extra_slices": 50,
    "extra_fries": 50,
    "extra_large_fries": 100,
}


@tagged("post_install", "-at_install")
class TestMenu(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plats = cls.env["product.template"].browse([cls.env.ref(f"his_pos_menu.dish_{x}").id for x in MENU])
        cls.cafe = cls.env["product.template"].browse([cls.env.ref(f"his_pos_menu.cafe_{x}").id for x in CAFETERIA])

    def test_prix_du_menu(self):
        for xmlid, prix in MENU.items():
            plat = self.env.ref(f"his_pos_menu.dish_{xmlid}")
            self.assertEqual(plat.list_price, prix, plat.name)

    def test_un_plat_ne_se_stocke_pas(self):
        self.assertEqual(set(self.plats.mapped("type")), {"consu"})
        self.assertFalse(any(self.plats.mapped("is_storable")))

    def test_prix_de_la_cafeteria(self):
        for xmlid, prix in CAFETERIA.items():
            article = self.env.ref(f"his_pos_menu.cafe_{xmlid}")
            self.assertEqual(article.list_price, prix, article.name)
            self.assertFalse(article.is_storable, article.name)

    def _charges(self, xmlid):
        Template = self.env["product.template"]
        return Template.search(Template._load_pos_data_domain({}, self.env.ref(xmlid)))

    def test_chaque_caisse_a_son_menu(self):
        """Une caisse a perimetre ne charge que ses onglets : chaque menu arrive a la sienne, seulement."""
        restaurant = self._charges("his_stock_mdm.pos_config_restaurant")
        cafeteria = self._charges("his_stock_mdm.pos_config_cafeteria")
        self.assertFalse(self.plats - restaurant, "le Restaurant ne charge pas tout le menu du traiteur")
        self.assertFalse(self.cafe - cafeteria, "la Cafeteria ne charge pas tout son menu")
        self.assertFalse(self.plats & cafeteria, "le menu du traiteur est encore a la Cafeteria")
        self.assertFalse(self.cafe & restaurant, "le menu de la Cafeteria est au Restaurant")

    def test_le_copy_center_ne_vend_rien_de_comestible(self):
        config = self.env.ref("his_stock_mdm.pos_config_copy_center")
        Template = self.env["product.template"]
        self.assertFalse((self.plats | self.cafe) & Template.search(Template._load_pos_data_domain({}, config)))

    def test_seule_une_taxe_comprise_est_posee(self):
        """Une taxe hors taxe ferait payer plus que le prix du menu : on n'en pose pas."""
        Tax = self.env["account.tax"]
        exclue = Tax.create(
            {"name": "HT 19", "amount": 19.0, "type_tax_use": "sale", "price_include_override": "tax_excluded"}
        )
        comprise = Tax.create(
            {"name": "TTC 9", "amount": 9.0, "type_tax_use": "sale", "price_include_override": "tax_included"}
        )
        tout = self.plats | self.cafe
        tout.write({"taxes_id": [Command.clear()]})

        self.env.company.account_sale_tax_id = exclue
        taxer_plats(self.env)
        self.assertFalse(tout.taxes_id)

        self.env.company.account_sale_tax_id = comprise
        taxer_plats(self.env)
        self.assertEqual(tout.taxes_id, comprise)
        self.assertAlmostEqual(comprise.compute_all(300.0)["total_included"], 300.0)
