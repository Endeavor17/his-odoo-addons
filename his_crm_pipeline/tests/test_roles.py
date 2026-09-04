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
        cls.type_copy = cls.env.ref('his_crm_pipeline.deliverable_type_copy')
        cls.type_design = cls.env.ref('his_crm_pipeline.deliverable_type_design')
        cls.type_video = cls.env.ref('his_crm_pipeline.deliverable_type_video')

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

    def _demande(self, statut_copy='a_faire', statut_design='a_faire',
                 assignee_copy=False, assignee_design=False, **vals):
        """Une demande de contenu prete a etre travaillee : texte et design."""
        return self.env['crm.lead'].create({
            'name': "Campagne rentree",
            'team_id': self.team_contenu.id,
            'stage_id': self.st_production.id,
            'deliverable_ids': [
                (0, 0, {'type_id': self.type_copy.id, 'statut': statut_copy,
                        'assignee_id': assignee_copy}),
                (0, 0, {'type_id': self.type_design.id, 'statut': statut_design,
                        'assignee_id': assignee_design}),
            ],
            **vals,
        })

    def _livrable(self, demande, type_livrable):
        return demande.deliverable_ids.filtered(
            lambda d: d.type_id == type_livrable
        )

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
        copy = self._livrable(demande, self.type_copy)
        design = self._livrable(demande, self.type_design)

        copy.with_user(redacteur).statut = 'approuve'
        design.with_user(graphiste).statut = 'approuve'
        self.assertEqual(copy.statut, 'approuve')
        self.assertEqual(design.statut, 'approuve')

        with self.assertRaises(AccessError):
            copy.with_user(graphiste).statut = 'rejete'
        with self.assertRaises(AccessError):
            design.with_user(redacteur).statut = 'rejete'

    def test_la_priorisation_arbitre_tous_les_livrables(self):
        strategiste = self._user(
            'r_prio', 'his_crm_pipeline.group_contenu_priorisation', self.team_contenu,
        )
        demande = self._demande()
        copy = self._livrable(demande, self.type_copy)

        copy.with_user(strategiste).statut = 'approuve'
        self._livrable(demande, self.type_design).with_user(
            strategiste
        ).assignee_id = strategiste.id

        self.assertEqual(copy.statut, 'approuve')

    def test_la_production_n_affecte_pas_les_livrables(self):
        graphiste = self._user(
            'r_prod_aff', 'his_crm_pipeline.group_contenu_production', self.team_contenu,
        )
        demande = self._demande()

        with self.assertRaises(AccessError):
            self._livrable(demande, self.type_design).with_user(
                graphiste
            ).assignee_id = graphiste.id

    def test_les_dates_du_livrable_sont_posees_par_les_transitions(self):
        """Ce que les anciens triplets de champs ne savaient pas dire.

        Sans ces dates il n'y a ni delai de production, ni retard, ni debit —
        donc aucun indicateur possible sur la Production Contenu.
        """
        redacteur = self._user(
            'r_dates', 'his_crm_pipeline.group_contenu_production', self.team_contenu,
        )
        demande = self._demande(assignee_copy=redacteur.id)
        copy = self._livrable(demande, self.type_copy)
        self.assertFalse(copy.date_debut)
        self.assertFalse(copy.date_fin)

        copy.with_user(redacteur).statut = 'en_cours'
        self.assertTrue(copy.date_debut)
        self.assertFalse(copy.date_fin)

        copy.with_user(redacteur).statut = 'approuve'
        debut, fin = copy.date_debut, copy.date_fin
        self.assertTrue(fin)

        # Renvoye en revision : il n'est plus termine, mais il reste demarre.
        copy.with_user(redacteur).statut = 'revision_interne'
        self.assertFalse(copy.date_fin)
        self.assertEqual(copy.date_debut, debut, "la date de demarrage est un fait")

    def test_la_charge_par_personne_est_groupable(self):
        """La raison d'etre du modele : une ligne par livrable se groupe."""
        redacteur = self._user(
            'r_charge', 'his_crm_pipeline.group_contenu_production', self.team_contenu,
        )
        self._demande(assignee_copy=redacteur.id)
        self._demande(assignee_copy=redacteur.id)

        groupes = self.env['his.content.deliverable']._read_group(
            [('assignee_id', '=', redacteur.id)],
            groupby=['statut'], aggregates=['__count'],
        )
        self.assertEqual(dict(groupes), {'a_faire': 2})

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

    def test_le_demandeur_lit_les_etiquettes(self):
        """Sans groupe commercial, aucune etiquette n'est lisible par defaut.

        base.group_user ne recoit RIEN sur crm.tag dans Odoo natif
        (sales_team/security/ir.model.access.csv : 0,0,0,0). Les roles
        Admissions s'en sortent parce qu'ils portent group_sale_salesman, qui
        lui donne l'acces ; les roles Contenu n'en portent aucun, deliberement.

        Consequence sans droit explicite : une demande etiquetee devient
        illisible pour son propre demandeur des qu'une vue affiche tag_ids.
        """
        rh = self._user('r_rh_tags', 'his_crm_pipeline.group_contenu_demandeur')
        demande = self.env['crm.lead'].with_user(rh).create({
            'name': "Affiche RH", 'team_id': self.team_contenu.id,
            'tag_ids': [(4, self.env.ref('his_crm_pipeline.tag_urgent').id)],
        })

        self.assertEqual(
            demande.with_user(rh).tag_ids.mapped('name'), ["Urgent"],
        )

    def test_seule_la_priorisation_definit_la_taxonomie(self):
        """Etiqueter n'est pas definir les etiquettes.

        Le tri des demandes entrantes appartient a la Priorisation : c'est donc
        elle qui fait vivre la taxonomie, comme elle le fait deja pour les types
        de livrable. La Production etiquette avec ce qui existe, sans pouvoir
        inventer de nouveaux mots.
        """
        graphiste = self._user(
            'r_prod_tags', 'his_crm_pipeline.group_contenu_production', self.team_contenu,
        )
        strategiste = self._user(
            'r_prio_tags', 'his_crm_pipeline.group_contenu_priorisation', self.team_contenu,
        )

        with self.assertRaises(AccessError):
            self.env['crm.tag'].with_user(graphiste).create({'name': "Invente"})

        etiquette = self.env['crm.tag'].with_user(strategiste).create({'name': "Podcast"})
        self.assertEqual(etiquette.name, "Podcast")

        # Renommer oui, supprimer non : une etiquette effacee disparait de tous
        # les leads qui la portaient, sans trace.
        etiquette.with_user(strategiste).name = "Podcast long"
        with self.assertRaises(AccessError):
            etiquette.with_user(strategiste).unlink()

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

    # ============================== Direction ================================

    def test_la_direction_voit_les_deux_processus(self):
        """Le role large voit ce que chaque role etroit ne voit que chez lui.

        Sans rule_lead_direction ce test echouerait : toutes les autres regles
        sont bornees a user.crm_team_ids, et la Direction n'est membre d'aucune
        equipe — volontairement, pour rester hors de la rotation d'affectation.
        """
        candidature = self.env['crm.lead'].create({
            'name': "Candidat", 'team_id': self.team_ventes.id,
        })
        demande = self._demande()
        directeur = self._user('r_direction_vue', 'his_crm_pipeline.group_direction')

        self.assertFalse(directeur.crm_team_ids)
        vus = self.env['crm.lead'].with_user(directeur).search([])
        self.assertIn(candidature, vus)
        self.assertIn(demande, vus)

    def test_la_direction_herite_des_trois_echelles(self):
        directeur = self._user('r_direction_roles', 'his_crm_pipeline.group_direction')

        for role in (
            'his_crm_pipeline.group_admissions_responsable',
            'his_crm_pipeline.group_admissions_orientation',
            'his_crm_pipeline.group_contenu_approbation',
        ):
            self.assertTrue(directeur.has_group(role), role)

    def test_la_direction_ne_porte_pas_le_manager_commercial(self):
        """Deliberement : ce groupe donne l'unlink sur crm.lead, et tout ce
        qu'Odoo y ajoutera aux prochaines versions. Un directeur ne supprime
        pas une candidature — il la marque perdue."""
        directeur = self._user('r_direction_unlink', 'his_crm_pipeline.group_direction')
        candidature = self.env['crm.lead'].create({
            'name': "Candidat", 'team_id': self.team_ventes.id,
        })

        self.assertFalse(directeur.has_group('sales_team.group_sale_manager'))
        with self.assertRaises(AccessError):
            candidature.with_user(directeur).unlink()

    # ===================== Les portes natives du CRM =========================

    def _menus_visibles(self, user):
        """Les menus que cet utilisateur verrait reellement.

        _filter_visible_menus() filtre le recordset sur lequel il est appele —
        l'appeler sur un recordset vide rend toute assertion « absent » vraie
        pour rien. On part donc de tous les menus.
        """
        return self.env['ir.ui.menu'].with_user(user).search([])._filter_visible_menus()

    def test_les_portes_natives_sont_fermees_aux_roles_admissions(self):
        """Nos roles portent group_sale_salesman : ils heritent donc du menu
        CRM natif en entier. « Clients » ouvre tout le carnet de contacts en
        ecriture — donc les fiches etudiants, qui sont des res.partner."""
        conseillere = self._user(
            'r_conseil_menus', 'his_crm_pipeline.group_admissions_conseiller',
            self.team_ventes,
        )
        visibles = self._menus_visibles(conseillere)

        for xmlid in (
            'crm.res_partner_menu_customer',
            'crm.menu_crm_opportunities',
            'crm.sales_team_menu_team_pipeline',
            'crm.crm_menu_report',
            # Odoo la reserve deja a group_sale_manager : close sans que nous
            # y touchions. Le test la surveille quand meme — c'est une porte
            # dont nous dependons sans la tenir.
            'crm.crm_menu_config',
        ):
            self.assertNotIn(self.env.ref(xmlid), visibles, xmlid)

        # Ce qui reste ouvert : sa porte a elle, et son propre agenda.
        self.assertIn(self.env.ref('his_crm_pipeline.menu_admissions_pipeline'), visibles)
        self.assertIn(self.env.ref('crm.crm_lead_menu_my_activities'), visibles)

    def test_le_responsable_garde_l_analyse(self):
        """Arbitrer la file sans pouvoir la mesurer n'a pas de sens.

        La regle n'a pas change ; l'OUTIL qui la sert, si. Ce test exigeait le
        menu Reporting natif, ecrit quand on le croyait fonctionnel. Il ne
        l'est pas ici : ses quatre rapports mesurent `prorated_revenue`, derive
        d'`expected_revenue`, et ce pipeline ne porte AUCUN montant sur le lead
        — l'argent vit sur his.engagement, c'est une decision assumee du
        module. Verifie sur la base de recette : 13 candidatures, somme des
        `expected_revenue` a zero, quatre graphiques qui tracent correctement
        nos etapes et n'y empilent que des zeros.

        Un graphique de zeros n'est pas un rapport vide, c'est un rapport qui
        ment par omission — et qu'on finit par croire. Le responsable garde
        donc son analyse, mais c'est le cockpit qui la lui donne, avec des
        chiffres justes.
        """
        responsable = self._user(
            'r_resp_menus', 'his_crm_pipeline.group_admissions_responsable',
            self.team_ventes,
        )
        visibles = self._menus_visibles(responsable)

        self.assertIn(
            self.env.ref('his_crm_pipeline.menu_admissions_cockpit'), visibles,
            "Le responsable doit pouvoir mesurer sa file",
        )
        self.assertNotIn(self.env.ref('crm.crm_menu_report'), visibles)
        self.assertNotIn(self.env.ref('crm.res_partner_menu_customer'), visibles)

    def test_la_direction_garde_les_portes_natives(self):
        directeur = self._user('r_direction_menus', 'his_crm_pipeline.group_direction')
        visibles = self._menus_visibles(directeur)

        for xmlid in (
            'crm.res_partner_menu_customer',
            'crm.menu_crm_opportunities',
            'crm.sales_team_menu_team_pipeline',
        ):
            self.assertIn(self.env.ref(xmlid), visibles, xmlid)

        # Le Reporting natif ne fait plus partie des portes : il mesure un
        # chiffre d'affaires que ce pipeline ne porte pas. Voir
        # test_le_responsable_garde_l_analyse.
        self.assertNotIn(self.env.ref('crm.crm_menu_report'), visibles)
