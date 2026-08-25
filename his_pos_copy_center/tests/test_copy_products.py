from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
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
        product = self.env['product.template'].create({
            'name': "Photocopie A4 N&B Recto",
            'type': 'consu',
            'list_price': 10.0,
            'available_in_pos': True,
            'copy_service': 'photocopie',
            'copy_format': 'a4',
            'copy_color': 'bw',
            'copy_sides': 'recto',
        })
        self.assertEqual(product.copy_service, 'photocopie')
        self.assertEqual(product.copy_format, 'a4')
        self.assertEqual(product.copy_color, 'bw')
        self.assertEqual(product.copy_sides, 'recto')

    def test_an_ordinary_product_is_untouched(self):
        """A product carrying no copy_service is invisible to the builder."""
        product = self.env['product.template'].create({'name': "Stylo"})
        self.assertFalse(product.copy_service)
        self.assertFalse(product.copy_format)

    def test_tagging_does_not_trip_the_mdm_rule(self):
        """The whole reason these are fields and not attributes.

        Nothing here creates a product.template.attribute.line, so
        his_stock_mdm's rule 6 has nothing to object to.
        """
        product = self.env['product.template'].create({
            'name': "Photocopie A3 Couleur Recto-verso",
            'type': 'consu',
            'list_price': 30.0,
            'copy_service': 'photocopie',
            'copy_format': 'a3',
            'copy_color': 'color',
            'copy_sides': 'duplex',
        })
        self.assertTrue(product.id)

    def test_the_dimensions_reach_the_till(self):
        """The silent failure this module is most exposed to.

        `product.product` ships an explicit field whitelist for POS. A field
        left out of it does not raise — it just never arrives in the browser,
        so the builder matches nothing while every product looks perfectly
        configured in the backend. Pin the list.
        """
        config = self.env['pos.config'].create({'name': "Copy Till"})
        fields = self.env['product.product']._load_pos_data_fields(config)
        for name in ('copy_service', 'copy_format', 'copy_color', 'copy_sides'):
            self.assertIn(
                name, fields,
                "%s must be loaded into the POS or the job builder is blind to it." % name,
            )

    def test_the_mdm_rule_that_forced_this_design_still_bites(self):
        """Pin the constraint this module was shaped around.

        If a future MDM change permits Format on the copy categories, this test
        fails — and that failure is the signal to reconsider whether the four
        fields should become attributes after all. Without it, the reason for
        this design quietly rots into folklore.
        """
        copy_categ = self.env.ref(
            'his_stock_mdm.categ_copy_photocopie', raise_if_not_found=False)
        fmt = self.env.ref(
            'his_stock_mdm.attribute_format', raise_if_not_found=False)
        if not copy_categ or not fmt:
            # This module does not depend on his_stock_mdm and must install
            # without it. The rule is only assertable where it exists.
            self.skipTest("his_stock_mdm is not installed on this database.")
        self.assertNotIn(
            copy_categ, fmt.allowed_categ_ids,
            "his_stock_mdm still forbids Format on the copy categories; the "
            "copy dimensions therefore stay plain fields on the product.",
        )
