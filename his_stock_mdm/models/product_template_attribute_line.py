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
                        'The attribute "%(attr)s" is not allowed on the category "%(categ)s".\n'
                        "Eligible categories: %(allowed)s.\nOutside these categories, a physical "
                        "variation must be carried by a separate product.",
                        attr=line.attribute_id.name,
                        categ=line.product_tmpl_id.categ_id.complete_name,
                        allowed=", ".join(allowed.mapped("complete_name")),
                    )
                )
