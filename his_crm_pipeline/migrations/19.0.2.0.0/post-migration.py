# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Passage au modele de roles. Ce script ne REATTRIBUE volontairement rien.

Deviner qui devient Conseiller, Approbateur ou simple Demandeur a partir des
groupes commerciaux portes aujourd'hui produirait des droits faux — et un droit
faux est bien plus difficile a reperer qu'un droit absent : personne ne signale
qu'il voit trop de choses.

Les roles se posent donc a la main, dans Parametres > Utilisateurs, ou par
`tools/seed_test_users.py` pour une base de recette. Tant qu'un compte n'a
recu aucun role, il ne voit simplement plus les deux pipelines : c'est le defaut
sur.

Ce script se contente de retirer les groupes commerciaux devenus incoherents
avec le nouveau modele : les roles Admissions les IMPLIQUENT desormais, et un
groupe pose en direct par-dessus l'echelle rend illisible ce que la personne
peut vraiment faire. Un compte qui n'a rien d'autre se retrouve sans acces au
CRM — ce qui est exactement l'etat d'un compte a qui aucun role n'a encore ete
attribue.
"""
from odoo import SUPERUSER_ID, api

GROUPES_A_RETIRER = (
    'sales_team.group_sale_salesman',
    'sales_team.group_sale_salesman_all_leads',
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    roles = env['res.groups']
    for xmlid in (
        'his_crm_pipeline.group_admissions_acquisition',
        'his_crm_pipeline.group_admissions_conseiller',
        'his_crm_pipeline.group_admissions_responsable',
        'his_crm_pipeline.group_admissions_orientation',
    ):
        groupe = env.ref(xmlid, raise_if_not_found=False)
        if groupe:
            roles |= groupe

    for xmlid in GROUPES_A_RETIRER:
        groupe = env.ref(xmlid, raise_if_not_found=False)
        if not groupe:
            continue
        # L'administrateur garde ses acces : le lui retirer fermerait la porte
        # a celui-la meme qui doit distribuer les nouveaux roles.
        concernes = groupe.user_ids.filtered(
            lambda u: not u.has_group('base.group_system') and not (u.group_ids & roles),
        )
        if concernes:
            concernes.write({'group_ids': [(3, groupe.id)]})
