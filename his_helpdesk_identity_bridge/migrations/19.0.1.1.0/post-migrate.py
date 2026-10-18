# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Quatre equipes -> une seule (Support).

Les quatre equipes du 2026-10-07 etaient en noupdate : retirees des donnees,
elles restent en base. Leurs tickets passent a Support, elles sont archivees.
"""

from odoo import SUPERUSER_ID, api

ANCIENNES = ("team_informatique", "team_scolarite", "team_admissions", "team_finance")


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Canal Web : le fichier de donnees ne l'archive qu'a l'installation (le
    # canal est noupdate chez OCA, une mise a jour ne le reecrit pas).
    web = env.ref("helpdesk_mgmt.helpdesk_ticket_channel_web", raise_if_not_found=False)
    if web:
        web.active = False

    support = env.ref("his_helpdesk_identity_bridge.team_support")
    trouvees = (env.ref("his_helpdesk_identity_bridge." + xmlid, raise_if_not_found=False) for xmlid in ANCIENNES)
    anciennes = env["helpdesk.ticket.team"].browse([equipe.id for equipe in trouvees if equipe])
    if not anciennes:
        return
    tickets = env["helpdesk.ticket"].with_context(active_test=False).search([("team_id", "in", anciennes.ids)])
    # user_id est recalcule au changement d'equipe (vide s'il n'est pas membre) :
    # le garder tel quel, l'agent d'avant reste le responsable du ticket.
    for user, groupe in tickets.grouped("user_id").items():
        groupe.write({"team_id": support.id, "user_id": user.id})
    anciennes.write({"active": False})
