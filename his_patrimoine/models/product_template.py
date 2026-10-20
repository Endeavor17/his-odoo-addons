# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _his_is_patrimoine(self):
        self.ensure_one()
        root = self.env.ref("his_patrimoine.categ_patrimoine", raise_if_not_found=False)
        return bool(root) and self.categ_id.parent_path.startswith(root.parent_path)

    @api.model_create_multi
    def create(self, vals_list):
        root = self.env.ref("his_patrimoine.categ_patrimoine")
        categories = self.env["product.category"].search([("id", "child_of", root.id)])
        for vals in vals_list:
            if vals.get("categ_id") in categories.ids:
                # Un bien se compte a l'unite : stockable, une etiquette PAT- chacun.
                vals.setdefault("is_storable", True)
                vals.setdefault("tracking", "serial")
                vals.setdefault("sale_ok", False)
                vals.setdefault("lot_sequence_id", self.env.ref("his_patrimoine.seq_patrimoine").id)
        return super().create(vals_list)

    @api.constrains("tracking", "is_storable", "categ_id")
    def _check_his_patrimoine_serial(self):
        for template in self:
            if template._his_is_patrimoine() and (not template.is_storable or template.tracking != "serial"):
                raise ValidationError(
                    _('"%s" is a durable item (Patrimoine): it must be storable and tracked by serial number.', template.name)
                )
