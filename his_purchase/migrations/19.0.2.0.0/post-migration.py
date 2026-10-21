# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Apres le passage au type d'achat (2026-10-20).

- Investissements deja approuves : le montant approuve est l'estimation, sinon
  toutes leurs commandes ouvertes retomberaient chez le directeur.
- Demandes soumises : l'approbateur suit maintenant le type, plus le chef.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    cr.execute(
        """UPDATE his_purchase_request SET his_approved_amount = estimated_amount
           WHERE his_purchase_type = 'investment' AND state IN ('approved', 'sourcing', 'ordered', 'done')"""
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["his.purchase.request"].search([("state", "=", "submitted")])._compute_approver_id()
