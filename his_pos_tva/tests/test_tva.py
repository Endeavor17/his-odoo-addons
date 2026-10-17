"""La TVA a 9 % comprise dans le prix : ce que le client paie ne bouge pas.

Sur la societe principale, parce que c'est elle qui porte le plan comptable dz
(charge en CI par tools/charger_plan_comptable_dz.py) ; les societes de test
d'AccountTestInvoicingCommon naissent sur un plan generique.
"""

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..hooks import TVA_BIENS, TVA_SERVICES, appliquer_tva


@tagged("post_install", "-at_install")
class TestTvaCaisse(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.chart = cls.env["account.chart.template"].with_company(cls.company)
        cls.biens = cls.chart.ref(TVA_BIENS)
        cls.services = cls.chart.ref(TVA_SERVICES)
        cls.production_19 = cls.chart.ref("l10n_dz_vat_sale_19_prod")
        cls.revente_19 = cls.chart.ref("l10n_dz_vat_sale_19_resale")
        # La formule Restaurant : « Meal 600 » est archive depuis les formules
        # (2026-10-15), et un produit archive n'a plus de variante a facturer.
        cls.repas = cls.env.ref("his_meal_management.product_formule_restaurant")
        cls.forfait = cls.env.ref("his_meal_management.product_plan_weekly")

    def _produit(self, nom, prix, taxes, **vals):
        return self.env["product.template"].create(
            {"name": nom, "list_price": prix, "available_in_pos": True, "taxes_id": [Command.set(taxes.ids)], **vals}
        )

    def test_repas_et_forfaits_a_9_pour_cent_prix_inchange(self):
        """Le repas a 600 DA coute toujours 600 DA : 550,46 HT + 49,54 de TVA."""
        self.assertEqual(self.repas.taxes_id, self.biens)
        self.assertEqual(self.forfait.taxes_id, self.biens)
        res = self.biens.compute_all(600.0)
        self.assertAlmostEqual(res["total_included"], 600.0)
        self.assertAlmostEqual(res["total_excluded"], 550.46)

    def test_taxe_par_defaut_et_prix_ttc(self):
        """Un produit cree apres l'installation nait a 9 %, TTC."""
        self.assertEqual(self.company.account_sale_tax_id, self.biens)
        for tax in self.biens | self.services:
            self.assertTrue(tax.active)
            self.assertTrue(tax.price_include, tax.name)
            self.assertEqual(tax.amount, 9.0)

    def test_affectation_rejouable(self):
        """Tout 19 % passe a 9 %, Copy Center -> services, autre taux manuel respecte."""
        catalogue = self._produit("Candia", 60.0, self.production_19)
        revente = self._produit("Caps Cafe", 70.0, self.revente_19)
        sans_taxe = self._produit("Gaz 33 CL", 60.0, self.env["account.tax"])
        copie = self._produit("Copie A4", 10.0, self.production_19, copy_service="photocopie")
        manuel_tax = self.chart.ref("l10n_dz_vat_sale_0_g")
        manuel = self._produit("Livre", 500.0, manuel_tax)

        appliquer_tva(self.env, self.company)
        appliquer_tva(self.env, self.company)  # idempotent

        self.assertEqual(catalogue.taxes_id, self.biens)
        self.assertEqual(revente.taxes_id, self.biens)
        self.assertEqual(sans_taxe.taxes_id, self.biens)
        self.assertEqual(copie.taxes_id, self.services)
        self.assertEqual(manuel.taxes_id, manuel_tax)

    def test_plats_des_formules_a_9_pour_cent(self):
        """Recette P-09 : un plat choisi dans une formule est hors grille, mais vendu."""
        plat = self.env.ref("his_meal_management.product_choix_pizza").product_tmpl_id
        plat.taxes_id = self.production_19
        appliquer_tva(self.env, self.company)
        self.assertEqual(plat.taxes_id, self.biens)

    def test_facture_mixte_total_egal_aux_prix_affiches(self):
        """3 capsules a 70 DA + un repas a 600 DA = 810 DA, ni plus ni moins.

        70 DA est choisi expres : 70 / 1,09 ne tombe pas juste, c'est la ou un
        arrondi derive d'un centime si le total est recompose depuis le HT.
        """
        capsule = self._produit("Caps Cafe", 70.0, self.biens)
        repas = self._produit("Repas 600", 600.0, self.biens)
        client = self.env["res.partner"].create({"name": "Etudiant TVA"})
        ligne = {"product_id": capsule.product_variant_id.id, "quantity": 1, "price_unit": 70.0}
        facture = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": client.id,
                "invoice_line_ids": [
                    Command.create(ligne),
                    Command.create(ligne),
                    Command.create(ligne),
                    Command.create({"product_id": repas.product_variant_id.id, "quantity": 1, "price_unit": 600.0}),
                ],
            }
        )
        self.assertAlmostEqual(facture.amount_total, 810.0)
        self.assertAlmostEqual(facture.amount_untaxed + facture.amount_tax, 810.0)
        self.assertAlmostEqual(facture.amount_tax, 66.88, delta=0.02)

    def test_rejouable_avec_une_session_ouverte(self):
        """Le balayage repasse sans toucher une taxe deja vendue en session ouverte.

        Le point de vente refuse toute ecriture de price_include_override sur une
        taxe portee par une ligne de commande non cloturee ; la migration
        19.0.1.1.0 a bloque le demarrage du staging pour cette raison.
        """
        config = self.env["pos.config"].create({"name": "Caisse test TVA"})
        config.open_ui()
        commande = self.env["pos.order"].create(
            {
                "session_id": config.current_session_id.id,
                "lines": [
                    Command.create(
                        {
                            "product_id": self.repas.product_variant_id.id,
                            "qty": 1,
                            "price_unit": 600.0,
                            "price_subtotal": 550.46,
                            "price_subtotal_incl": 600.0,
                            "tax_ids": [Command.set(self.biens.ids)],
                        }
                    )
                ],
                "amount_tax": 49.54,
                "amount_total": 600.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            }
        )
        self.assertNotEqual(commande.session_id.state, "closed")
        # Le garde du point de vente est bien arme : l'ecriture brute est refusee.
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.biens.price_include_override = "tax_included"
        appliquer_tva(self.env, self.company)
        self.assertTrue(self.biens.active)
        self.assertTrue(self.biens.price_include)
