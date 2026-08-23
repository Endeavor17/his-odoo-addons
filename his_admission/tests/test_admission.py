# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un test par regle du dossier d'admission. Il echoue si une regle saute."""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAdmission(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.spec_licence = cls.env.ref('his_admission.spec_info_systemes')
        cls.spec_master = cls.env.ref('his_admission.spec_info_cyber_master')
        cls.spec_st = cls.env.ref('his_admission.spec_st_electronique')

    def _personne(self, name="Yacine Belkacem"):
        return self.env['his.person'].create({
            'name': name, 'type_personne': 'candidat', 'source_system': 'manual',
        })

    def _dossier(self, **vals):
        return self.env['his.engagement'].create({
            'person_id': vals.pop('person_id', None) or self._personne().id,
            'cycle': 'licence',
            'type_inscription': 'nouveau',
            'specialite_id': self.spec_licence.id,
            **vals,
        })

    # --- Pieces attendues ----------------------------------------------------

    def test_les_pieces_sont_generees_a_la_creation(self):
        dossier = self._dossier()
        self.assertTrue(dossier.document_ids)
        codes = set(dossier.document_ids.mapped('type_id.code'))
        self.assertIn('CNI', codes)
        self.assertIn('CONTRAT', codes)

    def test_un_master_demande_des_pieces_qu_une_licence_ne_demande_pas(self):
        licence = self._dossier()
        master = self._dossier(cycle='master', specialite_id=self.spec_master.id)

        codes_licence = set(licence.document_ids.mapped('type_id.code'))
        codes_master = set(master.document_ids.mapped('type_id.code'))

        self.assertNotIn('LIC', codes_licence)
        self.assertIn('LIC', codes_master)
        self.assertIn('RELEVE-UNIV', codes_master)

    def test_l_equivalence_ne_concerne_que_les_dossiers_en_equivalence(self):
        """Le classeur laissait la case vide sans dire si la piece manquait
        ou ne s'appliquait pas. Ici la ligne n'existe simplement pas."""
        ordinaire = self._dossier(bac_filiere='se')
        equivalent = self._dossier(bac_filiere='equivalence')

        self.assertNotIn('EQUIV', ordinaire.document_ids.mapped('type_id.code'))
        self.assertIn('EQUIV', equivalent.document_ids.mapped('type_id.code'))

    def test_changer_de_cycle_ajoute_sans_effacer(self):
        """Une piece deja cochee garde sa trace : elle a reellement ete recue."""
        dossier = self._dossier()
        cni = dossier.document_ids.filtered(lambda d: d.type_id.code == 'CNI')
        cni.fourni = True

        dossier.cycle = 'master'

        self.assertIn('LIC', dossier.document_ids.mapped('type_id.code'))
        self.assertTrue(cni.exists())
        self.assertTrue(cni.fourni)

    # --- Le verrou -----------------------------------------------------------

    def _dossier_pret(self):
        dossier = self._dossier()
        dossier.document_ids.filtered(lambda d: d.type_id.obligatoire).fourni = True
        dossier.action_encaisser_frais_inscription()
        dossier.action_encaisser_frais_scolarite()
        return dossier

    def test_inscrit_refuse_si_une_piece_obligatoire_manque(self):
        dossier = self._dossier_pret()
        manquante = dossier.document_ids.filtered(
            lambda d: d.type_id.code == 'CONTRAT',
        )
        manquante.fourni = False

        with self.assertRaises(ValidationError):
            dossier.etat = 'inscrit'

        manquante.fourni = True
        dossier.etat = 'inscrit'
        self.assertEqual(dossier.etat, 'inscrit')

    def test_inscrit_refuse_si_les_droits_ne_sont_pas_encaisses(self):
        dossier = self._dossier()
        dossier.document_ids.filtered(lambda d: d.type_id.obligatoire).fourni = True
        dossier.action_encaisser_frais_inscription()
        # La scolarite reste due : le classeur ne montre aucune ligne Inscrit
        # sans ces deux droits regles.

        with self.assertRaises(ValidationError):
            dossier.etat = 'inscrit'

        dossier.action_encaisser_frais_scolarite()
        dossier.etat = 'inscrit'
        self.assertEqual(dossier.etat, 'inscrit')

    def test_une_piece_facultative_ne_bloque_pas(self):
        dossier = self._dossier_pret()
        facultative = dossier.document_ids.filtered(
            lambda d: d.type_id.code == 'TRANSFERT',
        )
        self.assertTrue(facultative)
        self.assertFalse(facultative.fourni)

        dossier.etat = 'inscrit'
        self.assertEqual(dossier.etat, 'inscrit')

    def test_admis_n_exige_rien(self):
        """Le verrou porte sur l'inscription, pas sur l'admission."""
        dossier = self._dossier()
        dossier.etat = 'admis'
        self.assertEqual(dossier.etat, 'admis')

    # --- Eligibilite ---------------------------------------------------------

    def test_eligibilite_mi(self):
        """Le cas MI du classeur : (13,37 x 2 + 8,5) / 3 = 11,75."""
        dossier = self._dossier(bac_moyenne=13.37, note_math=8.5)
        self.assertAlmostEqual(dossier.moyenne_ponderee, 11.75, places=2)
        self.assertEqual(dossier.eligibilite, 'eligible')

    def test_eligibilite_st(self):
        """Le cas ST du classeur : (11,22 x 2 + 13,5 + 10,5) / 4 = 11,61."""
        dossier = self._dossier(
            specialite_id=self.spec_st.id,
            bac_moyenne=11.22, note_math=13.5, note_physique=10.5,
        )
        self.assertAlmostEqual(dossier.moyenne_ponderee, 11.61, places=2)
        self.assertEqual(dossier.eligibilite, 'eligible')

    def test_st_sous_le_seuil_est_a_verifier(self):
        """Le cas que le classeur rate.

        Sa cellule C20 compare `D18`, une cellule de TEXTE, au lieu de `C18`
        qui porte la moyenne. Excel juge tout texte superieur a tout nombre :
        la branche ST repondait ELIGIBLE quelle que soit la moyenne, et un
        dossier sous le seuil passait sans que personne le voie.
        """
        dossier = self._dossier(
            specialite_id=self.spec_st.id,
            bac_moyenne=10.5, note_math=10.0, note_physique=10.0,
        )
        self.assertLess(dossier.moyenne_ponderee, 11.0)
        self.assertEqual(dossier.eligibilite, 'a_verifier')

    def test_un_plancher_est_eliminatoire_malgre_une_bonne_moyenne(self):
        """Une excellente moyenne ne rachete pas une note de maths sous le minimum.

        Le plancher est pose ici et non dans les donnees du module : aucune
        valeur de plancher n'est livree, faute de source fiable (cf. le
        commentaire de his_domaine_data.xml). Le test verifie le mecanisme,
        pas une valeur inventee.
        """
        self.env.ref('his_admission.domaine_mi').min_math = 10.0
        dossier = self._dossier(bac_moyenne=18.0, note_math=4.0)
        self.assertGreater(dossier.moyenne_ponderee, 11.0)
        self.assertEqual(dossier.eligibilite, 'a_verifier')
        self.assertIn("maths", dossier.eligibilite_motif)

    # --- Reinscription -------------------------------------------------------

    def test_reinscription_est_un_second_engagement_pas_un_statut(self):
        """Le classeur rangeait Re-Registration parmi les statuts. Une
        reinscription est un second parcours sur la meme personne."""
        personne = self._personne("Sofia Hamidi")
        premier = self._dossier(person_id=personne.id)
        premier.etat = 'abandonne'
        second = self._dossier(person_id=personne.id, type_inscription='reinscription')

        self.assertEqual(len(personne.engagement_ids), 2)
        self.assertNotEqual(premier, second)
        self.assertEqual(
            self.env['his.person'].search_count(
                [('matricule_institutionnel', '=', personne.matricule_institutionnel)],
            ), 1,
        )

    # --- Passation Ventes -> Admission ---------------------------------------

    def test_pre_admission_fait_passer_l_engagement_a_admis(self):
        conseillere = self.env.ref('his_crm_pipeline.user_aicha')
        lead = self.env['crm.lead'].create({
            'name': "Candidature Licence",
            'contact_name': "Nadir Bouzid",
            'email_from': "nadir.bouzid@example.com",
            'team_id': self.env.ref('his_crm_pipeline.crm_team_ventes').id,
            'stage_id': self.env.ref('his_crm_pipeline.stage_vente_contact_etabli').id,
            'user_id': conseillere.id,
        })
        engagement = lead.his_person_id.engagement_ids
        self.assertEqual(engagement.etat, 'prospect')

        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_pre_admis')

        self.assertEqual(engagement.etat, 'admis')
        self.assertEqual(engagement.conseiller_id, conseillere)
        self.assertEqual(engagement.lead_id, lead)

    def test_un_dossier_deja_inscrit_ne_redescend_pas(self):
        dossier = self._dossier_pret()
        dossier.etat = 'inscrit'
        lead = self.env['crm.lead'].create({
            'name': "Repassage",
            'team_id': self.env.ref('his_crm_pipeline.crm_team_ventes').id,
            'his_person_id': dossier.person_id.id,
        })

        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_pre_admis')

        self.assertEqual(dossier.etat, 'inscrit')

    # --- Acces ---------------------------------------------------------------

    def test_la_conseillere_ventes_lit_mais_n_ecrit_pas(self):
        """L'Admission est une unite distincte : elle seule valide le dossier."""
        dossier = self._dossier()
        conseillere = self.env['res.users'].create({
            'name': "Conseillere test",
            'login': "conseillere_admission_test",
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('sales_team.group_sale_salesman').id,
            ])],
        })

        self.assertTrue(dossier.with_user(conseillere).read(['etat']))

        with self.assertRaises(AccessError):
            dossier.with_user(conseillere).write({'numero_etudiant': "999"})

    def test_le_guichet_encaisse_mais_ne_touche_a_rien_d_autre(self):
        """Le guichet n'a que la lecture : le bouton est sa seule action.

        C'est ce qui separe « enregistrer un encaissement » de « modifier un
        dossier ». Un guichetier ne corrige pas une note de BAC, meme par API.
        """
        dossier = self._dossier()
        guichetier = self.env['res.users'].create({
            'name': "Guichet test",
            'login': "guichet_test",
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('his_admission.group_his_finance').id,
            ])],
        })

        with self.assertRaises(AccessError):
            dossier.with_user(guichetier).write({'bac_moyenne': 20.0})

        dossier.with_user(guichetier).action_encaisser_frais_inscription()
        self.assertTrue(dossier.frais_inscription_payes)

    # --- Le gagne suit l'encaissement, pas la decision -----------------------

    def _lead_pre_admis(self):
        lead = self.env['crm.lead'].create({
            'name': "Candidature a convertir",
            'contact_name': "Lyes Merabet",
            'email_from': "lyes.merabet@example.com",
            'team_id': self.env.ref('his_crm_pipeline.crm_team_ventes').id,
            'stage_id': self.env.ref('his_crm_pipeline.stage_vente_contact_etabli').id,
        })
        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_pre_admis')
        return lead

    def test_la_pre_admission_ne_gagne_pas_le_lead(self):
        """Une decision des Ventes n'est pas une conversion."""
        lead = self._lead_pre_admis()
        self.assertFalse(lead.stage_id.is_won)

    def test_l_encaissement_gagne_le_lead(self):
        lead = self._lead_pre_admis()
        dossier = lead._his_engagement()
        self.assertEqual(dossier.etat, 'admis')

        dossier.action_encaisser_frais_inscription()

        self.assertEqual(
            lead.stage_id, self.env.ref('his_crm_pipeline.stage_vente_frais_payes'),
        )
        self.assertTrue(lead.stage_id.is_won)

    def test_les_ventes_ne_peuvent_pas_gagner_un_lead_a_la_main(self):
        """Meme un administrateur, meme par API : sans encaissement, pas de gagne."""
        lead = self._lead_pre_admis()

        with self.assertRaises(ValidationError):
            lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_frais_payes')

    def test_la_scolarite_seule_ne_gagne_pas_le_lead(self):
        """Seuls les frais d'inscription non remboursables convertissent."""
        lead = self._lead_pre_admis()
        dossier = lead._his_engagement()

        dossier.action_encaisser_frais_scolarite()

        self.assertNotEqual(
            lead.stage_id, self.env.ref('his_crm_pipeline.stage_vente_frais_payes'),
        )
