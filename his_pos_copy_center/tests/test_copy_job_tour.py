from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged('post_install', '-at_install')
class TestCopyJobTour(TestPointOfSaleHttpCommon):
    """The builder, driven the way a cashier drives it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Make the catalogue deterministic before adding to it. Demo data and
        # a real catalogue both put copy products in the database, and either
        # would decide for us whether the "missing combination" path can even
        # be reached. Clear the field on everything, then create exactly the
        # four A4 products these tours reason about — so A3 is guaranteed
        # absent, and the refusal path is a fact rather than a hope.
        cls.env['product.template'].search(
            [('copy_service', '!=', False)]
        ).write({'copy_service': False})

        def copy_product(name, color, price):
            return cls.env['product.template'].create({
                'name': name,
                'type': 'consu',
                'list_price': price,
                'available_in_pos': True,
                'sale_ok': True,
                'taxes_id': [(5, 0, 0)],
                'copy_service': 'photocopie',
                'copy_format': 'a4',
                'copy_color': color,
                'copy_sides': 'recto',
            })

        copy_product("Photocopie A4 N&B Recto", 'bw', 10.0)
        copy_product("Photocopie A4 Couleur Recto", 'color', 40.0)

    def test_copy_job_adds_one_line(self):
        """Four chips and a quantity become one ordinary order line."""
        self.main_pos_config.write({'his_pos_theme': 'copy_center'})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("his_copy_job_tour")

    def test_copy_job_refuses_a_combination_nobody_configured(self):
        """A catalogue gap is reported as a catalogue gap, and nothing is sold."""
        self.main_pos_config.write({'his_pos_theme': 'copy_center'})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("his_copy_job_missing_tour")
