# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Article absent du catalogue : le magasinier le cree (2026-10-18, role
dedie le 2026-10-19).

Le demandeur decrit l'article ; a l'approbation, chaque responsable catalogue
recoit un a-faire (a defaut, l'acheteur de la demande) ; il pose l'article sur la ligne, rien d'autre ; l'a-faire se
clot quand plus aucune ligne n'attend.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from .common import HisPurchaseCase

LIGNE_LIBRE = {"description": "Ampoule videoprojecteur Epson EB-X41", "product_qty": 1}


@tagged("post_install", "-at_install")
class TestArticleACreer(HisPurchaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.magasinier = new_test_user(cls.env, login="his_catalogue", groups="his_purchase.group_catalogue")
        cls.magasinier_2 = new_test_user(cls.env, login="his_catalogue2", groups="his_purchase.group_catalogue")
        # Les directeurs portent Inventaire / Administrateur sur le staging : le
        # role de gestion du stock ne fait plus recevoir l'a-faire.
        cls.stock_manager = new_test_user(
            cls.env, login="his_stock_mgr", groups="stock.group_stock_manager,product.group_product_manager"
        )

    def _catalogue_activities(self, request):
        type_ = self.env.ref("his_purchase.mail_act_catalogue")
        return request.activity_ids.filtered(lambda a: a.activity_type_id == type_)

    def test_approbation_previent_chaque_responsable_catalogue(self):
        request = self._approved_request(lines=[LIGNE_LIBRE])
        self.assertTrue(request.his_needs_product)
        activities = self._catalogue_activities(request)
        self.assertEqual(activities.user_id, self.magasinier | self.magasinier_2)
        self.assertIn("Epson EB-X41", activities[0].summary)

    def test_le_gestionnaire_de_stock_ne_recoit_pas_l_a_faire(self):
        request = self._approved_request(lines=[LIGNE_LIBRE])
        self.assertNotIn(self.stock_manager, self._catalogue_activities(request).user_id)

    def test_sans_responsable_catalogue_l_acheteur_est_prevenu(self):
        (self.magasinier | self.magasinier_2).write(
            {"group_ids": [(3, self.env.ref("his_purchase.group_catalogue").id)]}
        )
        request = self._approved_request(lines=[LIGNE_LIBRE])
        self.assertEqual(self._catalogue_activities(request).user_id, self.officer)

    def test_le_gestionnaire_de_stock_ne_pose_pas_l_article(self):
        request = self._approved_request(lines=[LIGNE_LIBRE])
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            request.line_ids.with_user(self.stock_manager).write({"product_id": self.toner.id})

    def test_pas_d_a_faire_quand_tout_est_au_catalogue(self):
        request = self._approved_request()
        self.assertFalse(request.his_needs_product)
        self.assertFalse(self._catalogue_activities(request))

    def test_le_gestionnaire_pose_l_article_et_l_a_faire_se_clot(self):
        request = self._approved_request(lines=[LIGNE_LIBRE])
        ampoule = (
            self.env["product.product"]
            .with_user(self.magasinier)
            .create({"name": "Ampoule ELPLP78", "type": "consu", "purchase_ok": True})
        )
        self.env.invalidate_all()
        line = request.line_ids.with_user(self.magasinier)
        line.write({"product_id": ampoule.id})
        self.assertEqual(request.line_ids.product_id, ampoule)
        self.assertFalse(request.his_needs_product)
        self.assertFalse(self._catalogue_activities(request))

    def test_par_le_formulaire_de_la_demande(self):
        # Le formulaire enregistre la ligne a travers la demande (line_ids).
        request = self._approved_request(lines=[LIGNE_LIBRE])
        self.env.invalidate_all()
        request.with_user(self.magasinier).write(
            {"line_ids": [(1, request.line_ids.id, {"product_id": self.toner.id})]}
        )
        self.assertEqual(request.line_ids.product_id, self.toner)

    def test_le_gestionnaire_ne_touche_ni_quantite_ni_prix(self):
        request = self._approved_request(lines=[LIGNE_LIBRE])
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            request.line_ids.with_user(self.magasinier).write({"product_qty": 50})
        with self.assertRaises(UserError):
            request.with_user(self.magasinier).write({"justification": "Autre chose"})

    def test_le_gestionnaire_ne_remplace_pas_un_article_deja_choisi(self):
        request = self._approved_request()
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            request.line_ids.with_user(self.magasinier).write({"product_id": self.tomatoes.id})

    def test_le_gestionnaire_ne_modifie_pas_un_brouillon(self):
        request = self._request(lines=[LIGNE_LIBRE])
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            request.line_ids.with_user(self.magasinier).write({"product_id": self.toner.id})

    def test_le_demandeur_ne_cree_pas_d_article(self):
        with self.assertRaises(AccessError):
            self.env["product.product"].with_user(self.requester).create({"name": "Ampoule maison"})

    def test_l_acheteur_est_prevenu_de_l_attente(self):
        request = self._approved_request(lines=[LIGNE_LIBRE])
        with self.assertRaisesRegex(UserError, "catalogue team"):
            self._source_rfq(request, self.supplier_a)
