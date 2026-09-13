# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un test par regle du pont Campus+. Il echoue si une regle saute."""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.campus_teacher_management.tests.common import CampusCommon


@tagged('post_install', '-at_install')
class TestCampusIdentityBridge(CampusCommon):

    def setUp(self):
        super().setUp()
        self.Person = self.env['his.person']
        self.Partner = self.env['res.partner']

    def _applicant(self, name="Fatma Maamri", **vals):
        return self._make_applicant(name, partner_phone="0661223344", **vals)

    def _select(self, applicant):
        # L'ecriture d'etat est ce que fait action_campus_select ; le passage
        # par l'action elle-meme est couvert par test_embauche.
        applicant.campus_hiring_state = 'invited'

    # --- Creation ------------------------------------------------------------

    def test_avant_select_aucune_fiche(self):
        applicant = self._applicant()
        self.assertFalse(applicant.his_person_id)
        self.assertFalse(self.Person.search([('source_system', '=', 'campus_plus'),
                                             ('external_ref', '=', str(applicant.id))]))

    def test_select_cree_un_candidat_sans_matricule_sur_le_meme_contact(self):
        applicant = self._applicant()
        partner = applicant.partner_id
        partenaires = self.Partner.search_count([])

        self._select(applicant)

        person = applicant.his_person_id
        self.assertEqual(person.type_personne, 'candidat')
        self.assertEqual(person.source_system, 'campus_plus')
        self.assertFalse(person.matricule_institutionnel)
        self.assertEqual(person.partner_id, partner)
        self.assertEqual(self.Partner.search_count([]), partenaires)
        self.assertIn(self.env.ref('his_person_core.categ_partner_identite'), partner.category_id)

    def test_rejouer_l_etape_ne_duplique_pas(self):
        applicant = self._applicant()
        self._select(applicant)
        personnes = self.Person.search_count([])
        applicant.campus_hiring_state = 'not_selected'
        applicant.campus_hiring_state = 'invited'
        self.assertEqual(self.Person.search_count([]), personnes)

    def test_une_etape_plus_loin_declenche_aussi(self):
        applicant = self._applicant()
        applicant.campus_hiring_state = 'meeting_1'
        self.assertTrue(applicant.his_person_id)

    # --- Rapprochement -------------------------------------------------------

    def test_correspondance_probable_proposee_puis_confirmee(self):
        existante = self.Person.sudo().create({
            'name': "Maamri Fatma", 'type_personne': 'candidat', 'source_system': 'manual',
            'email_personnel': "fatma.maamri@example.com", 'phone': "0661223344",
        })
        applicant = self._applicant()
        self._select(applicant)

        self.assertFalse(applicant.his_person_id)
        self.assertEqual(applicant.his_person_candidate_id, existante)

        applicant.action_confirm_person_match()
        self.assertEqual(applicant.his_person_id, existante)
        self.assertEqual(existante.matched_by, self.env.user)
        # Adresse de la fiche portee par email_personnel, pas par le contact :
        # la candidature garde donc son propre contact.
        self.assertNotEqual(applicant.partner_id, existante.partner_id)
        self.assertEqual(applicant.email_from, "fatma.maamri@example.com")

    def test_correspondance_probable_refusee_cree_une_fiche_distincte(self):
        existante = self.Person.sudo().create({
            'name': "Maamri Fatma", 'type_personne': 'candidat', 'source_system': 'manual',
            'email_personnel': "fatma.maamri@example.com", 'phone': "0661223344",
        })
        applicant = self._applicant()
        self._select(applicant)
        applicant.action_reject_person_match()
        self.assertTrue(applicant.his_person_id)
        self.assertNotEqual(applicant.his_person_id, existante)
        self.assertFalse(applicant.his_person_candidate_id)

    def test_email_d_un_employe_rattache_sans_toucher_sa_fiche(self):
        employe = self.Person.sudo().create({
            'name': "Karim Benali", 'type_personne': 'employe', 'source_system': 'odoo_hr',
            'email': "karim.benali@example.com", 'phone': "0770000001",
        })
        applicant = self._make_applicant(
            "Benali Karim", email_from="karim.benali@example.com", partner_phone="0550999999",
        )
        self._select(applicant)

        self.assertEqual(applicant.his_person_id, employe)
        self.assertEqual(applicant.partner_id, employe.partner_id)
        employe.invalidate_recordset()
        self.assertEqual(employe.name, "Karim Benali")
        self.assertEqual(employe.email, "karim.benali@example.com")
        self.assertEqual(employe.phone, "0770000001")
        self.assertEqual(applicant.partner_phone, "0550999999")

    # --- Embauche ------------------------------------------------------------

    def test_embauche_reprend_la_fiche_et_emet_le_matricule(self):
        self._make_full_criteria_set()
        self.version.job_id = self.env['hr.job'].create({'name': "Poste pont"})
        self.version.action_publish()
        applicant = self._applicant(campus_scientific_rank='prof')
        applicant.action_campus_evaluate()
        self.env['campus.interview.slot'].create({
            'start_datetime': fields.Datetime.now() + timedelta(days=1),
            'duration': 0.5, 'round': '1', 'interviewer_id': self.env.user.id,
        })
        applicant.action_campus_select()
        person = applicant.his_person_id
        self.assertEqual(person.type_personne, 'candidat')

        applicant.campus_hiring_state = 'subjects_selected'
        applicant.action_campus_hire()

        employee = applicant.employee_id
        self.assertEqual(employee.person_id, person)
        self.assertEqual(person.type_personne, 'enseignant')
        self.assertRegex(person.matricule_institutionnel, r'^HIS-\d{4}-\d{6}-[0-9X]$')
