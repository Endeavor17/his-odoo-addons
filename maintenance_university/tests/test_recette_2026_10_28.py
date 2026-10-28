"""Recette du 2026-10-28 : l'ouvrier ne touche pas la date de la demande, et son
demarrage n'envoie pas de courriel au responsable."""

from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestRecette20261028(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env,
            login="recette_resp",
            groups="base.group_user,maintenance_university.group_maintenance_manager",
            email="resp@example.com",
        )
        cls.worker = new_test_user(
            cls.env,
            login="recette_ouvrier",
            groups="base.group_user,maintenance_university.group_maintenance_worker",
        )
        worker_emp = cls.env["hr.employee"].create({"name": "Bilal Ouvrier", "user_id": cls.worker.id})
        building = cls.env["maintenance.building"].create({"name": "Bloc R"})
        category = cls.env["maintenance.category"].create({"name": "Electricite"})
        cls.request = (
            cls.env["maintenance.request"]
            .with_user(cls.manager)
            .create(
                {
                    "name": "Prise grillee",
                    "building_id": building.id,
                    "maintenance_category_id": category.id,
                    "employee_ids": [(6, 0, worker_emp.ids)],
                }
            )
        )
        cls.request.with_user(cls.manager).action_assign()

    def _last_tracking(self):
        # Le suivi s'ecrit au precommit ; ses valeurs ne se lisent qu'en sudo.
        self.env.cr.precommit.run()
        return self.request.sudo().message_ids.filtered("tracking_value_ids")[:1]

    def test_le_demarrage_ne_previent_personne(self):
        self.assertIn(self.manager.partner_id, self.request.message_partner_ids)
        self.request.with_user(self.worker).action_start()
        message = self._last_tracking()
        self.assertEqual(message.subtype_id, self.env.ref("mail.mt_note"))
        self.assertFalse(message.notification_ids, "aucun courriel au responsable")

    def test_la_fin_previent_toujours(self):
        self.request.with_user(self.worker).action_start()
        self.request.with_user(self.worker).action_done()
        self.assertEqual(self._last_tracking().subtype_id, self.env.ref("maintenance.mt_req_status"))

    def test_la_date_de_la_demande_est_au_responsable(self):
        arch = self.env.ref("maintenance_university.view_maintenance_university_request_form").arch
        self.assertIn('name="request_date" readonly="not is_manager"', arch)
