from odoo import api, fields, models

# Les couleurs 1 a 11 de la palette Odoo (0 = sans couleur).
PALETTE = range(1, 12)


class HisHygieneMember(models.Model):
    """Une salariee de l'equipe hygiene.

    L'equipe se lit sur ce modele et non sur un groupe d'utilisateurs : la
    plupart des salariees n'ont pas de compte. La personne vient du
    referentiel (hr.employee), ce modele ne porte que ce que l'hygiene ajoute.
    """

    _name = "his.hygiene.member"
    _description = "Hygiene Team Member"
    _order = "sequence, id"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True, ondelete="restrict", index=True)
    name = fields.Char(related="employee_id.name", string="Name")
    user_id = fields.Many2one(related="employee_id.user_id", string="User")
    initials = fields.Char(compute="_compute_initials", store=True, readonly=False)
    color = fields.Integer(string="Colour", default=lambda self: self._next_color())
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _employee_unique = models.Constraint("UNIQUE(employee_id)", "This employee is already in the hygiene team.")

    @api.depends("employee_id.name")
    def _compute_initials(self):
        for member in self:
            words = (member.employee_id.name or "").split()
            member.initials = "".join(w[0] for w in words[:2]).upper()

    @api.model
    def _next_color(self):
        used = set(self.with_context(active_test=False).search([]).mapped("color"))
        return next((c for c in PALETTE if c not in used), 1)

    @api.model
    def _hygiene_members(self):
        return self.sudo().search([])
