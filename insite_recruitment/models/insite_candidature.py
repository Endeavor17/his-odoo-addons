from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class InsiteCandidature(models.Model):
    """One person's attempt against one insite.recruitment.need — internal or
    external. Deliberately not hr.applicant, and deliberately simple: the
    master pipeline position lives on the Need (a Need can try several
    Candidatures in sequence), so this model only tracks THIS person's own
    contact/response outcome, never a second copy of the Need's own state.
    """

    _name = 'insite.candidature'
    _description = 'InSite Candidature'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    person_id = fields.Many2one(
        'academic.person', "Person", required=True, ondelete='restrict', index=True, tracking=True)
    need_id = fields.Many2one(
        'insite.recruitment.need', "Recruitment Need", ondelete='set null', index='btree_not_null',
        help="Which Need this candidature is being considered for. Nullable: a "
             "submission-created candidature may not have one yet if the public "
             "payload didn't specify it — a human links it from here.")
    source = fields.Selection([
        ('internal', 'Internal Teacher'),
        ('external', 'External Candidate'),
    ], string="Source", compute='_compute_source', store=True,
        help="Derived from person_id.is_internal_teacher — never manually "
             "set. A Candidature cannot be created for an unclassified "
             "Person in the first place (see _check_person_classified).")

    # Display-only, read through the Person relation — not a duplicate of
    # the identity data, just a convenience so the candidature form doesn't
    # need a click-through to show who this is. Never stored, never edited
    # here: editing identity happens on academic.person itself.
    person_matricule = fields.Char(related='person_id.matricule_institutionnel', readonly=True)
    person_email_institutional = fields.Char(related='person_id.email_institutional', readonly=True)
    person_phone = fields.Char(related='person_id.phone', readonly=True)
    person_academic_rank = fields.Char(related='person_id.academic_rank', readonly=True)
    person_specialty = fields.Char(related='person_id.specialty', readonly=True)

    state = fields.Selection([
        ('prospect', 'Prospect'),
        ('contacted', 'Contacted'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('superseded', 'Superseded'),
    ], string="Status", default='prospect', required=True, tracking=True, copy=False, index=True)
    contacted_date = fields.Datetime("Contacted On", readonly=True, copy=False)
    reminder_sent = fields.Boolean("48h Reminder Sent", copy=False)

    # -- Explainable external ranking (never an opaque weighted score) ------
    insite_rank = fields.Integer("Rank", readonly=True, copy=False)
    rank_explanation = fields.Text("Rank Explanation", readonly=True, copy=False)

    # -- InSite-specific recruitment questions --------------------------
    motivation = fields.Text("Motivation")
    availability = fields.Char("Availability")
    teaching_experience = fields.Text("Teaching Experience")

    meeting_event_id = fields.Many2one(
        'calendar.event', "Meeting", ondelete='set null', index='btree_not_null', copy=False,
        help="Set by Schedule Meeting — the real, Pédagogie-scheduled meeting. "
             "Reschedule Meeting edits this same record; a second one is never created.")

    raw_submission_ids = fields.One2many(
        'insite.submission', 'candidature_id', "Raw Submissions")
    engagement_ids = fields.One2many(
        'academic.engagement', 'insite_candidature_id', "Engagements")
    contract_ids = fields.One2many(
        'insite.contract', 'candidature_id', "Contracts")

    # Display-only projections of the most recent contract/engagement's own
    # state, so the candidature form can show "where things actually stand"
    # without a click-through — not a duplicate of contract_ids/engagement_ids,
    # just their latest row's label.
    latest_contract_state = fields.Char("Contract Status", compute='_compute_latest_relation_states')
    latest_engagement_state = fields.Char("Engagement Status", compute='_compute_latest_relation_states')

    @api.depends('contract_ids.state', 'contract_ids.create_date',
                 'engagement_ids.state', 'engagement_ids.create_date')
    def _compute_latest_relation_states(self):
        for candidature in self:
            contract = candidature.contract_ids.sorted('create_date', reverse=True)[:1]
            candidature.latest_contract_state = (
                dict(contract._fields['state'].selection).get(contract.state) if contract else False)
            engagement = candidature.engagement_ids.sorted('create_date', reverse=True)[:1]
            candidature.latest_engagement_state = (
                dict(engagement._fields['state'].selection).get(engagement.state) if engagement else False)

    @api.depends('person_id', 'state')
    def _compute_display_name(self):
        for candidature in self:
            candidature.display_name = _(
                "%(person)s — %(state)s",
                person=candidature.person_id.display_name,
                state=dict(self._fields['state'].selection).get(candidature.state, candidature.state),
            )

    @api.depends('person_id.is_internal_teacher')
    def _compute_source(self):
        for candidature in self:
            candidature.source = candidature.person_id.is_internal_teacher or False

    @api.constrains('person_id')
    def _check_person_classified(self):
        for candidature in self:
            if candidature.person_id and not candidature.person_id.is_internal_teacher:
                raise ValidationError(_(
                    "%(person)s has not been classified as Internal or External yet. "
                    "Set this on the Person record before creating a Candidature for them.",
                    person=candidature.person_id.display_name))

    # ------------------------------------------------------------------
    # Explainable ranking — deterministic, factor-by-factor, never a single
    # opaque number. Each factor's contribution is fixed and documented here,
    # not derived from any configurable weighting table.
    # ------------------------------------------------------------------
    def _rank_candidates(self):
        """Rank self (a set of external candidatures for the same Need) and
        write insite_rank + rank_explanation on each. Ties broken by id, so
        the result is always reproducible."""
        scored = []
        for candidature in self:
            score, reasons = candidature._compute_rank_factors()
            scored.append((score, candidature.id, candidature, reasons))
        scored.sort(key=lambda row: (-row[0], row[1]))
        for position, (score, _id, candidature, reasons) in enumerate(scored, start=1):
            explanation = '; '.join(reasons) + f"; Total score: {score}."
            candidature.write({'insite_rank': position, 'rank_explanation': explanation})
        return True

    def _compute_rank_factors(self):
        """Returns (score, [reason strings]) for one candidature. Every point
        awarded is traceable to one named factor here — nothing hidden."""
        self.ensure_one()
        need = self.need_id
        person = self.person_id
        score = 0
        reasons = []

        specialty_match = bool(need and need.specialty and person.specialty and
                                need.specialty.strip().lower() == person.specialty.strip().lower())
        if specialty_match:
            score += 3
        reasons.append(_("Specialty match: %s (+%s)") % (_("Yes") if specialty_match else _("No"),
                                                           3 if specialty_match else 0))

        prior_history = bool(person.campus_applicant_id or person.engagement_ids)
        if prior_history:
            score += 2
        reasons.append(_("Prior institution history: %s (+%s)") % (
            _("Yes") if prior_history else _("No"), 2 if prior_history else 0))

        module_experience = bool(need and person.engagement_ids.filtered(
            lambda e: e.module_id == need.module_id))
        if module_experience:
            score += 2
        reasons.append(_("Experience with this exact module: %s (+%s)") % (
            _("Yes") if module_experience else _("No"), 2 if module_experience else 0))

        experience_provided = bool((self.teaching_experience or '').strip())
        if experience_provided:
            score += 1
        reasons.append(_("Teaching experience provided: %s (+%s)") % (
            _("Yes") if experience_provided else _("No"), 1 if experience_provided else 0))

        return score, reasons

    # ------------------------------------------------------------------
    # Contact / response — called by insite.recruitment.need's own actions
    # (action_contact_candidate), each independently permission-checked, same
    # defense-in-depth pattern the module already uses elsewhere (the
    # identity-match wizard checks even though its caller already did).
    # ------------------------------------------------------------------
    def action_select_this_candidate(self):
        """No-arg wrapper so this can be a plain view button — delegates to
        the Need's own action_select_candidate(), same permission check and
        state guard either way."""
        self.ensure_one()
        if not self.need_id:
            raise UserError(_("%s is not linked to a Recruitment Need yet.", self.display_name))
        return self.need_id.action_select_candidate(self)

    def action_contact(self):
        self.env['campus.process.permission']._check_process_permission('insite_candidatures', 'execute')
        template = self.env.ref('insite_recruitment.mail_template_insite_invitation', raise_if_not_found=False)
        for candidature in self:
            if candidature.state != 'prospect':
                raise UserError(_(
                    "%s is not a prospect, so it cannot be contacted.", candidature.display_name))
            candidature.write({'state': 'contacted', 'contacted_date': fields.Datetime.now(),
                                'reminder_sent': False})
            if template:
                template.send_mail(candidature.id, force_send=False)
            candidature.message_post(body=_("Candidate contacted. The phone call itself is manual — "
                                             "the system only records the outcome."))
        return True

    def action_mark_accepted(self):
        return self.action_record_response('accepted')

    def action_mark_declined(self):
        return self.action_record_response('declined')

    def action_record_response(self, response):
        self.env['campus.process.permission']._check_process_permission('insite_candidatures', 'execute')
        self.ensure_one()
        if self.state != 'contacted':
            raise UserError(_("%s has not been contacted yet.", self.display_name))
        if response not in ('accepted', 'declined'):
            raise UserError(_("Unknown response: %s", response))
        self.write({'state': response})
        self.message_post(body=_("Response recorded: %s.", response))
        if self.need_id:
            if response == 'accepted':
                self.need_id._on_candidate_accepted(self)
            else:
                self.need_id._on_candidate_declined(self)
        return True

    # ------------------------------------------------------------------
    # Meeting scheduling — entirely manual, Pédagogie-driven. No self-service
    # booking, no token, no public controller, no hardcoded datetime: the
    # wizard's fields are exactly what Pédagogie types in. Schedule and
    # Reschedule are deliberately separate entry points so a meeting can
    # never be silently double-booked or silently overwritten.
    # ------------------------------------------------------------------
    def action_schedule_meeting(self):
        self.ensure_one()
        if self.meeting_event_id:
            raise UserError(_(
                "A meeting is already scheduled for %s. Use 'Reschedule Meeting' to change it.",
                self.person_id.display_name))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Schedule Meeting"),
            'res_model': 'insite.meeting.schedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_candidature_id': self.id},
        }

    def action_reschedule_meeting(self):
        self.ensure_one()
        if not self.meeting_event_id:
            raise UserError(_(
                "No meeting is scheduled yet for %s — use 'Schedule Meeting' first.",
                self.person_id.display_name))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Reschedule Meeting"),
            'res_model': 'insite.meeting.schedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_candidature_id': self.id, 'reschedule': True},
        }

    # ------------------------------------------------------------------
    # 48h reminder — finds pending candidates, reminds Pédagogie, marks the
    # reminder sent (no duplicates). NEVER changes state or response: the
    # only writes this method ever performs are on reminder_sent and the
    # reminder activity itself — pinned down by a dedicated test.
    # ------------------------------------------------------------------
    @api.model
    def _cron_insite_reminder_check(self):
        deadline = fields.Datetime.now() - timedelta(hours=48)
        overdue = self.search([
            ('state', '=', 'contacted'),
            ('contacted_date', '<=', deadline),
            ('reminder_sent', '=', False),
        ])
        if not overdue:
            return
        template = self.env.ref('insite_recruitment.mail_template_insite_reminder', raise_if_not_found=False)
        validators = self.env['campus.process.permission'].sudo().search([
            ('process_id.code', '=', 'insite_needs'), ('can_validate', '=', True), ('active', '=', True),
        ]).mapped('user_id')
        for candidature in overdue:
            if template:
                template.send_mail(candidature.id, force_send=False)
            for user in validators:
                candidature.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=_("InSite: no response after 48h — %s", candidature.person_id.display_name),
                    note=_("Contacted on %s with no response yet. Decide whether to wait or "
                           "select another candidate — nothing advances automatically.",
                           candidature.contacted_date))
            candidature.reminder_sent = True
