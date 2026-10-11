# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HisPersonSyncLog(models.Model):
    _name = "his.person.sync.log"
    _description = "People Sync Log"
    _order = "create_date desc, id desc"

    # Un modele dedie plutot que le seul chatter : un import porte des
    # centaines de lignes, dont des conflits et des refus qui ne sont
    # rattaches a AUCUNE fiche — un message de chatter n'aurait nulle part ou
    # se poser. Les fiches effectivement touchees recoivent en plus leur
    # message de chatter.
    person_id = fields.Many2one("his.person", string="Person", ondelete="set null", index=True)
    source_system = fields.Selection(
        selection=[
            ("odoo_hr", "Odoo HR"),
            ("google_sheets", "Google Sheets"),
            ("uniflow", "Uniflow"),
            ("manual", "Manual Entry"),
        ],
        string="Source System",
        required=True,
    )
    external_ref = fields.Char(string="Source Reference", index=True)
    nom_source = fields.Char(string="Name in the source")
    matricule_source = fields.Char(string="Registration number in the source")
    outcome = fields.Selection(
        selection=[
            ("created", "Record Created"),
            ("updated", "Record Updated"),
            ("flagged", "To Review"),
            ("confirmed", "Match Confirmed"),
            ("rejected", "Match Rejected, Record Created"),
            ("conflict", "Conflict — row rejected"),
        ],
        string="Result",
        required=True,
        index=True,
    )
    match_method = fields.Selection(
        selection=[
            ("deterministic", "Deterministic"),
            ("probabilistic", "Probabilistic"),
            ("new", "Creation"),
        ],
        string="Method",
    )
    score = fields.Float(string="Score", digits=(3, 2))
    message = fields.Char(string="Detail")
    user_id = fields.Many2one(
        "res.users",
        string="Run By",
        default=lambda self: self.env.user,
        required=True,
    )
