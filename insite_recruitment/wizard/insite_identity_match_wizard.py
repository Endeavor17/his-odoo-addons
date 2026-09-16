from odoo import _, api, fields, models
from odoo.exceptions import UserError


class InsiteIdentityMatchWizard(models.TransientModel):
    """The mandatory human-confirmation step for anything short of an exact
    matricule match (spec section 13: "NEVER automatically merge a Person
    using probabilistic matching alone"). Opened on a submission left in
    'needs_matching' state, or standalone when soliciting a teacher who
    isn't an obvious exact match.
    """

    _name = "insite.identity.match.wizard"
    _description = "InSite Identity Matching"

    submission_id = fields.Many2one("insite.submission", "Raw Submission")

    matricule = fields.Char("Institutional Matricule")
    first_name = fields.Char("First Name")
    last_name = fields.Char("Last Name")
    name_ar = fields.Char("Name (Arabic)")
    email = fields.Char("Email")
    phone = fields.Char("Phone")

    possible_person_ids = fields.Many2many("his.person", string="Possible Existing Persons")
    possible_applicant_ids = fields.Many2many("hr.applicant", string="Possible Campus+ Applicants")

    selected_person_id = fields.Many2one("his.person", "Use This Person")
    selected_applicant_id = fields.Many2one("hr.applicant", "Use This Campus+ Applicant")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        submission = self.env["insite.submission"].browse(vals.get("submission_id"))
        if submission:
            payload = submission.payload or {}
            vals.update(
                {
                    "matricule": payload.get("matricule"),
                    "first_name": payload.get("firstName"),
                    "last_name": payload.get("lastName"),
                    "name_ar": payload.get("nameAr"),
                    "email": payload.get("email"),
                    "phone": payload.get("phone"),
                }
            )
        return vals

    def action_search(self):
        self.ensure_one()
        match, applicants = self.env["insite.submission"]._insite_identity_matches(
            matricule=self.matricule,
            first_name=self.first_name,
            last_name=self.last_name,
            name_ar=self.name_ar,
            email=self.email,
            phone=self.phone,
        )
        # A conflict (matricule held by a student) is not offered as a choice.
        person = match["person"] if not match["conflict"] else None
        self.possible_person_ids = [(6, 0, person.ids if person else [])]
        if person and match["method"] == "deterministic":
            self.selected_person_id = person
        self.possible_applicant_ids = [(6, 0, applicants.ids)]
        return {
            "type": "ir.actions.act_window",
            "name": _("Identity Matching"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm_existing_person(self):
        self.ensure_one()
        if not self.selected_person_id:
            raise UserError(_("Pick an existing Person before confirming."))
        return self._resolve(self.selected_person_id, "possible_match")

    def action_confirm_existing_applicant(self):
        """The operator recognised a Campus+ applicant: bring them into the
        register through the Campus+ bridge — the same path Select takes —
        rather than building a person by hand here."""
        self.ensure_one()
        if not self.selected_applicant_id:
            raise UserError(_("Pick an existing Campus+ applicant before confirming."))
        applicant = self.selected_applicant_id.sudo().with_context(campus_identity_force=True)
        applicant._his_creer_ou_rapprocher_personne()
        person = applicant.his_person_id
        if not person:
            raise UserError(
                _(
                    "%s resembles an existing person in the identity register. Confirm or "
                    "reject that match on the Campus+ application first.",
                    applicant.display_name,
                )
            )
        if not person.is_internal_teacher:
            person.is_internal_teacher = "external"
        return self._resolve(person, "possible_match")

    def action_confirm_new_person(self):
        self.ensure_one()
        person = self.env["his.person"]._insite_create_external(
            {
                "name": " ".join(filter(None, [self.first_name, self.last_name])),
                "nom_arabe": self.name_ar,
                "email_personnel": self.email,
                "phone": self.phone,
            }
        )
        return self._resolve(person, "new")

    def _resolve(self, person, match_method):
        # Confirming a match is the actual "execute" step of identity
        # matching, so it carries the same permission check as action_process.
        self.env["campus.process.permission"]._check_process_permission("insite_candidatures", "execute")
        if self.submission_id:
            self.submission_id._insite_resolve(person, match_method)
        return {
            "type": "ir.actions.act_window",
            "name": _("Person"),
            "res_model": "his.person",
            "res_id": person.id,
            "view_mode": "form",
        }
