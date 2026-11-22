# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Dossier fournisseur : 4 statuts de la Finance, lus sur la societe.

Un fournisseur nait « En attente » (orange) : les demandes de prix marchent,
seule la confirmation finale de la commande attend « Valide » (decision 4 du
2026-11-22). Seule la Finance change le statut.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .common import is_finance

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
        return super().create(vals_list)

    def write(self, vals):
        if (
            "his_supplier_status" in vals
            and not is_finance(self.env)
            and any(partner.his_supplier_status != vals["his_supplier_status"] for partner in self)
        ):
            raise AccessError(_("Only Finance can change the status of a supplier file."))
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
        bad = partner.his_supplier_document_ids.filtered(lambda d: d.status in ("expired", "non_compliant"))
        if bad:
            blockers.append(_("documents expired or non-compliant: %s", ", ".join(bad.mapped("display_name"))))
        return blockers
