from odoo import _, api, fields, models


class AcademicEngagement(models.Model):
    """A Person's assignment to a Module for an AcademicPeriod.

    Shared shape for both processes (see ``process``), but only InSite
    creates rows here in this module — Campus+'s own subject-acceptance flow
    (``campus.application.subject``) is untouched and does not feed this
    model. A Person may have any number of Engagements, from either process.
    """

    _name = 'academic.engagement'
    _description = 'Academic Engagement'
    _inherit = ['mail.thread']
    _order = 'academic_period_id desc, person_id, id'

    person_id = fields.Many2one(
        'academic.person', "Person", required=True, ondelete='cascade', index=True)
    # "Module" per the spec's data model: campus.subject is already exactly
    # that catalogue (name/level/track/language) — reused as-is rather than
    # duplicated. The field is labelled "Module" in the view; the underlying
    # model keeps its existing name and existing Campus+ records.
    module_id = fields.Many2one(
        'campus.subject', "Module", required=True, ondelete='restrict', index=True)
    academic_period_id = fields.Many2one(
        'academic.period', "Academic Period", required=True, ondelete='restrict', index=True)

    process = fields.Selection([
        ('campus', 'Campus+'),
        ('insite', 'InSite'),
    ], string="Process", required=True, default='insite', index=True)
    insite_candidature_id = fields.Many2one(
        'insite.candidature', "InSite Candidature", ondelete='set null', index='btree_not_null')
    need_id = fields.Many2one(
        'insite.recruitment.need', "Recruitment Need", ondelete='set null', index='btree_not_null',
        help="The Need this assignment fulfills. hourly_volume is read from "
             "here (need_id.hourly_volume) rather than duplicated on this model.")

    track = fields.Char("Track / Piste")
    hourly_volume = fields.Float("Hourly Volume", related='need_id.hourly_volume', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default='draft', required=True, tracking=True, index=True)

    @api.depends('person_id', 'module_id', 'academic_period_id')
    def _compute_display_name(self):
        for engagement in self:
            engagement.display_name = _(
                "%(person)s — %(module)s (%(period)s)",
                person=engagement.person_id.display_name,
                module=engagement.module_id.display_name,
                period=engagement.academic_period_id.display_name,
            )

    def _check_process_permission(self, level):
        for engagement in self:
            if engagement.process == 'insite':
                self.env['campus.process.permission']._check_process_permission(
                    'insite_engagements', level)

    def action_confirm(self):
        self._check_process_permission('execute')
        self.write({'state': 'confirmed'})
        return True

    def action_activate(self):
        self._check_process_permission('validate')
        self.write({'state': 'active'})
        return True

    def action_complete(self):
        self._check_process_permission('validate')
        self.write({'state': 'completed'})
        return True

    def action_cancel(self):
        self._check_process_permission('execute')
        self.write({'state': 'cancelled'})
        return True
