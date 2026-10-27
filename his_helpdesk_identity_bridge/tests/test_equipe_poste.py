# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""L'equipe Support suit le poste « Support Officer » : un remplacement ne demande aucun geste."""

from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestEquipePoste(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.poste = cls.env.ref("his_helpdesk_identity_bridge.job_support")
        cls.support = cls.env.ref("his_helpdesk_identity_bridge.team_support")
        # Le role metier du poste vient du catalogue (his_role_catalogue), qui
        # n'est pas une dependance : on le pose ici.
        cls.poste.role_ids = cls.env["his.role"].create(
            {
                "name": "Helpdesk Manager",
                "group_ids": [(6, 0, [cls.env.ref("helpdesk_mgmt.group_helpdesk_manager").id])],
            }
        )
        cls.autre_poste = cls.env["hr.job"].create({"name": "Comptable"})
        cls.karim = new_test_user(cls.env, login="karim_support")
        cls.nadia = new_test_user(cls.env, login="nadia_support")

    def _employe(self, user, poste):
        return self.env["hr.employee"].create({"name": user.name, "user_id": user.id, "job_id": poste.id})

    def test_prendre_le_poste_donne_l_equipe_et_le_role(self):
        self._employe(self.karim, self.poste)
        self.assertEqual(self.support.user_ids, self.karim)
        self.assertTrue(self.karim.has_group("helpdesk_mgmt.group_helpdesk_manager"))

    def test_le_remplacant_prend_la_place(self):
        karim = self._employe(self.karim, self.poste)
        nadia = self._employe(self.nadia, self.autre_poste)
        karim.job_id = self.autre_poste
        nadia.job_id = self.poste
        self.assertEqual(self.support.user_ids, self.nadia)
        self.assertFalse(self.karim.has_group("helpdesk_mgmt.group_helpdesk_manager"))

    def test_un_depart_vide_l_equipe(self):
        karim = self._employe(self.karim, self.poste)
        karim.active = False
        self.assertFalse(self.support.user_ids)

    def test_une_equipe_sans_poste_garde_ses_membres(self):
        equipe = self.env["helpdesk.ticket.team"].create({"name": "Libre", "user_ids": [self.nadia.id]})
        self._employe(self.karim, self.poste)
        self.assertEqual(equipe.user_ids, self.nadia)

    def _ticket(self):
        return self.env["helpdesk.ticket"].create({"name": "Wi-Fi", "description": "<p>Pas de reseau</p>"})

    def test_l_agent_unique_recoit_le_ticket(self):
        self._employe(self.karim, self.poste)
        self.assertEqual(self._ticket().user_id, self.karim)

    def test_deux_agents_le_ticket_reste_a_attribuer(self):
        self._employe(self.karim, self.poste)
        self._employe(self.nadia, self.poste)
        self.assertFalse(self._ticket().user_id)
