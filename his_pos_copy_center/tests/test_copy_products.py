from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCopyProducts(TransactionCase):
    """Tagging a copy product must not fight the MDM.

    `his_stock_mdm` forbids the Format attribute on the copy categories and
    enforces it with a ValidationError, which is precisely why these dimensions
    are plain fields on the template rather than product attributes. The last
    two tests here guard that decision from both sides: tagging stays legal,
    and the rule that made us choose fields is proven to still bite. If someone
    later "improves" this into attributes, the suite says why they cannot.
    """

    def test_a_copy_product_carries_its_dimensions(self):
        product = self.env["product.template"].create(
            {
                "name": "Photocopie N&B Recto",
                "type": "consu",
                "list_price": 10.0,
                "available_in_pos": True,
                "copy_service": "photocopie",
                "copy_paper": "normal",
                "copy_color": "bw",
                "copy_sides": "recto",
            }
        )
        self.assertEqual(product.copy_service, "photocopie")
        self.assertEqual(product.copy_paper, "normal")
        self.assertEqual(product.copy_color, "bw")
        self.assertEqual(product.copy_sides, "recto")

    def test_an_ordinary_product_is_untouched(self):
        """A product carrying no copy_service is invisible to the builder."""
        product = self.env["product.template"].create({"name": "Stylo"})
        self.assertFalse(product.copy_service)
        self.assertFalse(product.copy_paper)

    def test_tagging_does_not_trip_the_mdm_rule(self):
        """The whole reason these are fields and not attributes.

        Nothing here creates a product.template.attribute.line, so
        his_stock_mdm's rule 6 has nothing to object to.
        """
        product = self.env["product.template"].create(
            {
                "name": "Photocopie Couleur Recto-verso",
                "type": "consu",
                "list_price": 30.0,
                "copy_service": "photocopie",
                "copy_paper": "normal",
                "copy_color": "color",
                "copy_sides": "duplex",
            }
        )
        self.assertTrue(product.id)

    def test_the_dimensions_reach_the_till(self):
        """The silent failure this module is most exposed to.

        `product.product` ships an explicit field whitelist for POS. A field
        left out of it does not raise — it just never arrives in the browser,
        so the builder matches nothing while every product looks perfectly
        configured in the backend. Pin the list.
        """
        config = self.env["pos.config"].create({"name": "Copy Till"})
        fields = self.env["product.product"]._load_pos_data_fields(config)
        for name in ("copy_service", "copy_paper", "copy_color", "copy_sides", "copy_bulk_price"):
            self.assertIn(
                name,
                fields,
                "%s must be loaded into the POS or the job builder is blind to it." % name,
            )
        self.assertNotIn("copy_format", fields)

    def test_bulk_price_is_a_second_stored_price(self):
        """Le prix au-dela de 20 pages est un second prix stocke, pas un calcul."""
        product = self.env["product.template"].create(
            {
                "name": "Impression N&B Recto",
                "type": "service",
                "list_price": 10.0,
                "copy_service": "impression",
                "copy_paper": "normal",
                "copy_color": "bw",
                "copy_sides": "recto",
                "copy_bulk_price": 8.0,
            }
        )
        self.assertEqual(product.copy_bulk_price, 8.0)
        self.assertEqual(product.list_price, 10.0)

    def test_the_mdm_rule_that_forced_this_design_still_bites(self):
        """Pin the constraint this module was shaped around.

        If a future MDM change permits Format on the copy categories, this test
        fails — and that failure is the signal to reconsider whether the four
        fields should become attributes after all. Without it, the reason for
        this design quietly rots into folklore.
        """
        copy_categ = self.env.ref("his_stock_mdm.categ_copy_photocopie", raise_if_not_found=False)
        fmt = self.env.ref("his_stock_mdm.attribute_format", raise_if_not_found=False)
        if not copy_categ or not fmt:
            # This module does not depend on his_stock_mdm and must install
            # without it. The rule is only assertable where it exists.
            self.skipTest("his_stock_mdm is not installed on this database.")
        self.assertNotIn(
            copy_categ,
            fmt.allowed_categ_ids,
            "his_stock_mdm still forbids Format on the copy categories; the "
            "copy dimensions therefore stay plain fields on the product.",
        )

    # --- The Copy Center form group -----------------------------------------

    def test_le_groupe_suit_la_categorie(self):
        photocopie = self.env.ref("his_stock_mdm.categ_copy_photocopie", raise_if_not_found=False)
        if not photocopie:
            self.skipTest("his_stock_mdm is not installed on this database.")
        Template = self.env["product.template"]
        copy = Template.create({"name": "Photocopie groupe", "categ_id": photocopie.id})
        cafe = Template.create(
            {
                "name": "Cafe groupe",
                "categ_id": self.env.ref("his_stock_mdm.categ_cafe_divers").id,
            }
        )
        self.assertTrue(copy.copy_center_visible)
        self.assertFalse(cafe.copy_center_visible)

    def test_un_service_copie_reste_visible(self):
        cafe = self.env.ref("his_stock_mdm.categ_cafe_divers", raise_if_not_found=False)
        vals = {"name": "Impression hors categorie", "copy_service": "impression"}
        if cafe:
            vals["categ_id"] = cafe.id
        self.assertTrue(self.env["product.template"].create(vals).copy_center_visible)

    def test_sans_mdm_tout_reste_visible(self):
        Template = self.env["product.template"]
        vals = {"name": "Sans MDM"}
        cafe = self.env.ref("his_stock_mdm.categ_cafe_divers", raise_if_not_found=False)
        if cafe:
            vals["categ_id"] = cafe.id  # la regle 2 refuse la categorie par defaut
        with patch.object(type(Template), "_copy_center_categories", return_value=[]):
            product = Template.create(vals)
            self.assertTrue(product.copy_center_visible)
