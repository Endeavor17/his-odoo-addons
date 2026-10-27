# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Adresse du helpdesk : support@ -> odoo-support@ (boite creee par Mohamed, 2026-10-27).

L'alias est en noupdate : une mise a jour ne le reecrit pas. Seul l'ancien nom
est remplace, un nom change a la main reste.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    alias = env.ref("helpdesk_mgmt.mail_alias_lead_info_helpdesk", raise_if_not_found=False)
    if alias and alias.alias_name == "support":
        alias.alias_name = "odoo-support"
