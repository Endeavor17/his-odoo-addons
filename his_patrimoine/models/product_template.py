# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _his_is_patrimoine(self):
        self.ensure_one()
        root = self.env.ref("his_patrimoine.categ_patrimoine", raise_if_not_found=False)
        # Odoo 19 admet un article sans categorie (pas de parent_path).
        return bool(root and self.categ_id) and self.categ_id.parent_path.startswith(root.parent_path)

    @api.model
    def _his_patrimoine_defaults(self, vals_list):
        """Un bien se compte a l'unite : stockable, une etiquette PAT- chacun.
        Appele aussi par product.product.create, qui cree le modele sans
        passer par ce create (Odoo 19, _inherits)."""
        root = self.env.ref("his_patrimoine.categ_patrimoine")
        categories = self.env["product.category"].search([("id", "child_of", root.id)])
        for vals in vals_list:
            if vals.get("categ_id") in categories.ids:
                # Le formulaire envoie ses defauts (suivi aucun, prefixe vide
                # qui remet la sequence du coeur) : on impose, pas setdefault.
                vals.pop("serial_prefix_format", None)
                vals.update(
                    is_storable=True,
                    tracking="serial",
                    lot_sequence_id=self.env.ref("his_patrimoine.seq_patrimoine").id,
                )
                vals.setdefault("sale_ok", False)
        return vals_list

    @api.onchange("categ_id")
    def _onchange_his_patrimoine_categ(self):
        if self._his_is_patrimoine():
            self.is_storable = True
            self.tracking = "serial"
            self.sale_ok = False
            self.lot_sequence_id = self.env.ref("his_patrimoine.seq_patrimoine")

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(self._his_patrimoine_defaults(vals_list))

    @api.constrains("tracking", "is_storable", "categ_id")
    def _check_his_patrimoine_serial(self):
        for template in self:
            if template._his_is_patrimoine() and (not template.is_storable or template.tracking != "serial"):
                raise ValidationError(
                    _(
                        '"%s" is a durable item (Patrimoine): it must be storable and tracked by serial number.',
                        template.name,
                    )
                )


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(self.env["product.template"]._his_patrimoine_defaults(vals_list))
