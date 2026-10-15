{
    "name": "HIS Theme",
    "version": "19.0.1.1.0",
    "summary": "The university identity - seal navy, till teal, Figtree - as one set of tokens for the client, the till and the login page",
    "description": """
HIS Theme
=========
The single owner of the group's design tokens and faces, so no other module
writes a brand value.

* primary_variables.scss holds every brand value once, as $his-* SCSS
  variables. It is prepended to web._assets_primary_variables, which the web
  client, the till and the login page all compile, so Odoo's own colours
  ($o-community-color and the rest) derive from the same values.
* tokens.scss publishes those values as CSS custom properties (--his-*) and
  declares the faces. It is listed in the three bundles, so the till gets the
  tokens without anyone retyping a value.
* The faces ship in static/src/fonts: Figtree for Latin, Readex Pro for Arabic
  glyphs only, IBM Plex Mono for codes and figures. Nothing is fetched from a
  CDN at runtime. Sources and licences are in README.md.
* The action that completes a task is the seal navy (--his-action). Gold stays
  as a legacy token for the maintenance dashboards and the printed meal card.

Depends on nothing but web, and the POS rules are ignored when point_of_sale is
not installed - so this can be dropped into any database of the group's.
""",
    "author": "Abdo Chabouti",
    "category": "Theme",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [],
    "assets": {
        # Prepended, not appended: these must be read before Odoo's own
        # primary_variables.scss to win its `!default` assignments.
        "web._assets_primary_variables": [
            ("prepend", "his_theme/static/src/scss/primary_variables.scss"),
        ],
        # One file, three bundles: the values themselves live in
        # primary_variables.scss, which all three compile.
        "web.assets_backend": [
            "his_theme/static/src/scss/tokens.scss",
        ],
        "web.assets_frontend": [
            "his_theme/static/src/scss/tokens.scss",
        ],
        # Silently ignored on a database without point_of_sale.
        "point_of_sale._assets_pos": [
            "his_theme/static/src/scss/tokens.scss",
            "his_theme/static/src/scss/pos.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
