# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un test par regle du matricule institutionnel. Il echoue si une regle saute."""
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.his_person_core.models.his_person import (
    MATRICULE_RE,
    _compute_matricule_checksum,
)


@tagged('post_install', '-at_install')
class TestMatricule(TransactionCase):

    def _person(self, **vals):
        return self.env['his.person'].create({
            'name': "Test Personne",
            'type_personne': 'etudiant',
            'source_system': 'manual',
            **vals,
        })

    # --- Regle 1 : format complet, cle de controle comprise -----------------

    def test_matricule_format(self):
        person = self._person()
        self.assertRegex(person.matricule_institutionnel, r'^HIS-\d{4}-\d{6}-[0-9X]$')
        self.assertTrue(MATRICULE_RE.match(person.matricule_institutionnel))

    def test_matricule_checksum_matches_sequential_part(self):
        """La cle stockee est bien celle des 6 chiffres qui la precedent."""
        person = self._person()
        sequential = person.matricule_institutionnel.split('-')[2]
        expected = _compute_matricule_checksum(sequential)
        self.assertEqual(person.matricule_institutionnel[-1], expected)

    # --- Regle 2 : la fonction de cle, isolee du modele et de la sequence ---

    def test_checksum_known_vectors(self):
        """Vecteurs calcules a la main : mod 11, poids 2..7 de droite a gauche."""
        # 000001 -> 1*2 = 2       -> 2 % 11 = 2
        # 000002 -> 2*2 = 4       -> 4
        # 000004 -> 4*2 = 8       -> 8
        # 000005 -> 5*2 = 10      -> reste 10 -> 'X'
        # 000010 -> 1*3 = 3       -> 3
        # 000123 -> 3*2+2*3+1*4 = 16 -> 16 % 11 = 5
        # 123456 -> 7+12+15+16+15+12 = 77 -> 77 % 11 = 0
        # 999999 -> 9*27 = 243    -> 243 % 11 = 1
        for sequential, expected in [
            ('000001', '2'),
            ('000002', '4'),
            ('000004', '8'),
            ('000005', 'X'),
            ('000010', '3'),
            ('000123', '5'),
            ('123456', '0'),
            ('999999', '1'),
        ]:
            self.assertEqual(
                _compute_matricule_checksum(sequential), expected,
                "cle attendue %s pour %s" % (expected, sequential),
            )

    def test_checksum_accepts_int_and_pads(self):
        self.assertEqual(_compute_matricule_checksum(1), '2')
        self.assertEqual(_compute_matricule_checksum('1'), '2')

    def test_checksum_rejects_non_numeric(self):
        with self.assertRaises(ValueError):
            _compute_matricule_checksum('00A001')

    # --- Regle 3 : unicite --------------------------------------------------

    def test_matricule_unique(self):
        self._person(matricule_institutionnel='HIS-2024-000042-7')
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self._person(matricule_institutionnel='HIS-2024-000042-7')

    # --- Regle 4 : une valeur fournie est conservee telle quelle ------------

    def test_explicit_matricule_is_preserved(self):
        person = self._person(matricule_institutionnel='HIS-2021-000777-3')
        self.assertEqual(person.matricule_institutionnel, 'HIS-2021-000777-3')

    def test_legacy_matricule_without_checksum_is_stored_not_rejected(self):
        """Une valeur anterieure a ce module n'a pas de cle : on la stocke quand meme.

        La rejeter ferait perdre des matricules reels deja distribues. C'est a
        l'import (his_person_sync_sheets) de signaler ce qui est malforme, pas
        au socle de refuser la donnee existante.
        """
        person = self._person(matricule_institutionnel='HIS-2023-000015')
        self.assertEqual(person.matricule_institutionnel, 'HIS-2023-000015')
        self.assertFalse(MATRICULE_RE.match(person.matricule_institutionnel))

    def test_matricule_is_never_reissued(self):
        person = self._person()
        original = person.matricule_institutionnel
        with self.assertRaises(ValidationError):
            person.write({'matricule_institutionnel': 'HIS-2030-000001-2'})
        self.assertEqual(person.matricule_institutionnel, original)

    # --- Regle 5 : l'annee vient de matricule_sequence_date -----------------

    def test_sequence_date_drives_year_prefix(self):
        person = self._person(matricule_sequence_date='2022-09-01')
        self.assertTrue(
            person.matricule_institutionnel.startswith('HIS-2022-'),
            person.matricule_institutionnel,
        )
        self.assertNotIn('matricule_sequence_date', person._fields)

    # --- Regle 6 : un seul compteur, tous types confondus -------------------

    def test_counter_is_shared_across_person_types(self):
        first = self._person(type_personne='employe', matricule_sequence_date='2020-03-01')
        second = self._person(type_personne='etudiant', matricule_sequence_date='2020-03-01')
        third = self._person(type_personne='enseignant', matricule_sequence_date='2020-03-01')
        numbers = [int(p.matricule_institutionnel.split('-')[2]) for p in (first, second, third)]
        self.assertEqual(numbers[1], numbers[0] + 1)
        self.assertEqual(numbers[2], numbers[1] + 1)
        self.assertEqual(len({p.matricule_institutionnel for p in (first, second, third)}), 3)

    # --- Regle 7 : la fiche est creable a la main depuis l'interface --------

    def test_manual_creation_needs_no_partner(self):
        """Saisie manuelle : la delegation cree le contact, l'utilisateur non.

        partner_id est required, mais il n'est renseigne qu'au create par la
        delegation. S'il apparait vide dans le formulaire, le client web
        bloque la sauvegarde sur « champs requis manquants » — un champ que
        l'utilisateur ne peut pas remplir.
        """
        arch = self.env['his.person'].get_view(
            view_id=self.env.ref('his_person_core.view_his_person_form').id,
            view_type='form',
        )['arch']
        self.assertIn(
            'invisible="not partner_id"', arch,
            "partner_id visible et vide bloquerait toute creation manuelle",
        )
        person = self.env['his.person'].create({
            'name': "Saisie Manuelle",
            'type_personne': 'candidat',
            'source_system': 'manual',
        })
        self.assertTrue(person.partner_id, "la delegation n'a pas cree de contact")
        self.assertEqual(person.partner_id.name, "Saisie Manuelle")
