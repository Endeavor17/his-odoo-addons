# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""support@ : un courriel devient un ticket, rattache a sa personne sans jamais en creer."""

from odoo.tests import TransactionCase, tagged

COURRIEL = """Return-Path: <{expediteur}>
From: {expediteur}
To: {destinataire}
Subject: {sujet}
Message-ID: <{message_id}@example.com>
{en_tetes}Date: Tue, 07 Oct 2026 10:00:00 +0000
Content-Type: text/plain; charset=utf-8

Bonjour, j'ai besoin d'une attestation.
"""


@tagged("post_install", "-at_install")
class TestCourrielEntrant(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        domaine = cls.env.company.alias_domain_id
        if not domaine:
            domaine = cls.env["mail.alias.domain"].create({"name": "his.edu.dz"})
            cls.env.company.alias_domain_id = domaine
        cls.alias = cls.env.ref("helpdesk_mgmt.mail_alias_lead_info_helpdesk")
        cls.alias.alias_domain_id = domaine
        cls.support = "support@%s" % domaine.name
        cls.etudiant = cls.env["his.person"].create(
            {
                "name": "Ines Merabet",
                "type_personne": "etudiant",
                "source_system": "manual",
                "email": "ines.merabet@his.edu.dz",
                "email_personnel": "ines.merabet@gmail.com",
            }
        )

    def _recevoir(self, expediteur, sujet="Attestation", message_id="m1", en_tetes="", destinataire=None):
        raw = COURRIEL.format(
            expediteur=expediteur,
            destinataire=destinataire or self.support,
            sujet=sujet,
            message_id=message_id,
            en_tetes=en_tetes,
        )
        return self.env["mail.thread"].message_process(None, raw)

    def test_l_adresse_est_support(self):
        self.assertEqual(self.alias.alias_name, "support")

    def test_un_courriel_devient_un_ticket_canal_email(self):
        ticket = self.env["helpdesk.ticket"].browse(self._recevoir("Quelqu'un <qq@example.com>"))
        self.assertEqual(ticket.name, "Attestation")
        self.assertEqual(ticket.channel_id, self.env.ref("helpdesk_mgmt.helpdesk_ticket_channel_email"))

    def test_l_email_personnel_retrouve_la_personne(self):
        ticket = self.env["helpdesk.ticket"].browse(self._recevoir("Ines <Ines.Merabet@gmail.com>"))
        self.assertEqual(ticket.his_person_id, self.etudiant)
        # L'adresse d'ou elle a ecrit reste sur le ticket : c'est la qu'elle lit.
        self.assertIn("ines.merabet@gmail.com", ticket.partner_email.lower())

    def test_un_inconnu_ne_cree_ni_personne_ni_contact(self):
        personnes, contacts = self.env["his.person"].search_count([]), self.env["res.partner"].search_count([])
        ticket = self.env["helpdesk.ticket"].browse(self._recevoir("Inconnu <inconnu@example.com>"))
        self.assertFalse(ticket.his_person_id)
        self.assertEqual(self.env["his.person"].search_count([]), personnes)
        self.assertEqual(self.env["res.partner"].search_count([]), contacts)

    def test_email_personnel_partage_aucun_rattachement(self):
        self.env["his.person"].create(
            {
                "name": "Ines M. (doublon)",
                "type_personne": "candidat",
                "source_system": "manual",
                "email_personnel": "ines.merabet@gmail.com",
            }
        )
        ticket = self.env["helpdesk.ticket"].browse(self._recevoir("ines.merabet@gmail.com"))
        self.assertFalse(ticket.his_person_id)

    def test_une_reponse_rejoint_son_ticket(self):
        ticket = self.env["helpdesk.ticket"].browse(self._recevoir("Ines <ines.merabet@gmail.com>"))
        message = ticket.message_ids.filtered(lambda m: m.message_type == "email")[:1]
        reponse = self._recevoir(
            "Ines <ines.merabet@gmail.com>",
            sujet="Re: Attestation",
            message_id="m2",
            en_tetes="In-Reply-To: %s\nReferences: %s\n" % (message.message_id, message.message_id),
            destinataire="catchall@%s" % self.env.company.alias_domain_id.name,
        )
        self.assertEqual(reponse, ticket.id)
        self.assertEqual(self.env["helpdesk.ticket"].search_count([("name", "like", "Attestation")]), 1)

    def test_la_cloture_va_aussi_a_l_adresse_d_ecriture(self):
        ticket = self.env["helpdesk.ticket"].browse(self._recevoir("Ines <ines.merabet@gmail.com>"))
        self.env.cr.precommit.run()
        contacts = self.env["res.partner"].search_count([])
        ticket.stage_id = self.env.ref("helpdesk_mgmt.helpdesk_ticket_stage_done")
        self.env.cr.precommit.run()
        # Le compositeur transforme la copie en contacts (find_or_create) : un
        # second contact pour une personne du referentiel. Il n'en faut aucun.
        self.assertEqual(self.env["res.partner"].search_count([]), contacts)
        mail = self.env["mail.mail"].search(
            [("model", "=", "helpdesk.ticket"), ("res_id", "=", ticket.id), ("subject", "like", "clôturée")]
        )
        self.assertTrue(mail)
        self.assertIn("ines.merabet@gmail.com", (mail.email_cc or "").lower())
        self.assertIn("répondre à ce message", mail.body_html)
