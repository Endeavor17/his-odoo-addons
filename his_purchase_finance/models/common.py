# Part of Odoo. See LICENSE file for full copyright and licensing details.


def is_finance(env):
    """La Finance (role Comptable), ou le superutilisateur."""
    return env.su or env.user.has_group("his_purchase_finance.group_finance")


# Decret executif 15-153 : un achat de biens ou services de 1 000 000 DA ou plus
# se paie par cheque ou virement (procedure 8.2 : especes « dans les limites de
# la reglementation »). Bloquant, sans derogation (Mohamed, 2026-11-26).
CASH_VAT_LIMIT = 1_000_000
