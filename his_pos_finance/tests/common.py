# Part of Odoo. See LICENSE file for full copyright and licensing details.
import uuid

from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class HisPosFinanceCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        ref = cls.env.ref
        cls.cafeteria = ref("his_stock_mdm.pos_config_cafeteria")
        cls.restaurant = ref("his_stock_mdm.pos_config_restaurant")
        cls.copy_center = ref("his_stock_mdm.pos_config_copy_center")
        cls.cashier_user = new_test_user(
            cls.env, login="pf_cashier", name="Rym Caissiere", groups="his_stock_mdm.group_caisse_cafeteria"
        )
        cls.pos_manager = new_test_user(
            cls.env, login="pf_pos_manager", name="Chef POS", groups="point_of_sale.group_pos_manager"
        )
        cls.finance = new_test_user(
            cls.env, login="pf_finance", name="Agent Finance", groups="his_purchase_finance.group_finance"
        )
        cls.finance_head = new_test_user(
            cls.env, login="pf_finance_head", name="Responsable Finance", groups="his_pos_finance.group_finance_head"
        )
        cls.director = new_test_user(
            cls.env, login="pf_director", name="Directeur", groups="his_purchase.group_purchase_director"
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Article test caisse", "available_in_pos": True, "list_price": 100.0, "taxes_id": False}
        )

    def _open_session(self, config, cashbox=None, notes=""):
        config.open_ui()
        session = config.current_session_id
        if session.state == "opening_control":
            session.set_opening_control(session.cash_register_balance_start if cashbox is None else cashbox, notes)
        return session

    def _sell_cash(self, session, amount):
        """Une vente payee en especes, par le point d'entree de la caisse."""
        cash = session.payment_method_ids.filtered("is_cash_count")[:1]
        ref = str(uuid.uuid4())
        self.env["pos.order"].sync_from_ui(
            [
                {
                    "company_id": self.company.id,
                    "session_id": session.id,
                    "uuid": ref,
                    "state": "paid",
                    "lines": [
                        [
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "qty": 1,
                                "price_unit": amount,
                                "discount": 0,
                                "tax_ids": [[6, False, []]],
                                "price_subtotal": amount,
                                "price_subtotal_incl": amount,
                            },
                        ]
                    ],
                    "payment_ids": [[0, 0, {"amount": amount, "name": fields.Datetime.now(), "payment_method_id": cash.id}]],
                    "amount_paid": amount,
                    "amount_total": amount,
                    "amount_tax": 0.0,
                    "amount_return": 0.0,
                    "last_order_preparation_change": "{}",
                }
            ]
        )
        return self.env["pos.order"].search([("uuid", "=", ref)])

    def _account(self, code):
        return self.env["account.account"].search(
            [("code", "=", code), ("company_ids", "in", self.company.id)], limit=1
        )

    def _journal(self, code):
        return self.env["account.journal"].search([("code", "=", code), ("company_id", "=", self.company.id)], limit=1)

    def _balance(self, code):
        lines = self.env["account.move.line"].search(
            [("account_id", "=", self._account(code).id), ("parent_state", "=", "posted"), ("company_id", "=", self.company.id)]
        )
        return sum(lines.mapped("balance"))
