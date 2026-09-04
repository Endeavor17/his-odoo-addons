# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Rattrape les candidats parvenus au-dela de l'etape declencheuse sans fiche.

Le declencheur comparait l'etape par EGALITE. Tirer une carte de « Pris en
charge » droit vers « Dossier et pre-admission » — geste que le kanban autorise
— ne creait donc ni personne ni dossier, et rien ne le signalait : le candidat
n'existait tout simplement pas pour l'Admission.

Le code compare desormais les sequences, ce qui repare les mouvements A VENIR.
Les candidats deja passes a travers, eux, resteraient invisibles pour toujours :
aucune ecriture ne viendra plus les faire repasser par le declencheur. C'est ce
que ce script repare.

Il n'invente rien — il rejoue exactement la methode du pont sur les leads
concernes, donc un rapprochement probable reste signale et non rattache, comme
si le lead venait d'atteindre l'etape.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    etape = env['crm.lead']._his_etape_declencheuse()
    equipe = env.ref('his_crm_pipeline.crm_team_ventes', raise_if_not_found=False)
    if not etape or not equipe:
        return

    # active_test=False : une candidature perdue apres avoir atteint l'etape a
    # elle aussi droit a sa fiche. Le matricule constate un passage, il ne
    # recompense pas une issue.
    orphelins = env['crm.lead'].with_context(active_test=False).search([
        ('team_id', '=', equipe.id),
        ('stage_id.sequence', '>=', etape.sequence),
        ('his_person_id', '=', False),
        ('his_person_candidate_id', '=', False),
    ])
    if not orphelins:
        return

    orphelins._his_creer_ou_rapprocher_personne()

    rattrapes = orphelins.filtered(lambda l: l.his_person_id)
    signales = orphelins.filtered(lambda l: l.his_person_candidate_id)
    env['ir.logging'].sudo().create({
        'name': 'his_crm_identity_bridge',
        'type': 'server',
        'level': 'INFO',
        'dbname': cr.dbname,
        'message': (
            "Rattrapage des candidats sans fiche : %s examines, %s rattaches, "
            "%s signales pour arbitrage humain."
            % (len(orphelins), len(rattrapes), len(signales))
        ),
        'path': __name__,
        'func': 'migrate',
        'line': '0',
    })
