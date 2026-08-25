from odoo import fields, models


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
