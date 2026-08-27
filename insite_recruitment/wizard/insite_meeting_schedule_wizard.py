from odoo import _, api, fields, models
from odoo.exceptions import UserError


class InsiteMeetingScheduleWizard(models.TransientModel):
    """Schedule/Reschedule Meeting — entirely manual, Pédagogie-driven. No
    self-service booking page, no token, no public controller: every field
    here is exactly what Pédagogie types in, nothing defaulted or hardcoded.
    """

    _name = 'insite.meeting.schedule.wizard'
    _description = 'InSite Meeting Scheduling'

    candidature_id = fields.Many2one('insite.candidature', "Candidature", required=True)
    meeting_start = fields.Datetime("Meeting Start", required=True)
    meeting_end = fields.Datetime("Meeting End", required=True)
    location = fields.Char("Location / Meeting Link")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        candidature = self.env['insite.candidature'].browse(vals.get('candidature_id'))
        if self.env.context.get('reschedule') and candidature.meeting_event_id:
            event = candidature.meeting_event_id
            vals.update({
                'meeting_start': event.start,
                'meeting_end': event.stop,
                'location': event.location,
            })
        return vals

    def action_confirm(self):
        self.env['campus.process.permission']._check_process_permission('insite_candidatures', 'execute')
        self.ensure_one()
        if self.meeting_end <= self.meeting_start:
            raise UserError(_("The meeting end time must be after its start time."))

        candidature = self.candidature_id
        if self.env.context.get('reschedule'):
            if not candidature.meeting_event_id:
                raise UserError(_("No meeting is scheduled yet for %s — use 'Schedule Meeting' first.",
                                   candidature.person_id.display_name))
            candidature.meeting_event_id.write({
                'start': self.meeting_start, 'stop': self.meeting_end, 'location': self.location,
            })
            candidature.message_post(body=_(
                "Meeting rescheduled to %(start)s – %(end)s.",
                start=self.meeting_start, end=self.meeting_end))
        else:
            if candidature.meeting_event_id:
                raise UserError(_("A meeting is already scheduled for %s. Use 'Reschedule Meeting' to change it.",
                                   candidature.person_id.display_name))
            event = self.env['calendar.event'].create({
                'name': _("InSite Meeting — %(person)s (%(need)s)",
                          person=candidature.person_id.display_name,
                          need=candidature.need_id.display_name if candidature.need_id else ''),
                'start': self.meeting_start,
                'stop': self.meeting_end,
                'location': self.location,
            })
            candidature.meeting_event_id = event.id
            template = self.env.ref('insite_recruitment.mail_template_insite_confirmation', raise_if_not_found=False)
            if template:
                template.send_mail(candidature.id, force_send=False)
            candidature.message_post(body=_(
                "Meeting scheduled for %(start)s – %(end)s. Acceptance email sent.",
                start=self.meeting_start, end=self.meeting_end))
            if candidature.need_id:
                candidature.need_id._on_meeting_scheduled()
        return {'type': 'ir.actions.act_window_close'}
