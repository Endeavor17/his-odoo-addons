"""Pose les niveaux de depart des regles de reapprovisionnement de la Cafeteria
(stock.warehouse.orderpoint sur WH/Stock/Cafeteria), une valeur par famille.

    # A blanc : affiche ce qui serait fait, n'ecrit rien
    docker compose exec -T odoo odoo shell -c /etc/odoo/odoo.conf -d his_dev \
        --no-http < tools/seed_reappro_cafeteria.py

    # Pour de bon
    docker compose exec -T -e APPLIQUER=1 odoo odoo shell -c /etc/odoo/odoo.conf \
        -d his_dev --no-http < tools/seed_reappro_cafeteria.py

Les responsables n'ont pas rempli les fiches de tools/reappro/ : ces niveaux
sont une premiere estimation imposee, a corriger dans l'ecran
Reapprovisionnement apres 3-4 semaines de ventes reelles. Une fois posees, les
regles appartiennent a l'interface : ce script ne reecrit JAMAIS une regle
qu'un humain a reglee (min ou max non nul). Il cree les manquantes et remplit
celles restees a 0/0.

Rejouable apres chaque vague de catalogue : il n'ajoute que les regles des
nouveaux articles. Les transferts passent par la route « Réappro comptoirs »
de his_stock_mdm (WH/Stock -> comptoir), a installer avant.
"""

import os

APPLIQUER = os.environ.get("APPLIQUER") == "1"

# Unite de l'article (toutes en « Unités » a ce jour). Declenchement manuel :
# le Manager Inventaire commande une fois par semaine, un seul transfert.
NIVEAUX = {
    "his_stock_mdm.categ_cafe_boissons": (4, 12),
    "his_stock_mdm.categ_cafe_chocolat": (3, 10),
    "his_stock_mdm.categ_cafe_snacks": (3, 10),
    "his_stock_mdm.categ_cafe_biscuits": (3, 10),
    "his_stock_mdm.categ_cafe_bonbons": (5, 20),
}

# « Divers » melange ingredients de cuisine (chantilly 5 kg, gelatine), plats
# faits sur place (paliers de gateaux, sandwichs, the) et un peu de revente :
# un niveau unique serait faux pour les trois. Compte et signale, pas regle.
EXCLUE = "his_stock_mdm.categ_cafe_divers"

# PAS en superutilisateur. `odoo shell` tourne en uid 1, et chaque ouverture de
# l'ecran Reapprovisionnement supprime les regles manuelles creees par uid 1
# dont la quantite a commander est nulle (_unlink_processed_orderpoints) : les
# regles d'un comptoir plein disparaitraient au premier affichage.
env = env(user=env.ref("base.user_admin"))

Product = env["product.product"]
# active_test=False : la contrainte unique(produit, emplacement, societe)
# compte aussi les regles archivees ; en creer une doublon echouerait.
Orderpoint = env["stock.warehouse.orderpoint"].with_context(active_test=False)
comptoir = env.ref("his_stock_mdm.loc_cafeteria")


def articles(categorie):
    return Product.search(
        [
            ("categ_id", "child_of", categorie.id),
            ("is_storable", "=", True),
            ("product_tmpl_id.available_in_pos", "=", True),
        ]
    )


lignes = []  # (famille, min, max, creees, remplies, gardees, archivees)
archivees_noms = []

for xmlid, (mini, maxi) in NIVEAUX.items():
    categorie = env.ref(xmlid)
    produits = articles(categorie)
    existantes = {
        regle.product_id: regle
        for regle in Orderpoint.search([("location_id", "=", comptoir.id), ("product_id", "in", produits.ids)])
    }

    a_creer = []
    remplies = gardees = archivees = 0
    for produit in produits:
        regle = existantes.get(produit)
        if not regle:
            a_creer.append(
                {
                    "product_id": produit.id,
                    "location_id": comptoir.id,
                    "product_min_qty": mini,
                    "product_max_qty": maxi,
                    "trigger": "manual",
                }
            )
        elif not regle.active:
            archivees += 1
            archivees_noms.append(produit.display_name)
        elif not regle.product_min_qty and not regle.product_max_qty:
            regle.write({"product_min_qty": mini, "product_max_qty": maxi})
            remplies += 1
        else:
            gardees += 1

    Orderpoint.create(a_creer)
    lignes.append((categorie.name, mini, maxi, len(a_creer), remplies, gardees, archivees))

print("=== REGLES DE REAPPROVISIONNEMENT — %s ===" % comptoir.complete_name)
print("%-20s %4s %4s %8s %9s %8s %10s" % ("Famille", "Min", "Max", "Creees", "Remplies", "Gardees", "Archivees"))
for ligne in lignes:
    print("%-20s %4d %4d %8d %9d %8d %10d" % ligne)
totaux = [sum(ligne[i] for ligne in lignes) for i in range(3, 7)]
print("%-20s %4s %4s %8d %9d %8d %10d" % ("Total", "", "", *totaux))

if archivees_noms:
    print("\nRegles archivees laissees telles quelles (a reactiver a la main si voulu) :")
    for nom in archivees_noms:
        print("  - %s" % nom)

print("\n%d articles « Divers » sans regle (famille exclue, a trier)." % len(articles(env.ref(EXCLUE))))

if APPLIQUER:
    env.cr.commit()
    print("\nEcrit en base.")
else:
    env.cr.rollback()
    print("\nA blanc : rien n'est ecrit. Relancer avec APPLIQUER=1 pour appliquer.")
