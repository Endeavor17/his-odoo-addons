# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un test par regle du module. Il echoue si une regle saute."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


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

    # --- Cloisonnement des deux pipelines -----------------------------------

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

    def test_file_d_affectation_triee_par_score_decroissant(self):
        leads = self.env['crm.lead'].create([
            {'name': "Faible", 'team_id': self.team_ventes.id, 'score_academique': 10},
            {'name': "Fort", 'team_id': self.team_ventes.id, 'score_academique': 90},
        ])
        tries = self.env['crm.lead'].search(
            [('id', 'in', leads.ids)], order='score_academique desc',
        )
        self.assertEqual(tries[0].name, "Fort")
