"""Le menu du traiteur arrive dans les deux caisses de restauration, au prix du menu."""

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


@tagged("post_install", "-at_install")
class TestMenu(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plats = cls.env["product.template"].browse([cls.env.ref(f"his_pos_menu.dish_{x}").id for x in MENU])

    def test_prix_du_menu(self):
        for xmlid, prix in MENU.items():
            plat = self.env.ref(f"his_pos_menu.dish_{xmlid}")
            self.assertEqual(plat.list_price, prix, plat.name)

    def test_un_plat_ne_se_stocke_pas(self):
        self.assertEqual(set(self.plats.mapped("type")), {"consu"})
        self.assertFalse(any(self.plats.mapped("is_storable")))

    def test_cafeteria_et_restaurant_chargent_tout_le_menu(self):
        """Une caisse a perimetre ne charge que ses onglets : chaque plat doit y arriver."""
        Template = self.env["product.template"]
        for xmlid in ("his_stock_mdm.pos_config_cafeteria", "his_stock_mdm.pos_config_restaurant"):
            config = self.env.ref(xmlid)
            charges = Template.search(Template._load_pos_data_domain({}, config))
            self.assertFalse(self.plats - charges, f"{config.name} ne charge pas tout le menu")

    def test_le_copy_center_ne_vend_rien_de_comestible(self):
        config = self.env.ref("his_stock_mdm.pos_config_copy_center")
        Template = self.env["product.template"]
        self.assertFalse(self.plats & Template.search(Template._load_pos_data_domain({}, config)))

    def test_seule_une_taxe_comprise_est_posee(self):
        """Une taxe hors taxe ferait payer plus que le prix du menu : on n'en pose pas."""
        Tax = self.env["account.tax"]
        exclue = Tax.create(
            {"name": "HT 19", "amount": 19.0, "type_tax_use": "sale", "price_include_override": "tax_excluded"}
        )
        comprise = Tax.create(
            {"name": "TTC 9", "amount": 9.0, "type_tax_use": "sale", "price_include_override": "tax_included"}
        )
        self.plats.write({"taxes_id": [Command.clear()]})

        self.env.company.account_sale_tax_id = exclue
        taxer_plats(self.env)
        self.assertFalse(self.plats.taxes_id)

        self.env.company.account_sale_tax_id = comprise
        taxer_plats(self.env)
        self.assertEqual(self.plats.taxes_id, comprise)
        self.assertAlmostEqual(comprise.compute_all(300.0)["total_included"], 300.0)
