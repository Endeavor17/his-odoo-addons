import json

from odoo import _, api, fields, models


class InsiteSubmission(models.Model):
    """The raw InSite payload exactly as received — mirrors campus.submission's
    shape and its core guarantee (never overwrite the original; reprocess
    rebuilds from ``payload``), plus the identity-matching trail campus.submission
    doesn't need: ``person_id`` and ``match_method``.
    """

    _name = 'insite.submission'
    _description = 'InSite Raw Submission'
    _order = 'create_date desc, id desc'
    _rec_name = 'reference'

    reference = fields.Char("Reference", required=True, index=True, copy=False)
    external_ref = fields.Char(
        "External Reference", index=True, copy=False,
        help="Idempotency key: a retry carrying a reference already seen returns "
             "the original record instead of creating a duplicate.")
    payload = fields.Json("Payload", help="The request body as received. Never edited.")
    payload_preview = fields.Text("Payload (readable)", compute='_compute_payload_preview')

    # Read-only projections of the same payload keys action_process() already
    # reads (matricule/firstName/lastName/nameAr/email/phone/motivation/
    # availability/teachingExperience) — not a second copy of the data, just
    # a labelled view onto it, so non-technical staff don't have to read raw
    # JSON to see who applied and what they answered. No write path back into
    # ``payload`` from any of these, by design. candidate_name/first_name/
    # last_name are store=True — the standard way to make a computed field
    # usable in search/list sorting — the other, purely-display-only ones
    # aren't referenced from any search view, so they stay unstored.
    candidate_name = fields.Char("Candidate Name", compute='_compute_payload_fields', store=True)
    first_name = fields.Char("First Name", compute='_compute_payload_fields', store=True)
    last_name = fields.Char("Last Name", compute='_compute_payload_fields', store=True)
    name_ar = fields.Char("Name (Arabic)", compute='_compute_payload_fields')
    submitted_email = fields.Char("Email", compute='_compute_payload_fields')
    submitted_phone = fields.Char("Phone", compute='_compute_payload_fields')
    submitted_matricule = fields.Char("Institutional Matricule", compute='_compute_payload_fields')
    submitted_motivation = fields.Text("Motivation", compute='_compute_payload_fields')
    submitted_availability = fields.Char("Availability", compute='_compute_payload_fields')
    submitted_teaching_experience = fields.Text("Teaching Experience", compute='_compute_payload_fields')

    state = fields.Selection([
        ('received', 'Received'),
        ('needs_matching', 'Needs Matching'),
        ('processed', 'Processed'),
        ('rejected', 'Rejected'),
        ('duplicate', 'Duplicate'),
    ], string="Status", default='received', required=True, index=True)
    error_code = fields.Char("Error Code", readonly=True)
    error_message = fields.Text("Error", readonly=True)

    person_id = fields.Many2one(
        'academic.person', "Matched Person", ondelete='set null', index='btree_not_null',
        help="Set once identity matching resolves this submission to a Person — "
             "either an exact matricule hit, or a human confirming a probable match.")
    match_method = fields.Selection([
        ('exact_matricule', 'Exact Matricule'),
        ('possible_match', 'Possible Match (confirmed)'),
        ('new', 'New Person'),
    ], string="Match Method", readonly=True, copy=False,
        help="How ``person_id`` was resolved, for identity-matching traceability.")
    candidature_id = fields.Many2one(
        'insite.candidature', "InSite Candidature", ondelete='set null', index='btree_not_null')

    source_ip = fields.Char("Source IP", index=True, readonly=True)
    origin = fields.Char("Origin", readonly=True)
    user_agent = fields.Char("User Agent", readonly=True)
    email = fields.Char("Email", index=True, readonly=True)

    _reference_uniq = models.Constraint(
        'unique(reference)',
        'Submission references must be unique.',
    )

    @api.depends('payload', 'reference')
    def _compute_payload_fields(self):
        for submission in self:
            payload = submission.payload or {}
            first_name = (payload.get('firstName') or '').strip()
            last_name = (payload.get('lastName') or '').strip()
            name_ar = (payload.get('nameAr') or '').strip()
            submission.first_name = first_name
            submission.last_name = last_name
            submission.name_ar = name_ar
            submission.candidate_name = (
                ' '.join(part for part in (first_name, last_name) if part)
                or name_ar or submission.reference)
            submission.submitted_email = payload.get('email') or ''
            submission.submitted_phone = payload.get('phone') or ''
            submission.submitted_matricule = payload.get('matricule') or ''
            submission.submitted_motivation = payload.get('motivation') or ''
            submission.submitted_availability = payload.get('availability') or ''
            submission.submitted_teaching_experience = payload.get('teachingExperience') or ''

    @api.depends('payload')
    def _compute_payload_preview(self):
        for submission in self:
            if not submission.payload:
                submission.payload_preview = ''
                continue
            try:
                submission.payload_preview = json.dumps(
                    submission.payload, indent=2, ensure_ascii=False, sort_keys=True)
            except (TypeError, ValueError):
                submission.payload_preview = str(submission.payload)

    @api.model
    def _next_reference(self):
        return self.env['ir.sequence'].next_by_code('insite.submission') or \
            fields.Datetime.now().strftime('INS/%Y%m%d/%H%M%S%f')

    # ------------------------------------------------------------------
    # Identity matching entry point (spec section 13): exact matricule and
    # "nobody similar at all" both resolve automatically; anything with a
    # probable-but-not-exact match pauses in 'needs_matching' for a human to
    # confirm through insite.identity.match.wizard — never auto-merged.
    # ------------------------------------------------------------------
    def action_process(self):
        self.env['campus.process.permission']._check_process_permission('insite_candidatures', 'execute')
        Person = self.env['academic.person']
        for submission in self:
            payload = submission.payload or {}
            matches = Person.insite_find_matches(
                matricule=payload.get('matricule'),
                first_name=payload.get('firstName'), last_name=payload.get('lastName'),
                name_ar=payload.get('nameAr'), email=payload.get('email'), phone=payload.get('phone'),
            )
            if matches['exact']:
                submission._insite_resolve(matches['exact'], 'exact_matricule')
            elif matches['possible_persons'] or matches['possible_applicants']:
                submission.write({'state': 'needs_matching', 'email': payload.get('email')})
            else:
                person = Person.create({
                    'first_name': payload.get('firstName'),
                    'last_name': payload.get('lastName'),
                    'name_ar': payload.get('nameAr'),
                    'matricule_institutionnel': payload.get('matricule') or False,
                    'email_institutional': payload.get('email'),
                    'phone': payload.get('phone'),
                    # Arriving via the external submission form — classified
                    # external the moment they're created, so the Candidature
                    # this leads to isn't blocked by _check_person_classified.
                    'is_internal_teacher': 'external',
                })
                submission._insite_resolve(person, 'new')
        return True

    def _insite_resolve(self, person, match_method):
        """Finish processing this submission against a now-known Person —
        called either directly (exact/new) or by the matching wizard after a
        human confirms a probable match."""
        self.ensure_one()
        candidature = self._insite_get_or_create_candidature(person)
        self.write({
            'person_id': person.id,
            'match_method': match_method,
            'candidature_id': candidature.id,
            'state': 'processed',
            'email': (self.payload or {}).get('email'),
        })
        return candidature

    def _insite_get_or_create_candidature(self, person):
        """Reuses an existing not-yet-concluded candidature for this Person if
        one exists; otherwise creates a fresh one in 'prospect'. Deliberately
        does NOT auto-advance the state or link it to a Need — a human links
        it (need_id) and selects/contacts it explicitly through the Need,
        since a public submission has no way to know which Need it's for."""
        self.ensure_one()
        candidature = person.insite_candidature_ids.filtered(
            lambda c: c.state not in ('declined', 'superseded'))[:1]
        if candidature:
            return candidature
        payload = self.payload or {}
        return self.env['insite.candidature'].create({
            'person_id': person.id,
            'motivation': payload.get('motivation'),
            'availability': payload.get('availability'),
            'teaching_experience': payload.get('teachingExperience'),
        })

    def action_view_candidature(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("InSite Candidature"),
            'res_model': 'insite.candidature',
            'res_id': self.candidature_id.id,
            'view_mode': 'form',
        }

    def action_open_matching_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Identity Matching"),
            'res_model': 'insite.identity.match.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_submission_id': self.id},
        }
