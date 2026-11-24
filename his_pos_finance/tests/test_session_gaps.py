# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged

from .common import HisPosFinanceCase


@tagged("post_install", "-at_install")
class TestSessionGaps(HisPosFinanceCase):
    def _counted(self, session, counted, notes):
        session.post_closing_cash_details(counted)
        session.update_closing_control_state_session(notes)
        return session.close_session_from_ui()

    def test_close_with_gap_needs_notes(self):
        session = self._open_session(self.cafeteria)
        self._sell_cash(session, 600)
        result = self._counted(session, 590, "")
        self.assertFalse(result["successful"])
        self.assertIn("Explain", result["message"])
        self.assertNotEqual(session.state, "closed")

    def test_close_with_gap_opens_form_on_476(self):
        session = self._open_session(self.cafeteria)
        self._sell_cash(session, 600)
        self.assertTrue(self._counted(session, 590, "Erreur de monnaie")["successful"])
        form = session.his_discrepancy_ids
        self.assertEqual((form.kind, form.amount, form.explanation), ("closing", -10, "Erreur de monnaie"))
        self.assertEqual(form.journal_id.code, "CCAF")
        self.assertIn("476000", form.provisional_move_id.line_ids.account_id.mapped("code"))
        self.assertEqual(self._balance("476000"), 10)

    def test_close_without_gap_opens_nothing(self):
        session = self._open_session(self.cafeteria)
        self._sell_cash(session, 600)
        self.assertTrue(self._counted(session, 600, "")["successful"])
        self.assertFalse(session.his_discrepancy_ids)

    def test_back_end_close_without_notes_still_opens_form(self):
        session = self._open_session(self.cafeteria)
        self._sell_cash(session, 600)
        session.cash_register_balance_end_real = 590
        session.with_user(self.pos_manager).action_pos_session_closing_control()
        self.assertEqual(session.state, "closed")
        self.assertEqual(session.his_discrepancy_ids.amount, -10)
        self.assertFalse(session.his_discrepancy_ids.explanation)

    def test_sub_rounding_gap_ignored(self):
        session = self._open_session(self.cafeteria)
        self._sell_cash(session, 600)
        self.assertTrue(self._counted(session, 600.004, "")["successful"])
        self.assertFalse(session.his_discrepancy_ids)

    def test_opening_gap_posts_once(self):
        first = self._open_session(self.cafeteria)
        self._sell_cash(first, 1000)
        self._counted(first, 1000, "")
        second = self._open_session(self.cafeteria, cashbox=980, notes="Billet manquant")
        self.assertEqual(second.cash_register_balance_start, 1000)
        self.assertEqual(second.cash_register_balance_end, 980)  # attendu = compte, pas 960
        form = second.his_discrepancy_ids
        self.assertEqual((form.kind, form.amount, form.explanation), ("opening", -20, "Billet manquant"))
        self.assertEqual(self._balance("476000"), 20)

    def test_opening_without_gap_opens_nothing(self):
        first = self._open_session(self.cafeteria)
        self._sell_cash(first, 1000)
        self._counted(first, 1000, "")
        second = self._open_session(self.cafeteria, cashbox=1000)
        self.assertFalse(second.his_discrepancy_ids)
        self.assertFalse(second.statement_line_ids)
