from odoo import _, api, fields, models
from odoo.exceptions import UserError


class InsiteIdentityMatchWizard(models.TransientModel):
    """The mandatory human-confirmation step for anything short of an exact
    matricule match (spec section 13: "NEVER automatically merge a Person
    using probabilistic matching alone"). Opened on a submission left in
    'needs_matching' state, or standalone when soliciting a teacher who
    isn't an obvious exact match.
    """

    _name = 'insite.identity.match.wizard'
    _description = 'InSite Identity Matching'

    submission_id = fields.Many2one('insite.submission', "Raw Submission")

    matricule = fields.Char("Institutional Matricule")
    first_name = fields.Char("First Name")
    last_name = fields.Char("Last Name")
    name_ar = fields.Char("Name (Arabic)")
    email = fields.Char("Email")
    phone = fields.Char("Phone")

    possible_person_ids = fields.Many2many(
        'academic.person', string="Possible Existing Persons")
    possible_applicant_ids = fields.Many2many(
        'hr.applicant', string="Possible Campus+ Applicants")

    selected_person_id = fields.Many2one('academic.person', "Use This Person")
    selected_applicant_id = fields.Many2one('hr.applicant', "Use This Campus+ Applicant")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        submission = self.env['insite.submission'].browse(vals.get('submission_id'))
        if submission:
            payload = submission.payload or {}
            vals.update({
                'matricule': payload.get('matricule'),
                'first_name': payload.get('firstName'),
                'last_name': payload.get('lastName'),
                'name_ar': payload.get('nameAr'),
                'email': payload.get('email'),
                'phone': payload.get('phone'),
            })
        return vals

    def action_search(self):
        self.ensure_one()
        matches = self.env['academic.person'].insite_find_matches(
            matricule=self.matricule, first_name=self.first_name, last_name=self.last_name,
            name_ar=self.name_ar, email=self.email, phone=self.phone,
        )
        if matches['exact']:
            self.selected_person_id = matches['exact']
        self.possible_person_ids = matches['possible_persons']
        self.possible_applicant_ids = matches['possible_applicants']
        return {
            'type': 'ir.actions.act_window',
            'name': _("Identity Matching"),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm_existing_person(self):
        self.ensure_one()
        if not self.selected_person_id:
            raise UserError(_("Pick an existing Person before confirming."))
        return self._resolve(self.selected_person_id, 'possible_match')

    def action_confirm_existing_applicant(self):
        self.ensure_one()
        if not self.selected_applicant_id:
            raise UserError(_("Pick an existing Campus+ applicant before confirming."))
        person = self.env['academic.person'].insite_create_from_applicant(self.selected_applicant_id)
        return self._resolve(person, 'possible_match')

    def action_confirm_new_person(self):
        self.ensure_one()
        person = self.env['academic.person'].create({
            'first_name': self.first_name,
            'last_name': self.last_name,
            'name_ar': self.name_ar,
            'matricule_institutionnel': self.matricule or False,
            'email_institutional': self.email,
            'phone': self.phone,
            # Confirming a submission's identity match — external, same as
            # the auto-created-Person path in insite.submission.action_process().
            'is_internal_teacher': 'external',
        })
        return self._resolve(person, 'new')

    def _resolve(self, person, match_method):
        # Checkpoint 5 finding: confirming a match is the actual "execute"
        # step of identity matching (it's what turns a probable match, or a
        # brand-new payload, into a real Person/candidature link) but had no
        # permission check of its own — action_process() checks execute
        # before handing off to needs_matching, but nothing stopped calling
        # these confirm methods directly afterwards. Same check, same code,
        # as the entry point it completes.
        self.env['campus.process.permission']._check_process_permission('insite_candidatures', 'execute')
        if self.submission_id:
            self.submission_id._insite_resolve(person, match_method)
        return {
            'type': 'ir.actions.act_window',
            'name': _("Person"),
            'res_model': 'academic.person',
            'res_id': person.id,
            'view_mode': 'form',
        }
