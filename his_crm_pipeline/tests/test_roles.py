# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un test par case du tableau des roles, dans les DEUX sens.

Tout est joue en `with_user()`. Les tests Odoo tournent en superutilisateur par
defaut, qui contourne droits d'acces, regles d'enregistrement et garde-fous : un
parcours joue ainsi ne prouve strictement rien sur ce qu'un role peut faire.
C'est ce qui a laisse passer les defauts precedents — un graphiste capable de
clore une demande, une conseillere bloquee sur le seul geste de son metier.

Chaque test verifie donc les deux sens : ce que le role PEUT, et ce qu'il NE
PEUT PAS.
"""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRoles(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team_ventes = cls.env.ref('his_crm_pipeline.crm_team_ventes')
        cls.team_contenu = cls.env.ref('his_crm_pipeline.crm_team_contenu')
        cls.team_orientation = cls.env.ref('his_crm_pipeline.crm_team_orientation')
        cls.st_nouveau = cls.env.ref('his_crm_pipeline.stage_vente_nouveau')
        cls.st_pris = cls.env.ref('his_crm_pipeline.stage_vente_pris_en_charge')
        cls.st_psy = cls.env.ref('his_crm_pipeline.stage_vente_evaluation_psy')
        cls.st_dossier = cls.env.ref('his_crm_pipeline.stage_vente_dossier')
        cls.st_production = cls.env.ref('his_crm_pipeline.stage_contenu_production')
        cls.st_approbation = cls.env.ref('his_crm_pipeline.stage_contenu_approbation')

    def _user(self, login, role, team=None):
        user = self.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref(role).id,
            ])],
        })
        if team:
            self.env['crm.team.member'].create({
                'crm_team_id': team.id, 'user_id': user.id,
            })
        return user

    def _demande(self, **vals):
        """Une demande de contenu prete a etre travaillee."""
        return self.env['crm.lead'].create({
            'name': "Campagne rentree",
            'team_id': self.team_contenu.id,
            'stage_id': self.st_production.id,
            'besoin_copy': True, 'besoin_design': True,
            **vals,
        })

    # =================== Cloisonnement entre les deux processus ===============

    def test_un_role_contenu_ne_voit_aucune_candidature(self):
        """Le cloisonnement doit tenir SANS groupe commercial.

        Les roles Contenu n'ont aucun groupe de vente : aucune regle native ne
        s'applique donc a eux. Dans Odoo, une regle absente n'est pas une regle
        restrictive — c'est l'acces total. Sans nos regles propres, un graphiste
        verrait toutes les candidatures.
        """
        candidature = self.env['crm.lead'].create({
            'name': "Candidat", 'team_id': self.team_ventes.id,
        })
        demande = self._demande()
        graphiste = self._user(
            'r_design', 'his_crm_pipeline.group_contenu_production', self.team_contenu,
        )

        vus = self.env['crm.lead'].with_user(graphiste).search([])
        self.assertIn(demande, vus)
        self.assertNotIn(candidature, vus)

    def test_un_role_admissions_ne_voit_aucune_demande_de_contenu(self):
        demande = self._demande()
        conseillere = self._user(
            'r_conseil', 'his_crm_pipeline.group_admissions_conseiller', self.team_ventes,
        )
        self.assertNotIn(
            demande, self.env['crm.lead'].with_user(conseillere).search([]),
        )

    def test_un_role_contenu_n_a_pas_l_application_crm(self):
        """Le menu CRM est ouvert aux groupes commerciaux. Aucun role Contenu
        n'en porte : c'est ce qui evite de donner a un graphiste l'ecriture sur
        les contacts et la fusion de leads."""
        graphiste = self._user(
            'r_design_menu', 'his_crm_pipeline.group_contenu_production', self.team_contenu,
        )
        self.assertFalse(graphiste.has_group('sales_team.group_sale_salesman'))
        self.assertFalse(
            self.env.ref('crm.crm_menu_root').with_user(graphiste)._filter_visible_menus(),
        )

    # ========================= Production Contenu ============================

    def test_la_production_ne_peut_ni_gagner_ni_perdre_une_demande(self):
        """Le defaut signale : un graphiste cloturait une demande."""
        demande = self._demande(statut_copy='approuve', statut_design='approuve')
        graphiste = self._user(
            'r_prod_cloture', 'his_crm_pipeline.group_contenu_production', self.team_contenu,
        )
        vue_graphiste = demande.with_user(graphiste)

        with self.assertRaises(AccessError):
            vue_graphiste.stage_id = self.st_approbation
        with self.assertRaises(AccessError):
            vue_graphiste.action_set_lost()

    def test_l_approbation_peut_cloturer(self):
        demande = self._demande(statut_copy='approuve', statut_design='approuve')
        directeur = self._user(
            'r_direction', 'his_crm_pipeline.group_contenu_approbation', self.team_contenu,
        )

        demande.with_user(directeur).stage_id = self.st_approbation

        self.assertEqual(demande.stage_id, self.st_approbation)

    def test_un_livrable_n_avance_que_par_son_assigne(self):
        """Regle portee par la donnee, pas par des groupes : le designer ne
        touche pas au texte, le redacteur ne touche pas au design."""
        redacteur = self._user(
            'r_copy', 'his_crm_pipeline.group_contenu_production', self.team_contenu,
        )
        graphiste = self._user(
            'r_dsg', 'his_crm_pipeline.group_contenu_production', self.team_contenu,
        )
        demande = self._demande(
            assignee_copy=redacteur.id, assignee_design=graphiste.id,
        )

        demande.with_user(redacteur).statut_copy = 'approuve'
        demande.with_user(graphiste).statut_design = 'approuve'
        self.assertEqual(demande.statut_copy, 'approuve')
        self.assertEqual(demande.statut_design, 'approuve')

        with self.assertRaises(AccessError):
            demande.with_user(graphiste).statut_copy = 'rejete'
        with self.assertRaises(AccessError):
            demande.with_user(redacteur).statut_design = 'rejete'

    def test_la_priorisation_arbitre_tous_les_livrables(self):
        strategiste = self._user(
            'r_prio', 'his_crm_pipeline.group_contenu_priorisation', self.team_contenu,
        )
        demande = self._demande()

        demande.with_user(strategiste).write({
            'statut_copy': 'approuve', 'assignee_design': strategiste.id,
        })

        self.assertEqual(demande.statut_copy, 'approuve')

    def test_la_production_n_affecte_pas_les_livrables(self):
        graphiste = self._user(
            'r_prod_aff', 'his_crm_pipeline.group_contenu_production', self.team_contenu,
        )
        demande = self._demande()

        with self.assertRaises(AccessError):
            demande.with_user(graphiste).assignee_video = graphiste.id

    def test_le_demandeur_ne_voit_que_ses_propres_demandes(self):
        rh = self._user('r_rh', 'his_crm_pipeline.group_contenu_demandeur')
        autre = self._user('r_pedago', 'his_crm_pipeline.group_contenu_demandeur')

        sienne = self.env['crm.lead'].with_user(rh).create({
            'name': "Affiche RH", 'team_id': self.team_contenu.id,
        })
        celle_des_autres = self._demande()

        vues = self.env['crm.lead'].with_user(rh).search([])
        self.assertIn(sienne, vues)
        self.assertNotIn(celle_des_autres, vues)
        self.assertNotIn(sienne, self.env['crm.lead'].with_user(autre).search([]))

    def test_le_demandeur_est_trace_a_la_creation(self):
        """demandeur_id et non user_id : ce dernier change de main a la
        priorisation, et le demandeur perdrait sa demande de vue."""
        rh = self._user('r_rh_trace', 'his_crm_pipeline.group_contenu_demandeur')
        demande = self.env['crm.lead'].with_user(rh).create({
            'name': "Affiche RH", 'team_id': self.team_contenu.id,
        })
        self.assertEqual(demande.demandeur_id, rh)

    # ============================= Admissions ================================

    def test_l_acquisition_ne_fait_pas_avancer_un_lead(self):
        marketing = self._user(
            'r_acq', 'his_crm_pipeline.group_admissions_acquisition', self.team_ventes,
        )
        lead = self.env['crm.lead'].with_user(marketing).create({
            'name': "Capture", 'team_id': self.team_ventes.id,
        })
        self.assertEqual(lead.stage_id, self.st_nouveau)

        with self.assertRaises(AccessError):
            lead.with_user(marketing).stage_id = self.st_pris

    def test_la_conseillere_fait_avancer_un_lead(self):
        conseillere = self._user(
            'r_cons_av', 'his_crm_pipeline.group_admissions_conseiller', self.team_ventes,
        )
        lead = self.env['crm.lead'].create({
            'name': "Capture", 'team_id': self.team_ventes.id,
            'user_id': conseillere.id, 'stage_id': self.st_pris.id,
        })

        lead.with_user(conseillere).stage_id = self.st_dossier

        self.assertEqual(lead.stage_id, self.st_dossier)

    def test_seul_le_responsable_affecte(self):
        """La file est triee par score : s'y servir soi-meme viderait ce tri de
        son sens."""
        conseillere = self._user(
            'r_cons_aff', 'his_crm_pipeline.group_admissions_conseiller', self.team_ventes,
        )
        responsable = self._user(
            'r_resp', 'his_crm_pipeline.group_admissions_responsable', self.team_ventes,
        )
        lead = self.env['crm.lead'].create({
            'name': "Dans la file", 'team_id': self.team_ventes.id,
        })

        with self.assertRaises(AccessError):
            lead.with_user(conseillere).user_id = conseillere

        lead.with_user(responsable).user_id = conseillere
        self.assertEqual(lead.user_id, conseillere)

    def test_l_orientation_n_agit_que_dans_son_etape(self):
        psychologue = self._user(
            'r_orient', 'his_crm_pipeline.group_admissions_orientation', self.team_orientation,
        )
        hors_etape = self.env['crm.lead'].create({
            'name': "Pas encore evalue", 'team_id': self.team_ventes.id,
            'stage_id': self.st_pris.id,
        })
        en_evaluation = self.env['crm.lead'].create({
            'name': "En evaluation", 'team_id': self.team_ventes.id,
            'stage_id': self.st_psy.id,
        })

        with self.assertRaises(AccessError):
            hors_etape.with_user(psychologue).description = "Intrusion"

        en_evaluation.with_user(psychologue).stage_id = self.st_dossier
        self.assertEqual(en_evaluation.stage_id, self.st_dossier)

    # ========================= Interdits universels ==========================

    def test_aucun_role_ne_supprime_un_lead(self):
        """Un lead se perd avec un motif, il ne disparait pas. Aucun role de ce
        depot n'implique sales_team.group_sale_manager, seul groupe natif
        portant la suppression."""
        lead = self.env['crm.lead'].create({
            'name': "A conserver", 'team_id': self.team_ventes.id,
        })
        demande = self._demande()
        roles = [
            ('s_acq', 'his_crm_pipeline.group_admissions_acquisition', self.team_ventes, lead),
            ('s_cons', 'his_crm_pipeline.group_admissions_conseiller', self.team_ventes, lead),
            ('s_resp', 'his_crm_pipeline.group_admissions_responsable', self.team_ventes, lead),
            ('s_orient', 'his_crm_pipeline.group_admissions_orientation', self.team_orientation, lead),
            ('s_prod', 'his_crm_pipeline.group_contenu_production', self.team_contenu, demande),
            ('s_appro', 'his_crm_pipeline.group_contenu_approbation', self.team_contenu, demande),
        ]
        for login, role, team, cible in roles:
            user = self._user(login, role, team)
            with self.assertRaises(AccessError, msg="%s peut supprimer" % role):
                cible.with_user(user).unlink()

    def test_les_ecritures_systeme_traversent_les_garde_fous(self):
        """Une consequence n'est pas un geste d'utilisateur.

        Creer la fiche personne au premier contact, faire passer un dossier a
        « admis », gagner un lead sur encaissement sont declenches en sudo() par
        le code. Ils doivent aboutir meme quand celui qui a clique n'aurait pas
        le droit de les faire a la main.
        """
        marketing = self._user(
            'r_acq_sudo', 'his_crm_pipeline.group_admissions_acquisition', self.team_ventes,
        )
        lead = self.env['crm.lead'].with_user(marketing).create({
            'name': "Capture", 'team_id': self.team_ventes.id,
        })

        # Le Marketing ne peut pas, le systeme oui.
        with self.assertRaises(AccessError):
            lead.with_user(marketing).stage_id = self.st_pris
        lead.with_user(marketing).sudo().stage_id = self.st_pris
        self.assertEqual(lead.stage_id, self.st_pris)
