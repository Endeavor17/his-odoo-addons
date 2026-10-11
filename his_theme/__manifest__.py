{
    "name": "HIS Theme",
    "version": "19.0.1.0.1",
    "summary": "The university identity — seal navy, gold, Figtree — across the client, the till and the reports",
    "description": """
HIS Theme
=========
One place for the group's visual identity, so no other module carries a colour.

* The backend follows the seal navy (#003874) that his_web_ui paints the navbar
  with, and gold marks the single completing action on a screen. The till
  header keeps the site's petrol teal.
* Everything follows from $o-community-color. Odoo derives both $o-brand-odoo
  (the navbar) and $o-brand-primary (buttons, links, focus rings) from it, so
  the whole client re-skins from one line.
* $o-warning carries the gold on purpose: the workday banner reads --warning
  for its "on break" stripe, and the stripe is meant to be the brand's.
* Figtree and IBM Plex Mono are loaded through a web.layout inherit, with
  fallback stacks that hold the layout if the request never lands.
* The tokens are also published as CSS custom properties (--his-gold and the
  rest, plus the two validated chart inks), which is what the module
  stylesheets consume.

Depends on nothing but web, and the POS rules are ignored when point_of_sale is
not installed — so this can be dropped into any database of the group's.
""",
    "author": "Abdo Chabouti",
    "category": "Theme",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "views/fonts.xml",
    ],
    "assets": {
        # Prepended, not appended: these must be read before Odoo's own
        # primary_variables.scss to win its `!default` assignments.
        "web._assets_primary_variables": [
            ("prepend", "his_theme/static/src/scss/primary_variables.scss"),
        ],
        "web.assets_backend": [
            "his_theme/static/src/scss/backend.scss",
        ],
        # Its own bundle, its own copy of the tokens. Silently ignored on a
        # database without point_of_sale.
        "point_of_sale._assets_pos": [
            "his_theme/static/src/scss/pos.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
