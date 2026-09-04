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

# La sequence de « Contact etabli ». Un test de his_admission verifie que ce
# nombre est bien celui de l'etape : reordonner le pipeline le fait echouer.
SEQUENCE_CONTACT_ETABLI = 30


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
    if regle.exists():
        regle.domain_force = (
            "[('stage_id.sequence', '>=', %s)]" % SEQUENCE_CONTACT_ETABLI
        )
