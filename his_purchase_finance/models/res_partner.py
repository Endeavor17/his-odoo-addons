# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Dossier fournisseur : 4 statuts de la Finance, lus sur la societe.

Un fournisseur nait « En attente » (orange) : les demandes de prix marchent,
seule la confirmation finale de la commande attend « Valide » (decision 4 du
2026-11-22). Seule la Finance change le statut.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .common import is_finance

# Pieces exigees pour valider un dossier (procedure 4.1, defauts envoyes a la
# Finance le 2026-11-24). L'agrement reste verifie au cas par cas.
REQUIRED_COMPANY = ("rc", "nif", "nis", "tax_certificate", "rib", "id_card")
REQUIRED_INDIVIDUAL = ("nif", "nis", "id_card", "rib")

SUPPLIER_STATUSES = [
    ("waiting", "Waiting"),
    ("reserve", "On Reserve"),
    ("validated", "Validated"),
    ("refused", "Refused"),
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    his_supplier_status = fields.Selection(
        SUPPLIER_STATUSES,
        string="Supplier File",
        default="waiting",
        tracking=True,
        copy=False,
        help="Set by Finance. Waiting (orange): not checked yet. On Reserve (red): documents missing, "
        "expired or non-compliant. Validated (green): orders can be confirmed. Refused (dark red).",
    )
    his_supplier_status_reason = fields.Text(string="Supplier File Reason", tracking=True, copy=False)
    his_supplier_document_ids = fields.One2many("his.supplier.document", "partner_id", string="Supplier Documents")
    his_documents_exempt = fields.Boolean(
        string="No Documents Required",
        tracking=True,
        copy=False,
        help="Public body or utility (electricity, water, telephone): set by Finance.",
    )

    def _his_missing_documents(self):
        """Libelles des pieces exigees absentes, expirees ou non conformes ; lu sur la societe."""
        self.ensure_one()
        partner = self.commercial_partner_id.sudo()
        if partner.his_documents_exempt:
            return []
        required = REQUIRED_COMPANY if partner.is_company else REQUIRED_INDIVIDUAL
        held = set(partner.his_supplier_document_ids.filtered(lambda d: d.status in ("valid", "to_refresh")).mapped("doc_type"))
        labels = dict(self.env["his.supplier.document"]._fields["doc_type"]._description_selection(self.env))
        return [labels[doc_type] for doc_type in required if doc_type not in held]

    @api.constrains("his_supplier_status", "his_documents_exempt")
    def _check_his_required_documents(self):
        for partner in self:
            if partner.his_supplier_status != "validated" or not self.env.company.his_finance_confirms:
                continue
            missing = partner._his_missing_documents()
            if missing:
                raise ValidationError(
                    _(
                        "The supplier file of %(supplier)s cannot be validated: missing %(documents)s.",
                        supplier=partner.name,
                        documents=", ".join(missing),
                    )
                )

    @api.constrains("vat", "parent_id", "is_company")
    def _check_his_unique_nif(self):
        if not self.env.company.his_finance_confirms:
            return
        for partner in self:
            if not partner.vat or partner.parent_id:
                continue
            nif = partner.vat.replace(" ", "")
            others = self.sudo().search(
                [
                    ("id", "!=", partner.id),
                    ("parent_id", "=", False),
                    ("vat", "!=", False),
                    ("company_id", "in", [partner.company_id.id, False]),
                ]
            ).filtered(lambda other: other.vat.replace(" ", "") == nif)
            if others:
                raise ValidationError(
                    _("The NIF %(nif)s is already used by %(other)s.", nif=partner.vat, other=others[0].name)
                )

    @api.constrains("his_supplier_status", "his_supplier_status_reason")
    def _check_his_supplier_reason(self):
        for partner in self:
            if (
                partner.his_supplier_status in ("reserve", "refused")
                and not (partner.his_supplier_status_reason or "").strip()
            ):
                raise ValidationError(
                    _("Give the reason why the supplier file of %s is on reserve or refused.", partner.name)
                )

    @api.model_create_multi
    def create(self, vals_list):
        if not is_finance(self.env) and any(
            vals.get("his_supplier_status", "waiting") != "waiting" for vals in vals_list
        ):
            raise AccessError(_("Only Finance can validate a supplier file."))
        if not is_finance(self.env) and any(vals.get("his_documents_exempt") for vals in vals_list):
            raise AccessError(_("Only Finance can exempt a supplier from documents."))
        return super().create(vals_list)

    def write(self, vals):
        if (
            "his_supplier_status" in vals
            and not is_finance(self.env)
            and any(partner.his_supplier_status != vals["his_supplier_status"] for partner in self)
        ):
            raise AccessError(_("Only Finance can change the status of a supplier file."))
        if (
            "his_documents_exempt" in vals
            and not is_finance(self.env)
            and any(partner.his_documents_exempt != vals["his_documents_exempt"] for partner in self)
        ):
            raise AccessError(_("Only Finance can exempt a supplier from documents."))
        return super().write(vals)

    def _his_supplier_blockers(self):
        """Ce qui empeche de confirmer une commande chez ce fournisseur ; vide si rien."""
        self.ensure_one()
        partner = self.commercial_partner_id.sudo()
        blockers = []
        if partner.his_supplier_status != "validated":
            blockers.append(
                _(
                    "the supplier file of %(supplier)s is “%(status)s”",
                    supplier=partner.name,
                    status=dict(self._fields["his_supplier_status"]._description_selection(self.env))[
                        partner.his_supplier_status
                    ],
                )
            )
        missing = partner._his_missing_documents()
        if missing:
            blockers.append(_("documents missing: %s", ", ".join(missing)))
        bad = partner.his_supplier_document_ids.filtered(lambda d: d.status in ("expired", "non_compliant"))
        if bad:
            blockers.append(_("documents expired or non-compliant: %s", ", ".join(bad.mapped("display_name"))))
        return blockers
