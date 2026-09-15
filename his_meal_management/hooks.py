"""Rattachement des onglets de caisse du module.

Pourquoi un hook et pas un simple enregistrement de donnees : les trois
pos.config appartiennent a his_stock_mdm et sont crees en `noupdate="1"`. Le
drapeau etant stocke sur ir.model.data des la creation, aucun fichier de
donnees de ce module-ci ne peut plus les ecrire — y compris pendant
l'installation initiale, ou le pos.config vient d'etre cree par la dependance.

La meme fonction sert donc a l'installation (post_init_hook) et a la mise a
jour des bases existantes (migrations/19.0.3.3.0). Elle est idempotente : elle
n'ajoute que ce qui manque et ne retire jamais un onglet pose par l'exploitant.
"""

# « The IT centre sells the plans, and any food point of sale serves meals
# against the balance » (manifeste). Les deux moities de cette phrase ne se
# rattachent donc pas aux memes caisses :
#
#   - les RECHARGES a un seul point d'encaissement, le Copy Center ;
#   - les REPAS a tout point de restauration, Cafétéria comprise. C'est la
#     regle d'Abdo, et l'oublier avait rendu la Cafétéria incapable de servir
#     un etudiant sur ses credits alors que son bouton de service etait la.
#
# Le Copy Center n'est pas un point de restauration : il ne sert donc aucun
# repas, ce qui satisfait a la fois Abdo et la regle « rien de comestible ».
RATTACHEMENTS = [
    ("his_meal_management.pos_categ_repas", "his_stock_mdm.pos_config_restaurant"),
    ("his_meal_management.pos_categ_repas", "his_stock_mdm.pos_config_cafeteria"),
    ("his_meal_management.pos_categ_recharges", "his_stock_mdm.pos_config_copy_center"),
]


def lier_categories_pos(env):
    for categ_xmlid, config_xmlid in RATTACHEMENTS:
        categ = env.ref(categ_xmlid, raise_if_not_found=False)
        config = env.ref(config_xmlid, raise_if_not_found=False)
        if not categ or not config:
            continue
        if categ not in config.iface_available_categ_ids:
            config.write(
                {
                    "limit_categories": True,
                    "iface_available_categ_ids": [(4, categ.id)],
                }
            )


def taguer_produits(env):
    """Donne son rayon a chaque produit du module, et retire l'autre.

    Le rattachement est EXCLUSIF : un forfait recharge un compte, un repas le
    consomme, et les deux ne se vendent pas a la meme caisse. Laisser les deux
    rayons sur un forfait le ferait apparaitre au Restaurant, qui ne sert que
    des repas.

    Necessaire sur les bases existantes : les produits sont crees en noupdate,
    donc le pos_categ_ids ajoute dans meal_plans.xml ne les atteint pas. Sans
    rayon, un produit disparait de toute caisse qui restreint ses categories.
    """
    Template = env["product.template"]
    recharges = env.ref("his_meal_management.pos_categ_recharges", raise_if_not_found=False)
    repas = env.ref("his_meal_management.pos_categ_repas", raise_if_not_found=False)
    if not recharges or not repas:
        return

    for champ, rayon, rayon_a_retirer in (("meal_credits", recharges, repas), ("meal_credit_cost", repas, recharges)):
        for produit in Template.search([(champ, ">", 0)]):
            commandes = []
            if rayon not in produit.pos_categ_ids:
                commandes.append((4, rayon.id))
            # Un produit qui porte les deux champs est a la fois forfait et
            # repas : on ne lui retire alors rien.
            porte_les_deux = produit.meal_credits > 0 and produit.meal_credit_cost > 0
            if not porte_les_deux and rayon_a_retirer in produit.pos_categ_ids:
                commandes.append((3, rayon_a_retirer.id))
            if commandes:
                produit.write({"available_in_pos": True, "pos_categ_ids": commandes})


def post_init_hook(env):
    lier_categories_pos(env)
    taguer_produits(env)
