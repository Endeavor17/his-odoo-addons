# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models

CYCLE = [
    ("licence", "Bachelor"),
    ("master", "Master"),
]


class HisSpecialite(models.Model):
    """Specialite offerte, rattachee a son domaine.

    Un modele et non une Selection : la liste s'allonge a chaque rentree, et
    chaque specialite porte un code qui entre dans le numero d'etudiant. Une
    Selection imposerait une livraison de code pour ouvrir une specialite.
    """

    _name = "his.specialite"
    _description = "Specialty"
    _order = "domaine_id, sequence, name"

    name = fields.Char(string="Specialty", required=True, translate=True)
    name_arabe = fields.Char(string="Specialty (Arabic)")
    code = fields.Char(string="Code", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    domaine_id = fields.Many2one(
        "his.domaine",
        string="Field of Study",
        required=True,
        ondelete="restrict",
        help="Carries the eligibility scale applied to files in this specialty.",
    )
    cycle = fields.Selection(CYCLE, string="Cycle", required=True, default="licence")

    _code_unique = models.Constraint(
        "unique(code)",
        "This specialty code is already used.",
    )

    @api.depends("name", "name_arabe")
    def _compute_display_name(self):
        # Le classeur affiche les deux langues cote a cote (« إعلام آلي -
        # أنظمة الإعلام الآلي »). Les equipes reconnaissent la forme arabe :
        # la retirer les obligerait a reapprendre leur propre catalogue.
        for specialite in self:
            specialite.display_name = (
                "%s - %s" % (specialite.name, specialite.name_arabe) if specialite.name_arabe else specialite.name
            )
