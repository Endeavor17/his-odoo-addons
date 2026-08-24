# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
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
    _name = 'his.domaine'
    _description = "Domaine d'etudes"
    _order = 'sequence, name'

    name = fields.Char(string="Domaine", required=True, translate=True)
    name_arabe = fields.Char(string="Domaine (arabe)")
    code = fields.Char(string="Code", required=True, help="MI, ST, SEGC...")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Coefficients de la moyenne ponderee. Un coefficient a zero retire
    # simplement la note du calcul : le domaine Informatique ne regarde pas la
    # physique, il porte coef_physique = 0 et rien d'autre a coder.
    coef_bac = fields.Float(string="Coefficient BAC", default=2.0)
    coef_math = fields.Float(string="Coefficient maths", default=1.0)
    coef_physique = fields.Float(string="Coefficient physique", default=0.0)

    seuil_eligibilite = fields.Float(
        string="Seuil d'eligibilite", default=11.0,
        help="Moyenne ponderee en dessous de laquelle le dossier part en "
             "verification manuelle.",
    )
    min_bac = fields.Float(
        string="Moyenne BAC minimale", default=10.0,
        help="Plancher elimatoire, independant de la moyenne ponderee.",
    )
    min_math = fields.Float(
        string="Note de maths minimale", default=0.0,
        help="Plancher eliminatoire sur la note de maths. Zero = pas de plancher.",
    )

    specialite_ids = fields.One2many('his.specialite', 'domaine_id', string="Specialites")

    _code_unique = models.Constraint(
        'unique(code)', "Ce code de domaine est deja utilise.",
    )

    @api.constrains('coef_bac', 'coef_math', 'coef_physique')
    def _check_coefficients(self):
        """Au moins un coefficient non nul, sinon la moyenne ponderee divise par zero."""
        for domaine in self:
            if not (domaine.coef_bac + domaine.coef_math + domaine.coef_physique):
                raise ValidationError(
                    "Le domaine « %s » doit porter au moins un coefficient non nul, "
                    "sinon la moyenne ponderee n'est pas calculable." % domaine.name,
                )

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for domaine in self:
            domaine.display_name = "%s - %s" % (domaine.code, domaine.name)
