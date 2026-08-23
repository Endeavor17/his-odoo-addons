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
            'besoin_copy': True, 'statut_copy': 'approuve',
            'besoin_design': True, 'statut_design': 'revision_interne',
        })
        with self.assertRaises(ValidationError):
            lead.stage_id = self.stage_approbation

        lead.statut_design = 'approuve'
        lead.stage_id = self.stage_approbation
        self.assertEqual(lead.stage_id, self.stage_approbation)

    def test_livrable_non_demande_ne_bloque_pas(self):
        """Un statut « a faire » sur un livrable non demande n'est pas un blocage."""
        lead = self.env['crm.lead'].create({
            'name': "Post simple",
            'team_id': self.team_contenu.id,
            'stage_id': self.stage_production.id,
            'besoin_copy': True, 'statut_copy': 'approuve',
            'besoin_video': False, 'statut_video': 'a_faire',
        })
        lead.stage_id = self.stage_approbation
        self.assertEqual(lead.stage_id, self.stage_approbation)

    def test_approbation_bloquee_si_le_besoin_est_ajoute_apres_coup(self):
        """La contrainte tient aussi quand c'est le besoin, et non l'etape, qui change."""
        lead = self.env['crm.lead'].create({
            'name': "Campagne bis",
            'team_id': self.team_contenu.id,
            'stage_id': self.stage_approbation.id,
        })
        with self.assertRaises(ValidationError):
            lead.write({'besoin_video': True, 'statut_video': 'en_cours'})

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
