import secrets
import string

from odoo import api, fields, models, _
from odoo.addons.his_person_core.models.his_person import normalize_text
from odoo.exceptions import UserError

# Excludes visually ambiguous characters (0/O, 1/l/I) since these get
# hand-copied or read aloud when handing a worker their login.
_PASSWORD_ALPHABET = ''.join(c for c in string.ascii_letters + string.digits if c not in '0OoIl1')


def _generate_password(length=12):
    return ''.join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


class MaintenanceUniversityWorkerCreate(models.TransientModel):
    _name = 'maintenance.university.worker.create'
    _description = 'Create Workers'

    line_ids = fields.One2many(
        'maintenance.university.worker.create.line', 'wizard_id', string="Workers"
    )

    def action_create_workers(self):
        self.ensure_one()
        if not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            raise UserError(_("Only a manager can create workers."))
        if not self.line_ids:
            raise UserError(_("Add at least one worker before creating."))

        worker_group = self.env.ref('maintenance_university.group_maintenance_worker')
        # Creating user accounts and employee records both need elevated
        # rights our Manager group deliberately doesn't have (that's core
        # Odoo's own protection, not something to weaken) — the has_group()
        # check above is the real gate; sudo() here only unlocks the specific
        # privileged calls it just authorized.
        Employee = self.env['hr.employee'].sudo()
        Users = self.env['res.users'].sudo()

        for line in self.line_ids:
            if line.employee_id:
                continue  # already processed (wizard reopened after a partial run)

            person = line.person_id
            # The gate. Without it this wizard minted a fresh his.person and a
            # fresh matricule on every single run: hr.employee.create() falls
            # into his_hr_base._create_his_person() whenever person_id is
            # empty, and that only ever guarded against a *contact* already
            # carrying a person — never against the human already existing.
            # That is how one person ended up holding three records.
            if not person and line.suggested_person_id and not line.confirmed_new:
                raise UserError(_(
                    "%(name)s looks like someone already in the referential: "
                    "%(match)s (%(matricule)s).\n\n"
                    "Pick that person in the Existing Person column to give them "
                    "this maintenance role, or tick New Person if this really is "
                    "a different human who happens to share the name.",
                    name=line.name,
                    match=line.suggested_person_id.display_name,
                    matricule=line.suggested_person_id.matricule_affiche
                    or line.suggested_person_id.matricule_institutionnel,
                ))

            password = line.password or _generate_password()
            if person:
                # Un doublon deja archive reste propose (c'est bien l'alerte
                # qu'on veut), mais on ne rattache pas un employe a une fiche
                # mise de cote : il faudrait la reactiver sciemment d'abord.
                if not person.active:
                    raise UserError(_(
                        "%(person)s is archived. Restore that person in the "
                        "Personnes referential first, or pick another one — an "
                        "employee cannot hang off a record that was put aside.",
                        person=person.display_name,
                    ))
                # One person, one employee record — the same rule his_hr_base
                # now enforces on the model. Caught here too so the message
                # names the wizard line, instead of surfacing as a constraint
                # error halfway through a batch.
                existing_employee = Employee.with_context(active_test=False).search(
                    [('person_id', '=', person.id)], limit=1,
                )
                if existing_employee:
                    raise UserError(_(
                        "%(person)s already has an employee record (%(employee)s). "
                        "Give them the Worker group from Settings, Users instead "
                        "of creating a second one.",
                        person=person.display_name,
                        employee=existing_employee.display_name,
                    ))

                # Reuse the account this human already logs in with. A second
                # res.users would also create a second res.partner — it makes
                # its own unless handed one — which is the very fork the
                # delegation exists to prevent.
                user = person.partner_id.sudo().user_ids[:1]
                if user:
                    user.write({'group_ids': [(4, worker_group.id)]})
                    # Their password is theirs: we neither know it nor reset it.
                    password = False
                else:
                    user = Users.create(
                        self._user_vals(line, password, worker_group, person=person)
                    )
            else:
                user = Users.create(self._user_vals(line, password, worker_group))

            employee = Employee.create({
                'name': line.name,
                'user_id': user.id,
                'initial_password': password,
                'date_start_working': line.date_start_working,
                # Set explicitly so _create_his_person() is skipped entirely:
                # his_hr_base already guards on `if not employee.person_id`, so
                # attaching here needs no change on its side.
                'person_id': person.id if person else False,
            })
            line.write({
                'employee_id': employee.id,
                'password': password,
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _user_vals(self, line, password, worker_group, person=None):
        vals = {
            'name': line.name,
            'login': line.login,
            'password': password,
            'group_ids': [(6, 0, [worker_group.id])],
            # Explicit, not inherited from context: a new user's default
            # language falls back to whatever's on the session context,
            # which isn't reliably the creating Manager's own language
            # for a button-triggered server action.
            # ar_DZ, not ar_001: Odoo's web client hardcodes Arabic-Indic
            # digits specifically for ar-sa/ar-sy/ar-001 (see
            # localization_service.js NUMBERING_SYSTEMS) — ar_DZ isn't
            # in that list, so dates render with plain 0-9 digits.
            'lang': 'ar_DZ',
        }
        if person:
            # Attach to the contact the person already delegates to, rather
            # than letting res.users create a second one for the same human.
            vals['partner_id'] = person.partner_id.id
        return vals


class MaintenanceUniversityWorkerCreateLine(models.TransientModel):
    _name = 'maintenance.university.worker.create.line'
    _description = 'Create Workers - Line'

    wizard_id = fields.Many2one(
        'maintenance.university.worker.create', required=True, ondelete='cascade'
    )
    name = fields.Char(string="Name", required=True)
    login = fields.Char(string="Login", required=True)
    date_start_working = fields.Date(string="Start Date", default=fields.Date.context_today)
    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True, copy=False)
    password = fields.Char(string="Password", copy=False)

    # The same manual link the employee form already offers. Endeavor's comment
    # there puts it plainly — attaching to an existing record "est le seul
    # moyen d'eviter un doublon quand la personne est deja au referentiel" —
    # and this wizard was the one door into employee creation that never had
    # it. No type filter on purpose: a student or a candidate taking a
    # maintenance job is exactly the case that used to mint a second record.
    person_id = fields.Many2one(
        'his.person', string="Existing Person",
        help="The person in the referential who is taking this role. Leave "
             "empty only for someone genuinely not registered yet.",
    )
    suggested_person_id = fields.Many2one(
        'his.person', string="Possible Match", compute='_compute_suggestion',
    )
    suggestion_message = fields.Char(compute='_compute_suggestion')
    confirmed_new = fields.Boolean(
        string="New Person",
        help="Tick to confirm this is not the person suggested — a different "
             "human who happens to share the name.",
    )

    @api.depends('name', 'person_id')
    def _compute_suggestion(self):
        """Exact name match against the referential, ignoring case and word order.

        Deliberately NOT his.person._find_or_flag_match: that method scores a
        rich import row, and its name weight is 0.40 against a 0.75 threshold
        (see MATCH_WEIGHTS). Given the two fields this wizard has, it can never
        return a candidate — it would answer 'new' for a name matching someone
        perfectly. Nor is this a second matcher: it reuses the socle's own
        normalize_text, so "ABDO CHABOUTI", "Abdo Chabouti" and "Chabouti Abdo"
        resolve to one another exactly as they do there.

        A near-miss is not flagged, on purpose. This warning blocks the button,
        and one that cries wolf gets ticked away out of habit.
        """
        Person = self.env['his.person'].sudo().with_context(active_test=False)
        for line in self:
            line.suggested_person_id = False
            line.suggestion_message = False
            if line.person_id or not line.name:
                continue
            wanted = set(normalize_text(line.name).split())
            tokens = [token for token in wanted if len(token) > 2]
            if not tokens:
                continue
            # Preselect in SQL, compare in Python: the same shape the socle's
            # own matcher uses, so no full scan of the referential per line.
            domain = ['|'] * (len(tokens) - 1) + [('name', 'ilike', token) for token in tokens]
            match = Person.search(domain).filtered(
                lambda person: set(normalize_text(person.name).split()) == wanted
            )
            if not match:
                continue
            # Archived records are still worth warning about — an archived
            # duplicate is exactly what this wizard used to produce — but the
            # one offered should be the live record when there is one. _order
            # is the matricule, so among equals that is the earliest issued:
            # the original, not one of its copies.
            match = (match.filtered('active') or match)[:1]
            line.suggested_person_id = match
            line.suggestion_message = _(
                "Already registered as %(matricule)s — pick them, or tick New Person.",
                matricule=match.matricule_affiche or match.matricule_institutionnel,
            )
