# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class PurchaseRequisitionCreateAlternative(models.TransientModel):
    _inherit = "purchase.requisition.create.alternative"

    def _get_alternative_values(self):
        """Une demande de prix concurrente vise le meme besoin : meme demande
        d'achat, meme domaine (donc meme approbateur), meme date de reponse."""
        vals_list = super()._get_alternative_values()
        origin = self.origin_po_id
        for vals in vals_list:
            vals.update(
                {
                    "his_request_id": origin.his_request_id.id,
                    "his_purchase_domain": origin.his_purchase_domain,
                    "his_reply_by": origin.his_reply_by,
                }
            )
        return vals_list

    @api.model
    def _get_alternative_line_value(self, order_line, product_tmpl_ids_with_description):
        vals = super()._get_alternative_line_value(order_line, product_tmpl_ids_with_description)
        vals["his_request_line_id"] = order_line.his_request_line_id.id
        if order_line.date_planned and not order_line.display_type:
            vals["date_planned"] = order_line.date_planned
        return vals
