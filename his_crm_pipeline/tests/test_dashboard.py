# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Les indicateurs sont testes sur des donnees connues.

Un tableau de bord faux est pire qu'absent : il est cru. Chaque test pose un
nombre d'enregistrements qu'il connait et verifie le chiffre affiché, plus le
fait que l'action attachee ramene bien ce meme nombre — c'est ce dernier point
qui attrape une definition qui derive entre la tuile et le clic.
"""
from datetime import date, timedelta

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team_ventes = cls.env.ref('his_crm_pipeline.crm_team_ventes')
        cls.team_contenu = cls.env.ref('his_crm_pipeline.crm_team_contenu')
        cls.st_nouveau = cls.env.ref('his_crm_pipeline.stage_vente_nouveau')
        # Pas l'etape gagnante : une contrainte serveur refuse qu'on l'y mette a
        # la main, y compris en test. C'est voulu — un lead n'est gagne qu'a
        # l'encaissement. On mesure donc l'avancement sur « Pre-admis ».
        cls.st_pre_admis = cls.env.ref('his_crm_pipeline.stage_vente_pre_admis')
        cls.aujourdhui = date.today()
        cls.Dashboard = cls.env['his.dashboard']

    def _tuile(self, spec, cle):
        return next(t for t in spec['tiles'] if t['cle'] == cle)

    def _candidatures(self, combien, stage=None):
        return self.env['crm.lead'].create([{
            'name': "Candidat %s" % i,
            'team_id': self.team_ventes.id,
            'stage_id': (stage or self.st_nouveau).id,
        } for i in range(combien)])

    # ------------------------------------------------------------------------

    def test_les_candidatures_du_jour_sont_comptees(self):
        """La borne haute doit inclure la journee en cours.

        create_date est un Datetime : compare a une date seule il vaut minuit,
        et tout ce qui a ete cree aujourd'hui tombe hors periode. Le cockpit
        affichait alors zero un jour de forte activite.
        """
        self._candidatures(3)

        spec = self.Dashboard.get_admissions(self.aujourdhui, self.aujourdhui)

        self.assertEqual(self._tuile(spec, 'candidatures')['valeur'], 3)

    def test_chaque_tuile_ouvre_exactement_ce_qu_elle_annonce(self):
        """Le test qui attrape une definition fausse.

        Si le domaine de l'action et le calcul de la tuile divergent, le
        directeur clique sur « 12 » et trouve 30 lignes. Personne ne fait plus
        confiance au tableau de bord ensuite.
        """
        self._candidatures(4)
        self._candidatures(2, stage=self.st_pre_admis)

        spec = self.Dashboard.get_admissions(self.aujourdhui, self.aujourdhui)

        for tuile in spec['tiles']:
            if not tuile.get('action') or tuile.get('unite') == '%':
                continue
            trouves = self.env[tuile['action']['res_model']].search_count(
                tuile['action']['domain'],
            )
            self.assertEqual(
                trouves, tuile['valeur'],
                "la tuile « %s » n'ouvre pas ce qu'elle annonce" % tuile['label'],
            )

    def test_le_taux_de_conversion_ne_divise_pas_par_zero(self):
        spec = self.Dashboard.get_admissions(self.aujourdhui, self.aujourdhui)
        self.assertEqual(self._tuile(spec, 'conversion')['valeur'], 0)

    def test_l_ecart_est_muet_quand_la_periode_precedente_est_vide(self):
        """Passer de 0 a 5 n'est pas « +100 % » : ce n'est pas exprimable.

        Mieux vaut ne rien afficher qu'un pourcentage qui ment.
        """
        self._candidatures(5)
        spec = self.Dashboard.get_admissions(self.aujourdhui, self.aujourdhui)
        self.assertIsNone(self._tuile(spec, 'candidatures')['ecart'])

    def test_l_objectif_donne_atteinte_rythme_et_projection(self):
        self._candidatures(30)
        debut = self.aujourdhui - timedelta(days=9)
        self.env['his.objectif'].create({
            'name': "Rentree 2026", 'axe': 'candidatures',
            'valeur_cible': 100,
            'date_debut': debut, 'date_fin': debut + timedelta(days=19),
        })

        tuile = self._tuile(
            self.Dashboard.get_admissions(self.aujourdhui, self.aujourdhui),
            'candidatures',
        )

        self.assertEqual(tuile['cible'], 100)
        self.assertEqual(tuile['atteinte'], 30.0)
        self.assertEqual(tuile['jours_restants'], 10)
        # 70 restants sur 10 jours.
        self.assertEqual(tuile['rythme_requis'], 7.0)
        # 30 en 10 jours ecoules, sur 20 jours au total.
        self.assertEqual(tuile['projection'], 60)

    def test_sans_objectif_la_tuile_n_invente_pas_de_cible(self):
        self._candidatures(2)
        tuile = self._tuile(
            self.Dashboard.get_admissions(self.aujourdhui, self.aujourdhui),
            'candidatures',
        )
        self.assertNotIn('cible', tuile)

    def test_l_entonnoir_ne_remonte_jamais(self):
        """Un entonnoir cumulatif : chaque marche contient les suivantes.

        Compter les seuls presents dans l'etape ferait un entonnoir qui
        remonte, dont le taux de passage ne veut rien dire.
        """
        self._candidatures(5)
        self._candidatures(2, stage=self.st_pre_admis)

        marches = self.Dashboard.get_admissions(
            self.aujourdhui, self.aujourdhui,
        )['funnel']

        comptes = [m['count'] for m in marches]
        self.assertEqual(comptes, sorted(comptes, reverse=True))
        self.assertEqual(comptes[0], 7, "la premiere marche porte tout le monde")

        pre_admis = next(m for m in marches if m['label'] == self.st_pre_admis.name)
        self.assertEqual(pre_admis['count'], 2)
        # Personne n'a encaisse : la marche gagnante est vide, et c'est la
        # regle metier — un lead n'est gagne qu'au paiement.
        self.assertEqual(comptes[-1], 0)

    def test_la_vue_direction_reprend_les_memes_calculs(self):
        """Deux ecrans qui se contredisent, c'est un arbitrage impossible."""
        self._candidatures(6)

        direction = self.Dashboard.get_direction(self.aujourdhui, self.aujourdhui)
        admissions = self.Dashboard.get_admissions(self.aujourdhui, self.aujourdhui)

        self.assertEqual(
            self._tuile(direction, 'candidatures')['valeur'],
            self._tuile(admissions, 'candidatures')['valeur'],
        )

    def test_la_direction_ne_montre_que_les_files_non_vides(self):
        spec = self.Dashboard.get_direction(self.aujourdhui, self.aujourdhui)
        self.assertTrue(all(f['count'] for f in spec['attention']))


@tagged('post_install', '-at_install')
class TestDashboardRoles(TransactionCase):
    """Les cockpits joues par de vrais utilisateurs, jamais en superuser.

    Trois defauts ne se voyaient que la : un KeyError sur les modeles sans
    champ `name`, une erreur de droits sur les objectifs pour le role
    Priorisation, et des files calculees hors de la portee de l'utilisateur.
    Les tests Odoo tournent en superutilisateur, qui contourne ACL et regles —
    un cockpit valide ainsi ne prouve rien.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.aujourdhui = date.today()

    def _user(self, login, role, team_xmlid=None):
        user = self.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id, self.env.ref(role).id,
            ])],
        })
        if team_xmlid:
            self.env['crm.team.member'].create({
                'crm_team_id': self.env.ref(team_xmlid).id, 'user_id': user.id,
            })
        return user

    def _appeler(self, user, methode):
        return getattr(
            self.env['his.dashboard'].with_user(user), methode,
        )(self.aujourdhui, self.aujourdhui)

    def test_chaque_role_ouvre_son_cockpit(self):
        cas = [
            ('d_resp', 'his_crm_pipeline.group_admissions_responsable',
             'his_crm_pipeline.crm_team_ventes', 'get_admissions'),
            ('d_prio', 'his_crm_pipeline.group_contenu_priorisation',
             'his_crm_pipeline.crm_team_contenu', 'get_contenu'),
            ('d_dir', 'his_crm_pipeline.group_direction', None, 'get_direction'),
        ]
        for login, role, team, methode in cas:
            user = self._user(login, role, team)
            spec = self._appeler(user, methode)
            self.assertTrue(spec['tiles'], "%s : aucune tuile" % login)

    def test_une_file_nomme_ses_enregistrements_sans_champ_name(self):
        """his.engagement n'a pas de champ `name` — display_name le remplace.

        Le cockpit Dossiers levait un KeyError des qu'une file etait peuplee.
        """
        directeur = self._user('d_dir_files', 'his_crm_pipeline.group_direction')
        spec = self._appeler(directeur, 'get_direction')

        for file in spec['attention']:
            for ligne in file['apercu']:
                self.assertTrue(ligne['nom'], file['label'])

    def test_l_objectif_s_affiche_sans_droit_sur_le_modele(self):
        """La Priorisation n'a aucun droit sur his.objectif, et doit pourtant
        voir sa cible : c'est un chiffre affiche, pas une donnee reservee.
        L'ecriture, elle, reste a la Direction."""
        self.env['his.objectif'].create({
            'name': "Publications", 'axe': 'publications', 'valeur_cible': 50,
            'date_debut': self.aujourdhui - timedelta(days=5),
            'date_fin': self.aujourdhui + timedelta(days=5),
        })
        prio = self._user(
            'd_prio_obj', 'his_crm_pipeline.group_contenu_priorisation',
            'his_crm_pipeline.crm_team_contenu',
        )

        spec = self._appeler(prio, 'get_contenu')
        tuile = next(t for t in spec['tiles'] if t['cle'] == 'publications')
        self.assertEqual(tuile['cible'], 50)

        with self.assertRaises(AccessError, msg="la Priorisation ne fixe pas les cibles"):
            self.env['his.objectif'].with_user(prio).create({
                'name': "Cible pirate", 'axe': 'publications', 'valeur_cible': 1,
                'date_debut': self.aujourdhui, 'date_fin': self.aujourdhui,
            })

    def test_un_cockpit_ne_montre_que_ce_que_l_utilisateur_peut_voir(self):
        """Une conseillere ne voit que ses candidatures, jusque dans le chiffre.

        Un cockpit qui compterait en sudo afficherait a chacun le total du
        groupe — et donnerait a une conseillere le sentiment d'un retard qui
        n'est pas le sien.
        """
        ventes = self.env.ref('his_crm_pipeline.crm_team_ventes')
        conseillere = self._user(
            'd_conseil', 'his_crm_pipeline.group_admissions_conseiller',
            'his_crm_pipeline.crm_team_ventes',
        )
        etape = self.env.ref('his_crm_pipeline.stage_vente_pris_en_charge')
        self.env['crm.lead'].create([
            {'name': "A elle", 'team_id': ventes.id, 'stage_id': etape.id,
             'user_id': conseillere.id},
            {'name': "A une autre", 'team_id': ventes.id, 'stage_id': etape.id,
             'user_id': self.env.ref('base.user_admin').id},
        ])

        vu = self._appeler(conseillere, 'get_admissions')
        tuile = next(t for t in vu['tiles'] if t['cle'] == 'candidatures')
        lus = self.env['crm.lead'].with_user(conseillere).search_count(
            tuile['action']['domain'],
        )
        self.assertEqual(tuile['valeur'], lus)
