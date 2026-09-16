"""Retire la tracabilite par lot des articles alimentaires.

Le MDM Phase 5 imposait lot + peremption a tout le frais Restaurant. A l'usage
c'est un cout sans contrepartie ici : **aucun article trace n'est vendu en
caisse**, la contrainte ne pese donc qu'a la reception, ou elle exige un numero
de lot et une date sur chaque sac de farine et chaque bidon d'huile. Arbitrage
de Mohamed le 2026-09-09 : tout retirer.

Sans danger sur cette base : `stock_lot` est vide, il n'y a donc aucun lot a
reconcilier. Sur une base qui en porterait, cette migration est a revoir --
Odoo refuse de detracer un produit dont des lots existent encore.

La valorisation FIFO du frais n'est pas touchee : c'est une decision de cout,
pas de tracabilite.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    traces = env["product.template"].search([("tracking", "!=", "none")])
    if traces:
        traces.write({"tracking": "none", "use_expiration_date": False})

    # Les valeurs par defaut des categories sont remises a plat par le fichier
    # de donnees (hors noupdate), mais on ne laisse pas la base decider : une
    # categorie qui garderait `lot` retracerait le prochain produit cree.
    categories = env["product.category"].search([("default_tracking", "=", "lot")])
    if categories:
        categories.write({"default_tracking": "none", "default_use_expiration_date": False})
