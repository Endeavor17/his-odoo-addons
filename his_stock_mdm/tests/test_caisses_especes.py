"""Recette P-15 : sur une base neuve, seule la premiere caisse recevait les especes."""

from odoo.tests import TransactionCase, tagged

CAISSES = ("pos_config_cafeteria", "pos_config_restaurant", "pos_config_copy_center")


@tagged("post_install", "-at_install")
class TestCaissesEspeces(TransactionCase):
    def test_chaque_caisse_encaisse_en_especes(self):
        especes = self.env["pos.payment.method"]
        for xmlid in CAISSES:
            caisse = self.env.ref(f"his_stock_mdm.{xmlid}")
            cash = caisse.payment_method_ids.filtered("is_cash_count")
            self.assertEqual(len(cash), 1, caisse.name)
            especes |= cash
        self.assertEqual(len(especes), 3, "une caisse partage les especes d'une autre")
