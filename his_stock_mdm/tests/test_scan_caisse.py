# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un code-barres ne met pas un article en vente (recette du 2026-11-08).

Scanne en caisse, un article importe (sale_ok=False, prix 0) passait a 0 DA, et
sa vente sortait du stock.
"""

from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestScanCaisse(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.caisse = cls.env.ref("his_stock_mdm.pos_config_cafeteria")
        cls.categorie_caisse = cls.env["pos.category"].create({"name": "Scan categorie caisse"})
        cls.categorie_autre = cls.env["pos.category"].create({"name": "Scan autre categorie"})
        cls.caisse.write({"limit_categories": True, "iface_available_categ_ids": [(6, 0, cls.categorie_caisse.ids)]})
        if not cls.caisse.current_session_id:
            cls.env["pos.session"].create({"config_id": cls.caisse.id, "user_id": cls.env.uid})
        cls.comptoir = new_test_user(
            cls.env,
            login="zz_comptoir_scan",
            groups="base.group_user,point_of_sale.group_pos_user,his_stock_mdm.group_caisse_cafeteria",
        )

    def _article(self, barcode, **vals):
        return self.env["product.template"].create(
            {
                "name": f"Article {barcode}",
                "barcode": barcode,
                "type": "consu",
                "is_storable": True,
                "list_price": 50,
                "sale_ok": True,
                "available_in_pos": True,
                "pos_categ_ids": [(6, 0, self.categorie_caisse.ids)],
                **vals,
            }
        )

    def _scan(self, article, **context):
        # Le domaine exact de product_screen.js pour un code inconnu de la caisse.
        templates = self.env["product.template"].with_user(self.comptoir).with_context(**context)
        data = templates.load_product_from_pos(
            self.caisse.id, [("product_variant_ids.barcode", "in", [article.barcode])]
        )
        return [t["id"] for t in data["product.template"]]

    def test_article_en_vente_se_scanne(self):
        article = self._article("9990000000011")
        self.assertEqual(self._scan(article), article.ids)

    def test_article_decoche_ventes_refuse(self):
        article = self._article("9990000000012", sale_ok=False, list_price=0)
        self.assertEqual(self._scan(article), [])

    def test_article_hors_caisse_refuse(self):
        article = self._article("9990000000013", available_in_pos=False)
        self.assertEqual(self._scan(article), [])

    def test_article_d_une_autre_caisse_refuse(self):
        article = self._article("9990000000014", pos_categ_ids=[(6, 0, self.categorie_autre.ids)])
        self.assertEqual(self._scan(article), [])

    def test_ticket_passe_recharge_ses_articles(self):
        # data_service.js : un ticket deja vendu doit se rouvrir meme si son
        # article n'est plus en vente depuis.
        article = self._article("9990000000015", sale_ok=False, list_price=0)
        self.assertEqual(self._scan(article, load_archived=True), article.ids)

    def test_la_caisse_lit_sale_ok(self):
        # La grille et le scan le lisent pour ce qui est deja charge.
        article = self._article("9990000000016", sale_ok=False, list_price=0)
        data = self.env["product.template"]._load_pos_data_read(article, self.caisse)
        self.assertIs(data[0]["sale_ok"], False)
