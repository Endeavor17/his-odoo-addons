import re

from odoo import _, api, fields, models


class AcademicPerson(models.Model):
    """The one shared identity a teacher has, whatever process they're in.

    Campus+ has no equivalent of this — it stores identity fields directly on
    ``hr.applicant``. This model is the new shared spine InSite needs:
    ``hr.applicant`` is never modified to point here (see
    ``campus_applicant_id`` below), so Campus+ keeps working exactly as it
    does today whether or not this module is installed.

    ``campus_applicant_id`` is Many2many, not Many2one: a real teacher can
    have more than one Campus+ candidature over time (one per campaign a
    given ``campus.evaluation.version`` represents), and nothing here may
    assume there's only ever one.
    """

    _name = 'academic.person'
    _description = 'Academic Person (shared identity)'
    _inherit = ['mail.thread']
    _order = 'last_name, first_name, id'

    first_name = fields.Char("First Name", tracking=True)
    last_name = fields.Char("Last Name", tracking=True)
    name_ar = fields.Char("Name (Arabic)", tracking=True)
    name = fields.Char("Display Name", compute='_compute_name', store=True)

    matricule_institutionnel = fields.Char(
        "Institutional Matricule", index=True, tracking=True,
        help="Deterministic identity key. An exact match here always reuses "
             "the existing Person, before any probabilistic comparison runs.")
    email_institutional = fields.Char("Institutional Email", tracking=True)
    email_personal = fields.Char("Personal Email", tracking=True)
    phone = fields.Char("Phone", tracking=True)

    academic_rank = fields.Char("Academic Rank", tracking=True)
    specialty = fields.Char("Specialty", tracking=True)
    is_internal_teacher = fields.Selection([
        ('internal', 'Internal Teacher'),
        ('external', 'External Teacher'),
    ], string="Internal / External", tracking=True,
        help="Explicit classification — blank means not yet classified. "
             "Never inferred from engagement/application history: whoever "
             "enters this Person (the external submission pipeline, or a "
             "recruiter entering someone by hand) sets it explicitly, so "
             "it's always clear why someone is or isn't in the internal "
             "pool. An InSite Candidature cannot be created for a Person "
             "left unclassified.")
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ], string="Status", default='active', required=True, tracking=True)
    active = fields.Boolean(default=True)

    # One-directional reference only: a Many2many FROM this new model TO the
    # existing hr.applicant. This needs no change whatsoever to hr.applicant
    # itself (Many2many needs no field/inverse on the target model, just a
    # new relation table on InSite's side) — it's how "this Person also has
    # Campus+ candidature(s)" (scenario C) is recorded without touching a
    # single Campus+ file, while allowing any number of them.
    campus_applicant_id = fields.Many2many(
        'hr.applicant', string="Campus+ Applications",
        relation='academic_person_hr_applicant_rel',
        help="Every Campus+ application matched to, or created from, this "
             "Person — possibly more than one, across campaigns. Campus+ "
             "itself never reads this back — informational, InSite-side only.")

    insite_candidature_ids = fields.One2many(
        'insite.candidature', 'person_id', "InSite Candidatures")
    insite_candidature_count = fields.Integer(compute='_compute_counts')
    engagement_ids = fields.One2many(
        'academic.engagement', 'person_id', "Engagements")
    engagement_count = fields.Integer(compute='_compute_counts')

    _matricule_uniq = models.Constraint(
        'unique(matricule_institutionnel)',
        'This institutional matricule is already assigned to another Person.',
    )

    @api.depends('first_name', 'last_name', 'name_ar')
    def _compute_name(self):
        for person in self:
            latin = ' '.join(part for part in (person.first_name, person.last_name) if part)
            person.name = latin or person.name_ar or _("New Person")

    def _compute_counts(self):
        candidature_data = self.env['insite.candidature']._read_group(
            [('person_id', 'in', self.ids)], ['person_id'], ['__count'])
        candidature_map = {person.id: count for person, count in candidature_data}
        engagement_data = self.env['academic.engagement']._read_group(
            [('person_id', 'in', self.ids)], ['person_id'], ['__count'])
        engagement_map = {person.id: count for person, count in engagement_data}
        for person in self:
            person.insite_candidature_count = candidature_map.get(person.id, 0)
            person.engagement_count = engagement_map.get(person.id, 0)

    # ------------------------------------------------------------------
    # Identity matching (spec: exact matricule first, then probabilistic
    # name/email/phone — never auto-applied, always a candidate list for a
    # human to confirm through the matching wizard).
    # ------------------------------------------------------------------
    @api.model
    def _normalize_text(self, value):
        return ' '.join(str(value or '').strip().lower().split())

    @api.model
    def _normalize_phone(self, value):
        return re.sub(r'\D', '', str(value or ''))

    @api.model
    def insite_find_matches(self, matricule=None, first_name=None, last_name=None,
                             name_ar=None, email=None, phone=None):
        """Look up existing identities for the given details.

        Returns a dict with 'exact' (an academic.person, or empty — matricule
        matched, safe to reuse without confirmation), 'possible_persons' and
        'possible_applicants' (candidates a human must confirm before either
        is reused, per the spec's ban on automatic probabilistic merging).
        Never writes anything.
        """
        matricule = (matricule or '').strip()
        if matricule:
            exact = self.search([('matricule_institutionnel', '=', matricule)], limit=1)
            if exact:
                return {
                    'exact': exact,
                    'possible_persons': self.browse(),
                    'possible_applicants': self.env['hr.applicant'].browse(),
                }

        full_name = self._normalize_text(' '.join(filter(None, [first_name, last_name])))
        name_ar_norm = self._normalize_text(name_ar)
        email_norm = self._normalize_text(email)
        phone_norm = self._normalize_phone(phone)

        return {
            'exact': self.browse(),
            'possible_persons': self._probable_person_matches(full_name, name_ar_norm, email_norm, phone_norm),
            'possible_applicants': self._probable_applicant_matches(full_name, name_ar_norm, email_norm, phone_norm),
        }

    def _probable_person_matches(self, full_name, name_ar_norm, email_norm, phone_norm):
        if not (full_name or name_ar_norm or email_norm or phone_norm):
            return self.browse()
        candidates = self.search([('active', '=', True)])
        matches = self.browse()
        for person in candidates:
            names, names_ar, emails, phones = self._match_signals(person)
            if email_norm and email_norm in emails:
                matches |= person
            elif phone_norm and phone_norm in phones:
                matches |= person
            elif full_name and full_name in names:
                matches |= person
            elif name_ar_norm and name_ar_norm in names_ar:
                matches |= person
        return matches

    def _match_signals(self, person):
        """The full set of names/emails/phones this Person could be found
        under: the Person's own fields, UNION every linked Campus+
        application's fields — someone may have used different contact
        details across campaigns, and matching must consider all of them,
        not just whichever was on record first."""
        names = {self._normalize_text(' '.join(filter(None, [person.first_name, person.last_name])))}
        names_ar = {self._normalize_text(person.name_ar)}
        emails = {self._normalize_text(person.email_institutional), self._normalize_text(person.email_personal)}
        phones = {self._normalize_phone(person.phone)}
        for applicant in person.campus_applicant_id:
            names.add(self._normalize_text(applicant.partner_name))
            names_ar.add(self._normalize_text(applicant.campus_name_ar))
            emails.add(self._normalize_text(applicant.email_from))
            phones.add(self._normalize_phone(applicant.partner_phone))
        names.discard('')
        names_ar.discard('')
        emails.discard('')
        phones.discard('')
        return names, names_ar, emails, phones

    def _probable_applicant_matches(self, full_name, name_ar_norm, email_norm, phone_norm):
        """Candidates among Campus+'s own applicants — this is how scenario C
        ("existing Campus+ teacher enters InSite") is detected: the person
        never got an academic.person before, so the only trace of them is an
        hr.applicant row. Read-only lookup; hr.applicant is never written."""
        if not (full_name or name_ar_norm or email_norm or phone_norm):
            return self.env['hr.applicant'].browse()
        Applicant = self.env['hr.applicant'].sudo()
        already_linked = self.search([('campus_applicant_id', '!=', False)]).mapped('campus_applicant_id')
        candidates = Applicant.search([('id', 'not in', already_linked.ids)])
        matches = Applicant.browse()
        for applicant in candidates:
            if email_norm and email_norm == self._normalize_text(applicant.email_from):
                matches |= applicant
            elif phone_norm and phone_norm == self._normalize_phone(applicant.partner_phone):
                matches |= applicant
            elif full_name and full_name == self._normalize_text(applicant.partner_name):
                matches |= applicant
            elif name_ar_norm and name_ar_norm == self._normalize_text(applicant.campus_name_ar):
                matches |= applicant
        return matches

    @api.model
    def insite_create_from_applicant(self, applicant):
        """Materialize a Person from an existing Campus+ applicant's identity.

        Used once a human has confirmed the probable match in
        ``_probable_applicant_matches`` — this is the "existing Person
        reused" path for a teacher who so far only exists through Campus+.
        """
        return self.create({
            'first_name': applicant.partner_name,
            'name_ar': applicant.campus_name_ar,
            'email_institutional': applicant.email_from,
            'phone': applicant.partner_phone,
            'academic_rank': applicant.campus_scientific_rank,
            'specialty': applicant.campus_specialty,
            'campus_applicant_id': [(4, applicant.id)],
            # Resolving an InSite submission's identity match against a
            # Campus+ applicant is still the external InSite pipeline —
            # classified external, same as every other submission-driven
            # Person creation. Campus+ history alone doesn't imply "already
            # an InSite-internal teacher."
            'is_internal_teacher': 'external',
        })

    def insite_link_campus_applicant(self, applicant):
        """Add one more Campus+ application to this Person's set.

        Always additive — ``(4, id)`` links the given applicant alongside
        whatever is already linked, it never replaces the existing set. A
        Person who applied to Campus+ in more than one campaign ends up with
        every one of those ``hr.applicant`` rows linked here.
        """
        self.ensure_one()
        self.write({'campus_applicant_id': [(4, applicant.id)]})
        return True
