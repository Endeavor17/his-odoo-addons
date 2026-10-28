# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le role « Helpdesk Agent » devient « Helpdesk Technician » et va sur le poste
du meme nom, a qui les tickets sont attribues (recette 2026-10-28).

Le catalogue est en noupdate : une mise a jour ne le reecrit pas, et le lien
vers le poste (cree par his_helpdesk_identity_bridge 19.0.1.5.0) n'est pose
qu'a l'installation. Un role renomme a la main garde son nom.
"""

from odoo import SUPERUSER_ID, Command, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    role = env.ref("his_role_catalogue.role_helpdesk_agent", raise_if_not_found=False)
    job = env.ref("his_helpdesk_identity_bridge.job_helpdesk_technician", raise_if_not_found=False)
    if not role:
        return
    if role.with_context(lang="en_US").name == "Helpdesk Agent":
        role.with_context(lang="en_US").name = "Helpdesk Technician"
        role.with_context(lang="fr_FR").name = "Technicien assistance"
    if job and role not in job.role_ids:
        job.role_ids = [Command.link(role.id)]
