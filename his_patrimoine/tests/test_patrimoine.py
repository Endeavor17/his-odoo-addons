# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Patrimoine : un bien = un numero de serie, range dans une salle, compte chaque annee."""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPatrimoine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mobilier = cls.env.ref("his_patrimoine.categ_mobilier")
        cls.sequence = cls.env.ref("his_patrimoine.seq_patrimoine")

    def _bien(self, name="Bureau 120 cm", **vals):
        return self.env["product.template"].create({"name": name, "categ_id": self.mobilier.id, **vals})

    def test_un_bien_est_suivi_par_numero_pat(self):
        bureau = self._bien()
        self.assertTrue(bureau.is_storable)
        self.assertEqual(bureau.tracking, "serial")
        self.assertEqual(bureau.lot_sequence_id, self.sequence)
        self.assertFalse(bureau.sale_ok)

    def test_un_bien_reste_suivi_par_numero(self):
        bureau = self._bien()
        with self.assertRaises(ValidationError):
            bureau.tracking = "none"

    def test_les_autres_categories_ne_changent_pas(self):
        boisson = self.env["product.template"].create(
            {"name": "Eau 50 cl", "categ_id": self.env.ref("his_stock_mdm.categ_cafe_boissons").id}
        )
        self.assertNotEqual(boisson.lot_sequence_id, self.sequence, "Odoo 19 lui donne sa sequence par defaut")
        self.assertNotEqual(boisson.tracking, "serial")
