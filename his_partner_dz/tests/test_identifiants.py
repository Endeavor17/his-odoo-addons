# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Identifiants algeriens : ce qui manque pour acheter a un tiers."""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIdentifiants(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        cls.societe = Partner.create({"name": "Papeterie Test SARL", "is_company": True})
        cls.contact = Partner.create({"name": "Commercial", "parent_id": cls.societe.id})
        cls.artisan = Partner.create({"name": "Artisan Test", "is_company": False})

    def test_une_societe_doit_avoir_nif_et_rc(self):
        self.assertEqual(self.societe.his_missing_identifiers(), ["NIF", "Trade Register (RC)"])
        self.societe.write({"vat": "000016001234567", "his_rc": "16/00-1234567B21"})
        self.assertEqual(self.societe.his_missing_identifiers(), [])

    def test_un_contact_est_juge_sur_sa_societe(self):
        self.societe.write({"vat": "000016001234567", "his_rc": "16/00-1234567B21"})
        self.assertEqual(self.contact.his_missing_identifiers(), [])
        self.assertEqual(self.contact.his_rc, "16/00-1234567B21", "le RC est un champ commercial")

    def test_une_personne_physique_doit_avoir_nif_et_nin(self):
        self.assertEqual(self.artisan.his_missing_identifiers(), ["NIF", "National ID (NIN)"])
        self.artisan.write({"vat": "123456789012345", "his_nin": "109870123456789012"})
        self.assertEqual(self.artisan.his_missing_identifiers(), [])

    def test_regime_sans_tva(self):
        self.assertFalse(self.societe.his_is_vat_free())
        self.societe.his_tax_regime = "ifu"
        self.assertTrue(self.contact.his_is_vat_free(), "le contact herite du regime de sa societe")

    def test_nis_ai_nin_en_chiffres(self):
        with self.assertRaises(ValidationError):
            self.societe.his_nis = "12A45"
        self.societe.his_nis = "0991 6001 2345 678"

    def test_la_societe_lit_ses_identifiants_sur_son_partenaire(self):
        self.env.company.his_rc = "16/00-7654321B19"
        self.assertEqual(self.env.company.partner_id.his_rc, "16/00-7654321B19")
