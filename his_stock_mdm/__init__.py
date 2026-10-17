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

    Category = env["product.category"]
    cache = {}
    for path in MDM_CATEGORIES.values():
        parent = None
        chemin = ""
        for segment in path.split(" / "):
            chemin = f"{chemin} / {segment}" if chemin else segment
            categorie = cache.get(chemin)
            if not categorie:
                domaine = [("name", "=", segment), ("parent_id", "=", parent.id if parent else False)]
                categorie = Category.search(domaine, limit=1) or Category.create(
                    {
                        "name": segment,
                        "parent_id": parent.id if parent else False,
                    }
                )
                cache[chemin] = categorie
            parent = categorie


CAISSES = ("pos_config_cafeteria", "pos_config_restaurant", "pos_config_copy_center")


def post_init_hook(env):
    donner_especes(env)


def donner_especes(env):
    """Chaque caisse encaisse en especes, avec son propre journal de caisse.

    Odoo ne donne des especes qu'a la premiere caisse creee : un moyen
    « especes » ne se partage pas entre deux caisses. Sur une base neuve, le
    Restaurant et le Copy Center naissaient avec la seule carte (recette P-15).
    Idempotent. Une caisse ouverte n'est pas touchee (Odoo refuse de changer
    ses moyens de paiement) : la fermer, puis ajouter les especes a la main.
    """
    for xmlid in CAISSES:
        caisse = env.ref(f"his_stock_mdm.{xmlid}", raise_if_not_found=False)
        if not caisse or caisse.payment_method_ids.filtered("is_cash_count") or caisse.current_session_id:
            continue
        if not caisse.company_id.chart_template:
            continue  # pas de plan comptable : pas de journal possible
        caisse = caisse.with_company(caisse.company_id)
        especes = caisse._create_cash_payment_method({"name": f"Cash {caisse.name}"})
        caisse.payment_method_ids = [(4, especes.id)]
