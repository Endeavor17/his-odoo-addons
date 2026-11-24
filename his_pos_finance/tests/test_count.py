# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import HisPosFinanceCase


@tagged("post_install", "-at_install")
class TestCount(HisPosFinanceCase):
    def _count(self, code, kind, counted, note="", user=None):
        return (
            self.env["his.cash.count"]
            .with_user(user or self.finance)
            .create({"journal_id": self._journal(code).id, "kind": kind, "counted": counted, "note": note})
        )

    def _fund_finance_box(self, amount):
        box = self._journal("CFIN")
        move = self.env["account.move"].create(
            {
                "journal_id": box.id,
                "line_ids": [
                    (0, 0, {"account_id": box.default_account_id.id, "debit": amount, "credit": 0}),
                    (0, 0, {"account_id": self._account("581000").id, "debit": 0, "credit": amount}),
                ],
            }
        )
        move.action_post()

    def test_count_without_gap(self):
        self._fund_finance_box(3000)
        count = self._count("CFIN", "opening", counted=3000)
        self.assertEqual(count.expected, 3000)
        self.assertFalse(count.his_discrepancy_ids)
        self.assertEqual(count.journal_id.his_count_state, "opened")

    def test_count_gap_needs_note_and_opens_form(self):
        self._fund_finance_box(3000)
        with self.assertRaises(ValidationError):
            self._count("CFIN", "closing", counted=2980)
        count = self._count("CFIN", "closing", counted=2980, note="Piece manquante")
        form = count.his_discrepancy_ids
        self.assertEqual((form.kind, form.amount, form.explanation), ("count", -20, "Piece manquante"))
        self.assertEqual(form._his_reviewer_group(), "his_purchase.group_purchase_director")
        self.assertEqual(self._balance("476000"), 20)
        self.assertEqual(self._balance("530001"), 2980)
        self.assertEqual(count.journal_id.his_count_state, "closed")

    def test_direction_box_counted_by_director(self):
        count = self._count("CDIR", "opening", counted=0, user=self.director)
        self.assertEqual(count.expected, 0)
        with self.assertRaises(AccessError):
            self._count("CDIR", "opening", counted=0, user=self.finance)

    def test_count_rights(self):
        with self.assertRaises(AccessError):
            self._count("CFIN", "opening", counted=0, user=self.cashier_user)

    def test_holder_may_count(self):
        holder = self.pos_manager
        self._journal("CDIR").his_holder_id = holder
        self._count("CDIR", "opening", counted=0, user=holder)
