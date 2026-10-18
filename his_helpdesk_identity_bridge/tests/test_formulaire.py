# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le formulaire de ticket adapte a HIS (decisions de Mohamed, 2026-10-18).

Pas de odoo.tests.Form : il ne sait pas evaluer `stage_id.closed`, une
condition de la vue OCA. On lit la vue et on appelle l'onchange du serveur,
comme le navigateur.
"""

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFormulaire(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.etudiant = cls.env["his.person"].create(
            {
                "name": "Amel Saidi",
                "type_personne": "etudiant",
                "source_system": "manual",
                "email": "amel.saidi@example.com",
            }
        )
        cls.support = cls.env.ref("his_helpdesk_identity_bridge.team_support")
        vues = cls.env["helpdesk.ticket"].get_views([(False, "form")])
        cls.arch = etree.fromstring(vues["views"]["form"]["arch"])

    def _champ(self, nom):
        return self.arch.xpath(f"//field[@name='{nom}']")[0]

    def test_la_personne_est_obligatoire(self):
        # Tout ticket parle d'une personne du referentiel, sauf le courriel
        # d'un expediteur inconnu : le ticket existe deja, a rattacher.
        self.assertEqual(self._champ("his_person_id").get("required"), "not partner_email")

    def test_contact_nom_et_email_caches(self):
        self.assertEqual(self._champ("partner_id").get("invisible"), "1")
        self.assertEqual(self._champ("partner_name").get("invisible"), "1")
        self.assertEqual(self._champ("partner_email").get("invisible"), "his_person_id or not partner_email")

    def test_la_personne_remplit_contact_nom_et_email(self):
        # Caches, ils restent recopies : la cloture et les destinataires
        # suggeres s'en servent.
        spec = dict.fromkeys(("his_person_id", "partner_id", "partner_name", "partner_email"), {})
        valeurs = self.env["helpdesk.ticket"].onchange({"his_person_id": self.etudiant.id}, ["his_person_id"], spec)[
            "value"
        ]
        self.assertEqual(valeurs["partner_id"], self.etudiant.partner_id.id)
        self.assertEqual(valeurs["partner_name"], "Amel Saidi")
        self.assertEqual(valeurs["partner_email"], "amel.saidi@example.com")

    def test_plus_de_conversion_en_opportunite(self):
        boutons = self.arch.xpath("//button[@icon='fa-arrow-right'] | //button[@name='action_open_leads']")
        self.assertEqual(len(boutons), 2)
        for bouton in boutons:
            self.assertEqual(bouton.get("invisible"), "1")

    def test_tout_ticket_va_a_support(self):
        ticket = self.env["helpdesk.ticket"].create({"name": "Wi-Fi", "description": "<p>?</p>"})
        self.assertEqual(ticket.team_id, self.support)
        self.assertEqual(self._champ("team_id").get("invisible"), "1")

    def test_la_categorie_dit_le_service(self):
        categorie = self.env.ref("his_helpdesk_identity_bridge.categ_it_reseau")
        self.assertEqual(categorie.complete_name, "IT / Wi-Fi & Network")

    def test_canal_web_archive(self):
        self.assertFalse(self.env.ref("helpdesk_mgmt.helpdesk_ticket_channel_web").active)
