# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.his_pos_finance.hooks import setup_pos_finance
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import HisPosFinanceCase


@tagged("post_install", "-at_install")
class TestSetup(HisPosFinanceCase):
    def test_accounts_and_journals(self):
        for code in (
            "530000",
            "530001",
            "530100",
            "581000",
            "476000",
            "657000",
            "757000",
            "700300",
            "701300",
            "706200",
            "411300",
        ):
            self.assertTrue(self._account(code), code)
        self.assertTrue(self._account("476000").reconcile)
        ccaf = self._journal("CCAF")
        self.assertEqual(ccaf.type, "cash")
        self.assertEqual(ccaf.default_account_id, self._account("530200"))
        self.assertEqual(ccaf.loss_account_id, self._account("476000"))
        self.assertEqual(ccaf.profit_account_id, self._account("476000"))
        self.assertEqual(self._journal("VCAF").type, "sale")
        for code in ("VGEN", "VCOP", "VRES", "CDIR", "CFIN", "CCOP", "CRES"):
            self.assertTrue(self._journal(code), code)
        self.assertEqual(self.company.transfer_account_id, self._account("581000"))

    def test_till_config(self):
        c = self.cafeteria
        self.assertEqual(c.journal_id.code, "VCAF")
        self.assertEqual(c.invoice_journal_id.code, "VCAF")
        self.assertTrue(c.cash_control)
        self.assertFalse(c.set_maximum_difference)
        self.assertTrue(c.restrict_price_control)
        self.assertEqual(c.payment_method_ids.filtered("is_cash_count").journal_id.code, "CCAF")
        fp = c.default_fiscal_position_id
        # comptes seulement : la TVA de his_pos_tva passe telle quelle
        for tax in self.env["account.tax"].search(
            [("type_tax_use", "=", "sale"), ("company_id", "=", self.company.id)]
        ):
            self.assertEqual(fp.map_tax(tax), tax, tax.name)
        self.assertIn(self._account("700200"), fp.account_ids.account_dest_id)
        resto = self.restaurant.default_fiscal_position_id
        self.assertEqual(resto.map_account(self._account("700200")), self._account("700300"))
        self.assertEqual(
            self.copy_center.default_fiscal_position_id.map_account(self._account("700200")), self._account("700100")
        )

    def test_income_by_category(self):
        ref = self.env.ref
        self.assertEqual(
            ref("his_stock_mdm.categ_copy_impression").property_account_income_categ_id, self._account("706200")
        )
        self.assertEqual(
            ref("his_stock_mdm.categ_cafe_boissons").property_account_income_categ_id, self._account("700200")
        )
        self.assertEqual(
            ref("his_meal_management.product_category_meal_plans").property_account_income_categ_id,
            self._account("701300"),
        )
        self.assertEqual(
            ref("his_pos_menu.product_category_menu").property_account_income_categ_id, self._account("701300")
        )

    def test_sale_taxes_on_445720(self):
        tax = self.company.account_sale_tax_id
        self.assertEqual(
            tax.invoice_repartition_line_ids.filtered(lambda r: r.repartition_type == "tax").account_id,
            self._account("445720"),
        )

    def test_setup_is_idempotent(self):
        n_journals = self.env["account.journal"].search_count([])
        n_accounts = self.env["account.account"].search_count([])
        setup_pos_finance(self.env, self.company)
        self.assertEqual(self.env["account.journal"].search_count([]), n_journals)
        self.assertEqual(self.env["account.account"].search_count([]), n_accounts)

    def test_setup_refuses_open_session(self):
        self.cafeteria.journal_id = self._journal("VGEN")  # quelque chose a reecrire
        self._open_session(self.cafeteria)
        with self.assertRaisesRegex(UserError, "Close every till"):
            setup_pos_finance(self.env, self.company)

    def test_finance_head_is_finance(self):
        self.assertTrue(self.finance_head.has_group("his_purchase_finance.group_finance"))

    def test_finance_head_role(self):
        role = self.env.ref("his_pos_finance.role_finance_head")
        self.assertIn(self.env.ref("his_pos_finance.group_finance_head"), role.group_ids)

    def test_legacy_float_carried_and_old_journal_archived(self):
        from odoo.addons.his_pos_finance.hooks import carry_legacy_cash

        cfin = self._journal("CFIN")
        legacy = self.env["account.journal"].create(
            {
                "name": "Ancienne caisse",
                "code": "OLDC",
                "type": "cash",
                "company_id": self.company.id,
                "default_account_id": cfin.default_account_id.id,
            }
        )
        # une session close avant le module, sur l'ancien journal (une base
        # de recette peut avoir la caisse ouverte : on la ferme ici)
        self.env["pos.session"].search([("config_id", "=", self.cafeteria.id), ("state", "!=", "closed")]).write(
            {"state": "closed"}
        )
        session = self.env["pos.session"].create({"config_id": self.cafeteria.id, "user_id": self.env.uid})
        session.write({"state": "closed", "cash_register_balance_end_real": 1500.0})
        session.cash_journal_id = legacy
        before = self._balance("530200"), self._balance(cfin.default_account_id.code)
        carry_legacy_cash(self.env, self.company)
        carry_legacy_cash(self.env, self.company)  # idempotent
        self.assertEqual(self._balance("530200") - before[0], 1500.0)
        self.assertEqual(self._balance(cfin.default_account_id.code) - before[1], -1500.0)
        self.assertFalse(legacy.active)
        self.assertTrue(cfin.active)

    def test_tills_take_cash_only(self):
        from odoo.addons.his_pos_finance.hooks import cash_only_tills

        bank = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", self.company.id)], limit=1
        )
        card = self.env["pos.payment.method"].create({"name": "Carte test", "journal_id": bank.id})
        self.env["pos.session"].search([("config_id", "=", self.cafeteria.id), ("state", "!=", "closed")]).write(
            {"state": "closed"}
        )
        self.cafeteria.payment_method_ids = [(4, card.id)]
        cash_only_tills(self.env, self.company)
        self.assertNotIn(card, self.cafeteria.payment_method_ids)
        self.assertEqual(self.cafeteria.payment_method_ids.journal_id.mapped("code"), ["CCAF"])
