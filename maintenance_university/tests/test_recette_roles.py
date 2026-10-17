"""Recette du 2026-10-17 : la maintenance ne donne plus de role ni ne ferme de menu
au-dela des siens (P-13, P-14)."""

from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestRecetteRoles(TransactionCase):
    def test_un_employe_avec_compte_n_est_pas_ouvrier(self):
        # P-13 : tout compte devenait Ouvrier, affectable aux interventions.
        user = new_test_user(self.env, login="recette_simple", groups="base.group_user")
        self.env["hr.employee"].create({"name": "Walid Simple", "user_id": user.id})
        self.assertFalse(user.has_group("maintenance_university.group_maintenance_worker"))

    def test_apps_reste_aux_administrateurs_discussion_a_tous(self):
        # P-14 : un (6, 0, ...) donnait Apps aux responsables maintenance et
        # retirait Discussion a tout le monde.
        manager = self.env.ref("maintenance_university.group_maintenance_manager")
        apps = self.env.ref("base.menu_management")
        self.assertIn(self.env.ref("base.group_system"), apps.group_ids)
        self.assertNotIn(manager, apps.group_ids)
        discuss = self.env.ref("mail.menu_root_discuss")
        self.assertIn(self.env.ref("base.group_user"), discuss.group_ids)
