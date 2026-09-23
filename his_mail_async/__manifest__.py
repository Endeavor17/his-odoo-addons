# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Envoi de facture asynchrone",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "PDF et courriel de facture hors de la requete (caisse POS, comptabilite)",
    "description": """
Quand une facture part par courriel (POS ou Comptabilite), le coeur d'Odoo
(`account.move.send._send_mail`, dans `account/models/account_move_send.py`)
appelle `message_post()` sans rien preciser sur la vitesse d'envoi. Or
`mail.thread._notify_thread_by_email` lit le contexte `mail_notify_force_send`
(vrai par defaut) : sous `mail.mail.force.send.limit` destinataires (100) —
donc systematiquement pour une facture — il envoie le courriel dans la
requete au lieu de le deposer en file (`mail.mail` a l'etat `outgoing`).
Si le relais SMTP est lent, c'est la requete (comptable ou caisse POS) qui
attend.

Ce module surcharge `_send_mail` pour poser `mail_notify_force_send=False`
sur la facture (c'est elle qui fait `message_post`), puis reveille le cron
`Mail: Email Queue Manager` : planifie toutes les heures, rien d'autre ne
le declenche quand un courriel entre en file. Mesure en local : le courriel
est traite dans les 5 secondes apres la validation.

Caisse POS : le coeur genere aussi le PDF (wkhtmltopdf) dans la requete de
la caisse (`pos.order._generate_pos_order_invoice` -> `_generate_and_send`).
Ce module passe `generate_pdf=False` (prevu par le coeur, voir
`l10n_sa_edi_pos`) et confie PDF + courriel au cron « Send invoices
automatically », comme un envoi par lot, en le reveillant (il ne tourne
qu'une fois par jour). Si ce cron est archive, le comportement du coeur
reste. Mesure en local : facturer une commande POS passe de 5,7-6,6 s a
1,5-2,3 s ; PDF et courriel suivent en arriere-plan en quelques secondes.

Ne touche ni au serveur sortant, ni a l'adresse d'expedition, ni au contenu
du courriel : seulement au moment ou il part.
    """,
    "author": "Groupe HIS-HTC-IRA",
    "license": "LGPL-3",
    "depends": [
        "account",
        "point_of_sale",
    ],
    "installable": True,
}
