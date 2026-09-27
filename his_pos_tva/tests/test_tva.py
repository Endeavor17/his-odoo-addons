"""La TVA a 19 % comprise dans le prix : ce que le client paie ne bouge pas.

Sur la societe principale, parce que c'est elle qui porte le plan comptable dz
(charge en CI par tools/charger_plan_comptable_dz.py) ; les societes de test
d'AccountTestInvoicingCommon naissent sur un plan generique.
"""

from odoo import Command
from odoo.tests import TransactionCase, tagged

from ..hooks import TVA_PRODUCTION, TVA_REVENTE, TVA_SERVICES, TVA_SUR_PLACE, appliquer_tva


@tagged("post_install", "-at_install")
class TestTvaCaisse(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        chart = cls.env["account.chart.template"].with_company(cls.company)
        cls.revente = chart.ref(TVA_REVENTE)
        cls.sur_place = chart.ref(TVA_SUR_PLACE)
        cls.services = chart.ref(TVA_SERVICES)
        cls.production = chart.ref(TVA_PRODUCTION)
        cls.repas = cls.env.ref("his_meal_management.product_daily_meal")
        cls.forfait = cls.env.ref("his_meal_management.product_plan_weekly")

    def _produit(self, nom, prix, taxes, **vals):
        return self.env["product.template"].create(
            {"name": nom, "list_price": prix, "available_in_pos": True, "taxes_id": [Command.set(taxes.ids)], **vals}
        )

    def test_repas_et_forfaits_taxes_sur_place_prix_inchange(self):
        """Le repas a 600 DA coute toujours 600 DA : 504,20 HT + 95,80 de TVA."""
        self.assertEqual(self.repas.taxes_id, self.sur_place)
        self.assertEqual(self.forfait.taxes_id, self.sur_place)
        res = self.sur_place.compute_all(600.0)
        self.assertAlmostEqual(res["total_included"], 600.0)
        self.assertAlmostEqual(res["total_excluded"], 504.20)

    def test_taxe_par_defaut_et_prix_ttc(self):
        """Un produit cree apres l'installation nait en revente, TTC."""
        self.assertEqual(self.company.account_sale_tax_id, self.revente)
        for tax in self.revente | self.sur_place | self.services:
            self.assertTrue(tax.active)
            self.assertTrue(tax.price_include, tax.name)

    def test_affectation_rejouable(self):
        """Production -> revente, Copy Center -> services, choix manuel respecte."""
        catalogue = self._produit("Candia", 60.0, self.production)
        sans_taxe = self._produit("Gaz 33 CL", 60.0, self.env["account.tax"])
        copie = self._produit("Copie A4", 10.0, self.production, copy_service="photocopie")
        manuel_tax = self.env["account.chart.template"].with_company(self.company).ref("l10n_dz_vat_sale_9_g")
        manuel = self._produit("Livre", 500.0, manuel_tax)

        appliquer_tva(self.env, self.company)
        appliquer_tva(self.env, self.company)  # idempotent

        self.assertEqual(catalogue.taxes_id, self.revente)
        self.assertEqual(sans_taxe.taxes_id, self.revente)
        self.assertEqual(copie.taxes_id, self.services)
        self.assertEqual(manuel.taxes_id, manuel_tax)

    def test_facture_mixte_total_egal_aux_prix_affiches(self):
        """3 capsules a 70 DA + un repas a 600 DA = 810 DA, ni plus ni moins.

        70 DA est choisi expres : 70 / 1,19 ne tombe pas juste, c'est la ou un
        arrondi derive d'un centime si le total est recompose depuis le HT.
        """
        capsule = self._produit("Caps Cafe", 70.0, self.revente)
        client = self.env["res.partner"].create({"name": "Etudiant TVA"})
        facture = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": client.id,
                "invoice_line_ids": [
                    Command.create({"product_id": capsule.product_variant_id.id, "quantity": 1, "price_unit": 70.0}),
                    Command.create({"product_id": capsule.product_variant_id.id, "quantity": 1, "price_unit": 70.0}),
                    Command.create({"product_id": capsule.product_variant_id.id, "quantity": 1, "price_unit": 70.0}),
                    Command.create(
                        {"product_id": self.repas.product_variant_id.id, "quantity": 1, "price_unit": 600.0}
                    ),
                ],
            }
        )
        self.assertAlmostEqual(facture.amount_total, 810.0)
        self.assertAlmostEqual(facture.amount_untaxed + facture.amount_tax, 810.0)
        self.assertAlmostEqual(facture.amount_tax, 129.33, delta=0.02)
