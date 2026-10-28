# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le catalogue de depart : charge, sans groupe sensible, et branche sur les caisses et postes."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCatalogue(TransactionCase):
    def _roles_du_catalogue(self):
        ids = (
            self.env["ir.model.data"]
            .search([("module", "=", "his_role_catalogue"), ("model", "=", "his.role")])
            .mapped("res_id")
        )
        return self.env["his.role"].with_context(active_test=False).browse(ids)

    def test_every_catalogue_role_loads_and_grants_no_sensitive_group(self):
        roles = self._roles_du_catalogue()
        self.assertEqual(len(roles), 26, "un role du catalogue a disparu (ou a ete ajoute sans test)")
        interdits = self.env["hr.job"]._his_groupes_sensibles()
        for role in roles:
            self.assertFalse(role.granted_group_ids & interdits, role.name)

    def test_each_till_has_its_cashier_and_its_counter(self):
        ref = self.env.ref
        for caisse in ("cafeteria", "restaurant", "copy_center"):
            caissier = ref(f"his_role_catalogue.role_cashier_{caisse}")
            self.assertEqual(caissier.pos_config_ids, ref(f"his_stock_mdm.pos_config_{caisse}"), caisse)
            self.assertFalse(caissier.group_ids, "le caissier tape son nom : son role ne donne aucun groupe")
            comptoir = ref(f"his_role_catalogue.role_counter_{caisse}")
            self.assertEqual(comptoir.kind, "counter", caisse)
            caisses_du_comptoir = comptoir.group_ids.filtered(lambda g: "group_caisse_" in (g.get_external_id()[g.id]))
            self.assertEqual(caisses_du_comptoir, ref(f"his_stock_mdm.group_caisse_{caisse}"), caisse)

    def test_purchasing_officer_post_carries_buyer(self):
        poste = self.env.ref("his_purchase.job_purchasing_officer")
        self.assertIn(self.env.ref("his_role_catalogue.role_buyer"), poste.role_ids)

    def test_helpdesk_posts_carry_their_roles(self):
        poste = self.env.ref("his_helpdesk_identity_bridge.job_support")
        self.assertIn(self.env.ref("his_role_catalogue.role_helpdesk_manager"), poste.role_ids)
        technicien = self.env.ref("his_helpdesk_identity_bridge.job_helpdesk_technician")
        self.assertIn(self.env.ref("his_role_catalogue.role_helpdesk_agent"), technicien.role_ids)
        self.assertEqual(self.env.ref("his_role_catalogue.role_helpdesk_agent").name, "Helpdesk Technician")

    def test_his_privileges_share_one_heading(self):
        rubrique = self.env.ref("his_access_base.module_category_his_access")
        for xmlid in (
            "his_access_base.res_groups_privilege_annuaire",
            "his_hygiene.res_groups_privilege_hygiene",
            "his_meal_management.res_groups_privilege_meal",
            "his_person_core.res_groups_privilege_his_person",
            "his_purchase.res_groups_privilege_purchase_request",
            "his_purchase.res_groups_privilege_catalogue",
            "helpdesk_mgmt.group_helpdesk_privilege",
            "maintenance_university.res_groups_privilege_maintenance_university",
            "maintenance_university.res_groups_privilege_maintenance_university_reporter",
        ):
            self.assertEqual(self.env.ref(xmlid).category_id, rubrique, xmlid)
