# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Regles de l'import Sheets. La plus importante : jamais de fusion automatique."""
import base64
import os

from odoo.tests import TransactionCase, tagged

HEADER = "matricule,nom latin,nom arabe,email personnel,telephone,carte,external ref"


@tagged('post_install', '-at_install')
class TestSheetsImport(TransactionCase):

    def _wizard(self, *rows, filename='export.csv'):
        content = "\n".join((HEADER,) + rows)
        return self.env['his.person.import'].create({
            'file': base64.b64encode(content.encode('utf-8')),
            'filename': filename,
        })

    def _run(self, *rows, **kwargs):
        wizard = self._wizard(*rows, **kwargs)
        wizard.action_import()
        return wizard

    def _person(self, **vals):
        return self.env['his.person'].create({
            'name': "Personne Test",
            'type_personne': 'etudiant',
            'source_system': 'google_sheets',
            **vals,
        })

    # --- Regle 1 : rapprochement deterministe par matricule exact -----------

    def test_exact_matricule_updates_without_reissuing(self):
        existing = self._person(
            matricule_institutionnel='HIS-2023-000090-6', name="Amina Haddad",
        )
        wizard = self._run("HIS-2023-000090-6,Amina Haddad,,amina@ex.ma,0600000001,,R-1")
        line = wizard.line_ids
        self.assertEqual(line.outcome, 'updated')
        self.assertEqual(line.person_id, existing)
        self.assertEqual(existing.matricule_institutionnel, 'HIS-2023-000090-6')
        self.assertEqual(existing.email_personnel, 'amina@ex.ma')

    def test_unknown_matricule_is_preserved_not_reissued(self):
        wizard = self._run("HIS-2019-000007-3,Karim Alaoui,,karim@ex.ma,0600000002,,R-2")
        line = wizard.line_ids
        self.assertEqual(line.outcome, 'created')
        self.assertEqual(line.person_id.matricule_institutionnel, 'HIS-2019-000007-3')
        self.assertEqual(line.person_id.match_method, 'deterministic')

    # --- Regle 2 : un matricule d'un type incompatible est un conflit -------

    def test_conflicting_matricule_is_reported_not_merged(self):
        employee_person = self._person(
            matricule_institutionnel='HIS-2020-000012-5',
            name="Said Bennani",
            type_personne='employe',
            source_system='odoo_hr',
        )
        wizard = self._run("HIS-2020-000012-5,Said Bennani,,said@ex.ma,0600000003,,R-3")
        line = wizard.line_ids
        self.assertEqual(line.outcome, 'conflict')
        self.assertFalse(line.person_id, "une fiche a ete creee malgre le conflit")
        self.assertEqual(employee_person.type_personne, 'employe', "type ecrase")
        self.assertEqual(employee_person.source_system, 'odoo_hr', "fiche fusionnee")
        self.assertIn('HIS-2020-000012-5', line.message)

    def test_conflict_is_traced_in_the_log(self):
        self._person(
            matricule_institutionnel='HIS-2020-000013-7',
            name="Nadia Fassi", type_personne='employe', source_system='odoo_hr',
        )
        self._run("HIS-2020-000013-7,Nadia Fassi,,nadia@ex.ma,0600000004,,R-4")
        log = self.env['his.person.sync.log'].search([('external_ref', '=', 'R-4')])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.outcome, 'conflict')
        self.assertEqual(log.user_id, self.env.user)

    # --- Regle 3 : au-dessus du seuil, on propose, on ne lie pas ------------

    def test_probabilistic_match_is_flagged_not_linked(self):
        existing = self._person(
            name="Youssef Idrissi",
            email_personnel='youssef@ex.ma',
            phone='0600000005',
            external_ref='ANCIEN-1',
        )
        wizard = self._run(",Youssef Idrissi,,youssef@ex.ma,0600000005,,R-5")
        line = wizard.line_ids
        self.assertEqual(line.outcome, 'flagged')
        self.assertEqual(line.candidate_person_id, existing)
        self.assertFalse(line.person_id, "rattachement automatique : interdit")
        self.assertFalse(existing.match_method, "match_method pose sans confirmation")
        self.assertEqual(
            self.env['his.person'].search_count([('external_ref', '=', 'R-5')]), 0,
            "une fiche a ete creee alors que la ligne devait etre arbitree",
        )

    def test_confirming_a_flagged_match_records_who_and_when(self):
        existing = self._person(
            name="Salma Cherkaoui",
            email_personnel='salma@ex.ma',
            phone='0600000006',
            external_ref='ANCIEN-2',
        )
        wizard = self._run(",Salma Cherkaoui,,salma@ex.ma,0600000006,,R-6")
        wizard.line_ids.action_confirm_match()
        self.assertEqual(wizard.line_ids.outcome, 'confirmed')
        self.assertEqual(wizard.line_ids.person_id, existing)
        self.assertEqual(existing.match_method, 'probabilistic')
        self.assertEqual(existing.matched_by, self.env.user)
        self.assertTrue(existing.matched_on)

    def test_rejecting_a_flagged_match_creates_a_distinct_person(self):
        existing = self._person(
            name="Omar Tazi", email_personnel='omar@ex.ma',
            phone='0600000007', external_ref='ANCIEN-3',
        )
        wizard = self._run(",Omar Tazi,,omar@ex.ma,0600000007,,R-7")
        wizard.line_ids.action_reject_match()
        line = wizard.line_ids
        self.assertEqual(line.outcome, 'rejected')
        self.assertNotEqual(line.person_id, existing)
        self.assertRegex(line.person_id.matricule_institutionnel, r'^HIS-\d{4}-\d{6}-[0-9X]$')
        self.assertFalse(existing.match_method)

    # --- Regle 4 : aucune correspondance -> fiche neuve ---------------------

    def test_new_row_creates_a_person_with_a_fresh_matricule(self):
        wizard = self._run(",Hind Berrada,,hind@ex.ma,0600000008,,R-8")
        person = wizard.line_ids.person_id
        self.assertEqual(wizard.line_ids.outcome, 'created')
        self.assertRegex(person.matricule_institutionnel, r'^HIS-\d{4}-\d{6}-[0-9X]$')
        self.assertEqual(person.type_personne, 'etudiant')
        self.assertEqual(person.source_system, 'google_sheets')
        self.assertEqual(person.match_method, 'new')
        self.assertEqual(person.external_ref, 'R-8')

    def test_row_without_reference_falls_back_to_its_position(self):
        wizard = self._run(",Rachid Slimani,,rachid@ex.ma,0600000009,,")
        self.assertEqual(wizard.line_ids.person_id.external_ref, 'export.csv#L2')

    # --- Regle 5 : rejouer un import ne duplique rien -----------------------

    def test_reimporting_the_same_file_creates_no_duplicate(self):
        row = ",Fatima Zahra,,fatima@ex.ma,0600000010,,R-9"
        first = self._run(row)
        self.assertEqual(first.line_ids.outcome, 'created')
        person = first.line_ids.person_id

        second = self._run(row)
        self.assertEqual(second.line_ids.outcome, 'updated', "ligne retraitee comme neuve")
        self.assertEqual(second.line_ids.person_id, person)
        self.assertEqual(
            self.env['his.person'].search_count([('external_ref', '=', 'R-9')]), 1,
            "doublon cree au second import",
        )

    def test_reimporting_a_matricule_row_creates_no_duplicate(self):
        row = "HIS-2018-000044-8,Bilal Ouazzani,,bilal@ex.ma,0600000011,,R-10"
        self._run(row)
        self._run(row)
        self.assertEqual(
            self.env['his.person'].search_count(
                [('matricule_institutionnel', '=', 'HIS-2018-000044-8')]
            ), 1,
        )

    def test_new_student_gets_exactly_one_partner(self):
        """La delegation cree un partenaire, un seul, par etudiant importe."""
        before = self.env['res.partner'].search_count([])
        wizard = self._run(",Souad Belkacem,,souad@ex.ma,0600000020,,R-20")
        person = wizard.line_ids.person_id
        self.assertTrue(person.partner_id)
        self.assertEqual(person.partner_id.name, "Souad Belkacem")
        self.assertEqual(
            self.env['res.partner'].search_count([]), before + 1,
            "l'import a cree plus d'un contact pour une seule personne",
        )

    def test_imported_partner_carries_the_identity_tag(self):
        """L'etiquette permettra aux Ventes d'ecarter les etudiants plus tard."""
        category = self.env.ref('his_person_core.categ_partner_identite')
        wizard = self._run(",Karim Belhadj,,karim.b@ex.ma,0600000021,,R-21")
        self.assertIn(category, wizard.line_ids.person_id.partner_id.category_id)

    # --- Regle 7 : la carte est captee, et n'appartient qu'a une personne ----

    def test_card_number_is_imported(self):
        wizard = self._run(",Yasmine Kaci,,yasmine@ex.ma,0600000030,CARD-9001,R-30")
        person = wizard.line_ids.person_id
        self.assertEqual(wizard.line_ids.outcome, 'created')
        self.assertEqual(person.numero_carte, 'CARD-9001')

    def test_card_column_is_optional(self):
        """Une feuille sans colonne carte s'importe comme avant."""
        content = "nom latin,email personnel\nSofiane Merad,sofiane@ex.ma"
        wizard = self.env['his.person.import'].create({
            'file': base64.b64encode(content.encode('utf-8')),
            'filename': 'sans_carte.csv',
        })
        wizard.action_import()
        self.assertEqual(wizard.line_ids.outcome, 'created')
        self.assertFalse(wizard.line_ids.person_id.numero_carte)

    def test_card_already_held_by_someone_else_is_a_conflict(self):
        """La caisse debiterait la mauvaise personne : on rejette la ligne."""
        holder = self._person(name="Titulaire Carte", numero_carte='CARD-9002')
        wizard = self._run(",Autre Personne,,autre@ex.ma,0600000031,CARD-9002,R-31")
        line = wizard.line_ids
        self.assertEqual(line.outcome, 'conflict')
        self.assertFalse(line.person_id, "une fiche a ete creee malgre le conflit")
        self.assertIn('CARD-9002', line.message)
        self.assertEqual(
            holder.numero_carte, 'CARD-9002', "la carte a ete deplacee",
        )

    def test_reimporting_the_same_card_is_not_a_conflict(self):
        """Rejouer un import ne doit pas transformer sa propre carte en conflit."""
        row = ",Nabil Cherif,,nabil@ex.ma,0600000032,CARD-9003,R-32"
        first = self._run(row)
        self.assertEqual(first.line_ids.outcome, 'created')
        second = self._run(row)
        self.assertEqual(second.line_ids.outcome, 'updated')
        self.assertEqual(second.line_ids.person_id.numero_carte, 'CARD-9003')

    # --- Regle 6 : le fichier source n'est jamais reecrit -------------------

    def test_import_is_one_way(self):
        """Aucun chemin d'ecriture vers la source : le fichier reste inchange."""
        wizard = self._wizard(",Mehdi Naciri,,mehdi@ex.ma,0600000012,,R-11")
        before = wizard.file
        wizard.action_import()
        self.assertEqual(wizard.file, before)


@tagged('post_install', '-at_install')
class TestSampleExport(TransactionCase):
    """Le fichier d'exemple livre avec le module, de bout en bout.

    Trois lignes, trois issues differentes : matricule exact, correspondance
    floue a arbitrer, nouvelle personne. C'est le scenario de recette.
    """

    def test_sample_export_produces_the_three_expected_outcomes(self):
        path = os.path.join(os.path.dirname(__file__), 'exemple_export.csv')
        with open(path, 'rb') as handle:
            content = handle.read()

        # Ligne 1 : la personne existe deja sous ce matricule.
        self.env['his.person'].create({
            'matricule_institutionnel': 'HIS-2023-000090-6',
            'name': "Amina Haddad",
            'type_personne': 'etudiant',
            'source_system': 'google_sheets',
        })
        # Ligne 2 : la personne existe, sans matricule dans la feuille.
        self.env['his.person'].create({
            'name': "Youssef Idrissi",
            'email_personnel': 'youssef.idrissi@example.ma',
            'phone': '0600000005',
            'type_personne': 'candidat',
            'source_system': 'manual',
        })
        # Ligne 3 : inconnue au bataillon.

        wizard = self.env['his.person.import'].create({
            'file': base64.b64encode(content),
            'filename': 'exemple_export.csv',
        })
        wizard.action_import()

        outcomes = {line.external_ref: line.outcome for line in wizard.line_ids}
        self.assertEqual(outcomes['ADM-2023-0090'], 'updated')
        self.assertEqual(outcomes['ADM-2024-0117'], 'flagged')
        self.assertEqual(outcomes['ADM-2024-0118'], 'created')
        self.assertEqual(wizard.flagged_count, 1)
        self.assertEqual(wizard.conflict_count, 0)

        new_person = wizard.line_ids.filtered(
            lambda line: line.external_ref == 'ADM-2024-0118'
        ).person_id
        self.assertRegex(new_person.matricule_institutionnel, r'^HIS-\d{4}-\d{6}-[0-9X]$')
        self.assertEqual(new_person.numero_carte, 'CARD-0118')
