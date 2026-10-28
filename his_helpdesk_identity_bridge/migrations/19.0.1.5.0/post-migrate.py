# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Les tickets vont aux techniciens, plus au responsable (recette 2026-10-28).

L'equipe Support et le poste « Support Officer » sont en noupdate : une mise a
jour ne les reecrit pas. L'equipe passe au poste « Helpdesk Technician » (cree
par les donnees) si elle suit encore l'ancien ; l'ancien poste, qui porte le
role « Helpdesk Manager », en prend le nom s'il n'a pas ete renomme a la main.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    manager_job = env.ref("his_helpdesk_identity_bridge.job_support", raise_if_not_found=False)
    technician_job = env.ref("his_helpdesk_identity_bridge.job_helpdesk_technician", raise_if_not_found=False)
    team = env.ref("his_helpdesk_identity_bridge.team_support", raise_if_not_found=False)
    if team and technician_job and team.his_job_id == manager_job:
        team.his_job_id = technician_job
    if manager_job and manager_job.with_context(lang="en_US").name == "Support Officer":
        manager_job.with_context(lang="en_US").name = "Helpdesk Manager"
        manager_job.with_context(lang="fr_FR").name = "Responsable assistance"
    if technician_job:
        technician_job.with_context(lang="fr_FR").name = "Technicien assistance"
