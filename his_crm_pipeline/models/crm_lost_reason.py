# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class CrmLostReason(models.Model):
    """Un ordre, parce que le motif le plus frequent doit etre le plus proche.

    Odoo livre crm.lost.reason SANS champ sequence et avec _order = 'id' : les
    motifs apparaissent donc dans l'ordre ou ils ont ete crees. Or trois motifs
    couvrent environ 70 % des pertes reelles. Les laisser disperses fait
    parcourir onze lignes a chaque cloture, et une cloture couteuse est une
    cloture qu'on saute — exactement ce que la contrainte de motif obligatoire
    cherche a empecher.

    Le champ est donc ajoute ici, avec un defaut eleve : un motif cree plus
    tard par une equipe se range apres les notres sans les bousculer.
    """
    _inherit = 'crm.lost.reason'
    _order = 'sequence, name'

    sequence = fields.Integer(default=50)
