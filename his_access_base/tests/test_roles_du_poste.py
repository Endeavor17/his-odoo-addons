# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""L'attribution des roles par le poste.

Le point qui merite des tests n'est pas « poser les roles » — c'est la
distinction entre un role venu DU POSTE et une DEROGATION individuelle. Sans
elle, une resynchronisation efface les exceptions : la conseillere a qui on
avait ouvert la Production Contenu pour un remplacement perd son acces un matin,
et personne ne comprend pourquoi.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRolesDuPoste(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.annuaire = cls.env.ref('his_access_base.group_annuaire')
        cls.interne = cls.env.ref('base.group_user')

    def _poste(self, nom, groupes=()):
        return self.env['hr.job'].create({
            'name': nom,
            'group_ids': [(6, 0, [g.id for g in groupes])],
        })

    def _employe(self, nom, poste=None, avec_compte=True):
        user = False
        if avec_compte:
            user = self.env['res.users'].create({
                'name': nom, 'login': 'zz_%s' % nom,
                'group_ids': [(6, 0, [self.interne.id])],
            })
        return self.env['hr.employee'].create({
            'name': nom,
            'job_id': poste.id if poste else False,
            'user_id': user.id if user else False,
        })

    # ------------------------------------------------------------------------

    def test_le_poste_pose_ses_roles(self):
        poste = self._poste("Assistante RH", [self.annuaire])
        employe = self._employe("arh", poste)

        self.assertTrue(employe.user_id.has_group('his_access_base.group_annuaire'))

    def test_changer_de_poste_retire_les_roles_de_l_ancien(self):
        """Sans cela, quelqu'un accumule les acces de toute sa carriere."""
        ancien = self._poste("Ancien poste", [self.annuaire])
        nouveau = self._poste("Nouveau poste")
        employe = self._employe("mute", ancien)
        self.assertTrue(employe.user_id.has_group('his_access_base.group_annuaire'))

        employe.job_id = nouveau

        self.assertFalse(employe.user_id.has_group('his_access_base.group_annuaire'))

    def test_une_derogation_individuelle_survit_a_la_reconciliation(self):
        """Le test qui compte.

        Un role pose a la main n'appartient pas au poste : la reconciliation ne
        doit jamais le retirer, meme quand le poste change entierement.
        """
        poste = self._poste("Poste sans role")
        employe = self._employe("derog", poste)
        # Derogation : accordee a la main, hors de tout poste.
        employe.user_id.sudo().write({'group_ids': [(4, self.annuaire.id)]})

        employe.job_id.action_appliquer_roles()

        self.assertTrue(
            employe.user_id.has_group('his_access_base.group_annuaire'),
            "la reconciliation a efface une derogation individuelle",
        )

    def test_retirer_un_role_du_poste_le_retire_des_comptes(self):
        poste = self._poste("Poste evolutif", [self.annuaire])
        employe = self._employe("evol", poste)

        poste.group_ids = [(5, 0, 0)]
        poste.action_appliquer_roles()

        self.assertFalse(employe.user_id.has_group('his_access_base.group_annuaire'))

    def test_un_employe_sans_compte_odoo_ne_fait_pas_echouer(self):
        """Le cas NORMAL, pas une anomalie : la majorite de l'organigramme —
        cuisine, securite, entretien — ne se connecte pas a Odoo."""
        poste = self._poste("Agent de cuisine", [self.annuaire])
        employe = self._employe("cuisine", poste, avec_compte=False)

        self.assertEqual(employe._his_appliquer_roles_du_poste(), 0)

    def test_le_cron_signale_sans_corriger(self):
        """Corriger en silence masquerait une attribution manuelle qui
        contredit le poste — ce qu'une revue d'acces doit precisement voir."""
        poste = self._poste("Poste desynchro", [self.annuaire])
        employe = self._employe("desync", poste)
        # On desynchronise en ne passant pas par la reconciliation.
        employe.user_id.sudo().write({'role_ids_du_poste': [(5, 0, 0)]})

        ecarts = self.env['hr.employee']._cron_reconcilier_roles()

        self.assertTrue(any("desync" in e for e in ecarts))
        self.assertFalse(
            employe.user_id.role_ids_du_poste,
            "le cron doit signaler l'ecart, pas le corriger",
        )
