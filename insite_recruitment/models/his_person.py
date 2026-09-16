from odoo import api, fields, models


class HisPerson(models.Model):
    """InSite's additions to the group's single identity record.

    InSite used to carry its own ``academic.person`` with its own matcher and
    matricule. A teacher is now one ``his.person`` whether they arrive through
    Campus+, InSite, HR or meals; only what InSite alone needs is added here.
    """

    _inherit = "his.person"

    is_internal_teacher = fields.Selection(
        [
            ("internal", "Internal Teacher"),
            ("external", "External Teacher"),
        ],
        string="Internal / External",
        tracking=True,
        help="Explicit classification — blank means not yet classified. "
        "Never inferred from history. An InSite Candidature cannot be "
        "created for a Person left unclassified.",
    )

    insite_candidature_ids = fields.One2many("insite.candidature", "person_id", "InSite Candidatures")
    insite_candidature_count = fields.Integer(compute="_compute_insite_counts")
    # Not ``engagement_ids``: his_person_core already uses that name for the
    # admission journey (his.engagement).
    insite_engagement_ids = fields.One2many("academic.engagement", "person_id", "InSite Engagements")
    insite_engagement_count = fields.Integer(compute="_compute_insite_counts")

    def _compute_insite_counts(self):
        candidatures = dict(
            self.env["insite.candidature"]._read_group([("person_id", "in", self.ids)], ["person_id"], ["__count"])
        )
        engagements = dict(
            self.env["academic.engagement"]._read_group([("person_id", "in", self.ids)], ["person_id"], ["__count"])
        )
        for person in self:
            person.insite_candidature_count = candidatures.get(person, 0)
            person.insite_engagement_count = engagements.get(person, 0)

    @api.model
    def _insite_create_external(self, vals):
        """A new external teacher enters as a candidate, WITHOUT a matricule.

        Same rule as admission: the lifetime number is issued once the
        institution commits — here, when the contract is signed.
        """
        vals = dict(vals)
        vals["name"] = vals.get("name") or vals.get("nom_arabe") or vals.get("email_personnel")
        vals.update(
            type_personne="candidat", source_system="manual", is_internal_teacher="external", match_method="new"
        )
        return self.sudo().create(vals)
