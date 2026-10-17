# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Les documents imprimes disent la meme chose que les donnees (AT-13)."""

from odoo.tests import tagged

from .common import HisPurchaseCase


@tagged("post_install", "-at_install")
class TestReports(HisPurchaseCase):
    def _html(self, xmlid, records):
        html, _format = self.env["ir.actions.report"]._render_qweb_html(xmlid, records.ids)
        return html.decode()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.partner_id.write(
            {"vat": "000916001112223", "his_rc": "16/00-9998887B09", "his_nis": "099916001112223"}
        )

    def test_les_quatre_documents(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.write({"his_quote_ref": "PF-2026-118"})
        order.order_line.price_unit = 9500
        self._alternative(order, self.supplier_b, 9000)

        proforma = self._html("his_purchase.report_proforma_request", order)
        self.assertIn(order.name, proforma)
        self.assertIn(request.name, proforma)
        self.assertIn("16/00-1234567B21", proforma, "RC du fournisseur")
        self.assertIn("16/00-9998887B09", proforma, "RC de l'acheteur")
        self.assertNotIn("9,500", proforma, "aucun prix sur la demande de proforma")
        self.assertNotIn("9 500", proforma)

        choice = self.env["his.purchase.choice"].create(
            {"order_id": order.id, "criterion": "quality", "note": "Original cartridges."}
        )
        action = choice.action_confirm()
        self.env[action["res_model"]].with_context(action["context"]).create({}).action_cancel_alternatives()
        order.with_user(self.director).button_approve()

        sheet = self._html("his_purchase.report_supplier_choice", order)
        self.assertIn("Supplier B", sheet)
        self.assertIn("Original cartridges.", sheet)
        self.assertIn("Leila Director", sheet)

        po = self._html("his_purchase.report_purchase_order", order)
        self.assertIn(order.name, po)
        self.assertIn("000016001234567", po, "NIF du fournisseur")
        self.assertIn(order._his_amount_in_words(), po)

        receipt = self._html("his_purchase.report_goods_receipt", order.picking_ids)
        self.assertIn(order.name, receipt)
        self.assertIn("Toner HP 85A", receipt)
