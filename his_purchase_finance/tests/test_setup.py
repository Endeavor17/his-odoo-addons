# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.his_purchase_finance.hooks import ACCOUNTS, JOURNALS, setup_accounts
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestSetup(TransactionCase):
    def test_setup_creates_missing_accounts_once(self):
        company = self.env.company
        setup_accounts(self.env, company)
        Account = self.env["account.account"]
        codes = [code for code, _name, _type in ACCOUNTS]
        accounts = Account.search([("code", "in", codes), ("company_ids", "in", company.id)])
        self.assertEqual(sorted(accounts.mapped("code")), sorted(codes))
        self.assertEqual(Account.search([("code", "=", "401200")]).account_type, "liability_payable")
        journals = self.env["account.journal"].search([("code", "in", [c for c, _n in JOURNALS])])
        self.assertEqual(set(journals.mapped("type")), {"purchase"})
        self.assertEqual(len(journals), 4)
        before = Account.search_count([]), self.env["account.journal"].search_count([])
        setup_accounts(self.env, company)
        self.assertEqual((Account.search_count([]), self.env["account.journal"].search_count([])), before)

    def test_setup_skips_company_without_chart(self):
        company = self.env["res.company"].create({"name": "No Chart SARL"})
        setup_accounts(self.env, company)
        self.assertFalse(self.env["account.journal"].search([("code", "=", "AGEN"), ("company_id", "=", company.id)]))

    def test_accountant_is_finance(self):
        user = new_test_user(self.env, login="his_accountant", groups="account.group_account_user")
        self.assertTrue(user.has_group("his_purchase_finance.group_finance"))
        self.assertTrue(user.has_group("account.group_validate_bank_account"))

    def test_privilege_under_his_heading(self):
        self.assertEqual(
            self.env.ref("his_purchase_finance.res_groups_privilege_finance").category_id,
            self.env.ref("his_access_base.module_category_his_access"),
        )
