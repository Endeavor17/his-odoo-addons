# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Commande mensuelle sur contrat-cadre annuel (AT-22 a AT-25, AT-29)."""

from datetime import date

from freezegun import freeze_time
from odoo.tests import tagged

from .common import HisPurchaseCase


@tagged("post_install", "-at_install")
class TestMonthly(HisPurchaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse_manager = cls.officer
        cls.agreement = cls.env["purchase.requisition"].create(
            {
                "requisition_type": "blanket_order",
                "vendor_id": cls.supplier_a.id,
                "date_start": date(2026, 9, 1),
                "date_end": date(2027, 8, 31),
                "his_purchase_type": "usual",
                "his_recurring": True,
                "his_delivery_day": 1,
                "his_prepare_days": 7,
                "his_owner_id": cls.warehouse_manager.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.tomatoes.id,
                            "product_qty": 1200,
                            "price_unit": 120,
                            "his_recurring_qty": 100,
                        },
                    ),
                ],
            }
        )
        cls.agreement.action_confirm()

    def _cron(self, day):
        with freeze_time(day):
            return self.env["purchase.requisition"]._cron_his_monthly_orders()

    def test_le_contrat_impose_fournisseur_et_prix(self):
        # Le prix du contrat vaut pour une commande passee SUR le contrat...
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.supplier_a.id,
                "requisition_id": self.agreement.id,
                "order_line": [(0, 0, {"product_id": self.tomatoes.id, "product_qty": 5})],
            }
        )
        self.assertEqual(order.order_line.price_unit, 120)
        # ...et le reapprovisionnement automatique choisit ce fournisseur.
        self.assertEqual(self.tomatoes._select_seller(quantity=5).partner_id, self.supplier_a)

    def test_un_brouillon_par_mois_sept_jours_avant(self):
        self.assertFalse(self._cron(date(2026, 11, 23)))
        order = self._cron(date(2026, 11, 24))
        self.assertEqual(len(order), 1)
        self.assertTrue(order.his_monthly)
        self.assertEqual(order.requisition_id, self.agreement)
        self.assertEqual(order.user_id, self.warehouse_manager)
        self.assertEqual(order.order_line.product_qty, 100)
        self.assertEqual(order.order_line.price_unit, 120)
        self.assertEqual(order.date_planned.date(), date(2026, 12, 1))
        self.assertEqual(order.his_purchase_type, "usual")
        self.assertEqual(len(order.activity_ids.filtered(lambda a: a.user_id == self.warehouse_manager)), 1)
        self.assertFalse(self._cron(date(2026, 11, 25)), "un seul par mois")
        self.assertFalse(self._cron(date(2026, 12, 1)))

    def test_la_commande_mensuelle_est_approuvee(self):
        order = self._cron(date(2026, 11, 24))
        order.with_user(self.officer).button_confirm()
        self.assertEqual(order.state, "to approve")
        order.with_user(self.manager).button_approve()
        self.assertEqual(order.state, "purchase")

    def test_besoin_ponctuel_ajoute_a_la_prochaine_commande(self):
        request = self._approved_request(
            user=self.cook,
            employee=self.cook_emp,
            purchase_type="usual",
            lines=[{"product_id": self.tomatoes.id, "product_qty": 20}],
        )
        wizard = (
            self.env["his.purchase.request.source"]
            .with_user(self.officer)
            .create({"request_id": request.id, "mode": "monthly", "requisition_id": self.agreement.id})
        )
        wizard.action_source()
        self.assertEqual(request.state, "sourcing")
        self.assertEqual(request.line_ids.his_monthly_requisition_id, self.agreement)
        order = self._cron(date(2026, 11, 24))
        self.assertEqual(sorted(order.order_line.mapped("product_qty")), [20, 100])
        self.assertEqual(order.order_line.filtered("his_request_line_id").his_request_line_id, request.line_ids)

    def test_besoin_ponctuel_rejoint_le_brouillon_ouvert(self):
        order = self._cron(date(2026, 11, 24))
        request = self._approved_request(
            user=self.cook,
            employee=self.cook_emp,
            purchase_type="usual",
            lines=[{"product_id": self.tomatoes.id, "product_qty": 15}],
        )
        wizard = (
            self.env["his.purchase.request.source"]
            .with_user(self.officer)
            .create({"request_id": request.id, "mode": "monthly", "requisition_id": self.agreement.id})
        )
        wizard.action_source()
        self.assertEqual(sorted(order.order_line.mapped("product_qty")), [15, 100])

    def test_rien_apres_la_fin_du_contrat(self):
        self.assertFalse(self._cron(date(2027, 8, 25)), "la livraison du 1er septembre 2027 est hors contrat")

    def test_renouvellement_annonce(self):
        with freeze_time(date(2027, 7, 1)):
            self.env["purchase.requisition"]._cron_his_followup()
        self.assertFalse(self.agreement.activity_ids)
        with freeze_time(date(2027, 8, 1)):
            self.env["purchase.requisition"]._cron_his_followup()
        self.assertEqual(self.agreement.activity_ids.user_id, self.manager)

    def _add_to_monthly(self, qty):
        request = self._approved_request(
            user=self.cook,
            employee=self.cook_emp,
            purchase_type="usual",
            lines=[{"product_id": self.tomatoes.id, "product_qty": qty}],
        )
        self.env["his.purchase.request.source"].with_user(self.officer).create(
            {"request_id": request.id, "mode": "monthly", "requisition_id": self.agreement.id}
        ).action_source()
        return request

    def test_la_commande_mensuelle_fait_avancer_la_demande(self):
        request = self._add_to_monthly(20)
        order = self._cron(date(2026, 11, 24))
        order.with_user(self.officer).button_confirm()
        order.with_user(self.manager).button_approve()
        self.assertEqual(request.state, "ordered", "sans attendre le cron")
        for move in order.picking_ids.move_ids:
            move.quantity = move.product_uom_qty
        order.picking_ids.button_validate()
        self.assertEqual(request.state, "done")

    def test_mensuelle_annulee_la_ligne_se_source_encore(self):
        order = self._cron(date(2026, 11, 24))
        request = self._add_to_monthly(15)
        order.button_cancel()
        rfq = self._source_rfq(request, self.supplier_b)
        self.assertEqual(rfq.order_line.his_request_line_id, request.line_ids)
        self.assertFalse(request.line_ids.his_monthly_requisition_id, "sortie de l'attente mensuelle")
