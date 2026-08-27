from odoo import _, api, fields, models
from odoo.exceptions import UserError


class InsiteContract(models.Model):
    """InSite's contract step — associated with the Person and the
    recruitment Need, never a reason to create another Person or another
    identity record. Created before any Engagement exists (Module Assignment
    now happens after Signature + Integration), so engagement_id is set later,
    not at creation."""

    _name = 'insite.contract'
    _description = 'InSite Contract'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    person_id = fields.Many2one(
        'academic.person', "Person", required=True, ondelete='restrict', index=True)
    candidature_id = fields.Many2one(
        'insite.candidature', "Candidature", ondelete='set null', index='btree_not_null')
    need_id = fields.Many2one(
        'insite.recruitment.need', "Recruitment Need", required=True, ondelete='restrict', index=True)
    engagement_id = fields.Many2one(
        'academic.engagement', "Engagement", ondelete='set null', index='btree_not_null',
        help="Set once Module Assignment happens, after signature — a "
             "contract exists before any Engagement does in this pipeline.")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('prepared', 'Prepared'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('signed', 'Signed'),
        ('rejected', 'Rejected'),
    ], string="Status", default='draft', required=True, tracking=True, copy=False)
    contract_date = fields.Date("Contract Date", default=fields.Date.context_today)
    signature_date = fields.Date("Signature Date", readonly=True, copy=False)
    document = fields.Binary("Document", attachment=True, copy=False)
    filename = fields.Char("Filename", copy=False)

    @api.depends('person_id', 'state')
    def _compute_display_name(self):
        for contract in self:
            contract.display_name = _(
                "%(person)s — %(state)s",
                person=contract.person_id.display_name,
                state=dict(self._fields['state'].selection).get(contract.state, contract.state),
            )

    def action_prepare(self):
        self.env['campus.process.permission']._check_process_permission('insite_contracts', 'execute')
        self.write({'state': 'prepared'})
        return True

    def action_send(self):
        self.env['campus.process.permission']._check_process_permission('insite_contracts', 'execute')
        self.write({'state': 'sent'})
        return True

    def action_candidate_accept(self):
        """The candidate reviewed the clauses and accepted them — a human
        conversation the system only records the outcome of."""
        self.env['campus.process.permission']._check_process_permission('insite_contracts', 'execute')
        for contract in self:
            if contract.state != 'sent':
                raise UserError(_("%s has not been sent yet.", contract.display_name))
            contract.state = 'accepted'
        return True

    def action_candidate_reject(self):
        self.env['campus.process.permission']._check_process_permission('insite_contracts', 'validate')
        for contract in self:
            if contract.state not in ('sent', 'accepted'):
                raise UserError(_("%s cannot be rejected from its current status.", contract.display_name))
            contract.write({'state': 'rejected'})
            contract.message_post(body=_("Contract rejected."))
            if contract.need_id:
                contract.need_id._on_contract_rejected()
        return True

    def action_sign(self):
        self.env['campus.process.permission']._check_process_permission('insite_contracts', 'validate')
        for contract in self:
            if contract.state != 'accepted':
                raise UserError(_("%s must be accepted by the candidate before it can be signed.",
                                   contract.display_name))
            if not contract.document:
                raise UserError(_(
                    "Attach the signed contract document before marking it signed."))
            contract.write({'state': 'signed', 'signature_date': fields.Date.context_today(contract)})
            contract.message_post(body=_("Contract signed."))
            if contract.need_id:
                contract.need_id._on_contract_signed()
        return True
