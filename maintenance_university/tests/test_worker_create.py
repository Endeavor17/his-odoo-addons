# -*- coding: utf-8 -*-
"""L'assistant « Creer des travailleurs » ne doit plus fabriquer de doublons.

C'etait la porte ouverte du referentiel : chaque passage creait un utilisateur,
un contact, un employe et — via his_hr_base._create_his_person() — une fiche
personne neuve avec un matricule neuf. Une meme personne a fini avec trois
fiches. Ces tests verrouillent le comportement corrige.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWorkerCreate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # L'assistant refuse quiconque n'est pas gestionnaire : c'est son
        # premier garde-fou, et il n'est pas ce qu'on teste ici.
        cls.env.user.group_ids = [(
            4, cls.env.ref('maintenance_university.group_maintenance_manager').id,
        )]

    def _person(self, name, **vals):
        return self.env['his.person'].create({
            'name': name,
            'type_personne': 'etudiant',
            'source_system': 'manual',
            **vals,
        })

    def _wizard(self, **line_vals):
        return self.env['maintenance.university.worker.create'].create({
            'line_ids': [(0, 0, {
                'name': "Sans Nom",
                'login': "sans.nom@his.test",
                **line_vals,
            })],
        })

    # --- Le garde-fou -------------------------------------------------------

    def test_a_known_name_stops_the_button(self):
        known = self._person("Abdo Chabouti")
        wizard = self._wizard(name="Abdo Chabouti", login="abdo.dup@his.test")

        self.assertEqual(wizard.line_ids.suggested_person_id, known)
        with self.assertRaises(UserError):
            wizard.action_create_workers()
        self.assertFalse(wizard.line_ids.employee_id, "l'employe a ete cree malgre tout")

    def test_the_suggestion_ignores_case_and_word_order(self):
        known = self._person("Abdo Chabouti")
        wizard = self._wizard(name="CHABOUTI ABDO", login="chabouti@his.test")
        self.assertEqual(wizard.line_ids.suggested_person_id, known)

    def test_an_unknown_name_goes_straight_through(self):
        wizard = self._wizard(name="Parfait Inconnu", login="inconnu@his.test")
        self.assertFalse(wizard.line_ids.suggested_person_id)
        wizard.action_create_workers()
        self.assertTrue(wizard.line_ids.employee_id)

    def test_confirming_a_namesake_creates_a_second_person(self):
        """Deux humains peuvent porter le meme nom : la case le dit explicitement."""
        self._person("Homonyme Reel")
        wizard = self._wizard(
            name="Homonyme Reel", login="homonyme2@his.test", confirmed_new=True,
        )
        wizard.action_create_workers()
        employee = wizard.line_ids.employee_id
        self.assertTrue(employee.person_id)
        self.assertEqual(
            self.env['his.person'].search_count([('name', '=', "Homonyme Reel")]), 2,
        )

    # --- Le rattachement ----------------------------------------------------

    def test_attaching_reuses_the_matricule_and_the_contact(self):
        known = self._person("Deja Enregistre")
        matricule = known.matricule_institutionnel
        partner = known.partner_id
        people_before = self.env['his.person'].search_count([])

        wizard = self._wizard(
            name="Deja Enregistre", login="deja@his.test", person_id=known.id,
        )
        wizard.action_create_workers()

        employee = wizard.line_ids.employee_id
        self.assertEqual(employee.person_id, known)
        self.assertEqual(employee.matricule_institutionnel, matricule)
        self.assertEqual(
            employee.user_id.partner_id, partner,
            "un second contact a ete cree pour la meme personne",
        )
        self.assertEqual(
            self.env['his.person'].search_count([]), people_before,
            "une fiche personne a ete emise alors qu'elle existait deja",
        )

    def test_attaching_reuses_an_account_the_person_already_has(self):
        known = self._person("Deja Connecte")
        existing_user = self.env['res.users'].create({
            'name': "Deja Connecte",
            'login': "deja.connecte@his.test",
            'partner_id': known.partner_id.id,
        })
        users_before = self.env['res.users'].search_count([])

        wizard = self._wizard(
            name="Deja Connecte", login="autre.login@his.test", person_id=known.id,
        )
        wizard.action_create_workers()

        self.assertEqual(wizard.line_ids.employee_id.user_id, existing_user)
        self.assertEqual(
            self.env['res.users'].search_count([]), users_before,
            "un second compte a ete cree pour la meme personne",
        )
        self.assertTrue(existing_user.has_group(
            'maintenance_university.group_maintenance_worker',
        ))
        self.assertFalse(
            wizard.line_ids.password,
            "un mot de passe a ete affiche pour un compte qu'on n'a pas cree",
        )

    def test_a_person_who_already_works_here_is_refused(self):
        known = self._person("Deja Employe")
        self.env['hr.employee'].create({'name': "Deja Employe", 'person_id': known.id})

        wizard = self._wizard(
            name="Deja Employe", login="deja.emp@his.test", person_id=known.id,
        )
        with self.assertRaises(UserError):
            wizard.action_create_workers()

    # --- Ce qui ne change pas ----------------------------------------------

    def test_a_new_worker_still_gets_a_person_and_a_password(self):
        wizard = self._wizard(name="Vrai Nouveau", login="nouveau@his.test")
        wizard.action_create_workers()

        employee = wizard.line_ids.employee_id
        self.assertTrue(employee.person_id)
        self.assertRegex(employee.matricule_institutionnel, r'^HIS-\d{4}-\d{6}-[0-9X]$')
        self.assertTrue(wizard.line_ids.password)
        self.assertEqual(employee.initial_password, wizard.line_ids.password)

    def test_running_the_wizard_twice_does_not_reprocess_a_line(self):
        wizard = self._wizard(name="Une Seule Fois", login="unefois@his.test")
        wizard.action_create_workers()
        employee = wizard.line_ids.employee_id
        wizard.action_create_workers()
        self.assertEqual(wizard.line_ids.employee_id, employee)
