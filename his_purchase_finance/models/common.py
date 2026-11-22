# Part of Odoo. See LICENSE file for full copyright and licensing details.


def is_finance(env):
    """La Finance (role Comptable), ou le superutilisateur."""
    return env.su or env.user.has_group("his_purchase_finance.group_finance")
