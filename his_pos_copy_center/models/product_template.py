from odoo import api, fields, models

# The his_stock_mdm categories matching the two copy_service values. Looked up
# softly: this module does not depend on his_stock_mdm.
COPY_CATEGORIES = (
    'his_stock_mdm.categ_copy_photocopie',
    'his_stock_mdm.categ_copy_impression',
)


class ProductTemplate(models.Model):
    """The dimensions a copy is priced by, carried as labels on the product.

    Not attributes, and not by choice. `his_stock_mdm`'s MDM rule 6 permits the
    Format attribute only on the café, restaurant and ménage categories and
    enforces it with a ValidationError in
    `product_template_attribute_line._check_mdm_categ_eligible`. Its message
    prescribes what to do instead — *"une variation physique doit être portée
    par une fiche produit distincte"* — so A4 N&B Recto and A3 Couleur
    Recto-verso are separate products, each with its own price and its own
    cost, and these four fields are how a till recognises which is which.

    Nothing here prices anything. The price is the product's own; the builder
    reads it and never computes it.

    A product carrying no `copy_service` is invisible to the builder and
    behaves exactly as it did before this module was installed.
    """

    _inherit = 'product.template'

    copy_service = fields.Selection(
        [
            ('photocopie', "Photocopie"),
            ('impression', "Impression"),
        ],
        string="Copy Service",
        help="Marks this product as a copy service the Copy Center job builder "
             "can offer. Leave empty for every other product.",
    )
    copy_format = fields.Selection(
        [('a4', "A4"), ('a3', "A3")],
        string="Copy Format",
    )
    copy_color = fields.Selection(
        [('bw', "N&B"), ('color', "Couleur")],
        string="Copy Colour",
    )
    copy_sides = fields.Selection(
        [('recto', "Recto"), ('duplex', "Recto-verso")],
        string="Copy Sides",
    )
    copy_center_visible = fields.Boolean(compute='_compute_copy_center_visible')

    def _copy_center_categories(self):
        return [categ for categ in (
            self.env.ref(xmlid, raise_if_not_found=False) for xmlid in COPY_CATEGORIES
        ) if categ]

    @api.depends('copy_service', 'categ_id')
    def _compute_copy_center_visible(self):
        """Show the form group only where it means something.

        Before this, every product form carried an empty Copy Center group.
        Articles Bureautique, Flexy and Scan are Copy Center categories too, but
        not copy services, so they stay hidden. Without his_stock_mdm there is
        no category to go by, and the group shows everywhere as it always did.
        """
        paths = [categ.parent_path for categ in self._copy_center_categories()]
        for template in self:
            template.copy_center_visible = (
                not paths
                or bool(template.copy_service)
                or any((template.categ_id.parent_path or '').startswith(path) for path in paths)
            )
