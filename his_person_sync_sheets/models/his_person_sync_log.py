# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisPersonSyncLog(models.Model):
    _name = 'his.person.sync.log'
    _description = "Journal de synchronisation des personnes"
    _order = 'create_date desc, id desc'

    # Un modele dedie plutot que le seul chatter : un import porte des
    # centaines de lignes, dont des conflits et des refus qui ne sont
    # rattaches a AUCUNE fiche — un message de chatter n'aurait nulle part ou
    # se poser. Les fiches effectivement touchees recoivent en plus leur
    # message de chatter.
    person_id = fields.Many2one('his.person', string="Personne", ondelete='set null', index=True)
    source_system = fields.Selection(
        selection=[
            ('odoo_hr', "Odoo RH"),
            ('google_sheets', "Google Sheets"),
            ('uniflow', "Uniflow"),
            ('manual', "Saisie manuelle"),
        ],
        string="Systeme source", required=True,
    )
    external_ref = fields.Char(string="Reference source", index=True)
    nom_source = fields.Char(string="Nom dans la source")
    matricule_source = fields.Char(string="Matricule dans la source")
    outcome = fields.Selection(
        selection=[
            ('created', "Fiche creee"),
            ('updated', "Fiche mise a jour"),
            ('flagged', "A arbitrer"),
            ('confirmed', "Rapprochement confirme"),
            ('rejected', "Rapprochement refuse, fiche creee"),
            ('conflict', "Conflit — ligne rejetee"),
        ],
        string="Resultat", required=True, index=True,
    )
    match_method = fields.Selection(
        selection=[
            ('deterministic', "Deterministe"),
            ('probabilistic', "Probabiliste"),
            ('new', "Creation"),
        ],
        string="Methode",
    )
    score = fields.Float(string="Score", digits=(3, 2))
    message = fields.Char(string="Detail")
    user_id = fields.Many2one(
        'res.users', string="Execute par", default=lambda self: self.env.user, required=True,
    )
