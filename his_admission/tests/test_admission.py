# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un test par regle du dossier d'admission. Il echoue si une regle saute."""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


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

    def _conseillere(self):
        """Une vraie conseillere, avec ses droits reels.

        Les tests tournent en superuser, qui contourne toute regle d'acces :
        un parcours joue ainsi ne prouve rien sur ce qu'une conseillere peut
        reellement faire. Celui-ci passe par with_user(), parce que les deux
        gestes qu'il verifie declenchent des ecritures sur le dossier — dont
        elle n'a QUE la lecture.
        """
        equipe = self.env.ref('his_crm_pipeline.crm_team_ventes')
        user = self.env['res.users'].create({
            'name': "Conseillere parcours",
            'login': "conseillere_parcours",
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('his_crm_pipeline.group_admissions_conseiller').id,
            ])],
        })
        self.env['crm.team.member'].create({
            'crm_team_id': equipe.id, 'user_id': user.id,
        })
        return user

    def test_le_parcours_des_ventes_tient_avec_les_droits_d_une_conseillere(self):
        """La pre-admission, jouee par la conseillere elle-meme.

        Son geste cree une fiche personne et ouvre un dossier : deux ecritures
        sur des modeles ou elle n'a pas le droit d'ecrire. Ce sont des
        consequences de sa decision, pas des modifications qu'elle s'autorise —
        d'ou le sudo() cote serveur. Sans lui, le seul geste legitime des
        Ventes leve une erreur de droits.

        L'etape est la PRE-ADMISSION depuis l'hypothese A1 : c'est la que le
        pont ouvre la fiche, et non plus au premier contact.
        """
        conseillere = self._conseillere()
        Lead = self.env['crm.lead'].with_user(conseillere)
        lead = Lead.create({
            'name': "Candidature Licence",
            'contact_name': "Nadir Bouzid",
            'email_from': "nadir.bouzid@example.com",
            'team_id': self.env.ref('his_crm_pipeline.crm_team_ventes').id,
            'stage_id': self.env.ref('his_crm_pipeline.stage_vente_pris_en_charge').id,
            'user_id': conseillere.id,
        })
        self.assertFalse(lead.his_person_id, "Avant la pre-admission, aucune fiche.")

        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_pre_admis')

        self.assertTrue(lead.his_person_id, "La pre-admission ouvre la fiche.")
        engagement = lead.his_person_id.sudo().engagement_ids
        # Pas de matricule : il attend l'encaissement des frais d'inscription.
        self.assertFalse(lead.his_person_id.sudo().matricule_institutionnel)
        self.assertEqual(engagement.etat, 'admis')
        self.assertEqual(engagement.conseiller_id, conseillere)
        self.assertEqual(engagement.lead_id, lead)

    def test_la_conseillere_ne_peut_toujours_pas_ecrire_le_dossier(self):
        """Le sudo du parcours ne lui ouvre pas le dossier pour autant."""
        conseillere = self._conseillere()
        lead = self.env['crm.lead'].with_user(conseillere).create({
            'name': "Candidature bis",
            'contact_name': "Sami Larbi",
            'email_from': "sami.larbi@example.com",
            'team_id': self.env.ref('his_crm_pipeline.crm_team_ventes').id,
            'stage_id': self.env.ref('his_crm_pipeline.stage_vente_pre_admis').id,
        })
        dossier = lead._his_engagement()
        self.assertTrue(dossier, "La pre-admission doit avoir ouvert le dossier")
        with self.assertRaises(AccessError):
            dossier.with_user(conseillere).write({'numero_etudiant': "123"})

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
                self.env.ref('his_crm_pipeline.group_admissions_conseiller').id,
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

    def test_les_actions_ont_un_domaine_et_un_contexte_evaluables(self):
        """Le piege %(xmlid)d, verrouille — cf. his_crm_pipeline pour le detail."""
        actions = self.env['ir.actions.act_window'].search([]).filtered(
            lambda a: a.get_external_id().get(a.id, '').startswith('his_admission.'),
        )
        self.assertTrue(actions, "Aucune action trouvee : le test ne verifie rien.")
        contexte = {'uid': self.env.uid, 'context': {}, 'active_id': 1, 'active_ids': []}
        for action in actions:
            self.assertNotIn('%(', action.domain or '', action.display_name)
            self.assertNotIn('%(', action.context or '', action.display_name)
            safe_eval(action.domain or '[]', dict(contexte))
            safe_eval(action.context or '{}', dict(contexte))

    # --- HIS Lead Score ------------------------------------------------------

    def _lead_score(self, **vals):
        return self.env['crm.lead'].create({
            'name': "Candidature scoree",
            'team_id': self.env.ref('his_crm_pipeline.crm_team_ventes').id,
            **vals,
        })

    def test_score_maximal(self):
        """BAC 16, maths 15 en informatique, motivation remplie : 6 + 3 + 1."""
        lead = self._lead_score(
            specialite_id=self.spec_licence.id,
            bac_moyenne=16.0, note_math=15.0,
            motivation_his="Reputation de l'ecole.",
        )
        self.assertEqual(lead.score_academique, 10)

    def test_les_trois_paliers_du_bac(self):
        for moyenne, attendu in ((15.0, 6), (13.0, 4), (10.0, 2)):
            lead = self._lead_score(
                specialite_id=self.spec_licence.id,
                bac_moyenne=moyenne, note_math=15.0,
            )
            # 3 pts de ponderee (moyenne >= 12 sauf dernier cas) + 0 motivation
            ponderee = (moyenne + 15.0) / 2
            self.assertEqual(
                lead.score_academique,
                attendu + (3 if ponderee >= 12 else 2),
                "BAC %s" % moyenne,
            )

    def test_la_moyenne_ponderee_suit_la_majeure(self):
        """Deux formules, deduites des notes que le domaine pondere."""
        info = self._lead_score(
            specialite_id=self.spec_licence.id, bac_moyenne=10.0, note_math=14.0,
        )
        # (10 + 14) / 2 = 12 -> 3 pts, plus 2 pts de BAC
        self.assertEqual(info.score_academique, 5)

        electronique = self._lead_score(
            specialite_id=self.spec_st.id,
            bac_moyenne=10.0, note_math=14.0, note_physique=6.0,
        )
        # (10 + 14 + 6) / 3 = 10 -> 2 pts, plus 2 pts de BAC
        self.assertEqual(electronique.score_academique, 4)

    def test_psychologie_et_droit_n_ont_pas_de_moyenne_ponderee(self):
        """Zero point, pas deux : le bareme saute l'etape pour ces majeures.

        Consequence a connaitre : ces candidats plafonnent a 7 sur 10 et se
        classent donc systematiquement sous les autres dans la file
        d'affectation. C'est le bareme fourni, pas un effet de bord du code.
        """
        lead = self._lead_score(
            specialite_id=self.env.ref('his_admission.spec_ss_psycho').id,
            bac_moyenne=18.0, motivation_his="Vocation.",
        )
        self.assertEqual(lead.score_academique, 7)
        self.assertIn("non applicable", lead.score_detail)

    def test_une_note_exigee_manquante_ne_rapporte_pas_de_ponderee(self):
        lead = self._lead_score(
            specialite_id=self.spec_st.id, bac_moyenne=18.0, note_math=15.0,
        )
        # Physique exigee en electronique, non saisie : ponderee incalculable.
        self.assertEqual(lead.score_academique, 6)

    def test_la_motivation_vaut_un_point_si_l_une_des_deux_est_remplie(self):
        base = {'specialite_id': self.spec_licence.id, 'bac_moyenne': 16.0,
                'note_math': 16.0}
        self.assertEqual(self._lead_score(**base).score_academique, 9)
        self.assertEqual(
            self._lead_score(motivation_majeure="Passion.", **base).score_academique, 10,
        )
        self.assertEqual(
            self._lead_score(motivation_his="   ", **base).score_academique, 9,
            "Un champ rempli d'espaces n'est pas une motivation.",
        )

    def test_le_score_n_est_pas_saisissable(self):
        """Il ordonne la file d'affectation : il doit venir des notes."""
        lead = self._lead_score(
            specialite_id=self.spec_licence.id, bac_moyenne=16.0, note_math=16.0,
            score_academique=99,
        )
        self.assertEqual(lead.score_academique, 9)

    def test_le_dossier_reprend_les_donnees_de_capture(self):
        lead = self._lead_score(
            contact_name="Ines Ferhat",
            email_from="ines.ferhat@example.com",
            specialite_id=self.spec_st.id,
            bac_moyenne=13.0, note_math=14.0, note_physique=12.0,
            # La pre-admission : c'est la que le dossier s'ouvre (hypothese A1).
            stage_id=self.env.ref('his_crm_pipeline.stage_vente_pre_admis').id,
        )
        dossier = lead._his_engagement()
        self.assertEqual(dossier.specialite_id, self.spec_st)
        self.assertEqual(dossier.cycle, 'licence')
        self.assertAlmostEqual(dossier.bac_moyenne, 13.0, places=2)
        self.assertAlmostEqual(dossier.note_physique, 12.0, places=2)

    # --- Capture web (formulaire de candidature -> n8n) -----------------------

    def test_la_capture_web_ne_cree_aucune_fiche_personne(self):
        """Un lead capte par le formulaire n'emet PAS de matricule.

        C'est l'hypothese A1, restee ouverte : quelle etape declenche la fiche
        personne n'est pas tranchee par la Direction. Le pont d'identite se
        declenche a « Contact etabli » et sur create() aussi bien que sur
        write() — un lead cree directement dans cette etape emettrait donc un
        matricule a vie a quelqu'un qui n'a rempli qu'un formulaire.

        La capture web nait en « Nouveau (score) », et ce test est ce qui
        empeche que cela change par inadvertance.
        """
        avant = self.env['his.person'].search_count([])
        lead = self._lead_score(
            contact_name="Lina Cherif",
            email_from="lina.cherif@example.com",
            stage_id=self.env.ref('his_crm_pipeline.stage_vente_nouveau').id,
            specialite_id=self.spec_licence.id,
            bac_moyenne=15.0, note_math=14.0,
        )
        self.assertFalse(lead.his_person_id)
        self.assertFalse(lead.his_person_candidate_id)
        self.assertEqual(self.env['his.person'].search_count([]), avant)

    def test_la_capture_web_laisse_le_lead_sans_proprietaire(self):
        """Sans quoi la file « Leads a affecter » resterait vide.

        his_crm_pipeline vide user_id a la creation en « Nouveau (score) ». Le
        compte de service qui porte l'appel n8n serait sinon inscrit comme
        commercial sur chaque candidature.
        """
        lead = self._lead_score(
            stage_id=self.env.ref('his_crm_pipeline.stage_vente_nouveau').id,
        )
        self.assertFalse(lead.user_id)

    def test_le_score_client_est_conserve_sans_influencer_le_calcul(self):
        """Il vient du navigateur du candidat : on le garde, on ne s'y fie pas."""
        lead = self._lead_score(
            specialite_id=self.spec_licence.id,
            bac_moyenne=16.0, note_math=16.0,
            score_client=99,
        )
        self.assertEqual(lead.score_client, 99)
        self.assertEqual(lead.score_academique, 9)

    def test_le_consentement_et_les_renseignements_du_formulaire_arrivent(self):
        """Loi 18-07 : le consentement se prouve par une date, pas par une case."""
        lead = self._lead_score(
            wilaya="Blida",
            bac_annee="2026",
            bac_filiere="Sciences experimentales",
            consentement_18_07=True,
            date_consentement="2026-09-02 14:03:11",
        )
        self.assertEqual(lead.wilaya, "Blida")
        self.assertEqual(lead.bac_annee, "2026")
        self.assertEqual(lead.bac_filiere, "Sciences experimentales")
        self.assertTrue(lead.consentement_18_07)
        self.assertTrue(lead.date_consentement)

    def test_une_note_absente_n_est_pas_une_note_a_zero(self):
        """Le formulaire envoie null, pas 0, pour une note qu'il n'a pas demandee.

        Droit public ne pondere ni maths ni physique : la moyenne ponderee
        n'est pas applicable, et le lead vaut ses points de BAC seuls. Un zero
        envoye a la place du vide se lirait comme une vraie note nulle.
        """
        lead = self._lead_score(
            specialite_id=self.env.ref('his_admission.spec_droit_public').id,
            bac_moyenne=15.0,
            motivation_his="Le droit public m'interesse.",
        )
        self.assertFalse(lead.note_math)
        self.assertFalse(lead.note_physique)
        self.assertEqual(lead.score_academique, 7)
        self.assertIn("non applicable", lead.score_detail)

    # --- Le matricule attend l'argent -----------------------------------------

    def test_le_matricule_est_emis_a_l_encaissement_et_pas_avant(self):
        """Hypothese A1 : le dossier s'ouvre a la pre-admission, le matricule
        s'emet a l'encaissement des frais d'inscription.

        Les frais sont non remboursables : c'est le premier engagement
        irreversible des DEUX cotes, donc le bon moment pour graver un
        identifiant a vie.
        """
        lead = self._lead_avec_dossier()
        personne = lead.his_person_id
        dossier = personne.engagement_ids[:1]
        self.assertTrue(dossier, "La pre-admission ouvre le dossier")
        self.assertFalse(
            personne.matricule_institutionnel,
            "Un candidat pre-admis n'a pas encore de matricule",
        )

        dossier.action_encaisser_frais_inscription()

        self.assertTrue(
            personne.matricule_institutionnel,
            "L'encaissement des frais d'inscription emet le matricule",
        )

    def test_un_candidat_perdu_avant_l_argent_ne_consomme_aucun_matricule(self):
        """La raison d'etre de tout ce changement.

        954 opportunites perdues sur 1558 dans le CRM reel : au premier
        contact, six numeros sur dix partaient a des gens qui ne seront jamais
        etudiants, et la sequence ne les rend jamais.
        """
        lead = self._lead_avec_dossier()
        personne = lead.his_person_id
        lead.action_set_lost(lost_reason_id=self.env.ref(
            'his_crm_pipeline.lost_reason_trop_cher').id)

        self.assertFalse(personne.matricule_institutionnel)

    # --- La carte etudiant ----------------------------------------------------

    def test_la_carte_ne_s_edite_que_sur_un_dossier_inscrit(self):
        """L'ecran « Cartes etudiant » ne liste que les inscrits.

        Sans verrou, on remplit sur un dossier admis des champs que cet ecran
        ignorera ensuite, sans que rien ne dise pourquoi — c'est arrive : un
        dossier admis portait une date de remise de carte, donc une carte
        remise a quelqu'un qui n'est pas encore inscrit.
        """
        arch = self.env.ref('his_admission.view_his_engagement_form_admission').arch
        for champ in ('carte_recue_it', 'carte_etudiant_informe', 'carte_date_remise'):
            self.assertIn(champ, arch)
        self.assertIn(
            "etat != 'inscrit'", arch,
            "Les champs de carte doivent etre verrouilles hors inscription",
        )

    def test_l_ecran_des_cartes_ne_montre_que_les_inscrits(self):
        """Le domaine de l'ecran est la raison d'etre du verrou ci-dessus : les
        deux doivent dire la meme chose, sinon le verrou protege le vide."""
        action = self.env.ref('his_admission.action_engagement_carte')
        self.assertIn("'inscrit'", action.domain)

    # --- Le dossier suit le lead ---------------------------------------------

    def _lead_avec_dossier(self, **vals):
        """Un lead parvenu a l'etape declencheuse : personne et dossier ouverts."""
        lead = self.env['crm.lead'].create({
            'name': "Candidature", 'contact_name': "Nadia Slimani",
            'email_from': "nadia.slimani@example.dz", 'phone': "0555443322",
            'team_id': self.env.ref('his_crm_pipeline.crm_team_ventes').id,
            'specialite_id': self.spec_licence.id, 'bac_moyenne': 13.5,
            'note_math': 12.0,
            **vals,
        })
        # La pre-admission : c'est la que le pont ouvre la fiche et le dossier
        # depuis l'hypothese A1. Le matricule, lui, attend l'encaissement.
        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_pre_admis')
        return lead

    def test_le_dossier_suit_les_corrections_du_lead(self):
        """Une correction saisie sur le lead doit atteindre le dossier.

        Avant, la recopie etait un ONE-SHOT : le dossier gardait a vie les
        valeurs du premier contact. Une conseillere qui corrigeait une moyenne
        de BAC voyait le lead changer et le dossier rester faux, sans le
        moindre signe.
        """
        lead = self._lead_avec_dossier()
        dossier = lead.his_person_id.engagement_ids[:1]
        self.assertEqual(dossier.bac_moyenne, 13.5)

        lead.write({'bac_moyenne': 16.75, 'note_math': 17.0})

        self.assertEqual(dossier.bac_moyenne, 16.75)
        self.assertEqual(dossier.note_math, 17.0)

    def test_changer_de_specialite_sur_le_lead_change_le_dossier(self):
        lead = self._lead_avec_dossier()
        dossier = lead.his_person_id.engagement_ids[:1]

        lead.specialite_id = self.spec_master

        self.assertEqual(dossier.specialite_id, self.spec_master)
        self.assertEqual(dossier.cycle, 'master')

    def test_le_dossier_inscrit_ne_se_laisse_plus_ecraser(self):
        """Une fois l'inscription prononcee, le lead cesse d'etre la source.

        Sans cette borne, une conseillere rouvrant un vieux lead ecraserait des
        donnees verifiees sur le dossier d'un etudiant deja inscrit.

        La borne est « inscrit » et non « admis » : depuis l'hypothese A1 le
        dossier naît a la pre-admission et passe « admis » aussitot. S'arreter
        la fermait la fenetre avant qu'elle ne s'ouvre.
        """
        lead = self._lead_avec_dossier()
        dossier = lead.his_person_id.engagement_ids[:1]
        for doc in dossier.document_ids:
            doc.sudo().write({'fourni': True})
        dossier.sudo().write({
            'frais_inscription_payes': True, 'frais_scolarite_payes': True,
        })
        dossier.sudo().etat = 'inscrit'

        lead.write({'bac_moyenne': 19.0})

        self.assertEqual(
            dossier.bac_moyenne, 13.5,
            "Le dossier d'un inscrit garde ses valeurs",
        )

    # --- Le pipeline partage --------------------------------------------------

    def _agent_admission(self):
        user = self.env['res.users'].create({
            'name': "Agent Admission", 'login': "agent_adm",
            'email': "agent.adm@example.dz",
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('his_admission.group_his_admission').id,
            ])],
        })
        return user

    def test_la_regle_de_l_admission_part_de_contact_etabli(self):
        """La regle nomme ses etapes, resolues a l'installation par eval."""
        regle = self.env.ref('his_admission.rule_crm_lead_admission')
        domaine = safe_eval(regle.domain_force)
        etapes = next(v for champ, _op, v in domaine if champ == 'stage_id')
        self.assertIn(
            self.env.ref('his_crm_pipeline.stage_vente_contact_etabli').id, etapes)
        self.assertNotIn(
            self.env.ref('his_crm_pipeline.stage_vente_pris_en_charge').id, etapes)

    def test_l_admission_ne_voit_pas_la_production_de_contenu(self):
        """Une borne de sequence seule laissait passer le pipeline Contenu.

        Ses etapes portent des sequences bien plus hautes que celles des
        admissions : « au-dela de Contact etabli » les incluait toutes, et
        l'Admission voyait les demandes de campagne du Marketing. Constate en
        montant la demonstration.
        """
        agent = self._agent_admission()
        demande = self.env['crm.lead'].create({'name': "Campagne rentree"})
        demande.write({
            'team_id': self.env.ref('his_crm_pipeline.crm_team_contenu').id,
            'stage_id': self.env.ref('his_crm_pipeline.stage_contenu_production').id,
        })

        self.assertNotIn(demande, self.env['crm.lead'].with_user(agent).search([]))

    def test_l_admission_voit_les_candidats_des_le_premier_contact(self):
        """Un seul enregistrement, deux equipes : rien a synchroniser.

        Avant le premier contact la candidature appartient aux Ventes, et
        l'Admission n'a rien a en connaitre. Des que la conseillere a parle au
        candidat, elle le suit — meme si son dossier ne s'ouvrira qu'a la
        pre-admission.
        """
        agent = self._agent_admission()
        lead = self._lead_avec_dossier()
        avant = self.env['crm.lead'].create({
            'name': "Pas encore contacte",
            'team_id': self.env.ref('his_crm_pipeline.crm_team_ventes').id,
            'stage_id': self.env.ref('his_crm_pipeline.stage_vente_nouveau').id,
        })

        vus = self.env['crm.lead'].with_user(agent).search([])

        self.assertIn(lead, vus, "Le candidat contacte doit etre visible")
        self.assertNotIn(avant, vus, "Avant le premier contact, rien a voir")

    def test_l_admission_peut_deplacer_une_carte(self):
        """« Les deux cotes deplacent les cartes en phase » : litteralement le
        meme enregistrement, donc le mouvement est visible des deux cotes."""
        agent = self._agent_admission()
        lead = self._lead_avec_dossier()
        dossier_stage = self.env.ref('his_crm_pipeline.stage_vente_dossier')

        lead.with_user(agent).stage_id = dossier_stage

        self.assertEqual(lead.stage_id, dossier_stage)

    def test_l_admission_ne_cree_ni_ne_supprime_de_candidature(self):
        """Elle instruit un dossier, elle n'invente pas de candidat et n'en
        efface pas : creer reste un geste des Ventes ou de la capture web."""
        agent = self._agent_admission()
        with self.assertRaises(AccessError):
            self.env['crm.lead'].with_user(agent).create({'name': "Invente"})

    # --- Grille tarifaire et revenu deduit -----------------------------------

    def _cockpit(self):
        return self.env['his.dashboard'].get_dossiers('2020-01-01', '2100-01-01')

    def test_sans_tarif_le_cockpit_n_affiche_aucun_montant(self):
        """Un chiffre d'affaires invente est pire qu'un chiffre absent : il se
        cite en reunion. Tant que la grille est vide, la tuile n'existe pas."""
        self.env['his.tarif'].search([]).unlink()
        cles = [t['cle'] for t in self._cockpit()['tiles']]
        self.assertNotIn('revenu_attendu', cles)

    def test_avec_un_tarif_le_revenu_se_deduit(self):
        """Deduit, jamais saisi. C'est la difference avec GoHighLevel, ou 454
        opportunites sur 505 n'ont aucun montant parce qu'il fallait le taper.
        """
        self.env['his.tarif'].create({
            'specialite_id': self.spec_licence.id,
            'frais_inscription': 400000.0,
        })
        equipe = self.env.ref('his_crm_pipeline.crm_team_ventes')
        self.env['crm.lead'].create([{
            'name': "Candidat chiffrable %s" % i,
            'team_id': equipe.id,
            'specialite_id': self.spec_licence.id,
        } for i in range(2)])

        tuile = next(
            t for t in self._cockpit()['tiles'] if t['cle'] == 'revenu_attendu'
        )
        self.assertEqual(tuile['valeur'], 800000.0)
        self.assertEqual(tuile['unite'], "DA")

    def test_la_tuile_de_revenu_ouvre_ce_qu_elle_chiffre(self):
        """Meme regle que toutes les autres tuiles : un chiffre qu'on ne peut
        pas ouvrir doit etre cru sur parole."""
        self.env['his.tarif'].create({
            'specialite_id': self.spec_licence.id,
            'frais_inscription': 400000.0,
        })
        equipe = self.env.ref('his_crm_pipeline.crm_team_ventes')
        self.env['crm.lead'].create({
            'name': "Candidat chiffrable",
            'team_id': equipe.id,
            'specialite_id': self.spec_licence.id,
        })

        tuile = next(
            t for t in self._cockpit()['tiles'] if t['cle'] == 'revenu_attendu'
        )
        lus = self.env['crm.lead'].search_count(tuile['action']['domain'])
        self.assertEqual(lus * 400000.0, tuile['valeur'])

    def test_un_seul_tarif_actif_par_specialite(self):
        """Deux tarifs actifs pour la meme specialite donneraient deux revenus
        possibles, et le cockpit en choisirait un au hasard."""
        self.env['his.tarif'].create({
            'specialite_id': self.spec_licence.id, 'frais_inscription': 400000.0,
        })
        with self.assertRaises(ValidationError):
            self.env['his.tarif'].create({
                'specialite_id': self.spec_licence.id,
                'frais_inscription': 450000.0,
            })

    def test_desactiver_l_ancien_tarif_permet_d_en_creer_un_nouveau(self):
        """Changer de bareme reste possible : on desactive, on ne supprime pas.
        L'historique de ce qu'on facturait la rentree precedente reste lisible.
        """
        ancien = self.env['his.tarif'].create({
            'specialite_id': self.spec_licence.id, 'frais_inscription': 400000.0,
        })
        ancien.active = False
        nouveau = self.env['his.tarif'].create({
            'specialite_id': self.spec_licence.id, 'frais_inscription': 450000.0,
        })
        self.assertTrue(nouveau.id)

    def test_les_specialites_sans_tarif_remontent_en_qualite(self):
        """Une specialite non tarifee rend ses candidatures invisibles au
        revenu attendu, sans que rien ne le dise. La file le dit."""
        self.env['his.tarif'].search([]).unlink()
        equipes = self.env['his.dashboard']._equipes_admissions()
        files = self.env['his.dashboard']._admissions_qualite(equipes)
        libelles = [f['label'] for f in files]
        self.assertIn("Specialites sans tarif", libelles)
        sans = next(f for f in files if f['label'] == "Specialites sans tarif")
        self.assertGreater(sans['count'], 0)
