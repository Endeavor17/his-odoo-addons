from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class CampusProcessPermission(models.Model):
    """What one user may do on one Campus+ Recruitment process.

    The central authorization table the rest of the module calls into: every
    "execute" or "validate" action in the workflow calls
    ``_check_process_permission`` instead of encoding who is allowed to do
    what, and the ``ir.rule`` on ``hr.applicant`` searches this model
    directly to decide which candidates a user may even see. Changing a row
    here changes behaviour immediately, with no code or restart involved.
    """

    _name = 'campus.process.permission'
    _description = 'Campus+ Process Permission'
    _order = 'process_id, user_id'

    process_id = fields.Many2one('campus.process', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    can_view = fields.Boolean("Can View", default=True)
    can_execute = fields.Boolean("Can Execute", default=False)
    can_validate = fields.Boolean("Can Validate", default=False)
    active = fields.Boolean(default=True)

    _process_user_uniq = models.Constraint(
        'unique(process_id, user_id)',
        'Only one permission record is allowed per user and process.',
    )

    @api.depends('process_id.name', 'user_id.name')
    def _compute_display_name(self):
        for perm in self:
            perm.display_name = f"{perm.process_id.name} — {perm.user_id.name}"

    # ------------------------------------------------------------------
    # Hierarchy: Validate needs Execute, Execute needs View. The onchanges
    # auto-correct the checkboxes as the Administrator ticks them in the
    # config screen; the constraint is the backend guarantee that also
    # catches direct RPC writes the UI never saw.
    # ------------------------------------------------------------------
    @api.onchange('can_validate')
    def _onchange_can_validate(self):
        for perm in self:
            if perm.can_validate:
                perm.can_execute = True
                perm.can_view = True

    @api.onchange('can_execute')
    def _onchange_can_execute(self):
        for perm in self:
            if perm.can_execute:
                perm.can_view = True
            else:
                perm.can_validate = False

    @api.onchange('can_view')
    def _onchange_can_view(self):
        for perm in self:
            if not perm.can_view:
                perm.can_execute = False
                perm.can_validate = False

    @api.constrains('can_view', 'can_execute', 'can_validate')
    def _check_hierarchy(self):
        for perm in self:
            if perm.can_validate and not (perm.can_execute and perm.can_view):
                raise ValidationError(_(
                    "%s: Can Validate requires Can Execute and Can View.", perm.display_name))
            if perm.can_execute and not perm.can_view:
                raise ValidationError(_(
                    "%s: Can Execute requires Can View.", perm.display_name))

    # ------------------------------------------------------------------
    # Central permission checker
    #
    # Named _has_process_permission/_check_process_permission, NOT
    # _has_access/_check_access: the latter is a reserved ORM framework
    # method (odoo/orm/models.py Model._check_access(self, operation)) that
    # Model.create()/write()/... call internally for ir.model.access checks;
    # overriding it with an incompatible signature breaks every ORM
    # operation on this model. Likewise the target-user argument is named
    # ``for_user``, not ``user``: Odoo's lazy ``_()`` walks the calling
    # frame for a local literally named ``user`` to guess the uid for
    # translation, and a same-named parameter left at its ``None`` default
    # crashes that lookup.
    # ------------------------------------------------------------------
    @api.model
    def _has_process_permission(self, process_code, level, for_user=None):
        """Whether ``for_user`` (default: current user) may ``level`` ``process_code``.

        No permission row at all means denied — the matrix is opt-in, not
        opt-out, so a process left unconfigured for someone is closed to them.

        Bypass rules: an explicit ``for_user`` is a deliberate "does this
        specific user have the right" query and is checked as-is, superuser
        aside. With no ``for_user`` (the common case: an action method
        checking "can the current caller do this") a call already running as
        superuser or under ``sudo()`` is system automation — e.g. the public
        application API scoring a fresh submission — not a human recruiter
        clicking a button, so it bypasses the check the same way it already
        bypasses every other access right.
        """
        if for_user is not None:
            if for_user._is_superuser():
                return True
        else:
            for_user = self.env.user
            if for_user._is_superuser() or self.env.su:
                return True
        permission = self.sudo().search([
            ('process_id.code', '=', process_code),
            ('user_id', '=', for_user.id),
            ('active', '=', True),
        ], limit=1)
        return bool(permission) and bool(permission[f'can_{level}'])

    @api.model
    def _check_process_permission(self, process_code, level, for_user=None):
        if not self._has_process_permission(process_code, level, for_user=for_user):
            process = self.env['campus.process'].sudo().search(
                [('code', '=', process_code)], limit=1)
            raise AccessError(_(
                "You do not have permission to %(level)s this process (%(process)s).",
                level=level, process=process.name or process_code))
        return True
