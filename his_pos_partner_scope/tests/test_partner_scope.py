# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Un candidat au recrutement n'est pas un client de la caisse."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPartnerScope(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Limite relevee : sur une base reelle le contact de test tomberait
        # sinon au-dela des 100 premiers et le test ne prouverait rien.
        cls.env["ir.config_parameter"].sudo().set_param(
            "point_of_sale.limited_customer_count",
            100000,
        )
        cls.config = cls.env["pos.config"].search([], limit=1) or cls.env["pos.config"].create(
            {"name": "Caisse de test"}
        )
        cls.applicant = cls.env["hr.applicant"].create(
            {
                "partner_name": "Zineb Candidate",
                "email_from": "zineb.candidate.pos@example.com",
            }
        )
        cls.partner = cls.applicant.partner_id

    def _loaded(self):
        return {row[0] for row in self.config.get_limited_partners_loading()}

    def _searched(self):
        found = self.env["res.partner"].get_new_partner(
            self.config.id,
            [("name", "ilike", "Zineb Candidate")],
            0,
        )
        return {row["id"] for row in found["res.partner"]}

    def test_un_candidat_seul_est_ecarte_du_chargement_et_de_la_recherche(self):
        self.assertTrue(self.partner)
        self.assertNotIn(self.partner.id, self._loaded())
        self.assertNotIn(self.partner.id, self._searched())

    def test_un_contact_ordinaire_reste_visible(self):
        client = self.env["res.partner"].create({"name": "Zineb Candidate (cliente)"})
        self.assertIn(client.id, self._loaded())
        self.assertIn(client.id, self._searched())

    def test_une_fiche_etudiant_le_rend_visible(self):
        self.env["his.person"].sudo().create(
            {
                "partner_id": self.partner.id,
                "type_personne": "etudiant",
                "source_system": "manual",
            }
        )
        self.assertIn(self.partner.id, self._loaded())
        self.assertIn(self.partner.id, self._searched())

    def test_une_fiche_candidat_ne_suffit_pas(self):
        self.env["his.person"].sudo().create(
            {
                "partner_id": self.partner.id,
                "type_personne": "candidat",
                "source_system": "manual",
            }
        )
        self.assertNotIn(self.partner.id, self._loaded())

    def test_une_commande_pos_le_rend_visible(self):
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.uid,
            }
        )
        self.env["pos.order"].create(
            {
                "session_id": session.id,
                "partner_id": self.partner.id,
                "amount_tax": 0.0,
                "amount_total": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            }
        )
        self.assertIn(self.partner.id, self._loaded())

    def test_le_contact_d_un_utilisateur_n_est_jamais_ecarte(self):
        user = self.env["res.users"].create(
            {
                "name": "Zineb Candidate",
                "login": "zineb.pos.scope",
            }
        )
        self.env["hr.applicant"].create(
            {
                "partner_id": user.partner_id.id,
                "partner_name": "Zineb Candidate",
            }
        )
        self.assertIn(user.partner_id.id, self._loaded())
