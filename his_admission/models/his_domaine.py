# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HisDomaine(models.Model):
    """Domaine d'etudes, porteur du bareme d'eligibilite.

    Le bareme vit ici et non dans le code : chaque domaine pondere le BAC, les
    maths et la physique differemment, et ces coefficients bougent d'une rentree
    a l'autre. Les figer en dur imposerait une livraison a chaque revision.

    Remplace la feuille CALCULATEUR du classeur, ou la formule etait recopiee a
    la main pour chaque domaine — avec l'erreur que cela suppose (cf. le test
    d'eligibilite : la branche ST du classeur comparait une cellule de texte et
    repondait ELIGIBLE quelle que soit la moyenne).
    """

    _name = "his.domaine"
    _description = "Academic Field"
    _order = "sequence, name"

    name = fields.Char(string="Field of Study", required=True, translate=True)
    name_arabe = fields.Char(string="Field of Study (Arabic)")
    code = fields.Char(string="Code", required=True, help="MI, ST, SEGC...")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Coefficients de la moyenne ponderee. Un coefficient a zero retire
    # simplement la note du calcul : le domaine Informatique ne regarde pas la
    # physique, il porte coef_physique = 0 et rien d'autre a coder.
    coef_bac = fields.Float(string="Baccalaureate Weight", default=2.0)
    coef_math = fields.Float(string="Maths Weight", default=1.0)
    coef_physique = fields.Float(string="Physics Weight", default=0.0)

    seuil_eligibilite = fields.Float(
        string="Eligibility Threshold",
        default=11.0,
        help="Weighted average below which the file goes to manual review.",
    )
    min_bac = fields.Float(
        string="Minimum Baccalaureate Average",
        default=10.0,
        help="Eliminatory floor, independent of the weighted average.",
    )
    min_math = fields.Float(
        string="Minimum Maths Mark",
        default=0.0,
        help="Eliminatory floor on the maths mark. Zero = no floor.",
    )

    specialite_ids = fields.One2many("his.specialite", "domaine_id", string="Specialties")

    _code_unique = models.Constraint(
        "unique(code)",
        "This field-of-study code is already used.",
    )

    @api.constrains("coef_bac", "coef_math", "coef_physique")
    def _check_coefficients(self):
        """Au moins un coefficient non nul, sinon la moyenne ponderee divise par zero."""
        for domaine in self:
            if not (domaine.coef_bac + domaine.coef_math + domaine.coef_physique):
                raise ValidationError(
                    _(
                        'The field of study "%s" must carry at least one non-zero weight, '
                        "otherwise the weighted average cannot be computed.",
                        domaine.name,
                    )
                )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for domaine in self:
            domaine.display_name = "%s - %s" % (domaine.code, domaine.name)
