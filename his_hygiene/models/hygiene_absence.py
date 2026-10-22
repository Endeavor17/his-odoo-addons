from odoo import fields, models


class HisHygieneAbsence(models.Model):
    """Une salariee absente un jour entier.

    Gardee ici et non dans les conges RH : c'est ce qui decouvre ses zones dans
    la matrice et ce que compte le recapitulatif. Une demi-journee n'est pas une
    absence : la responsable ajoute simplement quelqu'un sur les zones restantes.
    """

    _name = "his.hygiene.absence"
    _description = "Hygiene Absence"
    _order = "date desc, id"

    employee_id = fields.Many2one("hr.employee", string="Worker", required=True, ondelete="cascade", index=True)
    date = fields.Date(required=True, index=True)
    reason = fields.Char()

    _employee_date_unique = models.Constraint(
        "UNIQUE(employee_id, date)", "This worker is already marked absent on that day."
    )
