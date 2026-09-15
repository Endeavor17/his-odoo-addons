"""Rend a la Cafétéria sa capacite a servir un repas.

La 19.0.3.3.0 avait rattache l'onglet Repas au seul Restaurant. C'etait une
lecture trop etroite de « le Restaurant ne sert que des repas » : cette regle
dit ce que le Restaurant VEND, pas qu'il soit le seul a servir. Le manifeste de
ce module est explicite -- « any food point of sale serves meals against the
balance » -- et la Cafétéria en est un.

Consequence concrete de l'oubli : le bouton de service de la Cafétéria ne
proposait plus rien, puisqu'il n'offre que les repas CHARGES dans la caisse.
"""

from odoo import SUPERUSER_ID, api
from odoo.addons.his_meal_management.hooks import lier_categories_pos, taguer_produits


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lier_categories_pos(env)
    taguer_produits(env)
