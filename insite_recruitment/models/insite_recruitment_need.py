from odoo import _, api, fields, models
from odoo.exceptions import UserError


class InsiteRecruitmentNeed(models.Model):
    """The starting point of the InSite pipeline: a vacant teaching position or
    a decreed hourly volume that requires a teacher. Owns the master pipeline
    state (NEED -> ... -> PUBLISHED) — a Need can have several Candidatures
    tried against it in sequence (internal check, then external candidates one
    at a time), and the pipeline position belongs to the recruitment effort as
    a whole, not to any one attempt. Each Candidature only tracks its own
    contact/response outcome (see insite.candidature).
    """

    _name = 'insite.recruitment.need'
    _description = 'InSite Recruitment Need'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    module_id = fields.Many2one(
        'campus.subject', "Module", required=True, ondelete='restrict', index=True)
    specialty = fields.Char("Required Specialty")
    hourly_volume = fields.Float("Hourly Volume", required=True)
    academic_period_id = fields.Many2one(
        'academic.period', "Academic Period", required=True, ondelete='restrict', index=True)
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
    ], string="Priority", default='normal', required=True)
    reason = fields.Text("Reason for Recruitment")

    state = fields.Selection([
        ('need', 'Need'),
        ('searching_internal', 'Searching Internal Teachers'),
        ('searching_external', 'Searching External Candidates'),
        ('candidate_selected', 'Candidate Selected'),
        ('awaiting_response', 'Awaiting Response'),
        ('accepted', 'Accepted'),
        ('meeting_scheduled', 'Meeting Scheduled'),
        ('meeting_completed', 'Meeting Completed'),
        ('contract', 'Contract'),
        ('signed', 'Signed'),
        ('integration', 'Integration'),
        ('integration_pending', 'Integration Pending'),
        ('module_assigned', 'Module Assigned'),
        ('module_preparation', 'Module Preparation'),
        ('validation', 'Validation'),
        ('publication', 'Publication'),
        ('publication_pending', 'Publication Pending'),
        ('published', 'Published'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed'),
    ], string="Status", default='need', required=True, tracking=True, copy=False, index=True)

    internal_teacher_id = fields.Many2one(
        'academic.person', "Internal Teacher", ondelete='set null', index='btree_not_null',
        help="Set once an internal teacher is selected for this Need.")
    candidature_ids = fields.One2many(
        'insite.candidature', 'need_id', "Candidatures",
        help="Every candidate ever tried against this Need, internal or external.")
    selected_candidature_id = fields.Many2one(
        'insite.candidature', "Selected Candidature", ondelete='set null', copy=False,
        index='btree_not_null')
    engagement_ids = fields.One2many('academic.engagement', 'need_id', "Engagements")
    contract_ids = fields.One2many('insite.contract', 'need_id', "Contracts")
    module_sheet_ids = fields.One2many(
        'insite.module.sheet', compute='_compute_module_sheet_ids', string="Module Sheets")

    integration_pending = fields.Boolean("Integration Pending", copy=False)
    publication_pending = fields.Boolean("Publication Pending", copy=False)

    @api.depends('module_id', 'academic_period_id')
    def _compute_display_name(self):
        for need in self:
            need.display_name = _(
                "%(module)s (%(period)s)",
                module=need.module_id.display_name, period=need.academic_period_id.display_name,
            )

    def _compute_module_sheet_ids(self):
        for need in self:
            need.module_sheet_ids = self.env['insite.module.sheet'].search(
                [('engagement_id.need_id', '=', need.id)])

    # ------------------------------------------------------------------
    # Phase 1 — internal teacher search (never contacts external candidates
    # while an appropriate internal teacher exists — that's a human judgment
    # call on the search results, not something this method decides for them).
    # ------------------------------------------------------------------
    def action_search_internal(self):
        self.env['campus.process.permission']._check_process_permission('insite_needs', 'execute')
        self.write({'state': 'searching_internal'})
        return True

    def _internal_teacher_candidates(self):
        """Read-only lookup: teachers explicitly marked internal
        (academic.person.is_internal_teacher — an administrator-set flag, never
        inferred from history), for a human to review and add to the
        Candidates tab (as a source='internal' Candidature) if suitable."""
        self.ensure_one()
        return self.env['academic.person'].search([('is_internal_teacher', '=', 'internal')])

    def action_no_internal_teacher_found(self):
        self.env['campus.process.permission']._check_process_permission('insite_needs', 'execute')
        if self.state != 'searching_internal':
            raise UserError(_("Search internal teachers first."))
        self.write({'state': 'searching_external'})
        return True

    # ------------------------------------------------------------------
    # Phase 2 — external candidates: explicit, reproducible ranking (see
    # insite.candidature._compute_rank() for the factors), never an opaque
    # weighted score.
    # ------------------------------------------------------------------
    def action_rank_external_candidates(self):
        self.env['campus.process.permission']._check_process_permission('insite_needs', 'execute')
        self.ensure_one()
        if self.state != 'searching_external':
            raise UserError(_("Confirm no internal teacher was found before ranking external candidates."))
        candidates = self.candidature_ids.filtered(lambda c: c.source == 'external')
        candidates._rank_candidates()
        return True

    def action_select_candidate(self, candidature):
        self.env['campus.process.permission']._check_process_permission('insite_needs', 'execute')
        self.ensure_one()
        if candidature.need_id != self:
            raise UserError(_("%s is not a candidature for this Need.", candidature.display_name))
        if candidature.state not in ('prospect', 'declined'):
            raise UserError(_(
                "%(candidature)s is at status '%(state)s' and cannot be selected.",
                candidature=candidature.display_name, state=candidature.state))
        self.write({'selected_candidature_id': candidature.id, 'state': 'candidate_selected'})
        return True

    def action_contact_candidate(self):
        self.env['campus.process.permission']._check_process_permission('insite_needs', 'execute')
        self.ensure_one()
        if self.state != 'candidate_selected' or not self.selected_candidature_id:
            raise UserError(_("Select a candidate before contacting them."))
        self.selected_candidature_id.action_contact()
        self.write({'state': 'awaiting_response'})
        return True

    def _on_candidate_accepted(self, candidature):
        """Called by insite.candidature.action_record_response() — matches the
        existing pattern where a related record pushes the owning record's
        state forward (see insite.contract.action_sign() -> candidature.state)."""
        self.ensure_one()
        self.write({'state': 'accepted'})

    def _on_candidate_declined(self, candidature):
        """Never auto-selects the next candidate — reverts to whichever
        searching phase the declined candidature came from, so a human picks
        who's next, exactly as required."""
        self.ensure_one()
        self.write({
            'selected_candidature_id': False,
            'state': 'searching_internal' if candidature.source == 'internal' else 'searching_external',
        })

    def _on_meeting_scheduled(self):
        """Called by insite.meeting.schedule.wizard once Pédagogie has
        scheduled (not merely proposed) a real meeting — same
        related-record-pushes-state pattern as _on_candidate_accepted."""
        self.ensure_one()
        self.write({'state': 'meeting_scheduled'})

    def action_mark_meeting_completed(self):
        """The meeting itself is manual (a phone/in-person conversation) —
        the system only records that it happened, same as Signature."""
        self.env['campus.process.permission']._check_process_permission('insite_needs', 'validate')
        self.ensure_one()
        if self.state != 'meeting_scheduled':
            raise UserError(_("No meeting is scheduled for this Need yet."))
        self.write({'state': 'meeting_completed'})
        return True

    # ------------------------------------------------------------------
    # Phase 3 — contract
    # ------------------------------------------------------------------
    def action_start_contract(self):
        self.env['campus.process.permission']._check_process_permission('insite_contracts', 'execute')
        self.ensure_one()
        if self.state != 'meeting_completed':
            raise UserError(_("The meeting with the candidate must be completed before starting the contract."))
        contract = self.env['insite.contract'].create({
            'need_id': self.id,
            'person_id': self.selected_candidature_id.person_id.id,
            'candidature_id': self.selected_candidature_id.id,
        })
        self.write({'state': 'contract'})
        return contract

    def _on_contract_signed(self):
        self.ensure_one()
        self.write({'state': 'signed'})
        self._run_integration()

    def _on_contract_rejected(self):
        """Contract rejected -> recruitment does not continue to integration;
        stopping here is deliberate, matching 'recruitment stops / candidate
        replacement handled manually' — no automatic next step."""
        self.ensure_one()
        self.write({'state': 'cancelled'})

    # ------------------------------------------------------------------
    # Phase 4 — integration (stub service; see services/integration.py).
    # Never advances to module_assigned unless provisioning actually
    # succeeded — an unconfigured service lands on integration_pending and
    # stays there until a manager marks it done by hand.
    # ------------------------------------------------------------------
    def _run_integration(self):
        self.ensure_one()
        self.write({'state': 'integration'})
        from ..services.integration import InsiteAccountProvisioningService
        result = InsiteAccountProvisioningService().provision(self.selected_candidature_id.person_id)
        if result.success:
            self.write({'state': 'module_assigned', 'integration_pending': False})
        else:
            self.write({'state': 'integration_pending', 'integration_pending': True})

    def action_mark_integration_done(self):
        """Manual override: staff completed account/email/badge provisioning
        by hand (no real Google Workspace integration exists yet — see
        services/integration.py). The system records the result; a human
        performed the actual work, same as Signature."""
        self.env['campus.process.permission']._check_process_permission('insite_needs', 'validate')
        self.ensure_one()
        if self.state != 'integration_pending':
            raise UserError(_("Integration is not pending for this Need."))
        self.write({'state': 'module_assigned', 'integration_pending': False})
        return True

    # ------------------------------------------------------------------
    # Phase 5 — module assignment / preparation rollup. The fine-grained
    # module content workflow lives on insite.module.sheet; this just tracks
    # "an Engagement now exists for this Need."
    # ------------------------------------------------------------------
    def action_assign_module(self):
        self.env['campus.process.permission']._check_process_permission('insite_engagements', 'execute')
        self.ensure_one()
        if self.state != 'module_assigned':
            raise UserError(_("Integration must be completed before assigning a module."))
        engagement = self.env['academic.engagement'].create({
            'person_id': self.selected_candidature_id.person_id.id,
            'module_id': self.module_id.id,
            'academic_period_id': self.academic_period_id.id,
            'need_id': self.id,
        })
        self.env['insite.module.sheet'].create({'engagement_id': engagement.id})
        self.write({'state': 'module_preparation'})
        return engagement

    def _on_module_validated(self):
        self.ensure_one()
        self.write({'state': 'publication'})
        self._run_publication()

    def _run_publication(self):
        self.ensure_one()
        from ..services.publication import InsitePublicationService
        sheet = self.module_sheet_ids.filtered(lambda s: s.state == 'validated')[:1]
        result = InsitePublicationService().publish(sheet)
        if result.success:
            self.write({'state': 'published', 'publication_pending': False})
            sheet.write({'state': 'published'})
        else:
            self.write({'state': 'publication_pending', 'publication_pending': True})

    def action_mark_publication_done(self):
        self.env['campus.process.permission']._check_process_permission('insite_needs', 'validate')
        self.ensure_one()
        if self.state != 'publication_pending':
            raise UserError(_("Publication is not pending for this Need."))
        sheet = self.module_sheet_ids.filtered(lambda s: s.state == 'validated')[:1]
        sheet.write({'state': 'published'})
        self.write({'state': 'published', 'publication_pending': False})
        return True

    def action_cancel(self):
        self.env['campus.process.permission']._check_process_permission('insite_needs', 'validate')
        self.write({'state': 'cancelled'})
        return True
