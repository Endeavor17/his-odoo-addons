from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# A finding's severity drives the priority of the request it generates.
SEVERITY_TO_PRIORITY = {
    'low': '0',
    'medium': '1',
    'high': '2',
    'critical': '3',
}

# Fields that define the finding/report itself — locked once it's been sent
# to a manager (state != 'draft'), for the same reason maintenance.request
# locks its own defining fields once a manager owns it: whoever converts it
# is acting on these exact values, so the person who filed it shouldn't be
# able to silently change them out from under a review already in progress.
LOCKED_AFTER_SUBMIT_FIELDS = {
    'building_id', 'category_id', 'description', 'severity', 'image_ids', 'notes',
}


class MaintenanceUniversityFinding(models.Model):
    _name = 'maintenance.university.finding'
    _description = 'Inspection Finding'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    # Not required: a Reporter's standalone problem report (see the Reporter
    # group and action_maintenance_university_report) is this same model with
    # no inspection request behind it at all — only an inspection-tour
    # finding has one.
    request_id = fields.Many2one(
        'maintenance.request',
        string="Inspection Request",
        ondelete='cascade',
        index=True,
        domain=[('is_inspection', '=', True)],
    )
    # Not related to request_id.employee_ids (a Many2many, now that a request
    # can have several workers) — defaults to whoever is actually logging the
    # finding, i.e. the one of possibly several assigned workers on the tour.
    # sudo() on the search itself: a Reporter has no read access to
    # hr.employee at all (deliberately — see the Reporter group), but this
    # default still runs on every create regardless of whether the field is
    # shown on the view being used, so without sudo() every Reporter
    # submission raised an AccessError.
    employee_id = fields.Many2one(
        'hr.employee', string="Reported By",
        default=lambda self: self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1),
    )
    building_id = fields.Many2one(
        'maintenance.building',
        string="Building",
        required=True,
        compute='_compute_building_id',
        store=True,
        readonly=False,
        precompute=True,
    )
    category_id = fields.Many2one('maintenance.category', string="Category", required=True)
    description = fields.Text(string="Description", required=True)
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string="Severity", default='medium')
    notes = fields.Text(string="Notes")
    image_ids = fields.Many2many(
        'ir.attachment', 'maintenance_university_finding_image_rel',
        'finding_id', 'attachment_id', string="Photos",
    )
    found_date = fields.Datetime(string="Found On", default=fields.Datetime.now)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('converted', 'Converted'),
    ], string="Status", default='draft', copy=False, tracking=True)
    created_request_id = fields.Many2one(
        'maintenance.request',
        string="Generated Request",
        readonly=True,
        copy=False,
    )

    @api.depends('request_id.building_id')
    def _compute_building_id(self):
        """Default to the inspected building, but stay editable."""
        for rec in self:
            if rec.request_id.building_id:
                rec.building_id = rec.request_id.building_id

    @api.depends('building_id', 'description')
    def _compute_display_name(self):
        for rec in self:
            summary = (rec.description or '').strip().splitlines()
            summary = summary[0][:40] if summary else _("Finding")
            rec.display_name = f"{rec.building_id.name} - {summary}" if rec.building_id else summary

    @api.constrains('category_id')
    def _check_category_not_inspection(self):
        for rec in self:
            if rec.category_id.is_inspection:
                raise ValidationError(_(
                    "A finding cannot use the Inspection category: converting it would "
                    "create another inspection instead of a repair request."
                ))

    def write(self, vals):
        # Same defense-in-depth shape as maintenance.request's write() guard:
        # once this has been submitted, only a manager can still change what
        # it actually says.
        if self and not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            if set(vals) & LOCKED_AFTER_SUBMIT_FIELDS:
                for rec in self:
                    if rec.state != 'draft':
                        raise UserError(_("This has already been submitted and can no longer be edited."))
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            for rec in self:
                if rec.state != 'draft':
                    raise UserError(_("Only a draft finding or report can be deleted once it's been submitted."))
        return super().unlink()

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("This has already been submitted."))
            if self.env.user != rec.create_uid and not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
                raise UserError(_("Only the person who logged this can submit it."))
        self.write({'state': 'submitted'})

    def action_convert_to_request(self):
        self.ensure_one()
        if not self.env.user.has_group('maintenance_university.group_maintenance_manager'):
            raise UserError(_("Only a manager can convert a finding into a maintenance request."))
        if self.state == 'draft':
            raise UserError(_("This hasn't been submitted yet."))
        if self.state == 'converted':
            raise UserError(_("This finding has already been converted."))
        summary = (self.description or '').strip().splitlines()
        new_request = self.env['maintenance.request'].create({
            'name': summary[0][:120] if summary else _("Finding follow-up"),
            'building_id': self.building_id.id,
            'category_id': self.category_id.id,
            'description': self.description,
            'priority': SEVERITY_TO_PRIORITY.get(self.severity, '1'),
            'origin_finding_id': self.id,
        })
        self.write({
            'state': 'converted',
            'created_request_id': new_request.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Maintenance Request"),
            'res_model': 'maintenance.request',
            'view_mode': 'form',
            'res_id': new_request.id,
        }
