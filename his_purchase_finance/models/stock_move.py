# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Reception : quantites acceptees, refusees avec motif, restantes (procedure 6.1).

Accepte = la quantite recue ; refuse = jamais entre en stock ; restant = le
reliquat, que le coeur propose comme d'habitude. Un refus ouvre une anomalie.
"""

from markupsafe import Markup
from odoo import _, fields, models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = "stock.move"

    his_qty_refused = fields.Float(string="Refused", digits="Product Unit", copy=False)
    his_refusal_reason = fields.Char(string="Refusal Reason", copy=False)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _his_refused_moves(self):
        return self.move_ids.filtered(lambda m: m.his_qty_refused > 0)

    def _his_fully_refused(self):
        """Livraison entierement refusee : rien d'accepte, tout refuse."""
        self.ensure_one()
        moves = self.move_ids.filtered(lambda m: m.state not in ("done", "cancel"))
        return (
            self.picking_type_code == "incoming"
            and self.purchase_id
            and moves
            and all(m.product_uom.is_zero(m.quantity) and m.his_qty_refused > 0 for m in moves)
        )

    def button_validate(self):
        for picking in self:
            missing = picking._his_refused_moves().filtered(lambda m: not (m.his_refusal_reason or "").strip())
            if missing:
                raise UserError(_("Give the reason why %s was refused.", missing[0].product_id.display_name))
        # Le coeur refuse un transfert a quantite nulle : une livraison refusee
        # en entier ouvre l'anomalie et annule la reception.
        refused = self.filtered(lambda p: p._his_fully_refused())
        for picking in refused:
            picking._his_declare_refusal()
            picking.action_cancel()
        rest = self - refused
        return super(StockPicking, rest).button_validate() if rest else True

    def _action_done(self):
        res = super()._action_done()
        self.filtered(
            lambda p: p.picking_type_code == "incoming" and p.purchase_id and p._his_refused_moves()
        )._his_declare_refusal()
        return res

    def _his_declare_refusal(self):
        for picking in self:
            if not picking.company_id.his_finance_confirms:
                continue
            lines = Markup("").join(
                Markup("<li>%s</li>")
                % _(
                    "%(product)s: %(qty)s %(uom)s refused (%(reason)s)",
                    product=move.product_id.display_name,
                    qty=move.his_qty_refused,
                    uom=move.product_uom.name,
                    reason=move.his_refusal_reason,
                )
                for move in picking._his_refused_moves()
            )
            description = "\n".join(
                f"{move.product_id.display_name}: {move.his_qty_refused} {move.product_uom.name} ({move.his_refusal_reason})"
                for move in picking._his_refused_moves()
            )
            self.env["his.purchase.anomaly"]._his_declare(
                picking.purchase_id,
                "non_compliance",
                _("Refused at receipt %s:\n", picking.name) + description,
                picking=picking,
            )
            picking.message_post(body=Markup("%s<ul>%s</ul>") % (_("Refused at receipt:"), lines))
