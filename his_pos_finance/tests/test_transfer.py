# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import HisPosFinanceCase


@tagged("post_install", "-at_install")
class TestTransfer(HisPosFinanceCase):
    def _sent_handover(self, amount):
        session = self._open_session(self.cafeteria)
        self._sell_cash(session, amount)
        return self.env["his.cash.transfer"].browse(session.with_user(self.cashier_user).his_handover(amount, ""))

    def _backend_transfer(self, source, target, amount):
        transfer = (
            self.env["his.cash.transfer"]
            .with_user(self.finance)
            .create(
                {
                    "from_journal_id": self._journal(source).id,
                    "to_journal_id": self._journal(target).id,
                    "amount_sent": amount,
                }
            )
        )
        transfer.action_send()
        return transfer

    def test_handover_from_till(self):
        session = self._open_session(self.cafeteria)
        self._sell_cash(session, 6000)
        transfer = self.env["his.cash.transfer"].browse(session.with_user(self.cashier_user).his_handover(4000, ""))
        session.invalidate_recordset()
        self.assertEqual(
            (transfer.state, transfer.to_journal_id.code, transfer.from_journal_id.code), ("sent", "CFIN", "CCAF")
        )
        self.assertEqual(transfer.sent_by, self.cashier_user)
        self.assertEqual(session.cash_register_balance_end, 2000)
        transfer.with_user(self.finance).action_receive(4000)
        self.assertEqual(transfer.state, "received")
        self.assertEqual(transfer.received_by, self.finance)
        self.assertEqual(self._balance("581000"), 0)
        self.assertEqual(self._balance("530001"), 4000)
        self.assertFalse(transfer.his_discrepancy_ids)

    def test_receive_less_opens_handover_form(self):
        transfer = self._sent_handover(4000)
        transfer.with_user(self.finance).action_receive(3950)
        form = transfer.his_discrepancy_ids
        self.assertEqual((form.kind, form.amount, form.journal_id.code), ("handover", -50, "CFIN"))
        self.assertEqual(self._balance("581000"), 0)
        self.assertEqual(self._balance("476000"), 50)

    def test_invalid_handover_amount(self):
        session = self._open_session(self.cafeteria)
        self._sell_cash(session, 1000)
        for bad in (0, -5, 1000.01):
            with self.assertRaises(UserError):
                session.with_user(self.cashier_user).his_handover(bad, "")
        self.assertFalse(self.env["his.cash.transfer"].search([]))
        self.assertFalse(session.statement_line_ids)

    def test_injection_received_at_till(self):
        session = self._open_session(self.cafeteria)
        transfer = self._backend_transfer("CFIN", "CCAF", 2000)
        pending = session.with_user(self.cashier_user).his_pending_transfers()
        self.assertEqual([p["id"] for p in pending], transfer.ids)
        session.with_user(self.cashier_user).his_receive_transfer(transfer.id, 2000)
        session.invalidate_recordset()
        self.assertEqual(session.cash_register_balance_end, 2000)
        self.assertEqual(transfer.state, "received")
        self.assertEqual(self._balance("581000"), 0)

    def test_receive_at_till_needs_open_session(self):
        transfer = self._backend_transfer("CFIN", "CCAF", 2000)
        with self.assertRaises(UserError):
            transfer.with_user(self.finance).action_receive(2000)

    def test_only_finance_receives_handover(self):
        transfer = self._sent_handover(100)
        with self.assertRaises(AccessError):
            transfer.with_user(self.pos_manager).action_receive(100)

    def test_direction_box_receives_by_director(self):
        transfer = self._backend_transfer("CFIN", "CDIR", 500)
        with self.assertRaises(AccessError):
            transfer.with_user(self.finance).action_receive(500)
        transfer.with_user(self.director).action_receive(500)
        self.assertEqual(self._balance("530000"), 500)

    def test_receive_twice_refused(self):
        transfer = self._sent_handover(100)
        transfer.with_user(self.finance).action_receive(100)
        with self.assertRaises(UserError):
            transfer.with_user(self.finance).action_receive(100)

    def test_slip_renders(self):
        transfer = self._sent_handover(100)
        html, _type = self.env["ir.actions.report"]._render_qweb_html(
            "his_pos_finance.action_report_cash_transfer", transfer.ids
        )
        self.assertIn(transfer.name.encode(), html)
        self.assertTrue(transfer.name.startswith("VERS/"))

    def test_handover_proposal_keeps_the_float(self):
        self.cafeteria.his_float_amount = 500
        session = self._open_session(self.cafeteria)
        self.assertEqual(session.his_handover_proposal(), 0)
        self._sell_cash(session, 2000)
        session.invalidate_recordset()
        self.assertEqual(session.his_handover_proposal(), 1500)

    def test_closed_without_handover_filter(self):
        Session = self.env["pos.session"]
        sans = self._open_session(self.cafeteria)
        self._sell_cash(sans, 100)
        sans.post_closing_cash_details(100)
        sans.update_closing_control_state_session("")
        sans.close_session_from_ui()
        avec = self._open_session(self.cafeteria)
        self._sell_cash(avec, 100)
        avec.his_handover(100, "")
        avec.post_closing_cash_details(0)
        avec.update_closing_control_state_session("")
        avec.close_session_from_ui()
        found = Session.search([("his_no_handover", "=", True)])
        self.assertIn(sans, found)
        self.assertNotIn(avec, found)
        self.assertTrue(sans.his_no_handover)
        self.assertFalse(avec.his_no_handover)
