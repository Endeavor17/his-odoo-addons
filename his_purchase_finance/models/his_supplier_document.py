# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Pieces du dossier fournisseur (procedure Finance, etape 4.1)."""

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

DOC_TYPES = [
    ("rc", "Trade Register (RC)"),
    ("nif", "Tax ID (NIF)"),
    ("nis", "Statistical ID (NIS)"),
    ("tax_certificate", "Tax Existence Certificate (AI)"),
    ("rib", "Bank Details (RIB)"),
    ("licence", "Professional Licence"),
    ("id_card", "Legal Representative's ID"),
    ("other", "Other"),
]
STATUSES = [
    ("valid", "Valid"),
    ("to_refresh", "To Refresh"),
    ("expired", "Expired"),
    ("non_compliant", "Non-Compliant"),
]
# Alerte interne de la Finance : une piece fiscale a actualiser a 6 mois.
TAX_CERTIFICATE_MONTHS = 6
EXPIRY_WARNING_DAYS = 30


class HisSupplierDocument(models.Model):
    _name = "his.supplier.document"
    _description = "Supplier Document"
    _order = "doc_type, id desc"

    partner_id = fields.Many2one("res.partner", string="Supplier", required=True, ondelete="cascade", index=True)
    doc_type = fields.Selection(DOC_TYPES, string="Document", required=True)
    name = fields.Char(string="Reference")
    file = fields.Binary(string="File", attachment=True)
    file_name = fields.Char(string="File Name")
    received_on = fields.Date(string="Received On", default=fields.Date.context_today)
    expires_on = fields.Date(string="Expires On")
    non_compliant = fields.Boolean(string="Non-Compliant")
    non_compliant_note = fields.Char(string="Non-Compliance Reason")
    status = fields.Selection(STATUSES, string="Status", compute="_compute_status")

    @api.depends("doc_type", "received_on", "expires_on", "non_compliant")
    @api.depends_context("date")
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for doc in self:
            if doc.non_compliant:
                doc.status = "non_compliant"
            elif doc.expires_on and doc.expires_on < today:
                doc.status = "expired"
            elif (doc.expires_on and doc.expires_on <= today + relativedelta(days=EXPIRY_WARNING_DAYS)) or (
                doc.doc_type == "tax_certificate"
                and doc.received_on
                and doc.received_on + relativedelta(months=TAX_CERTIFICATE_MONTHS) <= today
            ):
                doc.status = "to_refresh"
            else:
                doc.status = "valid"

    @api.depends("doc_type", "name")
    def _compute_display_name(self):
        labels = dict(DOC_TYPES)
        for doc in self:
            doc.display_name = " ".join(filter(None, [labels.get(doc.doc_type), doc.name]))
