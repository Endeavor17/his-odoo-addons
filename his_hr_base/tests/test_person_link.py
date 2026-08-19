# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""hr.employee est un miroir du referentiel Personnes, jamais sa source."""
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.his_hr_base import BACKUP_TABLE, post_init_hook


@tagged('post_install', '-at_install')
class TestPersonLink(TransactionCase):

    def _employee(self, **vals):
        return self.env['hr.employee'].create({'name': "Test Employe", **vals})

    def _make_legacy(self, employee, matricule):
        """Ramene un employe a l'etat « avant reprise » : matricule brut, pas de fiche.

        La fiche creee par create() est supprimee, pas seulement detachee : son
        partenaire doit redevenir libre, sinon la reprise le verrait deja pris
        et creerait un second contact — un artefact du test, pas le
        comportement reel sur une base d'avant migration.
        """
        person = employee.person_id
        employee.person_id = False
        person.unlink()
        self.env.cr.execute(
            "INSERT INTO %s (employee_id, matricule) VALUES (%%s, %%s) "
            "ON CONFLICT (employee_id) DO UPDATE SET matricule = EXCLUDED.matricule"
            % BACKUP_TABLE,
            (employee.id, matricule),
        )

    # --- Regle 1 : tout employe cree obtient une fiche et un matricule ------

    def test_create_links_a_person(self):
        employee = self._employee()
        self.assertTrue(employee.person_id)
        self.assertEqual(employee.person_id.type_personne, 'employe')
        self.assertEqual(employee.person_id.source_system, 'odoo_hr')
        self.assertRegex(employee.matricule_institutionnel, r'^HIS-\d{4}-\d{6}-[0-9X]$')

    def test_matricule_mirrors_the_person(self):
        """Le champ de l'employe suit la fiche : c'est un related, pas une copie."""
        employee = self._employee()
        self.assertEqual(
            employee.matricule_institutionnel,
            employee.person_id.matricule_institutionnel,
        )

    def test_explicit_person_id_is_not_overridden(self):
        person = self.env['his.person'].create({
            'name': "Deja Enregistre",
            'type_personne': 'enseignant',
            'source_system': 'manual',
        })
        employee = self._employee(person_id=person.id)
        self.assertEqual(employee.person_id, person)
        self.assertEqual(employee.matricule_institutionnel, person.matricule_institutionnel)

    def test_two_employees_get_distinct_matricules(self):
        first, second = self._employee(), self._employee()
        self.assertNotEqual(first.matricule_institutionnel, second.matricule_institutionnel)

    # --- Regle 1 bis : un seul partenaire par humain ------------------------

    def test_create_reuses_the_employee_work_contact(self):
        """La fiche personne se pose sur le contact que l'employe a deja."""
        before = self.env['res.partner'].search_count([])
        employee = self._employee()
        self.assertTrue(employee.work_contact_id, "hr n'a pas cree de contact")
        self.assertEqual(
            employee.person_id.partner_id, employee.work_contact_id,
            "la fiche personne pointe un autre contact que celui de l'employe",
        )
        self.assertEqual(
            self.env['res.partner'].search_count([]), before + 1,
            "un second contact a ete cree pour le meme humain",
        )

    def test_shared_work_contact_is_refused(self):
        """Deux employes sur un meme contact rendraient le matricule ambigu."""
        first = self._employee()
        with self.assertRaises(ValidationError):
            self._employee(work_contact_id=first.work_contact_id.id)

    def test_a_partner_carries_at_most_one_person(self):
        employee = self._employee()
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['his.person'].create({
                    'partner_id': employee.work_contact_id.id,
                    'type_personne': 'etudiant',
                    'source_system': 'manual',
                })

    def test_partner_of_a_live_person_cannot_be_deleted(self):
        """ondelete='restrict' : supprimer un contact ne detruit pas une identite.

        Teste sur une personne sans employe : pour un employe, hr refuse deja
        la suppression de son contact de travail (UserError) avant meme que la
        contrainte n'entre en jeu. Le matricule est donc protege deux fois,
        mais c'est bien `restrict` qui couvre les etudiants, que hr ignore.
        """
        person = self.env['his.person'].create({
            'name': "Etudiante Test",
            'type_personne': 'etudiant',
            'source_system': 'manual',
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                person.partner_id.unlink()

    # --- Regle 2 : la reprise ne perd ni ne remplace aucune valeur ----------

    def test_backfill_preserves_existing_values(self):
        legacy = {}
        for matricule in ('HIS-2023-000004-8', 'HIS-2024-000117-9', 'HIS-2022-000031'):
            employee = self._employee()
            self._make_legacy(employee, matricule)
            legacy[employee] = matricule

        post_init_hook(self.env)

        for employee, matricule in legacy.items():
            self.assertTrue(employee.person_id, "employe non rattache")
            self.assertEqual(
                employee.person_id.matricule_institutionnel, matricule,
                "matricule reemis ou derive au lieu d'etre repris",
            )
            self.assertEqual(employee.matricule_institutionnel, matricule)
            self.assertEqual(employee.person_id.type_personne, 'employe')

    def test_backfill_preserves_legacy_value_without_checksum(self):
        """Une valeur sans cle de controle est reprise telle quelle, pas rejetee."""
        employee = self._employee()
        self._make_legacy(employee, 'HIS-2022-000031')
        post_init_hook(self.env)
        self.assertEqual(employee.matricule_institutionnel, 'HIS-2022-000031')

    def test_backfill_is_idempotent(self):
        employee = self._employee()
        self._make_legacy(employee, 'HIS-2023-000055-4')

        post_init_hook(self.env)
        person = employee.person_id
        count_before = self.env['his.person'].with_context(active_test=False).search_count([])

        post_init_hook(self.env)
        self.assertEqual(employee.person_id, person, "fiche remplacee au second passage")
        self.assertEqual(
            self.env['his.person'].with_context(active_test=False).search_count([]),
            count_before,
            "le second passage a cree des fiches en doublon",
        )
        self.assertEqual(employee.matricule_institutionnel, 'HIS-2023-000055-4')

    def test_backfill_mints_for_employees_without_any_matricule(self):
        """Un employe sans matricule du tout en recoit un neuf, et une fiche."""
        employee = self._employee()
        employee.person_id = False
        self.assertFalse(employee.matricule_institutionnel)
        post_init_hook(self.env)
        self.assertTrue(employee.person_id)
        self.assertRegex(employee.matricule_institutionnel, r'^HIS-\d{4}-\d{6}-[0-9X]$')

    def test_backfill_advances_the_sequence_past_reused_numbers(self):
        """Le compteur repart au-dessus des numeros que l'ancienne sequence a brules.

        Sinon une embauche datee de la meme annee recevrait HIS-AAAA-000031-C
        alors que HIS-AAAA-000031 est deja porte : deux chaines differentes a
        cause de la cle, donc l'unicite ne dit rien, mais le meme numero pour
        deux personnes.
        """
        employee = self._employee()
        self._make_legacy(employee, 'HIS-2022-000031')
        post_init_hook(self.env)

        newcomer = self.env['his.person'].create({
            'name': "Nouvelle Recrue",
            'type_personne': 'employe',
            'source_system': 'odoo_hr',
            'matricule_sequence_date': '2022-06-01',
        })
        number = int(newcomer.matricule_institutionnel.split('-')[2])
        self.assertGreater(number, 31, newcomer.matricule_institutionnel)

    # --- Regle 3 : l'annee du matricule vient de la date d'entree -----------

    def test_date_start_working_drives_the_year(self):
        if 'date_start_working' not in self.env['hr.employee']._fields:
            self.skipTest("date_start_working est fourni par maintenance_university")
        employee = self._employee(date_start_working='2021-11-02')
        self.assertTrue(
            employee.matricule_institutionnel.startswith('HIS-2021-'),
            employee.matricule_institutionnel,
        )

    # --- Regle 4 : ce module affiche ses propres champs ---------------------

    def test_module_ships_its_own_employee_view(self):
        """Les champs poses par ce module doivent etre visibles sans autre module.

        Ils dependaient auparavant de la vue de maintenance_university : les
        desinstaller rendait le matricule invisible sur la fiche employe.
        """
        view = self.env.ref(
            'his_hr_base.view_employee_form_inherit_his_hr_base',
            raise_if_not_found=False,
        )
        self.assertTrue(view, "his_hr_base n'expose aucune vue de ses champs")
        arch = self.env['hr.employee'].get_view(view_type='form')['arch']
        self.assertEqual(
            arch.count('name="matricule_institutionnel"'), 1,
            "matricule_institutionnel affiche zero ou plusieurs fois",
        )
        self.assertIn('name="person_id"', arch)
