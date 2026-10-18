# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Article absent du catalogue : les gestionnaires de stock le creent (2026-10-18).

Le demandeur decrit l'article ; a l'approbation, chaque gestionnaire de stock
recoit un a-faire ; il pose l'article sur la ligne, rien d'autre ; l'a-faire se
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
        # product.group_product_manager : his_stock_mdm le donne aux gestionnaires
        # de stock (recette P-17) ; ce module n'est pas installe ici.
        cls.magasinier = new_test_user(
            cls.env, login="his_stock_mgr", groups="stock.group_stock_manager,product.group_product_manager"
        )
        cls.magasinier_2 = new_test_user(
            cls.env, login="his_stock_mgr2", groups="stock.group_stock_manager,product.group_product_manager"
        )

    def _catalogue_activities(self, request):
        type_ = self.env.ref("his_purchase.mail_act_catalogue")
        return request.activity_ids.filtered(lambda a: a.activity_type_id == type_)

    def test_approbation_previent_chaque_gestionnaire_de_stock(self):
        request = self._approved_request(lines=[LIGNE_LIBRE])
        self.assertTrue(request.his_needs_product)
        activities = self._catalogue_activities(request)
        self.assertIn(self.magasinier, activities.user_id)
        self.assertIn(self.magasinier_2, activities.user_id)
        self.assertIn("Epson EB-X41", activities[0].summary)

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
        with self.assertRaisesRegex(UserError, "stock managers"):
            self._source_rfq(request, self.supplier_a)
