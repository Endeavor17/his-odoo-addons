# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Sourcer une demande approuvee : demande de prix, appel sur contrat-cadre,
ou ajout a la prochaine commande mensuelle."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.purchase_order import to_planned_datetime


class HisPurchaseRequestSource(models.TransientModel):
    _name = "his.purchase.request.source"
    _description = "Source Purchase Request"

    request_id = fields.Many2one("his.purchase.request", required=True)
    company_id = fields.Many2one(related="request_id.company_id")
    mode = fields.Selection(
        [
            ("rfq", "Request a quotation from a supplier"),
            ("calloff", "Order now on a blanket order"),
            ("monthly", "Add to the next monthly order"),
        ],
        string="How",
        required=True,
        default="rfq",
    )
    partner_id = fields.Many2one("res.partner", string="Supplier", domain="[('company_id', 'in', [False, company_id])]")
    requisition_id = fields.Many2one(
        "purchase.requisition",
        string="Blanket Order",
        domain="[('requisition_type', '=', 'blanket_order'), ('state', '=', 'confirmed'), ('company_id', '=', company_id)]",
    )
    suggestion = fields.Char(compute="_compute_suggestion")

    @api.depends("request_id", "requisition_id")
    def _compute_suggestion(self):
        for wizard in self:
            agreement = wizard.requisition_id or wizard._his_matching_agreement()
            if not agreement:
                wizard.suggestion = False
            elif (
                agreement.his_recurring
                and wizard.request_id.date_required
                and wizard.request_id.date_required >= agreement.his_next_delivery
            ):
                wizard.suggestion = _(
                    "Needed after the next monthly delivery (%s): add it to the monthly order.",
                    agreement.his_next_delivery,
                )
            else:
                wizard.suggestion = _("Covered by %s: order now on the blanket order.", agreement.name)

    def _his_lines(self):
        # Une ligne en attente de la commande mensuelle reste sourçable : la
        # commander tout de suite la retire de l'attente (action_source).
        lines = self.request_id.line_ids.filtered(lambda line: line._his_remaining_qty() > 0)
        if not lines:
            raise UserError(_("Every line of %s is already being sourced.", self.request_id.name))
        sans_produit = lines.filtered(lambda line: not line.product_id)
        if sans_produit:
            raise UserError(
                _(
                    "Choose a catalogue item for these lines, or wait for the stock managers to create it: %s.",
                    ", ".join(sans_produit.mapped("description")),
                )
            )
        return lines

    def _his_matching_agreement(self):
        products = self.request_id.line_ids.product_id
        if not products:
            return self.env["purchase.requisition"]
        agreements = self.env["purchase.requisition"].search(
            [
                ("requisition_type", "=", "blanket_order"),
                ("state", "=", "confirmed"),
                ("company_id", "=", self.request_id.company_id.id),
            ]
        )
        return agreements.filtered(lambda a: products <= a.line_ids.product_id)[:1]

    def action_source(self):
        self.ensure_one()
        request = self.request_id
        if not request._his_is_purchasing():
            raise UserError(_("Only the purchasing team can source a request."))
        lines = self._his_lines()
        if self.mode != "monthly":
            lines.write({"his_monthly_requisition_id": False})
        if self.mode == "rfq":
            if not self.partner_id:
                raise UserError(_("Choose the supplier."))
            order = self._his_create_order(self.partner_id, lines)
        else:
            agreement = self.requisition_id
            if not agreement:
                raise UserError(_("Choose the blanket order."))
            missing = lines.product_id - agreement.line_ids.product_id
            if missing:
                raise UserError(
                    _(
                        "%(agreement)s does not cover: %(products)s.",
                        agreement=agreement.name,
                        products=", ".join(missing.mapped("display_name")),
                    )
                )
            if self.mode == "calloff":
                order = self._his_create_order(agreement.vendor_id, lines, agreement)
            else:
                if not agreement.his_recurring:
                    raise UserError(_("%s has no monthly order.", agreement.name))
                order = agreement._his_add_to_monthly(lines)
        request.sudo().write({"state": "sourcing", "user_id": request.user_id.id or self.env.user.id})
        if not order:
            request.message_post(body=_("Added to the next monthly order of %s.", self.requisition_id.name))
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
        }

    def _his_create_order(self, partner, lines, agreement=False):
        request = self.request_id
        planned = to_planned_datetime(request.date_required) if request.date_required else fields.Datetime.now()
        order_lines = []
        for line in lines:
            if agreement:
                # Prix et unite du contrat, quantite convertie (comme la mensuelle).
                vals = agreement._his_monthly_line_vals(line.product_id, line._his_remaining_qty(), line)
            else:
                vals = {
                    "product_id": line.product_id.id,
                    "product_qty": line._his_remaining_qty(),
                    "product_uom_id": line.product_uom_id.id,
                    "his_request_line_id": line.id,
                }
            vals["date_planned"] = planned
            if line.description:
                vals["name"] = line.description
            order_lines.append((0, 0, vals))
        vals = {
            "partner_id": partner.id,
            "company_id": request.company_id.id,
            "user_id": request.user_id.id or self.env.user.id,
            "his_request_id": request.id,
            "his_purchase_domain": (agreement or request).his_purchase_domain,
            "origin": request.name,
            "date_planned": planned,
            "order_line": order_lines,
        }
        if agreement:
            vals.update({"requisition_id": agreement.id, "his_supplier_answer": "quoted"})
        return self.env["purchase.order"].create(vals)
