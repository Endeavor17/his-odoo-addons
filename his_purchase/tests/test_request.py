# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Demande d'achat : creation, soumission, approbation, droits (AT-01 a AT-03)."""

from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged

from .common import HisPurchaseCase


@tagged("post_install", "-at_install")
class TestRequest(HisPurchaseCase):
    def test_creer_et_soumettre(self):
        request = self._request()
        self.assertTrue(request.name.startswith("DA/"), request.name)
        self.assertEqual(request.department_id, self.it)
        self.assertEqual(request.approver_id, self.head)
        self.assertFalse(request.his_purchase_type, "l'acheteur choisit le type, pas le departement")
        self.assertEqual(request.estimated_amount, 18000)
        request.action_submit()
        self.assertEqual(request.state, "submitted")

    def test_soumission_incomplete_nomme_ce_qui_manque(self):
        request = self._request(justification=False, line_ids=[])
        request.line_ids.unlink()
        with self.assertRaisesRegex(ValidationError, "Justification.*at least one line"):
            request.action_submit()

    def test_date_passee_refusee(self):
        request = self._request(date_required=date(2020, 1, 1))
        with self.assertRaises(ValidationError):
            request.action_submit()

    def test_ligne_sans_produit_ni_description(self):
        with self.assertRaises(ValidationError):
            self._request(lines=[{"product_qty": 1}])

    def test_le_demandeur_ne_modifie_plus_apres_soumission(self):
        request = self._request()
        request.action_submit()
        with self.assertRaises(UserError):
            request.justification = "changed"
        with self.assertRaises(UserError):
            request.line_ids.product_qty = 5
        # Le fil reste ouvert : le demandeur peut toujours ecrire et joindre.
        request.message_post(body="Here is the old invoice.")
        # L'equipe achats, elle, peut corriger.
        request.with_user(self.officer).line_ids.product_qty = 3

    def test_chacun_voit_ses_demandes_le_chef_son_departement(self):
        request = self._request()
        Request = self.env["his.purchase.request"]
        self.assertIn(request, Request.with_user(self.requester).search([]))
        self.assertIn(request, Request.with_user(self.head).search([]))
        self.assertIn(request, Request.with_user(self.officer).search([]))
        self.assertNotIn(request, Request.with_user(self.outsider).search([]))
        with self.assertRaises(AccessError):
            request.with_user(self.outsider).read(["name"])

    def test_seul_l_approbateur_approuve(self):
        request = self._request()
        request.action_submit()
        with self.assertRaises(AccessError):
            request.with_user(self.requester).action_approve()
        with self.assertRaises(AccessError):
            request.with_user(self.officer).action_approve()
        request.with_user(self.head).action_approve()
        self.assertEqual(request.state, "approved")
        self.assertEqual(request.approved_by_id, self.head)
        self.assertEqual(request.user_id, self.officer, "l'acheteur de la societe reprend la demande")

    def test_le_chef_qui_demande_est_approuve_par_le_directeur(self):
        request = self._request(user=self.head, employee=self.head_emp)
        self.assertEqual(request.approver_id, self.director)

    def test_refus_renvoie_en_brouillon_avec_motif(self):
        request = self._request()
        request.action_submit()
        wizard = (
            self.env["his.purchase.request.reject"]
            .with_user(self.head)
            .create({"request_id": request.id, "reason": "Use the stock toner first."})
        )
        wizard.action_reject()
        self.assertEqual(request.state, "draft")
        self.assertIn("Use the stock toner first.", request.message_ids[0].body)

    def test_annuler_puis_remettre_en_brouillon(self):
        request = self._request()
        request.action_cancel()
        self.assertEqual(request.state, "cancel")
        request.action_draft()
        self.assertEqual(request.state, "draft")

    def test_le_departement_ne_porte_plus_de_domaine_achat(self):
        self.assertNotIn("his_purchase_domain", self.env["hr.department"]._fields)
        request = self._request(user=self.cook, employee=self.cook_emp)
        self.assertFalse(request.his_purchase_type)

    def test_le_demandeur_ne_peut_pas_sourcer(self):
        request = self._approved_request()
        with self.assertRaises(AccessError):
            request.with_user(self.requester).action_open_source()

    def test_le_demandeur_ne_s_approuve_pas_lui_meme(self):
        request = self._request()
        for vals in (
            {"state": "approved"},
            {"approved_by_id": self.requester.id},
            {"approver_id": self.requester.id},
            {"his_purchase_type": "usual"},
        ):
            with self.assertRaises(AccessError, msg=vals):
                request.write(vals)
        with self.assertRaises(AccessError):
            self._request(state="approved")
        self.assertEqual(request.state, "draft")
        # L'acheteur choisit le type (spec 2026-10-20, section 4.1).
        request.with_user(self.officer).his_purchase_type = "usual"

    def test_le_demandeur_enregistre_sa_demande_par_le_formulaire(self):
        # Staging 2026-10-19 : le formulaire envoie l'etat par defaut et les
        # champs calcules ; la garde refusait toute demande neuve du demandeur.
        with Form(self.env["his.purchase.request"].with_user(self.requester)) as form:
            form.justification = "The printer of room 12 is empty."
            form.date_required = date(2026, 11, 30)
            with form.line_ids.new() as line:
                line.product_id = self.toner
                line.product_qty = 2
        request = form.record
        self.assertEqual(request.state, "draft")
        self.assertEqual(request.approver_id, self.head)

    def test_le_demandeur_ne_choisit_pas_son_approbateur_a_la_creation(self):
        request = self._request(approver_id=self.requester.id, his_purchase_type="usual")
        self.assertEqual(request.approver_id, self.head)
        self.assertFalse(request.his_purchase_type)

    def test_le_demandeur_ne_choisit_pas_son_departement(self):
        # Recette P-07 : le departement decide du domaine, donc de l'approbateur.
        with self.assertRaises(AccessError):
            self._request(department_id=self.restaurant.id)
        request = self._request(department_id=self.it.id)
        with self.assertRaises(AccessError):
            request.write({"department_id": self.restaurant.id})
        request.with_user(self.officer).department_id = self.restaurant
        self.assertEqual(request.department_id, self.restaurant)

    def test_le_nouveau_directeur_devient_l_approbateur(self):
        self.company.his_purchase_director_id = False
        request = self._request(user=self.outsider, employee=self.outsider_emp)
        self.assertFalse(request.approver_id)
        self.company.his_purchase_director_id = self.director
        self.assertEqual(request.approver_id, self.director)
        request.action_submit()

    def test_l_acheteur_suit_le_poste(self):
        # Remplacer l'acheteur = changer l'occupant du poste, rien a choisir sur la demande.
        self.env["hr.employee"].search([("user_id", "=", self.officer.id)]).job_id = False
        self.env["hr.employee"].create(
            {"name": self.manager.name, "user_id": self.manager.id, "job_id": self.officer_job.id}
        )
        self.assertEqual(self._approved_request().user_id, self.manager)
