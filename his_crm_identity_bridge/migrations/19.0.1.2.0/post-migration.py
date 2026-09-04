# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Range les fiches ouvertes pour des candidats deja perdus.

L'hypothese A1 a ete tranchee : la fiche personne s'ouvre a la pre-admission,
et le matricule s'emet a l'encaissement. Les bases installees avant cette
decision portent des fiches creees au premier contact, dont certaines pour des
candidatures depuis perdues — deux sur neuf sur la base de recette, ce qui
suit exactement le taux de perte reel du CRM.

CE QUI NE PEUT PAS ETRE DEFAIT : le matricule deja distribue. La sequence ne
recycle jamais, et his_person_core refuse explicitement qu'une suppression
« libere » un numero. Ces numeros sont donc perdus pour toujours ; ce script
n'en fait pas semblant.

CE QUI PEUT L'ETRE : la presence de ces fiches dans le referentiel actif. On
les archive — le dossier suit par la meme occasion — de sorte que le
referentiel d'identite ne decrive plus que des gens que l'institution suit
reellement. Rien n'est supprime : une candidature perdue peut revenir, et la
fiche archivee sera retrouvee par la cle deterministe du pont.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    perdus = env['crm.lead'].with_context(active_test=False).search([
        ('active', '=', False),
        ('probability', '=', 0),
        ('his_person_id', '!=', False),
    ])
    fiches = perdus.mapped('his_person_id').filtered(
        # Seulement des candidats, et seulement ceux dont aucun dossier n'a
        # depasse l'admission : une personne devenue etudiante entre-temps
        # n'est pas concernee par la perte de sa premiere candidature.
        lambda p: p.type_personne == 'candidat'
        and not p.engagement_ids.filtered(lambda e: e.etat == 'inscrit')
    )
    if not fiches:
        return

    avec_matricule = fiches.filtered('matricule_institutionnel')
    fiches.action_archive()

    env['ir.logging'].sudo().create({
        'name': 'his_crm_identity_bridge',
        'type': 'server',
        'level': 'INFO',
        'dbname': cr.dbname,
        'message': (
            "Hypothese A1 : %s fiche(s) de candidats perdus archivee(s), dont "
            "%s portant un matricule deja emis — ces numeros restent consommes, "
            "la sequence ne les rend pas."
            % (len(fiches), len(avec_matricule))
        ),
        'path': __name__,
        'func': 'migrate',
        'line': '0',
    })
