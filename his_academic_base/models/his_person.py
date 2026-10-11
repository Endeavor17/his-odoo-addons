from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HisPerson(models.Model):
    _inherit = "his.person"

    rang_academique = fields.Selection(
        [
            ("PROF", "Professor"),
            ("MCA", "Associate Professor A"),
            ("MCB", "Associate Professor B"),
            ("MAA", "Assistant Lecturer A"),
            ("MAB", "Assistant Lecturer B"),
        ],
        string="Academic Rank",
        help="Teachers only.",
    )
    specialite = fields.Char(
        string="Specialty",
        help="Declarative free text, as it exists in the HIS referential.",
    )
    faculty_ids = fields.Many2many(
        "his.faculty",
        "his_faculty_person_rel",
        "person_id",
        "faculty_id",
        string="Faculties",
        help="A person may legitimately belong to more than one faculty.",
    )

    @api.constrains("rang_academique", "type_personne")
    def _check_rang_academique(self):
        for person in self:
            if person.rang_academique and person.type_personne != "enseignant":
                raise ValidationError(
                    _(
                        "An academic rank only applies to a teacher. %(person)s is recorded as %(kind)s.",
                        person=person.display_name,
                        kind=dict(self._fields["type_personne"].selection).get(person.type_personne)
                        or _("nothing in particular"),
                    )
                )
