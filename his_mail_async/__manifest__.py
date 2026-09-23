# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Envoi de facture asynchrone",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "L'envoi d'une facture par courriel ne bloque plus la requete",
    "description": """
Quand une facture part par courriel (POS ou Comptabilite), le coeur d'Odoo
(`account.move.send._send_mail`, dans `account/models/account_move_send.py`)
appelle `message_post()` sans rien preciser sur la vitesse d'envoi. Or
`mail.thread._notify_thread` lit le contexte `mail_notify_force_send`
(vrai par defaut) : en dessous de 50 destinataires — donc systematiquement
pour une facture unique — il envoie le courriel tout de suite, dans le fil de
la requete, au lieu de le deposer en file (`mail.mail` a l'etat `outgoing`)
pour le cron `Mail: Email Queue Manager`. Si le relais SMTP est lent, c'est
la requete de l'utilisateur (comptable ou caisse POS) qui attend.

Ce module surcharge `_send_mail` pour poser `mail_notify_force_send=False`
sur le contexte avant d'appeler le coeur. Rien d'autre ne change : le
courriel est cree exactement pareil, seulement laisse a l'etat `outgoing` ;
le cron le declenche en general en quelques secondes (Odoo redemarre son
propre timer des qu'un courriel entre en file), pas a la prochaine execution
planifiee.

Ne touche ni au serveur sortant, ni a l'adresse d'expedition, ni au contenu
du courriel : seulement au moment ou il part.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "account",
    ],
    "installable": True,
}
