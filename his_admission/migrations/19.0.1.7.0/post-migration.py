# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Libere la regle du pipeline partage de son drapeau noupdate.

La regle a d'abord ete livree dans le bloc `<data noupdate="1">` du fichier de
securite. Ce drapeau est pose sur l'`ir.model.data` de l'ENREGISTREMENT : le
sortir du bloc dans le XML ne le retire pas, et la correction de domaine ne
s'appliquait donc pas — la base gardait l'ancienne regle en silence. Le meme
piege que les motifs de perte natifs d'Odoo (voir his_crm_pipeline/hooks.py).

On remet donc le drapeau a False et on ecrit le domaine une fois. Les
livraisons suivantes passeront par le XML, comme une regle de securite doit
pouvoir le faire.
"""
from odoo import SUPERUSER_ID, api

# Les etapes a partir desquelles l'Admission suit le candidat. Nommees, et non
# bornees par une sequence : le pipeline Production Contenu porte des sequences
# bien plus hautes, et un simple seuil lui ouvrait ses demandes.
ETAPES = (
    'stage_vente_contact_etabli', 'stage_vente_accompagnement',
    'stage_vente_evaluation_psy', 'stage_vente_dossier',
    'stage_vente_pre_admis', 'stage_vente_frais_payes',
)
EQUIPES = ('crm_team_ventes', 'crm_team_orientation')


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    donnee = env['ir.model.data'].sudo().search([
        ('module', '=', 'his_admission'),
        ('name', '=', 'rule_crm_lead_admission'),
    ], limit=1)
    if not donnee:
        return
    donnee.noupdate = False

    regle = env['ir.rule'].sudo().browse(donnee.res_id)
    if not regle.exists():
        return
    equipes = [env.ref('his_crm_pipeline.%s' % x).id for x in EQUIPES]
    etapes = [env.ref('his_crm_pipeline.%s' % x).id for x in ETAPES]
    regle.domain_force = str([
        ('team_id', 'in', equipes),
        ('stage_id', 'in', etapes),
    ])
