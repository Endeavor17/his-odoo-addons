# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _send_mail(self, move, mail_template, **kwargs):
        # mail_notify_force_send vaut True par defaut dans mail.thread
        # (_notify_thread) : en dessous de 50 destinataires, ce qui est
        # toujours le cas pour une facture, le courriel part tout de suite
        # dans le fil de la requete au lieu d'etre depose en file. On le met
        # a False pour laisser mail.mail a l'etat outgoing ; le cron
        # "Mail: Email Queue Manager" l'envoie ensuite, en general en
        # quelques secondes.
        return super(
            AccountMoveSend, self.with_context(mail_notify_force_send=False)
        )._send_mail(move, mail_template, **kwargs)
