import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_ENGINE = 'campus.scoring.engine'


class HrApplicant(models.Model):
    """Campus+ evaluation layered onto Odoo's standard applicant.

    Nothing here re-implements recruitment: stages, chatter, activities, the UTM
    campaign, attachments and access rights all come from hr_recruitment. What
    is added is the answers the Campus+ form collects and the evaluation built
    on top of them.
    """

    _inherit = 'hr.applicant'

    # ------------------------------------------------------------------
    # Answers from the web form
    # ------------------------------------------------------------------
    campus_name_ar = fields.Char("Name (Arabic)", tracking=True)
    campus_name_lat = fields.Char("Name (Latin)", tracking=True)
    campus_dob = fields.Date("Date of Birth")
    campus_phone2 = fields.Char(
        "Secondary Phone",
        help="Not collected by the current web form; kept so the field exists the "
             "day the form starts asking for it.")
    campus_wilaya = fields.Char("Wilaya", help="Not collected by the current web form.")
    campus_commune = fields.Char("Commune", help="Not collected by the current web form.")

    campus_university = fields.Char("University / Institution")
    campus_faculty = fields.Char("Faculty")
    campus_specialty = fields.Char("Speciality")
    campus_gov_institution = fields.Char("Government Institution")

    campus_scientific_rank = fields.Char("Scientific Rank", tracking=True)
    campus_years_exp = fields.Float("Years of Experience", digits=(16, 1), tracking=True)

    campus_lang_ar = fields.Char("Arabic Teaching Level")
    campus_lang_en = fields.Char("English Teaching Level")
    campus_lang_fr = fields.Char("French Teaching Level")

    campus_taught_his = fields.Char("Already Taught at HIS")
    campus_taught_campus = fields.Char("Already Joined Campus+")

    campus_available_days = fields.Json("Campus+ Availability Codes")
    campus_available_days_display = fields.Char(
        "Campus+ Availability", compute='_compute_multi_displays', store=True)

    campus_teach_methods = fields.Json("Teaching Methods")
    campus_teach_methods_display = fields.Char(
        "Teaching Methods Label", compute='_compute_multi_displays', store=True)

    campus_digital_tools = fields.Json("Digital Tools")
    campus_digital_tools_display = fields.Char(
        "Digital Tools Label", compute='_compute_multi_displays', store=True)

    campus_flipped_knowledge = fields.Char("Flipped Classroom Knowledge")
    campus_flipped_def = fields.Text("Flipped Classroom, In Own Words")
    campus_redesigned = fields.Char("Redesigned a Course")
    campus_redesign_detail = fields.Text("Redesign Details")
    campus_concerns = fields.Text("Concerns About Digital Platforms")
    campus_concerns_handled = fields.Text("How Concerns Were Addressed")
    campus_video_rec = fields.Char("Prior Video Recording Experience")
    campus_camera_confidence = fields.Char("Confidence on Camera")
    campus_referrals = fields.Text("Referring Teachers")
    campus_referrals_field = fields.Text("Referrers' Field")

    campus_subject_ids = fields.One2many(
        'campus.application.subject', 'applicant_id', "Subjects")
    campus_subject_count = fields.Integer("Subject Count", compute='_compute_campus_counts')
    campus_accepted_subject_ids = fields.Many2many(
        'campus.subject', string="Accepted Subjects",
        compute='_compute_accepted_subjects', store=False)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    campus_version_id = fields.Many2one(
        'campus.evaluation.version', "Evaluation Version",
        index=True, ondelete='restrict', tracking=True)
    campus_score_ids = fields.One2many(
        'campus.application.score', 'applicant_id', "Score Breakdown")
    campus_score_count = fields.Integer("Score Lines", compute='_compute_campus_counts')

    campus_final_score = fields.Float(
        "Final Score", digits=(16, 4), index=True, readonly=True, copy=False, tracking=True,
        help="Weighted result on a 0-100 scale when normalization is on.")
    campus_rank = fields.Integer(
        "Rank", index=True, readonly=True, copy=False,
        help="Position within the same evaluation version. Ties share a rank.")
    campus_state = fields.Selection([
        ('not_started', 'Not Evaluated'),
        ('submitted', 'Submitted'),
        ('evaluated', 'Evaluated'),
        ('locked', 'Locked'),
    ], string="Evaluation Status", default='not_started', required=True,
        index=True, tracking=True, copy=False,
        help="Lifecycle of the score computation. Independent of the recruitment "
             "stage, which tracks the human hiring pipeline.")
    campus_evaluation_date = fields.Datetime("Evaluated On", readonly=True, copy=False)
    campus_engine_version = fields.Char("Scoring Engine", readonly=True, copy=False)
    campus_weighting_method = fields.Char("Weighting Method", readonly=True, copy=False)
    campus_locked = fields.Boolean(
        "Lock Evaluation", copy=False,
        help="Protects this application from bulk recalculation.")
    campus_external_ref = fields.Char(
        "External Reference", index=True, copy=False,
        help="Idempotency key from the web form; prevents a retried submission "
             "from creating a second application.")
    campus_submission_ids = fields.One2many(
        'campus.submission', 'applicant_id', "Raw Submissions")

    # ------------------------------------------------------------------
    # Hiring funnel — everything after "this candidate looks good"
    # ------------------------------------------------------------------
    # Deliberately separate from stage_id and campus_state. stage_id is the
    # pipeline a recruiter drags cards through; campus_state is the technical
    # lifecycle of the score. This is the paperwork sequence, and it is the only
    # one of the three where the order is enforced.
    campus_hiring_state = fields.Selection([
        ('not_selected', 'Not Selected'),
        ('invited', 'Invited — awaiting reply'),
        ('meeting_1', '1st Meeting Scheduled'),
        ('interview1_completed', '1st Interview Completed'),
        ('docs_sent', 'Documents Sent'),
        ('docs_accepted', 'Documents Accepted'),
        ('final_sent', 'Final Breakdown Sent'),
        ('meeting_2', '2nd Meeting Scheduled'),
        ('interview2_completed', '2nd Interview Completed'),
        ('subjects_selected', 'Subjects Selected'),
        ('hired', 'Hired'),
    ], string="Hiring Step", default='not_selected', required=True,
        index=True, tracking=True, copy=False,
        help="Where this candidate stands in the selection and paperwork sequence. "
             "'docs_sent'/'docs_accepted'/'final_sent' are the original single-round "
             "document flow, kept for backward compatibility; the interview1/2 + "
             "Course Breakdown + Contract steps are the current Campus+ workflow — "
             "see campus_cb_state and campus_contract_state for those two, which "
             "progress independently of this field.")

    campus_hiring_date = fields.Datetime("Hired On", readonly=True, copy=False)

    # Documents are uploaded per candidate rather than generated: the wording and
    # the hours differ per person, so Odoo sends whatever is attached here.
    campus_cb_file = fields.Binary("Course Breakdown", attachment=True, copy=False)
    campus_cb_filename = fields.Char("Course Breakdown Filename", copy=False)
    campus_contract_file = fields.Binary("Contract", attachment=True, copy=False)
    campus_contract_filename = fields.Char("Contract Filename", copy=False)
    campus_cb_final_file = fields.Binary("Final Course Breakdown", attachment=True, copy=False)
    campus_cb_final_filename = fields.Char("Final Course Breakdown Filename", copy=False)

    campus_slot_ids = fields.One2many(
        'campus.interview.slot', 'applicant_id', "Interview Slots", readonly=True)
    campus_interview1_id = fields.Many2one(
        'campus.interview.slot', "1st Interview", compute='_compute_campus_interviews', store=True)
    campus_interview2_id = fields.Many2one(
        'campus.interview.slot', "2nd Interview", compute='_compute_campus_interviews', store=True)
    campus_interview1_confirmed = fields.Boolean(
        related='campus_interview1_id.teacher_confirmed', string="Interview 1 Confirmed")
    campus_interview2_confirmed = fields.Boolean(
        related='campus_interview2_id.teacher_confirmed', string="Interview 2 Confirmed")

    # hr_applicant.stage_id's own domain (core hr_recruitment) is
    # "job_ids = False OR job_ids = job_id" - it always ORs in every
    # unscoped stage, for every job, by design. There is no way to make that
    # OR conditional on which job it is from within core's own domain, so a
    # Campus+ Teacher applicant would always see the 9 unscoped stages
    # (stock Odoo's 6 + this module's own original 4) alongside the 5
    # Campus+ ones in the top stage bar. This field is what the view uses
    # instead, purely for that one widget: exactly the 5 Campus+ stages for
    # a Campus+ Teacher applicant, and exactly core's own original formula
    # (reproduced, not bypassed) for every other job - so non-Campus+ jobs
    # see the identical stage bar they always have.
    campus_visible_stage_ids = fields.Many2many(
        'hr.recruitment.stage', compute='_compute_campus_visible_stage_ids',
        help="Stages offered in the top stage bar for this applicant's job.")

    campus_cb_ids = fields.One2many(
        'campus.course.breakdown', 'applicant_id', "Course Breakdown Submissions")
    campus_cb_state = fields.Selection([
        ('not_sent', 'Not Sent'),
        ('pending', 'Awaiting Submission'),
        ('submitted', 'Submitted'),
        ('modification_requested', 'Modification Requested'),
        ('approved', 'Approved'),
    ], string="Course Breakdown Status", compute='_compute_campus_cb_state', store=True,
        help="Independent of the Hiring Step: a candidate can have an approved Course "
             "Breakdown while the Contract is still awaiting signature, or vice versa.")

    campus_contract_state = fields.Selection([
        ('not_sent', 'Not Sent'),
        ('sent', 'Sent'),
        ('awaiting_signature', 'Awaiting Signature'),
        ('signed', 'Signed'),
        ('not_signed', 'Not Signed'),
    ], string="Contract Status", default='not_sent', required=True, copy=False, tracking=True)
    campus_in_contract_stage = fields.Boolean(
        "In Contrat Stage", compute='_compute_campus_in_contract_stage',
        help="Whether this application has actually reached the Contrat stage "
             "(only true once the Course Breakdown is approved). Marking a "
             "contract Signed or Not Signed is only available once this is true.")
    campus_in_cb_stage = fields.Boolean(
        "In Course Breakdown Stage", compute='_compute_campus_in_cb_stage',
        help="Whether this application is currently at the Course Breakdown "
             "stage. Used to surface the Course Breakdown section on the form "
             "even when the Hiring tab itself isn't open yet.")

    campus_shooting_ids = fields.One2many(
        'campus.shooting.session', 'applicant_id', "Shooting Sessions")
    campus_shooting_program_id = fields.Many2one(
        'campus.shooting.program', "Shooting Program", compute='_compute_campus_shooting_program_id',
        help="Created automatically once the contract is marked signed.")

    # ------------------------------------------------------------------
    # Process permissions
    # ------------------------------------------------------------------
    campus_process_id = fields.Many2one(
        'campus.process', "Campus+ Process", compute='_compute_campus_process_id',
        store=True, index=True,
        help="Which Campus+ Recruitment process (menu item) this application "
             "currently belongs to, derived from its stage. Drives the "
             "view-permission record rule.")
    campus_can_execute_process = fields.Boolean(
        compute='_compute_campus_process_access',
        help="Whether the current user may execute the current process, for buttons.")
    campus_can_validate_process = fields.Boolean(
        compute='_compute_campus_process_access',
        help="Whether the current user may validate the current process, for buttons.")

    # ------------------------------------------------------------------
    # ORM: keep job_id in step with campus_version_id
    # ------------------------------------------------------------------
    # hr.recruitment.stage.job_ids scopes the Campus+ stages (1er Interview,
    # 2ème Interview, Course Breakdown, Contrat, Shooting) to the Campus+
    # Teacher job position — that's what makes them show in the stage_id
    # statusbar instead of every recruitment pipeline in the database. That
    # only works if the applicant's own job_id is actually set. _campus_apply
    # _payload already does this for applications arriving through the public
    # API; these overrides make it true everywhere else too (manual creation,
    # scripts, imports) without requiring job_id to be picked by hand.
    @api.model_create_multi
    def create(self, vals_list):
        applicants = super().create(vals_list)
        for applicant in applicants:
            if applicant.campus_version_id and applicant.campus_version_id.job_id and not applicant.job_id:
                applicant.job_id = applicant.campus_version_id.job_id.id
        return applicants

    def write(self, vals):
        result = super().write(vals)
        if vals.get('campus_version_id'):
            version = self.env['campus.evaluation.version'].browse(vals['campus_version_id'])
            if version.job_id:
                self.filtered(lambda a: not a.job_id).write({'job_id': version.job_id.id})
        return result

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('campus_available_days', 'campus_teach_methods', 'campus_digital_tools')
    def _compute_multi_displays(self):
        for applicant in self:
            applicant.campus_available_days_display = self._join_display(applicant.campus_available_days)
            applicant.campus_teach_methods_display = self._join_display(applicant.campus_teach_methods)
            applicant.campus_digital_tools_display = self._join_display(applicant.campus_digital_tools)

    @api.model
    def _join_display(self, value):
        if not value:
            return ''
        if isinstance(value, (list, tuple)):
            return ' | '.join(str(item) for item in value)
        return str(value)

    @api.depends('campus_subject_ids', 'campus_score_ids')
    def _compute_campus_counts(self):
        subject_data = self.env['campus.application.subject']._read_group(
            [('applicant_id', 'in', self.ids)], ['applicant_id'], ['__count'])
        subject_map = {applicant.id: count for applicant, count in subject_data}
        score_data = self.env['campus.application.score']._read_group(
            [('applicant_id', 'in', self.ids)], ['applicant_id'], ['__count'])
        score_map = {applicant.id: count for applicant, count in score_data}
        for applicant in self:
            applicant.campus_subject_count = subject_map.get(applicant.id, 0)
            applicant.campus_score_count = score_map.get(applicant.id, 0)

    @api.depends('campus_subject_ids.is_accepted', 'campus_subject_ids.subject_id')
    def _compute_accepted_subjects(self):
        for applicant in self:
            applicant.campus_accepted_subject_ids = applicant.campus_subject_ids.filtered(
                lambda line: line.is_accepted and line.subject_id).mapped('subject_id')

    @api.depends('campus_slot_ids.round', 'campus_slot_ids.state')
    def _compute_campus_interviews(self):
        for applicant in self:
            slots = applicant.campus_slot_ids.filtered(lambda s: s.state != 'cancelled')
            applicant.campus_interview1_id = slots.filtered(lambda s: s.round == '1')[:1]
            applicant.campus_interview2_id = slots.filtered(lambda s: s.round == '2')[:1]

    @api.depends('job_id')
    def _compute_campus_visible_stage_ids(self):
        Stage = self.env['hr.recruitment.stage']
        campus_job = self.env.ref('campus_teacher_management.job_campus_teacher', raise_if_not_found=False)
        for applicant in self:
            if campus_job and applicant.job_id == campus_job:
                applicant.campus_visible_stage_ids = Stage.search([('job_ids', '=', campus_job.id)])
            else:
                # Reproduces core hr_applicant.stage_id's own domain exactly,
                # so every other job's stage bar is unaffected.
                applicant.campus_visible_stage_ids = Stage.search(
                    ['|', ('job_ids', '=', False), ('job_ids', '=', applicant.job_id.id)])

    @api.depends('campus_cb_ids.state', 'campus_hiring_state')
    def _compute_campus_cb_state(self):
        # A read_group keyed on id:max rather than relying on the cached
        # campus_cb_ids recordset's implicit order — a freshly created line
        # is not guaranteed to already be recomputed into that ordering within
        # the same transaction, while the max id always identifies the latest.
        latest_data = self.env['campus.course.breakdown']._read_group(
            [('applicant_id', 'in', self.ids)], ['applicant_id'], ['id:max'])
        latest_ids = {applicant.id: max_id for applicant, max_id in latest_data if max_id}
        latest_lines = self.env['campus.course.breakdown'].browse(latest_ids.values())
        state_by_applicant = {line.applicant_id.id: line.state for line in latest_lines}

        for applicant in self:
            state = state_by_applicant.get(applicant.id)
            if state:
                applicant.campus_cb_state = state
            elif applicant.campus_hiring_state in (
                    'meeting_2', 'interview2_completed', 'subjects_selected', 'hired'):
                # The 2nd-interview email (which carries the blank CB template) has
                # gone out, but nothing has come back yet.
                applicant.campus_cb_state = 'pending'
            else:
                applicant.campus_cb_state = 'not_sent'

    def _compute_campus_shooting_program_id(self):
        Program = self.env['campus.shooting.program']
        for applicant in self:
            applicant.campus_shooting_program_id = Program.search(
                [('applicant_id', '=', applicant.id)], limit=1)

    @api.depends('stage_id')
    def _compute_campus_in_contract_stage(self):
        contract_stage = self.env.ref('campus_teacher_management.stage_contract', raise_if_not_found=False)
        for applicant in self:
            applicant.campus_in_contract_stage = bool(contract_stage) and applicant.stage_id == contract_stage

    @api.depends('stage_id')
    def _compute_campus_in_cb_stage(self):
        cb_stage = self.env.ref('campus_teacher_management.stage_course_breakdown', raise_if_not_found=False)
        for applicant in self:
            applicant.campus_in_cb_stage = bool(cb_stage) and applicant.stage_id == cb_stage

    @api.depends('stage_id', 'campus_version_id')
    def _compute_campus_process_id(self):
        processes = self.env['campus.process'].search([])
        process_by_stage = {p.stage_id.id: p for p in processes if p.stage_id}
        candidatures = next((p for p in processes if p.code == 'candidatures'), self.env['campus.process'])
        for applicant in self:
            process = process_by_stage.get(applicant.stage_id.id)
            if not process and applicant.campus_version_id:
                process = candidatures
            applicant.campus_process_id = process or False

    def _compute_campus_process_access(self):
        Permission = self.env['campus.process.permission']
        for applicant in self:
            code = applicant.campus_process_id.code
            applicant.campus_can_execute_process = bool(code) and Permission._has_process_permission(code, 'execute')
            applicant.campus_can_validate_process = bool(code) and Permission._has_process_permission(code, 'validate')

    # ------------------------------------------------------------------
    # Answer payload: the vocabulary criteria point at
    # ------------------------------------------------------------------
    def _campus_answer_payload(self):
        """Answers keyed the way ``campus.criterion.source_key`` expects.

        Deliberately built from stored fields rather than the raw submission, so
        an application typed in by hand scores exactly like one that arrived
        through the API, and so correcting a field by hand changes the score.
        """
        self.ensure_one()
        catalogue_lines = self.campus_subject_ids.filtered(lambda line: line.source == 'catalogue')
        taught_selected = any(line.years_exp > 0 for line in catalogue_lines)
        any_experience = any(line.years_exp > 0 for line in self.campus_subject_ids)

        return {
            # identity
            'nameAr': self.campus_name_ar,
            'nameLat': self.campus_name_lat,
            'email': self.email_from,
            'phone': self.partner_phone,
            'dob': self.campus_dob and str(self.campus_dob) or '',
            'university': self.campus_university,
            'faculty': self.campus_faculty,
            'specialty': self.campus_specialty,
            'govInstitution': self.campus_gov_institution,
            # scored answers
            'rank': self.campus_scientific_rank,
            'yearsExp': self.campus_years_exp,
            'taughtHIS': self.campus_taught_his,
            'taughtCampus': self.campus_taught_campus,
            'digitalTools': self.campus_digital_tools or [],
            'teachMethods': self.campus_teach_methods or [],
            'availableDays': self.campus_available_days or [],
            'flippedKnowledge': self.campus_flipped_knowledge,
            'flippedDef': self.campus_flipped_def,
            'redesigned': self.campus_redesigned,
            'redesignDetail': self.campus_redesign_detail,
            'concerns': self.campus_concerns,
            'concernsHandled': self.campus_concerns_handled,
            'videoRec': self.campus_video_rec,
            'camConfidence': self.campus_camera_confidence,
            'referrals': self.campus_referrals,
            'referralsField': self.campus_referrals_field,
            'langAr': self.campus_lang_ar,
            'langEn': self.campus_lang_en,
            'langFr': self.campus_lang_fr,
            # derived — the web form has no direct question for these.
            # Re-point the criterion's source field if a better reading emerges.
            'taughtSelectedSubjects': 'oui' if taught_selected else 'non',
            'subjectExperienceProvided': 'oui' if any_experience else 'non',
            'selectedSubjects': [line.display_subject for line in catalogue_lines],
            'hisSubjects': [line.display_subject for line in self.campus_subject_ids
                            if line.source == 'free'],
        }

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    # payload key -> applicant field, for the plain scalar answers.
    _CAMPUS_SCALAR_MAP = {
        'nameAr': 'campus_name_ar',
        'nameLat': 'campus_name_lat',
        'university': 'campus_university',
        'faculty': 'campus_faculty',
        'specialty': 'campus_specialty',
        'govInstitution': 'campus_gov_institution',
        'rank': 'campus_scientific_rank',
        'taughtHIS': 'campus_taught_his',
        'taughtCampus': 'campus_taught_campus',
        'flippedKnowledge': 'campus_flipped_knowledge',
        'flippedDef': 'campus_flipped_def',
        'redesigned': 'campus_redesigned',
        'redesignDetail': 'campus_redesign_detail',
        'concerns': 'campus_concerns',
        'concernsHandled': 'campus_concerns_handled',
        'videoRec': 'campus_video_rec',
        'camConfidence': 'campus_camera_confidence',
        'referrals': 'campus_referrals',
        'referralsField': 'campus_referrals_field',
        'langAr': 'campus_lang_ar',
        'langEn': 'campus_lang_en',
        'langFr': 'campus_lang_fr',
        'phone2': 'campus_phone2',
        'wilaya': 'campus_wilaya',
        'commune': 'campus_commune',
    }
    _CAMPUS_LIST_MAP = {
        'digitalTools': 'campus_digital_tools',
        'teachMethods': 'campus_teach_methods',
        'availableDays': 'campus_available_days',
    }

    @api.model
    def _campus_payload_values(self, payload):
        """Translate a submitted payload into applicant field values."""
        values = {}
        for key, field_name in self._CAMPUS_SCALAR_MAP.items():
            if key in payload:
                values[field_name] = self._campus_clean_scalar(payload.get(key))

        for key, field_name in self._CAMPUS_LIST_MAP.items():
            if key in payload:
                values[field_name] = self._campus_clean_list(payload.get(key))

        # Standard Odoo fields rather than duplicates of them.
        if payload.get('nameLat') or payload.get('nameAr'):
            values['partner_name'] = self._campus_clean_scalar(
                payload.get('nameLat') or payload.get('nameAr'))
        if 'email' in payload:
            values['email_from'] = self._campus_clean_scalar(payload.get('email'))
        if 'phone' in payload:
            values['partner_phone'] = self._campus_clean_scalar(payload.get('phone'))

        if payload.get('dob'):
            try:
                values['campus_dob'] = fields.Date.to_date(payload['dob'])
            except (ValueError, TypeError):
                _logger.info("Ignoring unparseable date of birth %r.", payload.get('dob'))

        if 'yearsExp' in payload:
            try:
                values['campus_years_exp'] = max(float(payload['yearsExp'] or 0), 0.0)
            except (ValueError, TypeError):
                values['campus_years_exp'] = 0.0

        if payload.get('external_ref'):
            values['campus_external_ref'] = str(payload['external_ref'])[:64]
        return values

    @api.model
    def _campus_clean_scalar(self, value):
        """Normalize the form's 'no answer' markers to empty."""
        if value is None:
            return False
        if isinstance(value, (list, tuple)):
            return ' | '.join(str(item) for item in value) or False
        text = str(value).strip()
        return False if text in ('', '—', '-') else text

    @api.model
    def _campus_clean_list(self, value):
        return self.env['campus.scoring.engine']._as_list(value)

    @api.model
    def _campus_apply_payload(self, payload, applicant=None, version=None):
        """Create or update an application from a submitted payload.

        Shared by the public API and the re-process action, so both paths build
        the record identically.
        """
        values = self._campus_payload_values(payload)
        version = version or self._campus_resolve_version(payload)
        if version:
            values['campus_version_id'] = version.id
            # hr.applicant only computes a stage for an applicant that has a job
            # position. Without one the application is created with no stage and
            # never shows up in the recruitment pipeline, so carry the campaign's
            # job across and let Odoo's own compute pick the first stage.
            if version.job_id and not values.get('job_id'):
                values['job_id'] = version.job_id.id
        values.setdefault('campus_state', 'submitted')

        if applicant:
            applicant.write(values)
        else:
            applicant = self.create(values)

        applicant._campus_sync_subjects(payload)
        return applicant

    @api.model
    def _campus_resolve_version(self, payload):
        Version = self.env['campus.evaluation.version']
        if payload.get('version_id'):
            version = Version.browse(int(payload['version_id'])).exists()
            if version:
                return version
        return Version.search([('state', '=', 'published')], order='version desc, id desc', limit=1)

    def _campus_sync_subjects(self, payload):
        """Rebuild the subject lines from the payload, keeping accepted flags.

        Re-processing a submission must not silently revoke subjects a recruiter
        already granted, so acceptance is carried across by subject identity.
        """
        self.ensure_one()
        Subject = self.env['campus.subject']
        previously_accepted = {
            (line.subject_id.id, (line.subject_name or '').strip().lower())
            for line in self.campus_subject_ids if line.is_accepted
        }
        self.campus_subject_ids.unlink()

        lines = []
        for index, item in enumerate(payload.get('selectedSubjects') or []):
            values = self._campus_subject_line(item, Subject, source='catalogue')
            if values:
                values['sequence'] = index * 10
                lines.append(values)
        for index, item in enumerate(payload.get('hisSubjects') or []):
            values = self._campus_subject_line(item, Subject, source='free')
            if values:
                values['sequence'] = 500 + index * 10
                lines.append(values)

        for values in lines:
            key = (values.get('subject_id') or False,
                   (values.get('subject_name') or '').strip().lower())
            values['is_accepted'] = key in previously_accepted
            values['applicant_id'] = self.id
        if lines:
            self.env['campus.application.subject'].create(lines)
        return True

    @api.model
    def _campus_subject_line(self, item, Subject, source='catalogue'):
        """Accept both the structured and the legacy joined-string shapes."""
        subject = Subject.browse()
        name, years = '', 0.0

        if isinstance(item, dict):
            if item.get('id'):
                subject = Subject.search([('code', '=', str(item['id']))], limit=1) \
                    or Subject.browse(int(item['id'])).exists()
            name = (item.get('name') or '').strip()
            try:
                years = max(float(item.get('exp') or 0), 0.0)
            except (ValueError, TypeError):
                years = 0.0
        else:
            # Legacy shape: "Subject name (3 سنة)"
            text = str(item or '').strip()
            if not text:
                return None
            name = text
            if '(' in text:
                name = text.split('(')[0].strip()
                digits = ''.join(ch for ch in text.split('(')[-1] if ch.isdigit())
                years = float(digits) if digits else 0.0
            subject = Subject.search([('name', '=', name)], limit=1)

        if not subject and not name:
            return None
        return {
            'subject_id': subject.id if subject else False,
            'subject_name': False if subject else name,
            'source': 'catalogue' if subject else ('free' if source == 'free' else 'free'),
            'years_exp': years,
        }

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    @api.model
    def _campus_scoring_engine(self):
        """The engine named by configuration, or the built-in one.

        This indirection is the seam: a future module registers its own engine
        model and points the parameter at it, and no model, view, API route or
        dashboard changes.
        """
        name = self.env['ir.config_parameter'].sudo().get_param(
            'campus_teacher.scoring_engine', DEFAULT_ENGINE)
        if name not in self.env:
            _logger.warning(
                "Configured scoring engine %r is not installed; falling back to %s.",
                name, DEFAULT_ENGINE)
            name = DEFAULT_ENGINE
        return self.env[name]

    def action_campus_evaluate(self):
        """Score the selected applications and refresh their ranks."""
        self.env['campus.process.permission']._check_process_permission('candidatures', 'execute')
        candidates = self.filtered(lambda a: a.campus_version_id and not a.campus_locked)
        skipped = self - candidates
        if not candidates:
            if skipped:
                raise UserError(_(
                    "Nothing to evaluate: the selected applications are either locked "
                    "or have no evaluation version."))
            return False

        results = self._campus_scoring_engine().compute_scores(candidates)
        ScoreLine = self.env['campus.application.score']
        now = fields.Datetime.now()

        # Score lines are snapshots, so replacing them wholesale is both correct
        # and cheaper than diffing.
        ScoreLine.search([('applicant_id', 'in', candidates.ids)]).unlink()

        line_vals = []
        for applicant in candidates:
            result = results.get(applicant.id)
            if not result:
                continue
            for index, line in enumerate(result['lines']):
                criterion = line['criterion']
                line_vals.append({
                    'applicant_id': applicant.id,
                    'criterion_id': criterion.id,
                    'version_id': applicant.campus_version_id.id,
                    'sequence': index * 10,
                    'code_snapshot': criterion.code,
                    'name_snapshot': criterion.name,
                    'raw_value': line['raw_value'],
                    'raw_score': line['raw_score'],
                    'max_score_snapshot': line['max_score'],
                    'normalized_score': line['normalized_score'],
                    'weight_snapshot': line['weight'],
                    'weighted_score': line['weighted_score'],
                })
            applicant.write({
                'campus_final_score': result['final_score'],
                'campus_state': 'evaluated',
                'campus_evaluation_date': now,
                'campus_engine_version': result['engine_version'],
                'campus_weighting_method': result['weighting_method'],
            })
        if line_vals:
            ScoreLine.create(line_vals)

        candidates.mapped('campus_version_id')._campus_recompute_ranks()
        return True

    def action_campus_lock(self):
        self.env['campus.process.permission']._check_process_permission('candidatures', 'validate')
        self.write({'campus_locked': True, 'campus_state': 'locked'})
        return True

    def action_campus_unlock(self):
        self.env['campus.process.permission']._check_process_permission('candidatures', 'validate')
        self.write({'campus_locked': False})
        self.filtered(lambda a: a.campus_state == 'locked').write({'campus_state': 'evaluated'})
        return True

    # ------------------------------------------------------------------
    # Subject assignment
    # ------------------------------------------------------------------
    def action_campus_accept_all_subjects(self):
        for applicant in self:
            applicant.campus_subject_ids.filtered('is_wished').write({'is_accepted': True})
        return True

    # ------------------------------------------------------------------
    # Hiring funnel
    # ------------------------------------------------------------------
    # Which step each action may run from. Enforced rather than merely hidden in
    # the view, so a mistaken call from a server action or a script cannot skip
    # a document or send a contract twice.
    _CAMPUS_STEP_FROM = {
        'action_campus_select': ('not_selected',),
        'action_campus_send_documents': ('meeting_1',),
        'action_campus_record_acceptance': ('docs_sent',),
        'action_campus_send_final': ('docs_accepted',),
        # 'subjects_selected' added so the current Campus+ workflow (interview 1/2
        # + Course Breakdown + Contract + subject selection) can reach Hire without
        # going through the original docs_sent/docs_accepted/final_sent path.
        'action_campus_hire': ('meeting_2', 'final_sent', 'subjects_selected'),
        # Phase 2 — 1st/2nd interview + Course Breakdown + Contract + subjects.
        'action_campus_mark_interview1_completed': ('meeting_1',),
        'action_campus_mark_interview2_completed': ('meeting_2',),
        'action_campus_mark_subjects_selected': ('interview2_completed',),
    }

    def _campus_check_step(self, action):
        allowed = self._CAMPUS_STEP_FROM[action]
        for applicant in self:
            if applicant.campus_hiring_state not in allowed:
                raise UserError(_(
                    "%(name)s is at step '%(current)s', so this cannot be done yet.\n\n"
                    "Expected: %(expected)s.",
                    name=applicant.display_name,
                    current=dict(self._fields['campus_hiring_state'].selection)
                        .get(applicant.campus_hiring_state),
                    expected=", ".join(
                        dict(self._fields['campus_hiring_state'].selection)[step]
                        for step in allowed),
                ))

    def _campus_send_template(self, xmlid, attachments=()):
        """Render a template and queue it, carrying the uploaded files.

        Attachments are built from the binary fields at send time, so the mail
        always carries the document currently on the record rather than a copy
        taken when the template was written.
        """
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            raise UserError(_("The email template %s is missing. Reinstall the module.", xmlid))
        if not self.email_from:
            raise UserError(_("%s has no email address to write to.", self.display_name))

        attachment_ids = []
        for name, content in attachments:
            attachment_ids.append(self.env['ir.attachment'].create({
                'name': name,
                'datas': content,
                'res_model': 'hr.applicant',
                'res_id': self.id,
                'type': 'binary',
            }).id)

        template.send_mail(
            self.id,
            email_values={'attachment_ids': [(6, 0, attachment_ids)]} if attachment_ids else None,
            force_send=False,
        )
        return True

    def action_campus_select(self):
        """Accept the candidate and offer them the available first-meeting times."""
        self._campus_check_step('action_campus_select')
        Slot = self.env['campus.interview.slot']
        if not Slot._free_slots(1):
            raise UserError(_(
                "There are no free first-meeting slots to offer.\n\n"
                "Create some under Scheduling > Available Slots first — the email "
                "lists them, so sending now would ask the candidate to pick from "
                "an empty list."))
        for applicant in self:
            applicant._campus_send_template(
                'campus_teacher_management.mail_template_campus_selected')
            applicant.campus_hiring_state = 'invited'
            applicant.message_post(body=_(
                "Selected. Acceptance sent with the available first-meeting times."))
        return True

    def action_campus_schedule(self):
        """Open the wizard that records the time the candidate replied with."""
        self.ensure_one()
        round_number = '2' if self.campus_hiring_state in ('docs_accepted', 'final_sent') else '1'
        return {
            'type': 'ir.actions.act_window',
            'name': _("Record the chosen time"),
            'res_model': 'campus.schedule.interview',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_applicant_id': self.id,
                'default_round': round_number,
            },
        }

    def action_campus_send_documents(self):
        """Email the Course Breakdown and the contract."""
        self._campus_check_step('action_campus_send_documents')
        for applicant in self:
            missing = []
            if not applicant.campus_cb_file:
                missing.append(_("Course Breakdown"))
            if not applicant.campus_contract_file:
                missing.append(_("Contract"))
            if missing:
                raise UserError(_(
                    "Attach the %s on the Hiring tab before sending — the email "
                    "carries these files, and would go out empty.",
                    " and the ".join(missing)))

            applicant._campus_send_template(
                'campus_teacher_management.mail_template_campus_documents',
                attachments=[
                    (applicant.campus_cb_filename or 'course-breakdown.pdf',
                     applicant.campus_cb_file),
                    (applicant.campus_contract_filename or 'contract.pdf',
                     applicant.campus_contract_file),
                ])
            applicant.campus_hiring_state = 'docs_sent'
            applicant.message_post(body=_("Course Breakdown and contract sent."))
        return True

    def action_campus_record_acceptance(self):
        """The candidate accepted by email; the recruiter records it here."""
        self._campus_check_step('action_campus_record_acceptance')
        for applicant in self:
            applicant.campus_hiring_state = 'docs_accepted'
            applicant.message_post(body=_(
                "Candidate accepted the Course Breakdown and contract by email."))
        return True

    def action_campus_send_final(self):
        """Email the final Course Breakdown and offer second-meeting times."""
        self._campus_check_step('action_campus_send_final')
        Slot = self.env['campus.interview.slot']
        if not Slot._free_slots(2):
            raise UserError(_(
                "There are no free second-meeting slots to offer. Create some under "
                "Scheduling > Available Slots first."))
        for applicant in self:
            if not applicant.campus_cb_final_file:
                raise UserError(_(
                    "Attach the final Course Breakdown on the Hiring tab before sending."))
            applicant._campus_send_template(
                'campus_teacher_management.mail_template_campus_final',
                attachments=[(applicant.campus_cb_final_filename or 'course-breakdown-final.pdf',
                              applicant.campus_cb_final_file)])
            applicant.campus_hiring_state = 'final_sent'
            applicant.message_post(body=_(
                "Final Course Breakdown sent with the available second-meeting times."))
        return True

    def action_campus_hire(self):
        """Create the employee. Reuses Odoo's own hire action."""
        self._campus_check_step('action_campus_hire')
        self.ensure_one()
        action = self.create_employee_from_applicant()
        self.write({
            'campus_hiring_state': 'hired',
            'campus_hiring_date': fields.Datetime.now(),
        })
        self.message_post(body=_("Hired. Employee record created."))
        return action

    def action_campus_reset_hiring(self):
        """Put a candidate back to the start of the funnel.

        Documents and booked slots are left alone: releasing a slot removes a real
        calendar entry, which is a separate deliberate act.
        """
        for applicant in self:
            applicant.campus_hiring_state = 'not_selected'
            applicant.message_post(body=_("Hiring sequence reset."))
        return True

    # ------------------------------------------------------------------
    # Phase 2 — 1st/2nd interview, Course Breakdown, Contract, subjects
    # ------------------------------------------------------------------
    def _campus_check_manager(self, what):
        # Mirrors campus.course.breakdown._check_manager: some Phase 2 actions
        # are a higher trust tier than the ordinary read/write access Recruiters
        # already have on this model, so they need an explicit check rather than
        # relying on ir.model.access.csv, which cannot express "write is fine
        # except for this one field value."
        if not self.env.user.has_group('campus_teacher_management.group_campus_manager'):
            raise UserError(_("Only a Campus+ Manager can %s.", what))

    def _campus_book_direct_interview(self, round_number, start_datetime, duration=0.5, interviewer=None):
        """Book, or reschedule, this applicant's 1st/2nd interview directly.

        Unlike the pool-based flow (generate a week of slots, offer many, the
        candidate picks one), this creates or moves a single slot bound to this
        applicant from the start — the "recruiter picks one specific time"
        scheduling Stage 1/2 calls for. Still backed by campus.interview.slot, so
        both flows share one calendar, one booking model, one confirmation field.
        """
        self.ensure_one()
        round_str = str(round_number)
        existing = self.campus_slot_ids.filtered(
            lambda s: s.round == round_str and s.state == 'booked')[:1]
        if existing:
            existing._reschedule(start_datetime, duration)
            slot, is_reschedule = existing, True
        else:
            slot = self.env['campus.interview.slot'].create({
                'start_datetime': start_datetime,
                'duration': duration,
                'round': round_str,
                'interviewer_id': (interviewer or self.env.user).id,
            })
            slot._book(self)
            is_reschedule = False

        template = ('campus_teacher_management.mail_template_campus_interview1_invite'
                    if round_str == '1' else
                    'campus_teacher_management.mail_template_campus_interview2_invite')
        self._campus_send_template(template)

        if not is_reschedule:
            self.campus_hiring_state = 'meeting_1' if round_str == '1' else 'meeting_2'
            if round_str == '2' and self.campus_contract_state == 'not_sent':
                # The Contract PDF rides along in the same email as the 2nd
                # interview invite (mail_template_campus_interview2_invite's
                # static attachments), so its status moves together with it.
                self.campus_contract_state = 'sent'

        self.message_post(body=_(
            "%(which)s %(action)s for %(when)s.",
            which=_("1st interview") if round_str == '1' else _("2nd interview"),
            action=_("rescheduled") if is_reschedule else _("scheduled"),
            when=slot.display_name,
        ))
        return slot

    # --- UI glue: these only open a wizard or delegate to a one-line call on
    # an already-tested method; no new business logic lives here. ------------
    def _campus_open_schedule_wizard(self, round_number):
        self.ensure_one()
        round_str = str(round_number)
        existing = self.campus_slot_ids.filtered(
            lambda s: s.round == round_str and s.state == 'booked')[:1]
        return {
            'type': 'ir.actions.act_window',
            'name': _("Schedule 1st Interview") if round_str == '1' else _("Schedule 2nd Interview"),
            'res_model': 'campus.interview.direct.schedule',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_applicant_id': self.id,
                'default_round': round_str,
                'default_start_datetime': existing.start_datetime,
                'default_duration': existing.duration or (0.5 if round_str == '1' else 1.0),
            },
        }

    def action_campus_open_schedule_interview1(self):
        self.env['campus.process.permission']._check_process_permission('interview1', 'execute')
        return self._campus_open_schedule_wizard(1)

    def action_campus_open_schedule_interview2(self):
        self.env['campus.process.permission']._check_process_permission('interview2', 'execute')
        return self._campus_open_schedule_wizard(2)

    def action_campus_confirm_interview1(self):
        self.campus_interview1_id.action_confirm()
        return True

    def action_campus_confirm_interview2(self):
        self.campus_interview2_id.action_confirm()
        return True

    def _campus_advance_stage(self, xmlid):
        """Move to the named Campus+ stage, if it still exists.

        Looked up rather than hard-linked so a stage an administrator later
        renames or removes cannot turn a working action into a crash — the
        state change these actions record is the important part; the stage
        move is a best-effort convenience on top of it.
        """
        stage = self.env.ref(xmlid, raise_if_not_found=False)
        if stage:
            self.write({'stage_id': stage.id})
        else:
            _logger.warning("Campus+ stage %s not found; skipping automatic stage move.", xmlid)

    def action_campus_mark_interview1_completed(self):
        self.env['campus.process.permission']._check_process_permission('interview1', 'validate')
        self._campus_check_step('action_campus_mark_interview1_completed')
        self.write({'campus_hiring_state': 'interview1_completed'})
        # Posted before the stage moves: once it does, campus_process_id
        # becomes interview2, and a user only granted interview1 access would
        # otherwise get an AccessError writing this very confirmation message.
        self.message_post(body=_(
            "1st interview marked completed. Moved to the 2ème Interview stage."))
        self._campus_advance_stage('campus_teacher_management.stage_interview2')
        return True

    def action_campus_mark_interview2_completed(self):
        self.env['campus.process.permission']._check_process_permission('interview2', 'validate')
        self._campus_check_step('action_campus_mark_interview2_completed')
        self.write({'campus_hiring_state': 'interview2_completed'})
        self.message_post(body=_(
            "2nd interview marked completed. Moved to the Course Breakdown stage. "
            "Select the final subjects when ready."))
        self._campus_advance_stage('campus_teacher_management.stage_course_breakdown')
        return True

    def action_campus_mark_subjects_selected(self):
        """Record that subject assignment is done, once at least one is accepted."""
        self.env['campus.process.permission']._check_process_permission('course_breakdown', 'execute')
        self._campus_check_step('action_campus_mark_subjects_selected')
        for applicant in self:
            if not applicant.campus_accepted_subject_ids:
                raise UserError(_(
                    "Accept at least one subject on the Subjects tab before marking "
                    "subject selection complete."))
            applicant.campus_hiring_state = 'subjects_selected'
            applicant.message_post(body=_("Subject selection completed."))
        return True

    # --- Contract status --------------------------------------------------
    def action_campus_mark_contract_sent(self):
        self.env['campus.process.permission']._check_process_permission('contract', 'execute')
        self.write({'campus_contract_state': 'sent'})
        self.message_post(body=_("Contract marked as sent."))
        return True

    def action_campus_mark_contract_awaiting_signature(self):
        self.env['campus.process.permission']._check_process_permission('contract', 'execute')
        self.write({'campus_contract_state': 'awaiting_signature'})
        self.message_post(body=_("Contract marked as awaiting signature."))
        return True

    def _campus_check_contract_stage(self, what):
        # Course Breakdown approval is what actually moves an applicant into
        # Contrat (_campus_advance_stage in campus.course.breakdown.action_approve).
        # Signing/rejecting a contract before that has happened would let the
        # paperwork race ahead of an unapproved Course Breakdown.
        for applicant in self:
            if not applicant.campus_in_contract_stage:
                raise UserError(_(
                    "%(name)s has not reached the Contrat stage yet — approve the "
                    "Course Breakdown first before you can %(what)s.",
                    name=applicant.display_name, what=what))

    def action_campus_mark_contract_signed(self):
        self.env['campus.process.permission']._check_process_permission('contract', 'validate')
        self._campus_check_manager(_("mark a contract as signed"))
        self._campus_check_contract_stage(_("mark it signed"))
        for applicant in self:
            if not applicant.campus_contract_file:
                raise UserError(_(
                    "Attach the signed Contract PDF on the Hiring tab before marking "
                    "it signed."))
            applicant.campus_contract_state = 'signed'
            applicant.message_post(body=_("Contract signed. Moved to the Shooting stage."))
            applicant._campus_advance_stage('campus_teacher_management.stage_shooting')
            self.env['campus.shooting.program']._get_or_create_for_applicant(applicant)
        return True

    def action_campus_mark_contract_not_signed(self):
        self.env['campus.process.permission']._check_process_permission('contract', 'validate')
        self._campus_check_manager(_("mark a contract as not signed"))
        self._campus_check_contract_stage(_("mark it not signed"))
        self.write({'campus_contract_state': 'not_signed'})
        self.message_post(body=_("Contract marked as not signed."))
        return True

    # --- Course Breakdown: thin wrappers so the phase-specific list can act
    # on "the current submission" without the recruiter opening it first. ---
    def _campus_latest_cb(self):
        self.ensure_one()
        return self.env['campus.course.breakdown'].search(
            [('applicant_id', '=', self.id)], order='id desc', limit=1)

    def action_campus_approve_latest_cb(self):
        for applicant in self:
            latest = applicant._campus_latest_cb()
            if not latest:
                raise UserError(_("No Course Breakdown submission to approve yet."))
            latest.action_approve()
        return True

    def action_campus_open_latest_cb(self):
        self.ensure_one()
        latest = self._campus_latest_cb()
        if not latest:
            raise UserError(_("No Course Breakdown submission yet."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Course Breakdown Submission"),
            'res_model': 'campus.course.breakdown',
            'res_id': latest.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def action_campus_view_scores(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Score Breakdown"),
            'res_model': 'campus.application.score',
            'view_mode': 'list,form',
            'domain': [('applicant_id', '=', self.id)],
        }

    def action_campus_view_submissions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Raw Submissions"),
            'res_model': 'campus.submission',
            'view_mode': 'list,form',
            'domain': [('applicant_id', '=', self.id)],
        }

    def action_campus_view_shooting_program(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Shooting Program"),
            'res_model': 'campus.shooting.program',
            'res_id': self.campus_shooting_program_id.id,
            'view_mode': 'form',
        }
