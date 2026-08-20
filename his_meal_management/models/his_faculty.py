from odoo import fields, models


class HisFaculty(models.Model):
    """Faculty referential — data model section 3.

    Six codes were observed in the real HIS data. A person may legitimately
    belong to more than one, which is why `his.person.faculty_ids` is a
    many-to-many and not a single field: the specification calls that out as
    dictated by an inconsistency found in the real data, not as a theoretical
    allowance.
    """

    _name = 'his.faculty'
    _description = "HIS Faculty"
    _order = 'code'

    code = fields.Char(required=True, index=True, help="Short code as it appears in the HIS data, e.g. MI.")
    name = fields.Char(required=True, translate=True)
    name_confirmed = fields.Boolean(
        default=True,
        help="Unticked when the full name is not yet confirmed by a received catalogue.",
    )
    # Relation table renamed along with the retarget. Reusing the old
    # his_person_faculty_rel would leave Odoo pointing a partner_id column at
    # his.person ids; the 19.0.2.0.0 migration moves the existing rows across.
    person_ids = fields.Many2many(
        'his.person', 'his_faculty_person_rel', 'faculty_id', 'person_id',
        string="People",
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint('UNIQUE(code)', "This faculty code already exists.")

    def _compute_display_name(self):
        for faculty in self:
            faculty.display_name = f"{faculty.code} — {faculty.name}"
