# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le catalogue de depart : charge, sans groupe sensible, et branche sur les caisses et postes."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCatalogue(TransactionCase):
    def _roles_du_catalogue(self):
        ids = self.env["ir.model.data"].search(
            [("module", "=", "his_role_catalogue"), ("model", "=", "his.role")]
        ).mapped("res_id")
        return self.env["his.role"].with_context(active_test=False).browse(ids)

    def test_every_catalogue_role_loads_and_grants_no_sensitive_group(self):
        roles = self._roles_du_catalogue()
        self.assertGreaterEqual(len(roles), 25)
        interdits = self.env["hr.job"]._his_groupes_sensibles()
        for role in roles:
            self.assertFalse(role.granted_group_ids & interdits, role.name)

    def test_cafeteria_cashier_role_is_linked_to_cafeteria_only(self):
        role = self.env.ref("his_role_catalogue.role_cashier_cafeteria")
        self.assertEqual(role.pos_config_ids, self.env.ref("his_stock_mdm.pos_config_cafeteria"))
        self.assertFalse(role.group_ids, "le caissier tape son nom : son role ne donne aucun groupe")

    def test_purchasing_officer_post_carries_buyer(self):
        poste = self.env.ref("his_purchase.job_purchasing_officer")
        self.assertIn(self.env.ref("his_role_catalogue.role_buyer"), poste.role_ids)

    def test_support_officer_post_carries_helpdesk_manager(self):
        poste = self.env.ref("his_helpdesk_identity_bridge.job_support")
        self.assertIn(self.env.ref("his_role_catalogue.role_helpdesk_manager"), poste.role_ids)

    def test_his_privileges_share_one_heading(self):
        rubrique = self.env.ref("his_access_base.module_category_his_access")
        for xmlid in ("his_meal_management.res_groups_privilege_meal", "his_purchase.res_groups_privilege_catalogue"):
            self.assertEqual(self.env.ref(xmlid).category_id, rubrique, xmlid)
