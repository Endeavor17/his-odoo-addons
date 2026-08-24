# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""« Pre-admis » cesse d'etre l'etape gagnante.

Les etapes sont chargees en noupdate="1" — une mise a jour du module ne les
touche donc pas, c'est voulu : l'Admission doit pouvoir les ajuster sans qu'une
livraison ecrase son travail. Mais ce changement-ci n'est pas un ajustement de
libelle, c'est une correction de definition : compter la pre-admission comme
une conversion faisait afficher au pipeline des intentions au lieu d'argent
encaisse. Il doit donc atteindre les bases existantes, d'ou ce script.

Passer par l'ORM et non par un UPDATE SQL : crm.stage.write() recalcule la
probabilite des leads presents dans l'etape. Un UPDATE les laisserait a 100 %.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    stage = env.ref('his_crm_pipeline.stage_vente_pre_admis', raise_if_not_found=False)
    if stage and stage.is_won:
        stage.is_won = False
