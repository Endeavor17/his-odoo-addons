from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CampusCourseBreakdown(models.Model):
    """One Course Breakdown submission from a candidate, kept forever.

    Every submission is a new row rather than an update to a single field, so a
    requested revision never destroys the file or the review notes that came
    before it — the full history of what was sent, when, and by whom stays on
    the record. ``campus_cb_state`` on the applicant always reflects the latest
    row here; nothing about an older row ever changes once created.
    """

    _name = 'campus.course.breakdown'
    _description = 'Campus+ Course Breakdown Submission'
    _order = 'applicant_id, create_date desc, id desc'

    applicant_id = fields.Many2one(
        'hr.applicant', "Application", required=True, ondelete='cascade', index=True)

    file = fields.Binary("Course Breakdown", attachment=True, required=True)
    filename = fields.Char("Filename")

    state = fields.Selection([
        ('submitted', 'Submitted'),
        ('modification_requested', 'Modification Requested'),
        ('approved', 'Approved'),
    ], string="Status", default='submitted', required=True, index=True, copy=False)

    review_notes = fields.Text(
        "Review Notes",
        help="What needs to change. Sent to the candidate when a revision is requested.")
    reviewed_by = fields.Many2one('res.users', "Reviewed By", readonly=True, copy=False)
    reviewed_date = fields.Datetime("Reviewed On", readonly=True, copy=False)

    campus_can_execute_process = fields.Boolean(compute='_compute_campus_process_access')
    campus_can_validate_process = fields.Boolean(compute='_compute_campus_process_access')

    def _compute_campus_process_access(self):
        Permission = self.env['campus.process.permission']
        can_execute = Permission._has_process_permission('course_breakdown', 'execute')
        can_validate = Permission._has_process_permission('course_breakdown', 'validate')
        for line in self:
            line.campus_can_execute_process = can_execute
            line.campus_can_validate_process = can_validate

    @api.model_create_multi
    def create(self, vals_list):
        self.env['campus.process.permission']._check_process_permission('course_breakdown', 'execute')
        return super().create(vals_list)

    @api.depends('applicant_id', 'create_date', 'state')
    def _compute_display_name(self):
        for line in self:
            when = line.create_date and fields.Datetime.context_timestamp(
                line, line.create_date).strftime('%d %b %Y') or _("New")
            line.display_name = f"{line.applicant_id.display_name} — {when}"

    def _check_manager(self, what):
        # ir.model.access.csv grants Recruiters write access to this model so
        # they can upload submissions and request revisions; final approval is
        # a higher trust tier (same as Evaluate/Lock elsewhere in this module),
        # so it needs an explicit check rather than relying on model-level access.
        if not self.env.user.has_group('campus_teacher_management.group_campus_manager'):
            raise UserError(_("Only a Campus+ Manager can %s.", what))

    def _campus_send_own_template(self, xmlid):
        """Render a template against THIS submission, not the applicant.

        A candidate can have several submissions over time, so "the review
        notes"/"which version was approved" only means something if the email
        is rendered against this specific row — routing through
        hr.applicant._campus_send_template would leave the template unable to
        tell which one just happened. Mirrors that method's own checks.
        """
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            raise UserError(_("The email template %s is missing. Reinstall the module.", xmlid))
        if not self.applicant_id.email_from:
            raise UserError(_("%s has no email address to write to.", self.applicant_id.display_name))
        template.send_mail(self.id, force_send=False)
        return True

    def action_approve(self):
        self.env['campus.process.permission']._check_process_permission('course_breakdown', 'validate')
        self._check_manager(_("approve a Course Breakdown"))
        for line in self:
            if line.state == 'approved':
                continue
            line.write({
                'state': 'approved',
                'reviewed_by': self.env.user.id,
                'reviewed_date': fields.Datetime.now(),
            })
            line._campus_send_own_template('campus_teacher_management.mail_template_campus_cb_approved')
            line.applicant_id.message_post(body=_(
                "Course Breakdown submitted on %s approved.",
                fields.Datetime.context_timestamp(line, line.create_date).strftime('%d %b %Y')))
            # Only advance if this approval is still the CURRENT state - guards
            # against a stale/older line being approved after a newer
            # resubmission already moved the candidate on.
            if line.applicant_id.campus_cb_state == 'approved':
                line.applicant_id.message_post(body=_("Moved to the Contrat stage."))
                line.applicant_id._campus_advance_stage('campus_teacher_management.stage_contract')
        return True

    def action_request_modification(self):
        self.env['campus.process.permission']._check_process_permission('course_breakdown', 'execute')
        for line in self:
            if not (line.review_notes or '').strip():
                raise UserError(_(
                    "Explain what needs to change before requesting a revision — "
                    "the note is what the candidate receives."))
            line.write({
                'state': 'modification_requested',
                'reviewed_by': self.env.user.id,
                'reviewed_date': fields.Datetime.now(),
            })
            line._campus_send_own_template('campus_teacher_management.mail_template_campus_cb_modification')
            line.applicant_id.message_post(body=_(
                "Modification requested on the Course Breakdown submitted %s.",
                fields.Datetime.context_timestamp(line, line.create_date).strftime('%d %b %Y')))
        return True
