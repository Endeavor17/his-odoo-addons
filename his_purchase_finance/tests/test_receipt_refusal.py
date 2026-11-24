# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .common import HisFinanceCase


@tagged("post_install", "-at_install")
class TestReceiptRefusal(HisFinanceCase):
    """Procedure 6.1 : quantites acceptees, refusees (avec motif) et restantes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storekeeper = new_test_user(cls.env, login="his_storekeeper_ref", groups="stock.group_stock_user")

    def _validate(self, order, accepted, refused=0, reason=False, backorder=False):
        picking = order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
        self.env.invalidate_all()
        picking = picking.with_user(self.storekeeper)
        move = picking.move_ids
        move.write({"quantity": accepted, "his_qty_refused": refused, "his_refusal_reason": reason})
        res = picking.button_validate()
        if isinstance(res, dict) and res.get("res_model") == "stock.backorder.confirmation":
            wizard = self.env[res["res_model"]].with_user(self.storekeeper).with_context(res["context"]).create({})
            wizard.process() if backorder else wizard.process_cancel_backorder()
        return picking

    def test_refused_needs_reason(self):
        order = self._confirmed()
        with self.assertRaises(UserError):
            self._validate(order, 1, refused=1)

    def test_refusal_opens_anomaly(self):
        order = self._confirmed()
        picking = self._validate(order, 1, refused=1, reason="Box crushed")
        anomaly = self.env["his.purchase.anomaly"].sudo().search([("order_id", "=", order.id)])
        self.assertEqual(len(anomaly), 1)
        self.assertEqual(anomaly.kind, "non_compliance")
        self.assertEqual(anomaly.picking_id, picking)
        self.assertEqual(anomaly.declared_by_id, self.storekeeper)
        self.assertIn("Box crushed", anomaly.description)
        self.assertEqual(order.order_line.qty_received, 1)

    def test_no_refusal_no_anomaly(self):
        order = self._confirmed()
        self._validate(order, 2)
        self.assertFalse(self.env["his.purchase.anomaly"].sudo().search([("order_id", "=", order.id)]))

    def test_whole_delivery_refused(self):
        # Revue finale : tout refuser (0 accepte) doit etre possible.
        order = self._confirmed()
        picking = self._validate(order, 0, refused=2, reason="Wrong model delivered")
        self.assertEqual(picking.state, "cancel")
        anomaly = self.env["his.purchase.anomaly"].sudo().search([("order_id", "=", order.id)])
        self.assertEqual(len(anomaly), 1)
        self.assertIn("Wrong model", anomaly.description)
