from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .copy_grid import COPY_GRID, copy_product_vals


@tagged("post_install", "-at_install")
class TestCopyJobTour(TestPointOfSaleHttpCommon):
    """Copies & Prints, driven the way a cashier drives it, on the real grid."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Un catalogue deterministe : on efface toute copie existante (demo ou
        # reelle), puis on cree exactement la grille de tests/copy_grid.py.
        cls.env["product.template"].search([("copy_service", "!=", False)]).write({"copy_service": False})
        categ = cls.env.ref("his_stock_mdm.categ_copy_impression", raise_if_not_found=False)
        cls.copies = cls.env["product.template"]
        for row in COPY_GRID:
            vals = {**copy_product_vals(row), "taxes_id": [(5, 0, 0)]}
            if categ:
                vals["categ_id"] = categ.id
            cls.copies |= cls.env["product.template"].create(vals)

    def _start(self, tour):
        self.main_pos_config.write({"his_pos_theme": "copy_center"})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour(tour)

    def test_copy_job_adds_one_line(self):
        """Paper, colour, sides and a quantity become one ordinary order line."""
        self._start("his_copy_job_tour")

    def test_copy_job_refuses_a_combination_nobody_configured(self):
        """A catalogue gap is a disabled choice, and nothing is sold."""
        self.copies.filtered(lambda p: p.name == "Photocopie N&B Recto-verso").action_archive()
        self._start("his_copy_job_missing_tour")

    def test_bulk_price_follows_the_whole_order(self):
        """Over 20 B&W print pages, every B&W print page at the lower price."""
        self._start("his_copy_bulk_tour")

    def test_bulk_price_duplex_and_photocopies(self):
        """11 double-sided sheets are 22 pages; photocopies never drop."""
        self._start("his_copy_bulk_duplex_tour")
