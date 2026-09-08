"""Genere une fiche de saisie par point de vente, a faire remplir par les
responsables, pour construire ensuite les regles de reapprovisionnement
(stock.warehouse.orderpoint).

    docker compose exec -T odoo odoo shell -c /etc/odoo/odoo.conf -d his_dev \
        --no-http < tools/generer_fiches_reappro.py

Sort trois CSV dans tools/reappro/. A relancer apres tout ajout au catalogue
(la liste biscuits, par exemple) : les fichiers sont regeneres a neuf, donc
recopier les colonnes deja remplies avant de relancer.

Ce script ne cree AUCUNE regle : il ne fait que produire des fichiers a
remplir. La creation des orderpoints se fera par import, une fois les niveaux
valides.
"""
import csv
import os
import re

SORTIE = os.environ.get('REAPPRO_DIR', '/mnt/extra-addons/tools/reappro')

# Chaque branche du catalogue alimente un point de vente et un seul.
# « Ménage & Nettoyage » n'y figure pas volontairement : ces articles sont
# consommes sur tout le campus, pas vendus par une caisse, et restent au stock
# central tant que personne n'a tranche qui en est responsable.
BRANCHES = [
    ('Café', 'Cafétéria', 'his_stock_mdm.loc_cafeteria', 'cafeteria'),
    ('Restaurant', 'Restaurant', 'his_stock_mdm.loc_restaurant', 'restaurant'),
    ('Copy', 'Copy Center', 'his_stock_mdm.loc_copy_center', 'copy_center'),
]

PREFIXE = 'All / Retail & Consommables (Storable) / '

# Le conditionnement fournisseur (« C/10 », « F/12 », « BT25 ») est dans le nom
# de l'article. On l'extrait comme simple aide a la saisie : un niveau cible de
# 7 quand le carton en contient 12 donne des commandes iningerables.
CONDITIONNEMENT = re.compile(
    r'\b(?:[CFB]\s*/\s*\d+\s*\w*|BT\s*\d+|PQ\s*\d+|PAQ\s*\d+|CT\s*\d+|C/\d+)',
    re.IGNORECASE)

COLONNES = [
    'Reference', 'Article', 'Categorie', 'Conditionnement',
    'Stocker_ici_ON', 'Conso_Hebdo_Estimee', 'Niveau_Min', 'Niveau_Cible',
    'Commentaire',
]


def conditionnement(nom):
    trouve = CONDITIONNEMENT.search(nom)
    return trouve.group(0).strip() if trouve else ''


Product = env['product.product']
os.makedirs(SORTIE, exist_ok=True)

resume = []
for branche, point_de_vente, xmlid, fichier in BRANCHES:
    produits = Product.search(
        [('categ_id.complete_name', '=like', PREFIXE + branche + '%')],
        order='categ_id, name')

    chemin = os.path.join(SORTIE, 'reappro_%s.csv' % fichier)
    with open(chemin, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES)
        writer.writeheader()
        for produit in produits:
            writer.writerow({
                'Reference': produit.default_code or '',
                'Article': produit.name,
                'Categorie': produit.categ_id.complete_name.replace(PREFIXE, ''),
                'Conditionnement': conditionnement(produit.name),
                'Stocker_ici_ON': 'O',
                'Conso_Hebdo_Estimee': '',
                'Niveau_Min': '',
                'Niveau_Cible': '',
                'Commentaire': '',
            })
    resume.append((point_de_vente, len(produits), chemin))

print("=== FICHES DE REAPPROVISIONNEMENT ===")
for point_de_vente, nombre, chemin in resume:
    print("%-14s %4d articles  ->  %s" % (point_de_vente, nombre, chemin))

hors = Product.search_count([
    ('categ_id.complete_name', '=like', PREFIXE + 'Ménage%')])
print("\n%d articles Ménage & Nettoyage hors fiches (stock central)." % hors)
