# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""hr.employee est un miroir du referentiel Personnes, jamais sa source."""
from odoo.tests import TransactionCase, tagged

from odoo.addons.his_hr_base import BACKUP_TABLE, post_init_hook


@tagged('post_install', '-at_install')
class TestPersonLink(TransactionCase):

    def _employee(self, **vals):
        return self.env['hr.employee'].create({'name': "Test Employe", **vals})

    def _make_legacy(self, employee, matricule):
        """Ramene un employe a l'etat « avant reprise » : matricule brut, pas de fiche."""
        employee.person_id = False
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
            'nom_latin': "Deja Enregistre",
            'type_personne': 'enseignant',
            'source_system': 'manual',
        })
        employee = self._employee(person_id=person.id)
        self.assertEqual(employee.person_id, person)
        self.assertEqual(employee.matricule_institutionnel, person.matricule_institutionnel)

    def test_two_employees_get_distinct_matricules(self):
        first, second = self._employee(), self._employee()
        self.assertNotEqual(first.matricule_institutionnel, second.matricule_institutionnel)

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

    # --- Regle 3 : l'annee du matricule vient de la date d'entree -----------

    def test_date_start_working_drives_the_year(self):
        if 'date_start_working' not in self.env['hr.employee']._fields:
            self.skipTest("date_start_working est fourni par maintenance_university")
        employee = self._employee(date_start_working='2021-11-02')
        self.assertTrue(
            employee.matricule_institutionnel.startswith('HIS-2021-'),
            employee.matricule_institutionnel,
        )
