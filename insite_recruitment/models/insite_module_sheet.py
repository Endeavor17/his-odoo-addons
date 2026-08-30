from odoo import _, api, fields, models
from odoo.exceptions import UserError


class InsiteModuleSheet(models.Model):
    """The module *content* a newly assigned teacher prepares — plan,
    chapters, CLOs — deliberately a new, InSite-owned model rather than
    reusing campus_teacher_management's campus.course.breakdown: that model
    is Campus+'s own paperwork-approval record, a different concept (and a
    different module we don't touch), even though both happen to be a
    submit/review workflow.
    """

    _name = 'insite.module.sheet'
    _description = 'InSite Module Sheet'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    engagement_id = fields.Many2one(
        'academic.engagement', "Engagement", required=True, ondelete='cascade', index=True)

    plan = fields.Text("Plan")
    chapters = fields.Text("Chapters")
    clos = fields.Text("Course Learning Outcomes (CLOs)")
    document = fields.Binary("Document", attachment=True, copy=False)
    filename = fields.Char("Filename", copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('modification_requested', 'Modification Requested'),
        ('validated', 'Validated'),
        ('published', 'Published'),
    ], string="Status", default='draft', required=True, tracking=True, copy=False)
    review_notes = fields.Text("Review Notes")

    @api.depends('engagement_id', 'state')
    def _compute_display_name(self):
        for sheet in self:
            sheet.display_name = _(
                "%(engagement)s — %(state)s",
                engagement=sheet.engagement_id.display_name,
                state=dict(self._fields['state'].selection).get(sheet.state, sheet.state),
            )

    def action_submit(self):
        self.env['campus.process.permission']._check_process_permission(
            'insite_module_preparation', 'execute')
        for sheet in self:
            if sheet.state not in ('draft', 'modification_requested'):
                raise UserError(_(
                    "%s cannot be submitted from its current status.", sheet.display_name))
            sheet.state = 'submitted'
            sheet.message_post(body=_("Module sheet submitted for review."))
        return True

    def action_request_modification(self):
        self.env['campus.process.permission']._check_process_permission(
            'insite_module_preparation', 'validate')
        for sheet in self:
            if sheet.state != 'submitted':
                raise UserError(_("%s is not awaiting review.", sheet.display_name))
            if not sheet.review_notes:
                raise UserError(_("Add review notes before requesting a modification."))
            sheet.state = 'draft'
            sheet.message_post(body=_("Modification requested: %s", sheet.review_notes))
        return True

    def action_validate(self):
        self.env['campus.process.permission']._check_process_permission(
            'insite_module_preparation', 'validate')
        for sheet in self:
            if sheet.state != 'submitted':
                raise UserError(_("%s is not awaiting review.", sheet.display_name))
            sheet.state = 'validated'
            sheet.message_post(body=_("Module sheet validated."))
            need = sheet.engagement_id.need_id
            if need:
                need._on_module_validated()
        return True
