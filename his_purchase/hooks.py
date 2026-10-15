# Part of Odoo. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    """Toute commande passe par l'approbation (decision de Mohamed, 2026-10-15).

    Le reglage natif « Purchase Order Approval » a deux niveaux avec un montant
    de 0 : aucune commande n'est approuvee d'office. Les societes creees plus
    tard heritent du meme defaut (voir res_company.py).
    """
    env["res.company"].search([]).write({"po_double_validation": "two_step", "po_double_validation_amount": 0})
