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

    def _subtype_after(self, action):
        # Le sous-type choisit qui est prevenu : mt_note = personne.
        stage = self.request.stage_id
        getattr(self.request.with_user(self.worker), action)()
        return self.request._track_subtype({"stage_id": stage})

    def test_le_demarrage_ne_previent_personne(self):
        self.assertIn(self.manager.partner_id, self.request.message_partner_ids)
        self.assertEqual(self._subtype_after("action_start"), self.env.ref("mail.mt_note"))

    def test_la_fin_previent_toujours(self):
        self.request.with_user(self.worker).action_start()
        self.assertEqual(self._subtype_after("action_done"), self.env.ref("maintenance.mt_req_status"))

    def test_la_date_de_la_demande_est_au_responsable(self):
        arch = self.env.ref("maintenance_university.view_maintenance_university_request_form").arch
        self.assertIn('name="request_date" readonly="not is_manager"', arch)
