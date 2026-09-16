# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.exceptions import ValidationError


class ProductTemplateAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"

    @api.constrains("attribute_id", "product_tmpl_id")
    def _check_mdm_categ_eligible(self):
        """MDM regle 6 : Format et Variante ne sont activables que sur les
        categories listees. Odoo ne restreint pas les attributs par categorie."""
        for line in self:
            allowed = line.attribute_id.allowed_categ_ids
            if allowed and line.product_tmpl_id.categ_id not in allowed:
                raise ValidationError(
                    _(
                        "L'attribut « %(attr)s » n'est pas autorisé sur la catégorie « %(categ)s ».\n"
                        "Catégories éligibles : %(allowed)s.\n"
                        "En dehors de ces catégories, une variation physique doit être "
                        "portée par une fiche produit distincte.",
                        attr=line.attribute_id.name,
                        categ=line.product_tmpl_id.categ_id.complete_name,
                        allowed=", ".join(allowed.mapped("complete_name")),
                    )
                )
