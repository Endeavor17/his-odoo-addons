# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _send_mail(self, move, mail_template, **kwargs):
        # mail_notify_force_send vaut True par defaut dans mail.thread
        # (_notify_thread_by_email) : sous mail.mail.force.send.limit
        # destinataires (100), le courriel part dans la requete au lieu d'etre
        # depose en file. Le contexte va sur `move` : c'est lui qui fait
        # message_post, celui de `self` ne l'atteint pas.
        res = super()._send_mail(move.with_context(mail_notify_force_send=False), mail_template, **kwargs)
        # Le cron "Mail: Email Queue Manager" ne tourne que toutes les heures
        # et rien ne le reveille quand un courriel entre en file : on le
        # declenche au plus tot (apres le commit de la requete).
        self.env.ref("mail.ir_cron_mail_scheduler_action")._trigger()
        return res
