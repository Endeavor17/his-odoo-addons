from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPaperConsumption(TestPoSCommon):
    """Une copie vendue sort son papier du stock du comptoir.

    Le papier part vers « Consommation Copy Center », pas vers Customers : il
    a ete imprime, pas vendu. Seule une rame vendue telle quelle (produit sans
    copy_service) part vers le client. Un remboursement ne rend jamais le
    papier : les feuilles ont ete imprimees.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        # Sous his_stock_mdm une categorie terminale est obligatoire ; sans lui
        # n'importe quelle categorie convient.
        cls.categ_service = ref("his_stock_mdm.categ_copy_impression", raise_if_not_found=False) or cls.categ_basic
        cls.categ_paper = ref("his_stock_mdm.categ_copy_bureautique", raise_if_not_found=False) or cls.categ_basic

        cls.paper = cls.env["product.product"].create(
            {
                "name": "Papier A4 80g (test)",
                "is_storable": True,
                "categ_id": cls.categ_paper.id,
                "sale_ok": False,
                "list_price": 0.0,
            }
        )
        cls.print_duplex = cls._copy_product("Impression N&B Recto-verso (test)", "duplex", 15.0)
        cls.print_recto = cls._copy_product("Impression N&B Recto (test)", "recto", 10.0)
        cls.ream = cls.env["product.product"].create(
            {
                "name": "Rame Papier A4 500 feuilles (test)",
                "type": "service",
                "categ_id": cls.categ_paper.id,
                "lst_price": 650.0,
                "available_in_pos": True,
                "sale_ok": True,
                "taxes_id": [(5, 0, 0)],
                "copy_paper_product_id": cls.paper.id,
                "copy_sheets_per_unit": 500.0,
            }
        )
        cls.config = cls.basic_config
        cls.source = cls.config.picking_type_id.default_location_src_id
        cls.consumption = cls.env["stock.location"]._his_copy_consumption_location(cls.config.company_id)

    @classmethod
    def _copy_product(cls, name, sides, price, paper=True):
        return cls.env["product.product"].create(
            {
                "name": name,
                "type": "service",
                "categ_id": cls.categ_service.id,
                "lst_price": price,
                "available_in_pos": True,
                "sale_ok": True,
                "taxes_id": [(5, 0, 0)],
                "copy_service": "impression",
                "copy_paper": "normal",
                "copy_color": "bw",
                "copy_sides": sides,
                "copy_paper_product_id": cls.paper.id if paper else False,
            }
        )

    def _stock(self, qty):
        if qty:
            self.env["stock.quant"]._update_available_quantity(self.paper, self.source, qty)

    def _on_hand(self):
        return self.paper.with_context(location=self.source.id).qty_available

    def _consumed(self):
        lines = self.env["stock.move.line"].search(
            [
                ("product_id", "=", self.paper.id),
                ("location_dest_id", "=", self.consumption.id),
                ("state", "=", "done"),
            ]
        )
        return sum(lines.mapped("quantity"))

    def _sell(self, lines):
        orders = self._create_orders([{"pos_order_lines_ui_args": lines}])
        return next(iter(orders.values()))

    def test_copy_sale_moves_sheets_to_consumption(self):
        self._stock(1000)
        self.open_new_session()
        order = self._sell([(self.print_duplex, 25)])
        self.assertEqual(self._on_hand(), 975)
        self.assertEqual(self._consumed(), 25)
        paper_moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.paper)
        self.assertEqual(paper_moves.location_dest_id, self.consumption)

    def test_two_lines_same_paper_one_move(self):
        self._stock(1000)
        self.open_new_session()
        order = self._sell([(self.print_duplex, 10), (self.print_recto, 5)])
        paper_moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.paper)
        self.assertEqual(len(paper_moves), 1)
        self.assertEqual(paper_moves.product_uom_qty, 15)

    def test_ream_sale_goes_to_customer(self):
        self._stock(1000)
        self.open_new_session()
        order = self._sell([(self.ream, 1)])
        self.assertEqual(self._on_hand(), 500)
        self.assertEqual(self._consumed(), 0)
        paper_moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.paper)
        self.assertEqual(paper_moves.location_dest_id.usage, "customer")

    def test_refund_returns_no_paper(self):
        self._stock(1000)
        self.open_new_session()
        self._sell([(self.print_recto, 10)])
        self._sell([(self.print_recto, -10)])
        self.assertEqual(self._on_hand(), 990)

    def test_paper_moves_at_session_closing(self):
        self._stock(1000)
        self.config.company_id.point_of_sale_update_stock_quantities = "closing"
        session = self.open_new_session()
        self._sell([(self.print_recto, 4)])
        self._sell([(self.print_duplex, 6)])
        self.assertEqual(self._on_hand(), 1000, "Nothing moves before closing.")
        session.post_closing_cash_details(sum(session.order_ids.mapped("amount_total")))
        session.close_session_from_ui()
        self.assertEqual(self._on_hand(), 990)
        self.assertEqual(self._consumed(), 10)

    def test_sale_without_paper_stock_goes_negative(self):
        self.open_new_session()
        order = self._sell([(self.print_recto, 3)])
        self.assertEqual(order.state, "paid")
        self.assertEqual(self._on_hand(), -3)

    def test_one_consumption_location_per_company(self):
        """La societe du test (pas la societe 1) a le sien, et un seul."""
        again = self.env["stock.location"]._his_copy_consumption_location(self.config.company_id)
        self.assertEqual(again, self.consumption)
        self.assertEqual(self.consumption.company_id, self.config.company_id)
        main = self.env.ref("his_pos_copy_center.loc_consommation_copy_center").sudo()
        self.assertTrue(main.his_copy_consumption)

    def test_ream_receipt_counts_500_sheets(self):
        """Achete a la rame, compte a la feuille."""
        ream = self.env.ref("his_pos_copy_center.uom_rame_500")
        supplier = self.env.ref("stock.stock_location_suppliers")
        move = self.env["stock.move"].create(
            {
                "product_id": self.paper.id,
                "product_uom": ream.id,
                "product_uom_qty": 2,
                "location_id": supplier.id,
                "location_dest_id": self.source.id,
            }
        )
        move._action_confirm()
        move.quantity = 2
        move.picked = True
        move._action_done()
        self.assertEqual(self._on_hand(), 1000)

    def test_product_without_paper_moves_nothing(self):
        bare = self._copy_product("Impression sans papier (test)", "recto", 10.0, paper=False)
        self._stock(1000)
        self.open_new_session()
        order = self._sell([(bare, 7)])
        self.assertFalse(order.picking_ids)
        self.assertEqual(self._on_hand(), 1000)
