# Part of Odoo. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    """Les batiments existants recoivent leur emplacement Patrimoine."""
    env["maintenance.building"].search([])._his_ensure_location()
