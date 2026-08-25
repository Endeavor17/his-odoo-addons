from odoo import fields, models


class PosConfig(models.Model):
    """Which face this till wears.

    Deliberately a plain Selection and not a many2one to a theme model. There
    are three points of sale, they are named in the MDM, and each one's
    appearance is a stylesheet shipped in this module. A theme *table* would
    let someone create a fourth row that no CSS answers to — a configuration
    screen that lies about how configurable it is.

    Empty is the important value: it means stock Odoo, and every rule in this
    module hangs off a class that an empty theme never adds.
    """

    _inherit = 'pos.config'

    his_pos_theme = fields.Selection(
        [
            ('copy_center', "Copy Center"),
            ('restaurant', "Restaurant"),
            ('cafeteria', "Cafétéria"),
        ],
        string="HIS Theme",
        help="Appearance of this point of sale. Leave empty to keep the stock "
             "Odoo interface.",
    )
