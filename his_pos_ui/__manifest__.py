{
    'name': 'HIS POS Interface',
    'version': '19.0.1.0.0',
    'summary': 'Branded, touch-first interface shared by the HIS points of sale',
    'description': """
HIS POS Interface
=================
The interface may be redesigned; the transaction may not.

* A point of sale wears a theme, chosen on its own configuration. Unset means
  stock Odoo: that fallback is what makes a CSS-only theme safe to install on a
  register that is already taking money.
* The theme is CSS scoped under a class on the POS root element. No component
  is patched to apply styling, so no styling decision can break a sale.
* Touch sizing and the entry wallpaper reuse variables Odoo already exposes
  (--btn-height-size, --homeMenu-bg-image) rather than overriding rules. One
  token moves every button on the screen.
* A missing wallpaper is not a failure: each theme carries a deep tone the
  entry screen falls back to.
""",
    'author': 'Abdo Chabouti',
    'category': 'Sales/Point of Sale',
    'license': 'LGPL-3',

    'depends': ['point_of_sale'],

    'data': [
        'views/pos_config_views.xml',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            # Listed rather than globbed: tokens must be compiled before the
            # rules that consume them, and a glob would also sweep the image
            # folder's README into the bundle.
            'his_pos_ui/static/src/scss/tokens.scss',
            'his_pos_ui/static/src/scss/pos.scss',
            'his_pos_ui/static/src/scss/login.scss',
            'his_pos_ui/static/src/app/*.xml',
        ],
    },

    'installable': True,
}
