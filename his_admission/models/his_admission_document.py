# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class HisAdmissionDocument(models.Model):
    """Une piece attendue sur un dossier precis.

    Une ligne existe des que la piece est APPLICABLE, avant meme d'etre
    fournie. C'est ce qui distingue « pas encore recu » de « pas concerne » —
    distinction que le classeur ne savait pas faire : une case vide y pouvait
    signifier les deux, et personne ne pouvait dire laquelle.
    """
    _name = 'his.admission.document'
    _description = "Piece du dossier d'admission"
    _order = 'engagement_id, sequence, id'

    engagement_id = fields.Many2one(
        'his.engagement', string="Dossier", required=True,
        ondelete='cascade', index=True,
    )
    type_id = fields.Many2one(
        'his.document.type', string="Piece", required=True, ondelete='restrict',
    )
    sequence = fields.Integer(related='type_id.sequence', store=True)
    obligatoire = fields.Boolean(related='type_id.obligatoire', store=True, readonly=True)

    fourni = fields.Boolean(string="Fournie")
    date_fourniture = fields.Date(string="Date de reception")
    note = fields.Char(string="Remarque")

    _type_unique_par_dossier = models.Constraint(
        'unique(engagement_id, type_id)',
        "Cette piece figure deja sur ce dossier.",
    )

    @api.onchange('fourni')
    def _onchange_fourni(self):
        # Confort de saisie : cocher pose la date du jour, decocher l'efface.
        # Rien de plus, la date reste modifiable a la main pour une piece
        # recue la veille.
        for line in self:
            line.date_fourniture = fields.Date.context_today(line) if line.fourni else False
