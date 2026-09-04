# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un test par regle du module. Il echoue si une regle saute."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestPipeline(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team_ventes = cls.env.ref('his_crm_pipeline.crm_team_ventes')
        cls.team_contenu = cls.env.ref('his_crm_pipeline.crm_team_contenu')
        cls.stage_pris_en_charge = cls.env.ref('his_crm_pipeline.stage_vente_pris_en_charge')
        cls.stage_production = cls.env.ref('his_crm_pipeline.stage_contenu_production')
        cls.stage_approbation = cls.env.ref('his_crm_pipeline.stage_contenu_approbation')
        cls.type_copy = cls.env.ref('his_crm_pipeline.deliverable_type_copy')
        cls.type_design = cls.env.ref('his_crm_pipeline.deliverable_type_design')
        cls.type_video = cls.env.ref('his_crm_pipeline.deliverable_type_video')

    def _user(self, login, team=None):
        user = self.env['res.users'].create({
            'name': login,
            'login': login,
            'email': '%s@example.com' % login,
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('sales_team.group_sale_salesman_all_leads').id,
            ])],
        })
        if team:
            self.env['crm.team.member'].create({
                'crm_team_id': team.id, 'user_id': user.id,
            })
        return user

    # --- Verrou d'approbation des livrables ---------------------------------

    def test_approbation_bloquee_tant_qu_un_livrable_n_est_pas_approuve(self):
        lead = self.env['crm.lead'].create({
            'name': "Campagne rentree",
            'team_id': self.team_contenu.id,
            'stage_id': self.stage_production.id,
            'deliverable_ids': [
                (0, 0, {'type_id': self.type_copy.id, 'statut': 'approuve'}),
                (0, 0, {'type_id': self.type_design.id,
                        'statut': 'revision_interne'}),
            ],
        })
        with self.assertRaises(ValidationError):
            lead.stage_id = self.stage_approbation

        lead.deliverable_ids.filtered(
            lambda d: d.type_id == self.type_design
        ).statut = 'approuve'
        lead.stage_id = self.stage_approbation
        self.assertEqual(lead.stage_id, self.stage_approbation)

    def test_livrable_non_demande_ne_bloque_pas(self):
        """Un livrable non demande n'a pas de ligne, donc ne bloque rien.

        C'est ce que les anciens booleens disaient laborieusement : une ligne
        absente signifie « pas concerne », la ou un statut « a faire » sur un
        besoin decoche obligeait a lire deux champs pour comprendre la meme
        chose.
        """
        lead = self.env['crm.lead'].create({
            'name': "Post simple",
            'team_id': self.team_contenu.id,
            'stage_id': self.stage_production.id,
            'deliverable_ids': [
                (0, 0, {'type_id': self.type_copy.id, 'statut': 'approuve'}),
            ],
        })
        lead.stage_id = self.stage_approbation
        self.assertEqual(lead.stage_id, self.stage_approbation)

    def test_approbation_bloquee_si_le_livrable_est_ajoute_apres_coup(self):
        """La contrainte tient aussi quand c'est le livrable, et non l'etape, qui change."""
        lead = self.env['crm.lead'].create({
            'name': "Campagne bis",
            'team_id': self.team_contenu.id,
            'stage_id': self.stage_approbation.id,
        })
        with self.assertRaises(ValidationError):
            lead.write({'deliverable_ids': [
                (0, 0, {'type_id': self.type_video.id, 'statut': 'en_cours'}),
            ]})

    # --- Le resume d'avancement de la carte kanban ---------------------------

    def test_le_resume_des_livrables_suit_les_statuts(self):
        """La carte doit dire s'il reste du travail, et s'il y a du retard.

        Champ non stocke : il ne definit pas le retard, il relit celui que
        his.content.deliverable.en_retard a deja calcule. Ce test verrouille le
        lien entre les deux — si le resume cessait de suivre, la carte
        afficherait un avancement perime sans que rien n'echoue.
        """
        lead = self.env['crm.lead'].create({
            'name': "Campagne resume",
            'team_id': self.team_contenu.id,
            'stage_id': self.stage_production.id,
            'deliverable_ids': [
                (0, 0, {'type_id': self.type_copy.id, 'statut': 'approuve'}),
                (0, 0, {'type_id': self.type_design.id, 'statut': 'a_faire'}),
            ],
        })
        self.assertEqual(lead.livrables_resume, "1/2 approuves")

        design = lead.deliverable_ids.filtered(
            lambda d: d.type_id == self.type_design
        )
        design.statut = 'approuve'
        self.assertEqual(lead.livrables_resume, "2/2 approuves")

        # Le retard vient de la ligne, pas d'un second calcul. L'echeance est
        # portee par la demande (date_echeance est related sur
        # lead_id.date_deadline) : elle vaut donc pour tous ses livrables.
        design.statut = 'en_cours'
        lead.date_deadline = fields.Date.today() - timedelta(days=1)
        self.assertTrue(design.en_retard)
        self.assertEqual(lead.livrables_resume, "1/2 approuves - en retard")

    def test_une_demande_sans_livrable_n_a_pas_de_resume(self):
        """« 0/0 » dirait qu'on a mesure ; il n'y a rien a mesurer."""
        lead = self.env['crm.lead'].create({
            'name': "Pas encore arbitree",
            'team_id': self.team_contenu.id,
        })
        self.assertFalse(lead.livrables_resume)

    # --- Les actions doivent etre lisibles par le client web -----------------

    def test_les_actions_ont_un_domaine_et_un_contexte_evaluables(self):
        """Le piege %(xmlid)d, verrouille.

        La substitution %(xmlid)d n'a lieu QUE dans les champs de type xml —
        les arch de vues. Sur `domain` et `context` d'une action, qui sont de
        simples char, le texte est stocke tel quel : rien n'echoue au chargement,
        et le client web casse au premier clic sur le menu avec un
        « Token cannot be parsed » que rien ne relie a sa cause.

        Ce test relit ce qui est REELLEMENT en base, pas ce que le XML voulait
        dire.
        """
        actions = self.env['ir.actions.act_window'].search([]).filtered(
            lambda a: a.get_external_id().get(a.id, '').startswith('his_crm_pipeline.'),
        )
        self.assertTrue(actions, "Aucune action trouvee : le test ne verifie rien.")
        contexte = {'uid': self.env.uid, 'context': {}, 'active_id': 1, 'active_ids': []}
        for action in actions:
            self.assertNotIn('%(', action.domain or '', action.display_name)
            self.assertNotIn('%(', action.context or '', action.display_name)
            safe_eval(action.domain or '[]', dict(contexte))
            safe_eval(action.context or '{}', dict(contexte))

    def test_les_vues_enregistrees_sont_litterales_et_executables(self):
        """Les favoris, verrouilles de la meme facon que les actions.

        Deux pieges distincts, que rien ne signale au chargement :

        1. ir.filters.domain est relu par _get_eval_domain() avec
           `ast.literal_eval`, qui REFUSE tout appel de fonction. Un domaine
           ecrit avec context_today() ou relativedelta() s'installe sans bruit
           et casse a la lecture. Les dates relatives doivent donc passer par
           le mini-langage d'Odoo 19 ('now -4H'), qui reste une chaine.

        2. Un nom de champ errone dans un domaine de favori n'est verifie ni a
           l'installation — contrairement a l'arch d'une vue — ni par le
           literal_eval. Il n'echouerait qu'au premier clic d'un utilisateur.

        Ce test relit ce qui est REELLEMENT en base et l'execute.
        """
        filtres = self.env['ir.filters'].search([]).filtered(
            lambda f: f.get_external_id().get(f.id, '').startswith('his_crm_pipeline.'),
        )
        self.assertTrue(filtres, "Aucun favori trouve : le test ne verifie rien.")
        for filtre in filtres:
            domaine = filtre._get_eval_domain()
            self.env['crm.lead'].search(domaine, limit=1)
            self.assertTrue(
                filtre.action_id,
                "%s n'est rattache a aucune action : il apparaitrait dans les "
                "deux pipelines." % filtre.name,
            )

    # --- Cloisonnement des deux pipelines -----------------------------------

    def _etapes_visibles(self, team):
        """Les etapes qu'Odoo proposera sur un lead de cette equipe.

        Reproduit le domaine natif de crm.lead.stage_id — c'est lui, et non nos
        vues, qui decide ce que la barre d'etat affiche.
        """
        return self.env['crm.stage'].search(
            ['|', ('team_ids', '=', False), ('team_ids', 'in', team.ids)],
        )

    def test_aucune_etape_sans_equipe_ne_fuit_dans_les_pipelines(self):
        """Le defaut qui melangeait les deux pipelines, verrouille.

        crm.lead.stage_id porte le domaine natif
        ['|', ('team_ids','=',False), ('team_ids','in',team_id)] : une etape
        SANS equipe apparait dans TOUS les pipelines. Odoo en livre quatre
        (New, Qualified, Proposition, Won), qui se retrouvaient melees aux
        etapes Admissions comme aux etapes Production Contenu.
        """
        orphelines = self.env['crm.stage'].search([('team_ids', '=', False)])
        self.assertFalse(
            orphelines,
            "Etapes sans equipe, donc visibles dans les deux pipelines : %s"
            % orphelines.mapped('name'),
        )

    def test_chaque_pipeline_ne_voit_que_ses_etapes(self):
        etapes_ventes = self._etapes_visibles(self.team_ventes)
        etapes_contenu = self._etapes_visibles(self.team_contenu)

        self.assertFalse(etapes_ventes & etapes_contenu)
        self.assertIn(self.env.ref('his_crm_pipeline.stage_vente_contact_etabli'), etapes_ventes)
        self.assertIn(self.stage_approbation, etapes_contenu)
        self.assertNotIn(self.stage_approbation, etapes_ventes)
        self.assertNotIn(
            self.env.ref('his_crm_pipeline.stage_vente_contact_etabli'), etapes_contenu,
        )

    def test_l_orientation_ne_voit_que_son_etape_d_exception(self):
        """La Cellule d'Orientation possede l'evaluation psychologique, rien d'autre."""
        etapes = self._etapes_visibles(self.env.ref('his_crm_pipeline.crm_team_orientation'))
        self.assertEqual(etapes, self.env.ref('his_crm_pipeline.stage_vente_evaluation_psy'))

    def test_les_equipes_ne_voient_pas_les_leads_de_l_autre(self):
        """Odoo ne cloisonne PAS par equipe nativement : la regle est a nous.

        Le test tourne with_user() : en superuser toutes les regles sont
        contournees et le test passerait meme sans regle du tout.
        """
        lead_vente = self.env['crm.lead'].create({
            'name': "Candidat Amine", 'team_id': self.team_ventes.id,
        })
        lead_contenu = self.env['crm.lead'].create({
            'name': "Video portes ouvertes", 'team_id': self.team_contenu.id,
        })
        user_vente = self._user('conseiller_ventes', self.team_ventes)
        user_contenu = self._user('monteur_contenu', self.team_contenu)

        visibles_vente = self.env['crm.lead'].with_user(user_vente).search([
            ('id', 'in', (lead_vente + lead_contenu).ids),
        ])
        self.assertEqual(visibles_vente, lead_vente)

        visibles_contenu = self.env['crm.lead'].with_user(user_contenu).search([
            ('id', 'in', (lead_vente + lead_contenu).ids),
        ])
        self.assertEqual(visibles_contenu, lead_contenu)

    def test_la_file_d_attente_ne_deborde_pas_sur_l_autre_equipe(self):
        """Un lead sans proprietaire reste dans SON equipe.

        La regle native « mes leads » montre a chaque commercial ses leads et
        tous ceux sans proprietaire. Nos leads captes arrivant sans
        proprietaire par construction, la file des Admissions serait visible de
        toute la Production Contenu sans le resserrement pose ici.
        """
        capture = self.env['crm.lead'].create({
            'name': "Capture Admissions", 'team_id': self.team_ventes.id,
        })
        self.assertFalse(capture.user_id)

        user_contenu = self._user('monteur_file', self.team_contenu)
        self.assertFalse(
            self.env['crm.lead'].with_user(user_contenu).search([('id', '=', capture.id)]),
            "La file des Admissions ne doit pas etre visible a la Production Contenu.",
        )

        user_vente = self._user('conseillere_file_visible', self.team_ventes)
        self.assertEqual(
            self.env['crm.lead'].with_user(user_vente).search([('id', '=', capture.id)]),
            capture,
            "La file doit rester visible a son equipe, sinon personne n'affecte.",
        )

    def test_l_orientation_voit_les_candidats_qu_elle_doit_evaluer(self):
        """Sans quoi la derivation « Evaluation psychologique » est inutilisable.

        Le lead reste porte par les Ventes pendant l'evaluation — c'est leur
        candidat, leur conseillere. Seule l'ETAPE appartient aux deux equipes.
        La visibilite suit donc l'etape, et se referme quand le lead en sort.
        """
        equipe_orientation = self.env.ref('his_crm_pipeline.crm_team_orientation')
        psychologue = self._user('psychologue', equipe_orientation)
        lead = self.env['crm.lead'].create({
            'name': "Candidat a evaluer",
            'team_id': self.team_ventes.id,
            'stage_id': self.stage_pris_en_charge.id,
        })
        Lead = self.env['crm.lead'].with_user(psychologue)
        self.assertFalse(
            Lead.search([('id', '=', lead.id)]),
            "Avant la derivation, la Cellule n'a rien a voir.",
        )

        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_evaluation_psy')
        self.assertEqual(
            Lead.search([('id', '=', lead.id)]), lead,
            "Pendant l'evaluation, la Cellule doit voir le candidat.",
        )

        lead.stage_id = self.env.ref('his_crm_pipeline.stage_vente_dossier')
        self.assertFalse(
            Lead.search([('id', '=', lead.id)]),
            "Sorti de l'etape, le lead se referme sur son equipe.",
        )

    def test_l_etape_partagee_n_ouvre_pas_l_autre_pipeline(self):
        """La clause d'etape ne doit pas rouvrir ce que le cloisonnement ferme."""
        user_contenu = self._user('monteur_etape', self.team_contenu)
        lead_vente = self.env['crm.lead'].create({
            'name': "Candidat", 'team_id': self.team_ventes.id,
            'stage_id': self.env.ref('his_crm_pipeline.stage_vente_evaluation_psy').id,
        })
        self.assertFalse(
            self.env['crm.lead'].with_user(user_contenu).search([('id', '=', lead_vente.id)]),
        )

    def test_lead_sans_equipe_reste_visible(self):
        """Un lead entrant sans equipe ne doit disparaitre pour personne."""
        lead = self.env['crm.lead'].create({'name': "Formulaire web", 'team_id': False})
        user = self._user('trieur', self.team_contenu)
        self.assertEqual(
            self.env['crm.lead'].with_user(user).search([('id', '=', lead.id)]), lead,
        )

    # --- Relance SLA premier contact ----------------------------------------

    def _lead_en_retard(self, heures=5):
        lead = self.env['crm.lead'].create({
            'name': "Lead dormant",
            'team_id': self.team_ventes.id,
            'stage_id': self.stage_pris_en_charge.id,
            'user_id': self.env.ref('base.user_admin').id,
        })
        # date_last_stage_update est calcule et stocke : le forcer en SQL est le
        # seul moyen de simuler le temps qui passe sans attendre quatre heures.
        #
        # flush_all() est indispensable : sans lui la ligne n'est pas encore en
        # base, l'UPDATE ne touche rien, et le flush declenche plus tard par le
        # cron ecrit la vraie date par-dessus. Le test echoue alors sans que le
        # code teste soit en cause.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE crm_lead SET date_last_stage_update = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=heures), lead.id),
        )
        lead.invalidate_recordset(['date_last_stage_update'])
        return lead

    def _relances(self, lead):
        return self.env['mail.activity'].search([
            ('res_model', '=', 'crm.lead'), ('res_id', '=', lead.id),
            ('summary', '=', "Relance SLA - premier contact en retard (>4h)"),
        ])

    def test_sla_relance_le_responsable_pas_le_conseiller(self):
        responsable = self._user('responsable_admissions', self.team_ventes)
        self.team_ventes.user_id = responsable
        lead = self._lead_en_retard()

        self.env['crm.lead']._cron_relance_sla_premier_contact()

        relances = self._relances(lead)
        self.assertEqual(len(relances), 1)
        self.assertEqual(relances.user_id, responsable)
        self.assertNotEqual(relances.user_id, lead.user_id)

    def test_sla_ne_relance_qu_une_fois(self):
        """Le cron tourne toutes les heures : sans garde-fou il empilerait."""
        self.team_ventes.user_id = self._user('responsable_bis', self.team_ventes)
        lead = self._lead_en_retard()

        self.env['crm.lead']._cron_relance_sla_premier_contact()
        self.env['crm.lead']._cron_relance_sla_premier_contact()

        self.assertEqual(len(self._relances(lead)), 1)

    def test_sla_ignore_les_leads_dans_les_temps(self):
        self.team_ventes.user_id = self._user('responsable_ter', self.team_ventes)
        lead = self._lead_en_retard(heures=1)

        self.env['crm.lead']._cron_relance_sla_premier_contact()

        self.assertFalse(self._relances(lead))

    # --- Affectation en masse ------------------------------------------------

    def test_affectation_en_masse(self):
        """La vue multi_edit ecrit sur plusieurs leads en une passe."""
        conseiller = self._user('conseiller_masse', self.team_ventes)
        leads = self.env['crm.lead'].create([
            {'name': "Lead %s" % i, 'team_id': self.team_ventes.id,
             'stage_id': self.stage_pris_en_charge.id, 'score_academique': i}
            for i in range(3)
        ])
        leads.write({'user_id': conseiller.id})
        self.assertEqual(leads.mapped('user_id'), conseiller)

    def test_un_lead_capture_arrive_sans_commercial(self):
        """Sinon la file d'affectation est vide en permanence.

        crm.lead.user_id porte `default=lambda self: self.env.user`. Le
        Marketing capturant les leads, chacun naissait affecte au Marketing et
        la file — qui filtre sur les leads sans commercial — ne se remplissait
        jamais. Le geste d'arbitrage du responsable n'existait pas.
        """
        lead = self.env['crm.lead'].create({
            'name': "Capture marketing",
            'team_id': self.team_ventes.id,
        })
        self.assertEqual(lead.stage_id, self.env.ref('his_crm_pipeline.stage_vente_nouveau'))
        self.assertFalse(lead.user_id, "Un lead capture ne doit appartenir a personne.")

    def test_un_lead_cree_directement_en_prise_en_charge_garde_son_commercial(self):
        """La regle vaut pour la file, pas pour un lead deja pris en charge."""
        conseillere = self._user('conseillere_directe', self.team_ventes)
        lead = self.env['crm.lead'].create({
            'name': "Lead deja affecte",
            'team_id': self.team_ventes.id,
            'stage_id': self.stage_pris_en_charge.id,
            'user_id': conseillere.id,
        })
        self.assertEqual(lead.user_id, conseillere)

    def test_affecter_un_lead_de_la_file_reste_possible(self):
        """La regle ne joue qu'a la creation : elle ne doit rien bloquer ensuite."""
        conseillere = self._user('conseillere_file', self.team_ventes)
        lead = self.env['crm.lead'].create({
            'name': "A affecter", 'team_id': self.team_ventes.id,
        })
        lead.user_id = conseillere
        self.assertEqual(lead.user_id, conseillere)

    def test_file_d_affectation_triee_par_score_decroissant(self):
        """Le tri appartient a la vue, pas aux donnees.

        Ce test ne pose PAS de score a la main, deliberement. Ce module livre
        score_academique en saisie libre pour rester installable seul, mais
        his_admission le redefinit en champ calcule des que le referentiel
        academique est la — une valeur ecrite ici serait alors ignoree, et le
        test mesurerait quel module est installe plutot que ce que ce
        module-ci garantit.

        Ce qu'il garantit, c'est que la file d'affectation presente les leads
        du meilleur score au moins bon.
        """
        vue = self.env.ref('his_crm_pipeline.view_crm_lead_list_non_affectes')
        self.assertIn('score_academique desc', vue.arch)

    # --- Telephone et lien WhatsApp -----------------------------------------

    def test_le_numero_algerien_est_normalise_en_e164(self):
        """Les trois formes saisies par les candidats donnent le meme numero.

        C'est le lien WhatsApp qui en depend : wa.me refuse un zero initial et
        refuse le signe plus.
        """
        for saisi in ('0555123456', '+213555123456', '00213555123456'):
            lead = self.env['crm.lead'].create({
                'name': "Candidat %s" % saisi,
                'team_id': self.team_ventes.id,
                'phone': saisi,
            })
            self.assertEqual(
                lead.telephone_e164, '+213555123456',
                "« %s » n'a pas ete normalise" % saisi,
            )
            self.assertEqual(
                lead.whatsapp_url,
                'https://wa.me/213555123456',
                "Le lien WhatsApp doit porter les chiffres seuls",
            )

    def test_sans_telephone_il_n_y_a_pas_de_lien(self):
        """Un lien vide plutot qu'un lien casse : la carte le masque."""
        lead = self.env['crm.lead'].create({
            'name': "Sans telephone",
            'team_id': self.team_ventes.id,
        })
        self.assertFalse(lead.telephone_e164)
        self.assertFalse(lead.whatsapp_url)

    def test_un_numero_illisible_ne_donne_pas_de_lien(self):
        """phone_format rend la saisie telle quelle quand il echoue.

        Sans le controle du signe plus, une faute de frappe deviendrait une
        URL WhatsApp pointant vers rien — un lien mort est pire qu'une absence
        de lien, parce qu'on clique dessus.
        """
        lead = self.env['crm.lead'].create({
            'name': "Numero casse",
            'team_id': self.team_ventes.id,
            'phone': 'a rappeler chez la tante',
        })
        self.assertFalse(lead.telephone_e164)
        self.assertFalse(lead.whatsapp_url)

    # --- Boucle d'appel ------------------------------------------------------

    def _lead_pris_en_charge(self):
        return self.env['crm.lead'].create({
            'name': "Candidat a rappeler",
            'team_id': self.team_ventes.id,
            'stage_id': self.stage_pris_en_charge.id,
            'phone': '0555123456',
        })

    def test_une_tentative_sans_reponse_incremente_et_replanifie(self):
        lead = self._lead_pris_en_charge()
        self.assertEqual(lead.tentatives_appel, 0)

        lead.action_appel_sans_reponse()

        self.assertEqual(lead.tentatives_appel, 1)
        self.assertTrue(lead.derniere_tentative)
        # L'etape ne bouge pas : une tentative n'est pas un contact.
        self.assertEqual(lead.stage_id, self.stage_pris_en_charge)
        rappels = self.env['mail.activity'].search([
            ('res_model', '=', 'crm.lead'), ('res_id', '=', lead.id),
        ])
        self.assertEqual(len(rappels), 1)

    def test_trois_tentatives_ne_posent_qu_un_seul_rappel(self):
        """Sinon la conseillere recoit une activite par tentative et cesse de
        les lire — exactement le defaut que la relance SLA evite deja."""
        lead = self._lead_pris_en_charge()
        for _ in range(3):
            lead.action_appel_sans_reponse()

        self.assertEqual(lead.tentatives_appel, 3)
        rappels = self.env['mail.activity'].search([
            ('res_model', '=', 'crm.lead'), ('res_id', '=', lead.id),
        ])
        self.assertEqual(len(rappels), 1, "Un seul rappel, replanifie")

    def test_joint_avance_a_contact_etabli_et_efface_le_rappel(self):
        lead = self._lead_pris_en_charge()
        lead.action_appel_sans_reponse()

        action = lead.action_appel_joint()

        self.assertEqual(
            lead.stage_id,
            self.env.ref('his_crm_pipeline.stage_vente_contact_etabli'),
        )
        self.assertFalse(self.env['mail.activity'].search([
            ('res_model', '=', 'crm.lead'), ('res_id', '=', lead.id),
        ]), "Le rappel n'a plus d'objet une fois le candidat joint")
        self.assertEqual(action['res_id'], lead.id)
        self.assertEqual(action['res_model'], 'crm.lead')

    # --- Taxonomie des pertes ------------------------------------------------

    def test_les_motifs_d_issue_d_appel_existent(self):
        """Les leads meurent au telephone, pas en revue de dossier.

        Les quatre motifs d'origine decrivent tous une mort tardive. Les
        chiffres de GoHighLevel disent l'inverse : fantome, sans reponse et
        numero errone sont la majorite des pertes expliquees.
        """
        for xmlid in (
            'lost_reason_fantome', 'lost_reason_sans_reponse',
            'lost_reason_numero_errone', 'lost_reason_bac_ancien',
            'lost_reason_trop_cher', 'lost_reason_profil_inadapte',
            'lost_reason_autre',
        ):
            motif = self.env.ref(
                'his_crm_pipeline.%s' % xmlid, raise_if_not_found=False,
            )
            self.assertTrue(motif, "Motif manquant : %s" % xmlid)

    def test_les_motifs_d_origine_survivent(self):
        """noupdate et ondelete='restrict' : on ajoute, on ne remplace pas.

        Un motif supprime emporterait avec lui tous les leads qui le portaient.
        """
        for xmlid in (
            'lost_reason_hors_quota', 'lost_reason_dossier_non_retenu',
            'lost_reason_dossier_incomplet', 'lost_reason_paiement_non_confirme',
            'lost_reason_retour_production',
        ):
            self.assertTrue(self.env.ref(
                'his_crm_pipeline.%s' % xmlid, raise_if_not_found=False,
            ), "Motif d'origine perdu : %s" % xmlid)

    def test_les_motifs_anglais_natifs_sont_retires_de_la_liste(self):
        """« Too expensive » doublait « Frais trop eleves », en anglais.

        Le meme compartiment coupe en deux qu'on vient de fusionner pour
        « Sans reponse », reintroduit par le haut. Desactives et non
        supprimes : lost_reason_id est en ondelete='restrict' et l'un d'eux
        portait deja un lead sur la base de recette.
        """
        for xmlid in ('crm.lost_reason_1', 'crm.lost_reason_2', 'crm.lost_reason_3'):
            motif = self.env.ref(xmlid, raise_if_not_found=False)
            if not motif:
                continue
            self.assertFalse(
                motif.active,
                "« %s » doit disparaitre de la liste de selection" % motif.name,
            )

    def test_aucun_motif_selectionnable_n_est_en_anglais(self):
        """Le garde-fou general : la liste que voit la conseillere est
        entierement en francais, sans quoi deux vocabulaires cohabitent."""
        actifs = self.env['crm.lost.reason'].search([]).mapped('name')
        for interdit in ("Too expensive", "We don't have people/skills",
                         "Not enough stock"):
            self.assertNotIn(interdit, actifs)

    def test_les_motifs_sont_ordonnes_par_frequence_reelle(self):
        """Odoo trie les motifs par id : « Sans reponse », le plus frequent,
        se retrouverait au milieu d'une liste de onze. Trois motifs couvrent
        environ 70 % des pertes ; ils doivent etre en tete, sinon la cloture
        coute assez cher pour etre sautee."""
        motifs = self.env['crm.lost.reason'].search([])
        noms = motifs.mapped('name')
        self.assertEqual(noms[0], "Sans reponse")
        self.assertEqual(noms[1], "Candidature fantome")
        self.assertEqual(noms[-1], "Autre - a preciser")

    # --- Une perte doit dire quelque chose -----------------------------------

    def _lead_simple(self, **kw):
        vals = {'name': "Candidat", 'team_id': self.team_ventes.id}
        vals.update(kw)
        return self.env['crm.lead'].create(vals)

    def test_perdre_sans_motif_est_refuse(self):
        """626 pertes, 193 motifs. Le vide n'est plus une option.

        Contrainte serveur et non regle de vue : le kanban, l'import et l'API
        contournent une vue. Meme discipline que le verrou d'approbation et que
        « gagne seulement si encaisse ».
        """
        lead = self._lead_simple()
        with self.assertRaises(ValidationError):
            lead.action_set_lost()

    def test_perdre_avec_un_motif_passe(self):
        lead = self._lead_simple()
        lead.action_set_lost(lost_reason_id=self.env.ref(
            'his_crm_pipeline.lost_reason_sans_reponse').id)
        self.assertEqual(lead.won_status, 'lost')

    def test_autre_sans_precision_est_refuse(self):
        """La soupape d'honnetete a un prix : il faut ecrire la ligne. Sans
        cela « Autre » devient le raccourci universel et on aurait remplace un
        vide par un mot qui n'en dit pas davantage."""
        lead = self._lead_simple()
        with self.assertRaises(ValidationError):
            lead.action_set_lost(lost_reason_id=self.env.ref(
                'his_crm_pipeline.lost_reason_autre').id)

    def test_autre_avec_precision_passe(self):
        lead = self._lead_simple(
            perte_precision="Parti a l'etranger, ne rappellera pas.")
        lead.action_set_lost(lost_reason_id=self.env.ref(
            'his_crm_pipeline.lost_reason_autre').id)
        self.assertEqual(lead.won_status, 'lost')

    def test_archiver_n_est_pas_perdre(self):
        """La contrainte porte sur won_status, pas sur active.

        « Perdu » vaut probabilite 0 ET archive (crm_lead.py:1122). Un lead
        simplement archive garde sa probabilite : exiger un motif de perte
        la-dessus interdirait le rangement ordinaire d'une fiche.
        """
        lead = self._lead_simple(probability=40)
        lead.action_archive()
        self.assertFalse(lead.active)
        self.assertNotEqual(lead.won_status, 'lost')

    def test_la_note_de_cloture_atterrit_sur_le_lead(self):
        """Odoo ne se sert de lost_feedback que comme message de suivi : aucun
        champ ne la porte, donc aucune contrainte ne peut l'exiger. On la pose
        sur la fiche, ce qui rend « Autre » exigeable depuis l'assistant natif.
        """
        lead = self._lead_simple()
        wizard = self.env['crm.lead.lost'].create({
            'lead_ids': [(6, 0, [lead.id])],
            'lost_reason_id': self.env.ref('his_crm_pipeline.lost_reason_autre').id,
            'lost_feedback': '<p>Recu a l universite d Alger.</p>',
        })
        wizard.action_lost_reason_apply()
        self.assertEqual(lead.won_status, 'lost')
        self.assertIn("Alger", lead.perte_precision)

    def test_apres_trois_tentatives_la_perte_propose_fantome(self):
        """La fiche sait deja. Elle ne demande pas.

        C'est ce qui rend le motif obligatoire supportable : un clic sans
        reflexion plutot qu'un menu de onze lignes a lire.
        """
        lead = self._lead_pris_en_charge()
        for _ in range(3):
            lead.action_appel_sans_reponse()

        action = lead.action_perdre_rapide()

        self.assertEqual(
            action['context']['default_lost_reason_id'],
            self.env.ref('his_crm_pipeline.lost_reason_fantome').id,
        )
        self.assertEqual(action['res_model'], 'crm.lead.lost')

    def test_avant_trois_tentatives_aucun_motif_n_est_impose(self):
        """Deviner a la place de la conseillere serait pire que ne rien
        proposer : un motif faux ne se distingue pas d'un motif vrai — c'est
        exactement le defaut de « Unknown » qu'on vient de retirer."""
        lead = self._lead_pris_en_charge()
        lead.action_appel_sans_reponse()

        action = lead.action_perdre_rapide()

        self.assertFalse(action['context'].get('default_lost_reason_id'))

    def test_chaque_tentative_laisse_une_trace_datee(self):
        """Le compteur dit combien ; le fil dit quand. Le second explique le
        premier a qui relit la fiche trois semaines plus tard."""
        lead = self._lead_pris_en_charge()
        avant = len(lead.message_ids)
        lead.action_appel_sans_reponse()
        self.assertGreater(len(lead.message_ids), avant)
