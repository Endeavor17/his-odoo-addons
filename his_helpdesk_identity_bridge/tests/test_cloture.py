# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Donnees de depart, et le courriel de cloture qui ne fait pas attendre l'agent."""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCloture(TransactionCase):
    def test_l_equipe_support_le_poste_et_le_guichet(self):
        support = self.env.ref("his_helpdesk_identity_bridge.team_support")
        poste = self.env.ref("his_helpdesk_identity_bridge.job_support")
        self.assertEqual(support.his_job_id, poste)
        self.assertIn(self.env.ref("helpdesk_mgmt.group_helpdesk_manager"), poste.group_ids)
        self.assertTrue(self.env.ref("his_helpdesk_identity_bridge.channel_guichet"))

    def test_la_cloture_part_en_file_et_reveille_le_cron(self):
        person = self.env["his.person"].create(
            {
                "name": "Rym Bouzid",
                "type_personne": "etudiant",
                "source_system": "manual",
                "email": "rym.bouzid@example.com",
            }
        )
        ticket = self.env["helpdesk.ticket"].create(
            {"name": "Attestation", "description": "<p>x</p>", "his_person_id": person.id}
        )
        # Le suivi (et le courriel qu'il declenche) tourne au precommit : vider
        # celui de la creation, comme deux requetes distinctes en vrai.
        self.env.cr.precommit.run()
        cron = self.env.ref("mail.ir_cron_mail_scheduler_action")
        Trigger = self.env["ir.cron.trigger"]
        triggers_avant = Trigger.search_count([("cron_id", "=", cron.id)])
        MailMail = type(self.env["mail.mail"])
        # En test, l'envoi force passe par send_after_commit (il n'y a pas de
        # commit) : c'est lui qu'il faut espionner, pas seulement send.
        with (
            patch.object(MailMail, "send", autospec=True) as send,
            patch.object(MailMail, "send_after_commit", autospec=True) as send_after_commit,
        ):
            ticket.stage_id = self.env.ref("helpdesk_mgmt.helpdesk_ticket_stage_done")
            self.env.cr.precommit.run()
        self.assertFalse(send.called, "la cloture a ete envoyee dans la requete de l'agent")
        self.assertFalse(send_after_commit.called, "la cloture a ete envoyee dans la requete de l'agent")
        self.assertGreater(Trigger.search_count([("cron_id", "=", cron.id)]), triggers_avant)
        mail = self.env["mail.mail"].search(
            [("model", "=", "helpdesk.ticket"), ("res_id", "=", ticket.id), ("subject", "like", "clôturée")]
        )
        self.assertTrue(mail)
        self.assertIn("répondre à ce message", mail.body_html)
