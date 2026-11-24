# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import HisPosFinanceCase


@tagged("post_install", "-at_install")
class TestDiscrepancy(HisPosFinanceCase):
    def _form(self, amount, journal="CCAF", explanation="", manager_note=""):
        """Un ecart deja passe en 476 a titre provisoire, comme le ferait la cloture."""
        box = self._journal(journal)
        move = self.env["account.move"].create(
            {
                "journal_id": box.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {"account_id": box.default_account_id.id, "debit": max(amount, 0), "credit": max(-amount, 0)},
                    ),
                    (
                        0,
                        0,
                        {"account_id": self._account("476000").id, "debit": max(-amount, 0), "credit": max(amount, 0)},
                    ),
                ],
            }
        )
        move.action_post()
        form = self.env["his.cash.discrepancy"].his_open(
            "closing", box, expected=1000.0, counted=1000.0 + amount, provisional_move=move, explanation=explanation
        )
        if form and manager_note:
            form.manager_note = manager_note
        return form

    def _sent(self, amount, journal="CCAF"):
        form = self._form(amount, journal, explanation="Monnaie rendue", manager_note="Verifie")
        reviewer = {"CCAF": self.pos_manager, "CFIN": self.director, "CDIR": self.finance_head}[journal]
        form.with_user(reviewer).action_send_to_finance()
        return form

    def test_tier_and_nature(self):
        for amount, tier in ((-3, "minor"), (-5, "minor"), (-6, "significant"), (2500, "important"), (-5001, "major")):
            form = self._form(amount)
            self.assertEqual(form.tier, tier, amount)
            self.assertEqual(form.nature, "surplus" if amount > 0 else "shortage")
            self.assertEqual(form.amount, amount)
            self.assertEqual(form.state, "to_review")
            self.assertTrue(form.name.startswith("ECART/"))

    def test_no_form_without_gap(self):
        self.assertFalse(self._form(0.004))

    def test_reviewer_per_box(self):
        self.assertEqual(self._form(-10, journal="CCAF")._his_reviewer_group(), "point_of_sale.group_pos_manager")
        self.assertEqual(self._form(-10, journal="CFIN")._his_reviewer_group(), "his_purchase.group_purchase_director")
        self.assertEqual(self._form(-10, journal="CDIR")._his_reviewer_group(), "his_pos_finance.group_finance_head")

    def test_cashier_cannot_send(self):
        form = self._form(-10, explanation="x", manager_note="y")
        with self.assertRaises(AccessError):
            form.with_user(self.cashier_user).action_send_to_finance()

    def test_send_needs_explanation_and_review(self):
        form = self._form(-10)
        with self.assertRaises(UserError):
            form.with_user(self.pos_manager).action_send_to_finance()

    def test_reviewer_cannot_change_amounts(self):
        form = self._form(-10)
        with self.assertRaises(AccessError):
            form.with_user(self.pos_manager).write({"counted": 1000.0})
        form.with_user(self.pos_manager).write({"manager_note": "Ventes verifiees"})

    def test_accept_loss_posts_and_reconciles(self):
        form = self._sent(-100)
        form.with_user(self.finance).action_decide("accepted")
        self.assertEqual(form.state, "closed")
        self.assertTrue(form.closed_date)
        lines = form.regularisation_move_id.line_ids
        self.assertEqual(lines.filtered(lambda line: line.debit).account_id.code, "657000")
        ecart = (form.provisional_move_id | form.regularisation_move_id).line_ids.filtered(
            lambda line: line.account_id.code == "476000"
        )
        self.assertTrue(all(ecart.mapped("reconciled")))
        self.assertEqual(self._balance("476000"), 0)

    def test_accept_gain_goes_to_757(self):
        form = self._sent(40)
        form.with_user(self.finance).action_decide("accepted")
        self.assertEqual(
            form.regularisation_move_id.line_ids.filtered(lambda line: line.credit).account_id.code, "757000"
        )

    def test_important_needs_finance_head(self):
        form = self._sent(-3000)
        with self.assertRaises(AccessError):
            form.with_user(self.finance).action_decide("accepted")
        form.with_user(self.finance_head).action_decide("accepted")
        self.assertEqual(form.state, "closed")

    def test_major_goes_to_director(self):
        form = self._sent(-6000)
        form.with_user(self.finance_head).action_decide("accepted")
        self.assertEqual(form.state, "direction")
        self.assertFalse(form.regularisation_move_id)
        with self.assertRaises(AccessError):
            form.with_user(self.finance_head).action_direction_approve()
        form.with_user(self.director).action_direction_approve()
        self.assertEqual(form.state, "closed")
        self.assertTrue(form.regularisation_move_id)

    def test_director_sends_back(self):
        form = self._sent(-6000)
        form.with_user(self.finance_head).action_decide("accepted")
        form.with_user(self.director).action_send_back("Pieces manquantes")
        self.assertEqual(form.state, "finance")

    def test_refused_goes_back(self):
        form = self._sent(-10)
        form.with_user(self.finance).action_decide("refused", note="Recompter")
        self.assertEqual(form.state, "to_review")
        self.assertEqual(form.finance_decision, "refused")

    def test_investigating_keeps_476_open(self):
        form = self._sent(-10)
        form.with_user(self.finance).action_decide("investigating")
        self.assertEqual(form.state, "finance")
        self.assertEqual(self._balance("476000"), 10)

    def test_accept_twice_posts_once(self):
        form = self._sent(-10)
        form.with_user(self.finance).action_decide("accepted")
        with self.assertRaises(UserError):
            form.with_user(self.finance).action_decide("accepted")
        self.assertEqual(self.env["account.move"].search_count([("ref", "=", form.name)]), 1)

    def test_other_account_for_surplus(self):
        form = self._sent(50)
        sale = self._account("700200")
        form.with_user(self.finance).action_decide("accepted", account=sale)
        self.assertEqual(form.regularisation_move_id.line_ids.filtered(lambda line: line.credit).account_id, sale)

    def test_finance_box_form_reviewed_by_director(self):
        form = self._sent(-10, journal="CFIN")
        self.assertEqual(form.state, "finance")
        with self.assertRaises(AccessError):
            self._form(-10, journal="CFIN", explanation="x", manager_note="y").with_user(
                self.pos_manager
            ).action_send_to_finance()

    def test_decide_wizard(self):
        form = self._sent(-10)
        wizard = (
            self.env["his.cash.discrepancy.decide"]
            .with_user(self.finance)
            .create({"discrepancy_id": form.id, "decision": "accepted"})
        )
        wizard.action_confirm()
        self.assertEqual(form.state, "closed")
