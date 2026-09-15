# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models


def pre_init_hook(env):
    """S'assure que l'arborescence de categories du MDM existe AVANT le chargement.

    Le module se rattache a une arborescence supposee deja en base (cf.
    data/mdm_bind_data.xml). En production elle existe ; sur une base neuve
    (CI, reprise apres sinistre, base de recette) elle n'existe pas, et
    data/product_category_data.xml echoue alors sur une categorie inexistante,
    ce qui interrompt toute l'installation.

    On la cree ici de facon idempotente : chaque segment est cherche sous son
    parent et cree seulement s'il manque, donc une arborescence de production
    est reutilisee telle quelle et une base vide en recoit une. La source unique
    est MDM_CATEGORIES (models/product_category.py) : aucun arbre n'est duplique.
    """
    from .models.product_category import MDM_CATEGORIES

    Category = env['product.category']
    cache = {}
    for path in MDM_CATEGORIES.values():
        parent = None
        chemin = ''
        for segment in path.split(' / '):
            chemin = f'{chemin} / {segment}' if chemin else segment
            categorie = cache.get(chemin)
            if not categorie:
                domaine = [('name', '=', segment),
                           ('parent_id', '=', parent.id if parent else False)]
                categorie = Category.search(domaine, limit=1) or Category.create({
                    'name': segment, 'parent_id': parent.id if parent else False,
                })
                cache[chemin] = categorie
            parent = categorie
