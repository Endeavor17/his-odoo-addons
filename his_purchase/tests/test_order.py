# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Demandes de prix, choix du fournisseur, approbation (AT-04 a AT-12, AT-26)."""

from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .common import HisPurchaseCase


@tagged("post_install", "-at_install")
class TestOrder(HisPurchaseCase):
    def test_un_seul_fournisseur_sans_assistant(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        self.assertEqual(request.state, "sourcing")
        self.assertEqual(order.his_request_id, request)
        self.assertEqual(order.order_line.his_request_line_id, request.line_ids)
        self.assertEqual(order.his_purchase_type, "investment", "la commande reprend le type de la demande")
        self.assertTrue(order.his_reply_by)
        order.order_line.price_unit = 8500
        res = order.with_user(self.officer).button_confirm()
        self.assertIs(res, True, "pas d'assistant de choix sans concurrence")
        self.assertEqual(order.his_choice_criterion, "only_supplier")
        self.assertEqual(order.his_supplier_answer, "quoted")
        self.assertEqual(order.state, "to approve", "toute commande est approuvee")

    def test_concurrence_ouvre_l_assistant_prerempli(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 9500
        cheaper = self._alternative(order, self.supplier_b, 9000)
        self.assertEqual(cheaper.his_request_id, request)
        self.assertEqual(cheaper.order_line.his_request_line_id, request.line_ids)
        action = cheaper.with_user(self.officer).button_confirm()
        self.assertEqual(action["res_model"], "his.purchase.choice")
        self.assertEqual(action["context"]["default_criterion"], "lowest_price")
        action = order.with_user(self.officer).button_confirm()
        self.assertFalse(action["context"]["default_criterion"], "la plus chere n'est pas preremplie")

    def test_choisir_plus_cher_est_permis_et_trace(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 9500
        self._alternative(order, self.supplier_b, 9000)
        choice = (
            self.env["his.purchase.choice"]
            .with_user(self.officer)
            .create({"order_id": order.id, "criterion": "quality", "note": "Original cartridges only."})
        )
        self.assertFalse(choice.is_cheapest)
        action = choice.action_confirm()
        # Puis Odoo demande quoi faire des offres concurrentes : on les annule.
        self.assertEqual(action["res_model"], "purchase.requisition.alternative.warning")
        self.env[action["res_model"]].with_user(self.officer).with_context(action["context"]).create({}).action_cancel_alternatives()
        self.assertEqual(order.his_choice_criterion, "quality")
        self.assertEqual(order.his_chosen_by_id, self.officer)
        self.assertEqual(order.state, "to approve")
        self.assertEqual(order.alternative_po_ids.filtered(lambda o: o != order).state, "cancel")

    def test_refus_du_fournisseur(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 9500
        declined = self._alternative(order, self.supplier_b, 100)
        declined.his_supplier_answer = "declined"
        self.assertEqual(declined.amount_total, 0, "hors comparaison : quantites a zero")
        with self.assertRaises(UserError):
            declined.button_confirm()
        self.assertTrue(order.button_confirm(), "un refus n'est pas une offre concurrente")
        self.assertNotIn(declined, order._his_competitors())

    def test_offre_marquee_chiffree_sans_prix(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        with self.assertRaises(UserError):
            order.his_supplier_answer = "quoted"

    def test_le_choix_est_fige(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 8500
        order.button_confirm()
        with self.assertRaises(UserError):
            order.with_user(self.manager).his_choice_note = "rewritten"

    def _investment_order(self, price, qty=None):
        """Investissement approuve a 2 x 9000 = 18000 DA HT, plafond 21600."""
        request = self._approved_request(purchase_type="investment")
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = price
        if qty:
            order.order_line.product_qty = qty
        order.with_user(self.officer).button_confirm()
        self.assertEqual(order.state, "to approve")
        return request, order

    def test_investissement_dans_les_20_pourcents_l_acheteur_approuve(self):
        _request, order = self._investment_order(10800)  # 21600 HT, pile +20 %
        order.with_user(self.manager).button_approve()
        self.assertEqual(order.state, "purchase")
        self.assertEqual(order.his_approved_by_id, self.manager)

    def test_investissement_au_dela_des_20_pourcents_remonte_au_directeur(self):
        _request, order = self._investment_order(10801)  # 21602 HT
        with self.assertRaisesRegex(UserError, "more than 20% above"):
            order.with_user(self.manager).button_approve()
        order.with_user(self.director).button_approve()
        self.assertEqual(order.state, "purchase")
        self.assertEqual(order.his_approved_by_id, self.director)

    def test_decouper_la_commande_ne_contourne_pas_le_plafond(self):
        # Revue RF2 : deux commandes chacune sous le plafond, ensemble au-dessus.
        request, first = self._investment_order(10800, qty=1)
        first.with_user(self.manager).button_approve()
        second = self._source_rfq(request, self.supplier_b)
        self.assertEqual(second.order_line.product_qty, 1)
        second.order_line.price_unit = 10801
        second.with_user(self.officer).button_confirm()
        with self.assertRaisesRegex(UserError, "more than 20% above"):
            second.with_user(self.manager).button_approve()

    def test_les_devis_en_brouillon_ne_comptent_pas(self):
        # Revue RF3 : les 3 devis ne s'additionnent pas.
        request = self._approved_request(purchase_type="investment")
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 10000
        self._alternative(order, self.supplier_b, 10500)
        choice = (
            self.env["his.purchase.choice"]
            .with_user(self.officer)
            .create({"order_id": order.id, "criterion": "lowest_price"})
        )
        action = choice.action_confirm()
        self.env[action["res_model"]].with_user(self.officer).with_context(action["context"]).create({}).action_keep_alternatives()
        self.assertEqual(order.state, "to approve")
        order.with_user(self.manager).button_approve()
        self.assertEqual(order.state, "purchase")

    def test_investissement_sans_demande_approuvee_par_le_directeur(self):
        order = (
            self.env["purchase.order"]
            .with_user(self.officer)
            .create(
                {
                    "partner_id": self.supplier_a.id,
                    "his_purchase_type": "investment",
                    "order_line": [(0, 0, {"product_id": self.toner.id, "product_qty": 1, "price_unit": 100})],
                }
            )
        )
        order.button_confirm()
        with self.assertRaisesRegex(UserError, "no amount approved by the director"):
            order.with_user(self.manager).button_approve()
        order.with_user(self.director).button_approve()
        self.assertEqual(order.state, "purchase")

    def test_approbation_point_de_vente(self):
        request = self._approved_request(
            user=self.cook,
            employee=self.cook_emp,
            lines=[{"product_id": self.tomatoes.id, "product_qty": 50}],
            purchase_type="usual",
        )
        order = self._source_rfq(request, self.supplier_a)
        self.assertEqual(order.his_purchase_type, "usual")
        order.order_line.price_unit = 120
        order.with_user(self.officer).button_confirm()
        self.assertEqual(order.state, "to approve")
        order.with_user(self.manager).button_approve()
        self.assertEqual(order.state, "purchase")

    def test_approuver_un_brouillon_est_refuse(self):
        # Recette P-01 : approuver un brouillon le confirmait sans aucun controle.
        request = self._approved_request()
        bare = self._source_rfq(request, self.supplier_bare)
        bare.order_line.price_unit = 8500
        with self.assertRaisesRegex(UserError, "waiting for approval"):
            bare.with_user(self.director).button_approve()
        self.assertEqual(bare.state, "draft")
        order = self._source_rfq(self._approved_request(), self.supplier_a)
        order.order_line.price_unit = 9500
        self._alternative(order, self.supplier_b, 9000)
        with self.assertRaisesRegex(UserError, "waiting for approval"):
            order.with_user(self.director).button_approve()
        self.assertFalse(order.his_choice_criterion)

    def test_celui_qui_choisit_peut_approuver(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 8500
        order.with_user(self.director).button_confirm()
        self.assertEqual(order.state, "purchase", "decision du 2026-10-15 : pas de separation des taches")

    def test_pas_plus_que_demande(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.write({"price_unit": 8500, "product_qty": 5})
        with self.assertRaisesRegex(UserError, "purchase manager"):
            order.with_user(self.officer).button_confirm()
        order.with_user(self.manager).button_confirm()
        self.assertTrue(order.message_ids.filtered(lambda m: "top-up" in m.body))

    def test_fournisseur_ifu_sans_tva(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_ifu)
        self.assertFalse(order.order_line.tax_ids)
        normal = self._alternative(order, self.supplier_a, 9000)
        self.assertEqual(normal.order_line.tax_ids, self.tva19)

    def test_identifiants_obligatoires(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_bare)
        order.order_line.price_unit = 8500
        with self.assertRaisesRegex(UserError, "NIF, Trade Register"):
            order.button_confirm()

    def test_demande_commandee_puis_terminee(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 8500
        order.with_user(self.director).button_confirm()
        self.assertEqual(request.state, "ordered")
        # Le demandeur rouvre sa demande sans avoir acces aux commandes.
        lu = request.with_user(self.requester).line_ids.read(["qty_ordered", "qty_in_progress"])
        self.assertEqual(lu[0]["qty_ordered"], 2)
        request.with_user(self.requester).read(["order_count", "state"])
        picking = order.picking_ids
        picking.move_ids.quantity = 2
        picking.button_validate()
        self.assertEqual(request.state, "done")

    def test_le_magasinier_receptionne_une_commande_issue_d_une_demande(self):
        # Recette 2026-10-17 (P-02) : la reception passait par la demande avec
        # les droits du magasinier, qui n'a aucun droit sur les demandes.
        storekeeper = new_test_user(self.env, login="his_storekeeper", groups="stock.group_stock_user")
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 8500
        order.with_user(self.director).button_confirm()
        picking = order.picking_ids.with_user(storekeeper)
        picking.move_ids.quantity = 2
        # Sans cela le cache du test garde les lignes de demande lues en admin,
        # et le controle d'acces ne se declenche jamais.
        self.env.invalidate_all()
        picking.button_validate()
        self.assertEqual(request.state, "done")

    def test_un_service_est_termine_a_la_commande(self):
        repair = self.env["product.product"].create({"name": "Printer repair", "type": "service", "purchase_ok": True})
        request = self._approved_request(lines=[{"product_id": repair.id, "product_qty": 1}])
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 15000
        order.with_user(self.director).button_confirm()
        self.assertEqual(request.state, "done", "rien a recevoir pour un service")

    def test_appel_sur_contrat_cadre_sans_comparaison(self):
        agreement = self._agreement()
        request = self._approved_request()
        wizard = (
            self.env["his.purchase.request.source"]
            .with_user(self.officer)
            .create({"request_id": request.id, "mode": "calloff", "requisition_id": agreement.id})
        )
        order = self.env["purchase.order"].browse(wizard.action_source()["res_id"])
        self.assertEqual(order.partner_id, self.supplier_a)
        self.assertEqual(order.order_line.price_unit, 8000)
        self.assertEqual(order.his_supplier_answer, "quoted")
        order.with_user(self.officer).button_confirm()
        self.assertEqual(order.state, "to approve", "un appel sur contrat-cadre est approuve aussi")

    def test_appel_sur_contrat_suit_le_type_du_contrat(self):
        # Recette P-28 : le contrat Restaurant reste un achat courant, meme
        # appele depuis une demande courante d'un autre service.
        agreement = self._agreement()
        agreement.his_purchase_type = "usual"
        request = self._approved_request(purchase_type="usual")
        wizard = (
            self.env["his.purchase.request.source"]
            .with_user(self.officer)
            .create({"request_id": request.id, "mode": "calloff", "requisition_id": agreement.id})
        )
        order = self.env["purchase.order"].browse(wizard.action_source()["res_id"])
        self.assertEqual(order.his_purchase_type, "usual")

    def test_l_acheteur_ne_requalifie_pas_la_commande_d_un_investissement(self):
        # Revue RF1 : la commande ne contourne pas le verrou de la demande.
        order = self._source_rfq(self._approved_request(purchase_type="investment"), self.supplier_a)
        with self.assertRaisesRegex(UserError, "only the director"):
            order.with_user(self.officer).his_purchase_type = "usual"
        self.assertEqual(order.his_purchase_type, "investment")

    def test_un_contrat_courant_ne_declasse_pas_un_investissement_approuve(self):
        agreement = self._agreement()
        agreement.his_purchase_type = "usual"
        request = self._approved_request(purchase_type="investment")
        wizard = (
            self.env["his.purchase.request.source"]
            .with_user(self.officer)
            .create({"request_id": request.id, "mode": "calloff", "requisition_id": agreement.id})
        )
        order = self.env["purchase.order"].browse(wizard.action_source()["res_id"])
        self.assertEqual(order.his_purchase_type, "investment")

    def _agreement(self):
        agreement = self.env["purchase.requisition"].create(
            {
                "requisition_type": "blanket_order",
                "vendor_id": self.supplier_a.id,
                "his_purchase_type": "investment",
                "line_ids": [(0, 0, {"product_id": self.toner.id, "product_qty": 100, "price_unit": 8000})],
            }
        )
        agreement.action_confirm()
        return agreement

    def test_une_reponse_corrigee_rend_les_quantites(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 8500
        order.his_supplier_answer = "no_answer"
        self.assertEqual(order.order_line.product_qty, 0)
        order.his_supplier_answer = "quoted"
        self.assertEqual(order.order_line.product_qty, 2)
        self.assertEqual(order.amount_untaxed, 17000)

    def test_le_moins_cher_doit_l_etre(self):
        request = self._approved_request()
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 9500
        self._alternative(order, self.supplier_b, 9000)
        choice = (
            self.env["his.purchase.choice"]
            .with_user(self.officer)
            .create({"order_id": order.id, "criterion": "lowest_price"})
        )
        with self.assertRaisesRegex(UserError, "not the cheapest"):
            choice.action_confirm()
        self.assertFalse(order.his_choice_criterion)

    def test_appel_en_douzaines_converti(self):
        dozen = self.env.ref("uom.product_uom_dozen")
        dozen.active = True
        eggs = self.env["product.product"].create({"name": "Eggs", "type": "consu", "purchase_ok": True})
        agreement = self.env["purchase.requisition"].create(
            {
                "requisition_type": "blanket_order",
                "vendor_id": self.supplier_a.id,
                "his_purchase_type": "investment",
                "line_ids": [
                    (0, 0, {"product_id": eggs.id, "product_qty": 100, "price_unit": 300, "product_uom_id": dozen.id})
                ],
            }
        )
        agreement.action_confirm()
        request = self._approved_request(lines=[{"product_id": eggs.id, "product_qty": 24}])
        wizard = (
            self.env["his.purchase.request.source"]
            .with_user(self.officer)
            .create({"request_id": request.id, "mode": "calloff", "requisition_id": agreement.id})
        )
        order = self.env["purchase.order"].browse(wizard.action_source()["res_id"])
        self.assertEqual(order.order_line.product_uom_id, dozen)
        self.assertEqual(order.order_line.product_qty, 2, "24 oeufs = 2 douzaines")
        self.assertEqual(order.order_line.price_unit, 300)
        self.assertEqual(request.line_ids.qty_in_progress, 24)
        # 3 douzaines = 36 oeufs pour 24 demandes : depassement detecte.
        order.order_line.product_qty = 3
        with self.assertRaisesRegex(UserError, "more than requested"):
            order.with_user(self.officer).button_confirm()
