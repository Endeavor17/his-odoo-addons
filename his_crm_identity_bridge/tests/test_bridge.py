# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un test par regle du pont. Il echoue si une regle saute."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBridge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team_ventes = cls.env.ref('his_crm_pipeline.crm_team_ventes')
        cls.stage_pris_en_charge = cls.env.ref('his_crm_pipeline.stage_vente_pris_en_charge')
        # L'etape declencheuse, et non « Contact etabli » en dur : l'hypothese
        # A1 l'a placee a la pre-admission. Ces tests portent sur le MECANISME
        # — creer, rapprocher, ne pas dupliquer — pas sur le choix de l'etape,
        # qui reste un ir.config_parameter.
        cls.stage_declencheuse = cls.env.ref('his_crm_pipeline.stage_vente_pre_admis')

    def _lead(self, **vals):
        return self.env['crm.lead'].create({
            'name': "Candidature Licence",
            'contact_name': "Yacine Belkacem",
            'email_from': "yacine.belkacem@example.com",
            'phone': "0555112233",
            'team_id': self.team_ventes.id,
            'stage_id': self.stage_pris_en_charge.id,
            **vals,
        })

    # --- Creation ------------------------------------------------------------

    def test_premier_contact_cree_une_personne_un_partenaire_un_engagement(self):
        partenaires_avant = self.env['res.partner'].search_count([])
        lead = self._lead()
        self.assertFalse(lead.his_person_id)

        lead.stage_id = self.stage_declencheuse

        person = lead.his_person_id
        self.assertTrue(person)
        self.assertEqual(person.type_personne, 'candidat')
        self.assertEqual(person.source_system, 'odoo_crm')
        self.assertEqual(person.external_ref, str(lead.id))
        self.assertEqual(person.email_personnel, "yacine.belkacem@example.com")
        # PAS de matricule : un candidat entre dans le referentiel sans
        # numero. La sequence ne se recycle jamais, et six candidatures sur dix
        # sont perdues — en emettre un ici reviendrait a en bruler un par
        # candidature. Il est attribue a l'encaissement des frais
        # d'inscription (his_admission). Voir hypothese A1.
        self.assertFalse(person.matricule_institutionnel)

        # La delegation cree UN partenaire, pas deux. C'est le piege de
        # _inherits : un partenaire de trop et l'humain a deux fiches contact.
        self.assertEqual(self.env['res.partner'].search_count([]), partenaires_avant + 1)

        engagements = person.engagement_ids
        self.assertEqual(len(engagements), 1)
        # Le pont OUVRE le dossier a « prospect ». Son etat final ne lui
        # appartient plus : his_admission, quand il est installe, le fait
        # passer a « admis » dans la meme ecriture, puisque l'etape
        # declencheuse EST la pre-admission. On verifie donc qu'un dossier
        # existe et qu'il n'a pas saute au-dela de l'admission.
        self.assertIn(engagements.etat, ('prospect', 'admis'))

    def test_le_contact_du_lead_est_repris_et_non_duplique(self):
        partner = self.env['res.partner'].create({
            'name': "Sofia Hamidi", 'email': "sofia.hamidi@example.com",
        })
        partenaires_avant = self.env['res.partner'].search_count([])
        lead = self._lead(
            partner_id=partner.id, contact_name="Sofia Hamidi",
            email_from="sofia.hamidi@example.com", phone="0661000000",
        )

        lead.stage_id = self.stage_declencheuse

        self.assertEqual(lead.his_person_id.partner_id, partner)
        self.assertEqual(self.env['res.partner'].search_count([]), partenaires_avant)

    # --- Rapprochement -------------------------------------------------------

    def test_correspondance_deterministe_ne_duplique_pas(self):
        """Meme reference source : on retombe sur la fiche, on n'en cree pas une seconde."""
        lead = self._lead()
        lead.stage_id = self.stage_declencheuse
        person = lead.his_person_id

        # Un second lead portant la meme reference source que le premier : la
        # cle deterministe (external_ref, source_system) de his_person_core doit
        # le ramener sur la fiche existante.
        autre = self._lead(name="Doublon")
        autre.write({'his_person_id': False})
        self.env['his.person'].sudo().create({
            'name': "Homonyme", 'type_personne': 'candidat',
            'source_system': 'odoo_crm', 'external_ref': str(autre.id),
        })
        personnes_avant = self.env['his.person'].search_count([])
        autre.stage_id = self.stage_declencheuse
        self.assertEqual(self.env['his.person'].search_count([]), personnes_avant)
        self.assertTrue(autre.his_person_id)
        self.assertNotEqual(autre.his_person_id, person)

    def test_correspondance_probable_est_signalee_pas_rattachee(self):
        existante = self.env['his.person'].sudo().create({
            'name': "Yacine Belkacem",
            'type_personne': 'candidat',
            'source_system': 'manual',
            'email_personnel': "yacine.belkacem@example.com",
            'phone': "0555112233",
        })
        lead = self._lead()

        lead.stage_id = self.stage_declencheuse

        self.assertFalse(lead.his_person_id)
        self.assertEqual(lead.his_person_candidate_id, existante)
        self.assertGreater(lead.his_person_match_score, 0.0)
        self.assertFalse(existante.engagement_ids)

    def test_confirmation_rattache_et_trace(self):
        existante = self.env['his.person'].sudo().create({
            'name': "Yacine Belkacem",
            'type_personne': 'candidat',
            'source_system': 'manual',
            'email_personnel': "yacine.belkacem@example.com",
            'phone': "0555112233",
        })
        lead = self._lead()
        lead.stage_id = self.stage_declencheuse
        self.assertEqual(lead.his_person_candidate_id, existante)

        lead.action_confirm_person_match()

        self.assertEqual(lead.his_person_id, existante)
        self.assertFalse(lead.his_person_candidate_id)
        self.assertEqual(existante.match_method, 'probabilistic')
        self.assertTrue(existante.matched_by)
        self.assertIn(existante.engagement_ids.etat, ('prospect', 'admis'))

    def test_refus_cree_une_fiche_distincte(self):
        self.env['his.person'].sudo().create({
            'name': "Yacine Belkacem",
            'type_personne': 'candidat',
            'source_system': 'manual',
            'email_personnel': "yacine.belkacem@example.com",
            'phone': "0555112233",
        })
        lead = self._lead()
        lead.stage_id = self.stage_declencheuse

        lead.action_reject_person_match()

        self.assertTrue(lead.his_person_id)
        self.assertFalse(lead.his_person_candidate_id)
        self.assertEqual(lead.his_person_id.source_system, 'odoo_crm')

    # --- Idempotence et perimetre --------------------------------------------

    def test_repasser_par_l_etape_ne_cree_pas_de_seconde_fiche(self):
        lead = self._lead()
        lead.stage_id = self.stage_declencheuse
        person = lead.his_person_id
        personnes_avant = self.env['his.person'].search_count([])

        lead.stage_id = self.stage_pris_en_charge
        lead.stage_id = self.stage_declencheuse

        self.assertEqual(lead.his_person_id, person)
        self.assertEqual(self.env['his.person'].search_count([]), personnes_avant)
        self.assertEqual(len(person.engagement_ids), 1)

    def test_une_autre_equipe_ne_declenche_rien(self):
        """La Cellule d'Orientation ne cree pas d'identite, seules les Ventes."""
        lead = self._lead(team_id=self.env.ref('his_crm_pipeline.crm_team_orientation').id)
        lead.stage_id = self.stage_declencheuse
        self.assertFalse(lead.his_person_id)
        self.assertFalse(lead.his_person_candidate_id)

    def test_l_etape_declencheuse_est_parametrable(self):
        """A1 n'est pas tranche : changer d'etape doit rester un parametre."""
        self.env['ir.config_parameter'].sudo().set_param(
            'his_crm.identity_trigger_stage_xmlid',
            'his_crm_pipeline.stage_vente_dossier',
        )
        lead = self._lead()

        # « Contact etabli » est AVANT « Dossier » : en deca du declencheur
        # choisi, donc rien ne doit se creer.
        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_contact_etabli')
        self.assertFalse(lead.his_person_id)

        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_dossier')
        self.assertTrue(lead.his_person_id)

    def test_sauter_l_etape_declencheuse_cree_quand_meme_la_fiche(self):
        """Le declencheur est « parvenu a l'etape », pas « pose dessus ».

        Le kanban autorise de tirer une carte de « Pris en charge » droit vers
        « Dossier et pre-admission ». Avec une egalite stricte, ce geste
        ordinaire ne creait NI personne NI dossier : le candidat n'existait pas
        pour l'Admission, sans que rien ne le signale. Constate sur la base de
        recette — 2 candidatures en « Dossier » et 1 en « Pre-admis » sans
        aucun dossier.
        """
        # Le declencheur est ramene a « Contact etabli » pour ce test : il ne
        # reste sinon aucune etape ATTEIGNABLE au-dela de la pre-admission —
        # « Frais payes » exige un encaissement, donc un dossier, donc
        # precisement ce qu'on essaie de creer.
        self.env['ir.config_parameter'].sudo().set_param(
            'his_crm.identity_trigger_stage_xmlid',
            'his_crm_pipeline.stage_vente_contact_etabli',
        )
        lead = self._lead()
        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_dossier')

        self.assertTrue(
            lead.his_person_id,
            "Sauter l'etape declencheuse ne doit pas sauter l'identite",
        )
        self.assertTrue(lead.his_person_id.engagement_ids)

    def test_rester_avant_l_etape_declencheuse_ne_cree_rien(self):
        """La borne reste une borne : en deca, toujours rien."""
        lead = self._lead()
        self.assertFalse(lead.his_person_id)
        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_nouveau')
        self.assertFalse(lead.his_person_id)

    def test_le_pont_ouvre_UN_dossier_et_n_y_touche_plus(self):
        """Le pont ouvre l'engagement, et n'en cree jamais un second.

        Il ne verifie plus l'etat exact : depuis que l'etape declencheuse est
        la pre-admission, his_admission fait passer le dossier a « admis » dans
        la meme ecriture. Affirmer « prospect » ici reviendrait a tester un
        module dont celui-ci ne depend pas, et le resultat changerait selon les
        modules installes. Ce qui appartient au pont, c'est qu'il y ait UN
        dossier, et un seul.
        """
        lead = self._lead()
        lead.stage_id = self.stage_declencheuse
        person = lead.his_person_id
        self.assertEqual(len(person.engagement_ids), 1)

        # Revenir en arriere puis repasser n'en cree pas un second.
        lead.stage_id = self.stage_pris_en_charge
        lead.stage_id = self.stage_declencheuse
        self.assertEqual(len(person.engagement_ids), 1)
