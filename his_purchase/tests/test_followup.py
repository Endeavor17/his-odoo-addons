# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Relances et escalade (AT-17 a AT-21, AT-27, AT-28)."""

from datetime import date, timedelta

from freezegun import freeze_time
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import LUNDI, HisPurchaseCase


@tagged("post_install", "-at_install")
class TestFollowup(HisPurchaseCase):
    def _activities(self, record, user):
        return record.activity_ids.filtered(lambda a: a.user_id == user)

    def _notified(self, record, user):
        return record.message_ids.filtered(lambda m: user.partner_id in m.partner_ids)

    def _cron(self, day):
        with freeze_time(day):
            self.env["his.purchase.request"]._cron_his_followup()

    def test_chaque_etape_a_son_responsable(self):
        with freeze_time(LUNDI):
            request = self._request()
            request.action_submit()
            activity = self._activities(request, self.officer)
            self.assertEqual(len(activity), 1)
            # Lundi + 2 jours ouvres = mercredi.
            self.assertEqual(activity.date_deadline, date(2026, 11, 4))
            request.with_user(self.officer).his_purchase_type = "investment"
            self.assertFalse(self._activities(request, self.officer), "l'investissement passe au directeur")
            self.assertEqual(len(self._activities(request, self.director)), 1)
            request.with_user(self.director).action_approve()
        self.assertFalse(self._activities(request, self.director), "l'etape passee est close")
        self.assertEqual(len(self._activities(request, self.officer)), 1)

    def test_rien_le_week_end(self):
        # Recette P-06 : un retard decouvert un vendredi attend le dimanche.
        with freeze_time(LUNDI):
            request = self._request()
            request.action_submit()
        self._cron(date(2026, 11, 6))
        self._cron(date(2026, 11, 7))
        self.assertFalse(self._notified(request, self.officer), "vendredi et samedi : silence")
        self.assertEqual(request.his_step_level, 0)
        self._cron(date(2026, 11, 8))
        self.assertTrue(self._notified(request, self.officer))

    def test_rappel_puis_escalade(self):
        with freeze_time(LUNDI):
            request = self._request()
            request.action_submit()
        # Echeance mercredi 4 : rien avant.
        self._cron(date(2026, 11, 4))
        self.assertFalse(self._notified(request, self.officer))
        # Jeudi 5 : rappel a l'acheteur.
        self._cron(date(2026, 11, 5))
        self.assertTrue(self._notified(request, self.officer))
        self.assertTrue(request.his_is_late)
        self.assertFalse(self._notified(request, self.manager))
        # Echeance + 2 jours OUVRES : pas le vendredi 6, le dimanche 8.
        self._cron(date(2026, 11, 6))
        self.assertFalse(self._notified(request, self.manager), "pas d'escalade pendant le week-end")
        self._cron(date(2026, 11, 8))
        self.assertTrue(self._notified(request, self.manager))
        self.assertEqual(len(self._activities(request, self.manager)), 1)
        # Un achat courant ne monte jamais au directeur (2026-10-20).
        self._cron(date(2026, 11, 10))
        self._cron(date(2026, 11, 20))
        self.assertFalse(self._notified(request, self.director))
        self.assertFalse(self._activities(request, self.director))
        self.assertEqual(request.his_reminder_count, 2, "plus rien a escalader : le cron ne repete pas")

    def test_demande_courante_a_sourcer_ne_monte_pas_au_directeur(self):
        with freeze_time(LUNDI):
            request = self._approved_request(purchase_type="usual")
        for day in (5, 8, 10, 12, 20):
            self._cron(date(2026, 11, day))
        self.assertTrue(self._notified(request, self.manager))
        self.assertFalse(self._notified(request, self.director))
        self.assertFalse(self._activities(request, self.director))

    def test_investissement_a_sourcer_monte_au_directeur(self):
        with freeze_time(LUNDI):
            request = self._approved_request(purchase_type="investment")
        for day in (5, 8, 10, 12, 20):
            self._cron(date(2026, 11, day))
        self.assertTrue(self._notified(request, self.director))

    def test_chacun_lit_ses_rappels_dans_sa_langue(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"]._load_module_terms(["his_purchase"], ["fr_FR"], overwrite=True)
        self.officer.lang = "fr_FR"
        with freeze_time(LUNDI):
            request = self._request()
            request.action_submit()
        self.assertIn("Approuver la demande d'achat", self._activities(request, self.officer).summary)
        # Le cron tourne en anglais : le rappel part quand meme en francais.
        self._cron(date(2026, 11, 5))
        self.assertIn("Rappel", self._notified(request, self.officer)[0].body)

    def test_le_demandeur_relance_une_fois_par_jour(self):
        request = self._request()
        request.action_submit()
        request.action_remind()
        self.assertTrue(self._notified(request, self.officer))
        with self.assertRaises(UserError):
            request.action_remind()

    def test_relance_automatique_du_fournisseur(self):
        with freeze_time(LUNDI):
            request = self._approved_request()
            order = self._source_rfq(request, self.supplier_a)
        # Lundi + 5 jours ouvres = lundi suivant (week-end vendredi-samedi).
        self.assertEqual(order.his_reply_by, date(2026, 11, 9))

        def mails():
            return self.env["mail.mail"].search(
                [("model", "=", "purchase.order"), ("res_id", "=", order.id), ("subject", "ilike", "Reminder")]
            )

        self._cron(date(2026, 11, 8))
        self.assertFalse(mails())
        self._cron(date(2026, 11, 9))
        self.assertEqual(len(mails()), 1)
        self.assertEqual(mails().recipient_ids, self.supplier_a)
        self.assertTrue(mails().attachment_ids, "la demande de proforma est jointe")
        self.assertTrue(self._activities(order, self.officer))
        self._cron(date(2026, 11, 10))
        self.assertEqual(len(mails()), 1, "tous les 3 jours, pas tous les jours")
        self._cron(date(2026, 11, 12))
        self._cron(date(2026, 11, 20))
        self.assertEqual(len(mails()), 2, "deux relances au plus")

    def test_commande_courante_ne_monte_jamais_au_directeur(self):
        with freeze_time(LUNDI):
            request = self._approved_request(
                user=self.cook,
                employee=self.cook_emp,
                purchase_type="usual",
                lines=[{"product_id": self.tomatoes.id, "product_qty": 50}],
            )
            order = self._source_rfq(request, self.supplier_a)
            order.order_line.price_unit = 120
            order.with_user(self.officer).button_confirm()
        self.assertEqual(len(self._activities(order, self.manager)), 1)
        self._cron(date(2026, 11, 5))
        self.assertTrue(self._notified(order, self.manager))
        for day in (6, 8, 10, 20):
            self._cron(date(2026, 11, day))
        self.assertFalse(self._notified(order, self.director))
        self.assertFalse(self._activities(order, self.director))

    def test_investissement_hors_plafond_a_faire_au_directeur(self):
        request = self._approved_request(purchase_type="investment")
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 10801  # 21602 HT > 18000 + 20 %
        order.with_user(self.officer).button_confirm()
        self.assertEqual(len(self._activities(order, self.director)), 1)
        self.assertFalse(self._activities(order, self.manager))

    def test_investissement_dans_le_plafond_a_faire_a_l_acheteur(self):
        request = self._approved_request(purchase_type="investment")
        order = self._source_rfq(request, self.supplier_a)
        order.order_line.price_unit = 10000
        order.with_user(self.officer).button_confirm()
        self.assertEqual(len(self._activities(order, self.manager)), 1)
        self.assertFalse(self._activities(order, self.director))

    def test_besoin_urgent(self):
        with freeze_time(LUNDI):
            request = self._request(date_required=LUNDI + timedelta(days=3))
            request.action_submit()
        self._cron(LUNDI)
        self.assertTrue(request.his_urgent_alert_sent)
        self.assertTrue(self._notified(request, self.manager))

    def test_recapitulatif_hebdomadaire(self):
        old = self._request()
        old.action_submit()
        new = self._request()
        new.action_submit()
        self.env["his.purchase.request"]._cron_his_weekly_digest()
        mail = self.env["mail.mail"].search([("subject", "ilike", "Open purchase requests")], limit=1)
        self.assertEqual(mail.recipient_ids, self.manager.partner_id | self.director.partner_id)
        body = str(mail.body_html)
        self.assertIn(old.name, body)
        self.assertLess(body.index(old.name), body.index(new.name), "la plus ancienne d'abord")
        self.assertIn("Nadia Officer", body, "on voit qui tient la demande : l'acheteur trie (2026-10-20)")
