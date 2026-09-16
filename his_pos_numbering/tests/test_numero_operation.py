from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNumeroOperation(TransactionCase):
    """Le numero affiche en caisse doit arriver dans le navigateur, et etre par caisse.

    Ce module n'affiche pas un numero qu'il calcule : il affiche
    `sequence_number`, que le coeur pose deja depuis
    `pos.config.order_seq_id`. Ces tests pinnent les deux proprietes dont
    l'affichage depend, cote SERVEUR.

    Ce qu'ils ne peuvent PAS prouver : le texte rendu sur l'onglet. Cela
    demande un tour POS, et un tour est SKIP silencieux sans
    `python3-websocket` ni navigateur dans le conteneur -- le resume affiche
    alors « 0 failed » sans avoir rien joue. Un vert creux est pire que pas de
    test : la verification du rendu se fait donc en ouvrant une vraie caisse,
    et c'est dit dans le README plutot que simule ici.
    """

    def setUp(self):
        super().setUp()
        self.Order = self.env["pos.order"]
        self.config = self._caisse("Till Numerotation")

    def _caisse(self, nom):
        """Une caisse dont la session est ouverte, comme le fait Odoo.

        `open_ui()` et non `pos.session.create()` : une caisse n'accepte
        qu'une seule session ouverte a la fois (`_check_pos_config`), donc
        creer une session par commande leve « Another session is already
        opened for this point of sale ». C'est l'idiome du depot, cf.
        `his_meal_management/tests/test_meal_credits.py`.
        """
        config = self.env["pos.config"].create({"name": nom})
        config.open_ui()
        return config

    def test_le_numero_arrive_dans_le_navigateur(self):
        """`pos.order` est lu avec une liste de champs VIDE, donc tous les champs.

        C'est ce qui rend l'affichage possible sans toucher a une liste
        blanche. Si un Odoo futur se met a restreindre les champs de
        `pos.order`, `sequence_number` cesse d'arriver, l'onglet retombe sur le
        marqueur provisoire pour TOUTES les commandes, et le symptome
        ressemblera a « le module ne marche plus » sans rien dans le journal.
        Mieux vaut echouer ici, en nommant la cause.
        """
        champs = self.Order._load_pos_data_fields(self.config)
        self.assertFalse(
            champs,
            "le coeur restreint desormais les champs de pos.order : "
            "verifier que sequence_number y figure, sinon l'onglet n'affichera plus rien",
        )

        commande = self._commande(self.config)
        charge = commande.read(champs, load=False)[0]
        self.assertIn(
            "sequence_number",
            charge,
            "sequence_number ne parvient pas au navigateur : l'onglet restera au marqueur provisoire",
        )
        self.assertEqual(charge["sequence_number"], commande.sequence_number)

    def test_le_compteur_est_par_caisse(self):
        """Deux caisses numerotent chacune de leur cote.

        `order_seq_id` est cree par `pos.config._create_sequences()`, une
        sequence par caisse. Si ce n'etait pas le cas, deux caisses se
        partageraient une suite et le Restaurant sauterait de 7 a 12 parce que
        la Cafétéria a vendu entre-temps.
        """
        autre = self._caisse("Till Numerotation Bis")
        self.assertNotEqual(
            self.config.order_seq_id,
            autre.order_seq_id,
            "les deux caisses partagent une sequence : la numerotation sautera",
        )

        premiere_ici = self._commande(self.config).sequence_number
        premiere_la_bas = self._commande(autre).sequence_number
        suivante_ici = self._commande(self.config).sequence_number

        self.assertEqual(
            suivante_ici,
            premiere_ici + 1,
            "une vente sur l'autre caisse a decale le compteur de celle-ci",
        )
        self.assertEqual(
            premiere_la_bas,
            1,
            "une caisse neuve doit commencer sa propre numerotation a 1",
        )

    def _commande(self, config):
        """Une commande minimale sur la session ouverte de cette caisse.

        `sequence_number` est pose par `_complete_values_from_session` au
        `create()` : on passe donc par le vrai chemin, sans fournir le champ,
        sinon le test se contenterait de relire ce qu'il a lui-meme ecrit.
        """
        return self.Order.create(
            {
                "session_id": config.current_session_id.id,
                "company_id": config.company_id.id,
                "amount_tax": 0,
                "amount_total": 0,
                "amount_paid": 0,
                "amount_return": 0,
            }
        )
