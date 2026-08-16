# his_stock_mdm — MDM Produits, Stock & POS

Traduit `MDM_Produits_Stock_POS_v1.md` et le plan d'implémentation Stock/Inventaire
en contraintes serveur et données versionnées, pour Odoo 19.0 Community.

**Aucune reprise de données.** Les contraintes sont en Python (`@api.constrains`),
pas en SQL : elles ne se déclenchent qu'à l'écriture, donc uniquement sur les
données créées ou modifiées après installation. Les 1 301 fiches historiques et
leurs anomalies (51 références dupliquées, stocks négatifs) restent en place.

## Installation

Le module se **rattache** à l'arborescence de catégories déjà en base ; il n'en
crée aucune. `data/mdm_bind_data.xml` doit rester le premier fichier chargé.

Si une catégorie du MDM est absente de la base, l'installation échoue sur un
`External ID not found: his_stock_mdm.categ_*`. Le log liste juste avant les
chemins non résolus (`MDM: N categorie(s) introuvable(s)`) : créer les catégories
manquantes, puis relancer.

```
odoo-bin -d <db> -i his_stock_mdm
odoo-bin -d <db> -i his_stock_mdm --test-enable --test-tags /his_stock_mdm --stop-after-init
```

Sans installation Odoo locale, via Docker (image officielle pour les
dépendances Python, source de ce dépôt monté) :

```
docker run -d --name mdm-pg -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo postgres:16-alpine
docker run --rm --link mdm-pg:db -v "<repo>:/src" odoo:19.0 \
  python3 /src/odoo-bin -d <db> --db_host=db --db_user=odoo --db_password=odoo \
  --addons-path=/src/addons --without-demo -i his_stock_mdm \
  --test-enable --test-tags /his_stock_mdm --stop-after-init
```

**Prérequis comptable :** les catégories sont configurées en valorisation
`real_time` (perpétuelle). Les comptes de valorisation et le journal de stock
doivent être paramétrés au niveau société avant la première réception, sinon
celle-ci échoue. À valider avec la comptabilité avant mise en production.

## Ce que le module applique

| Règle MDM | Où | Comportement |
|---|---|---|
| Référence interne obligatoire et unique | `models/product_product.py` | Bloquant à l'écriture |
| Catégorie terminale obligatoire | `models/product_template.py` | Bloquant |
| Prix de vente obligatoire si stockable + vendable | `models/product_template.py` | Bloquant |
| Attributs Format/Variante restreints par catégorie | `models/product_template_attribute_line.py` | Bloquant. Éligibilité = donnée (`allowed_categ_ids`), vide = sans restriction |
| Traçabilité et péremption par catégorie | `models/product_category.py` + `product_template.py` | Valeur par défaut héritée, modifiable à la main |
| Valorisation FIFO / CUMP par catégorie | `data/product_category_data.xml` | Donnée |
| Motif de perte obligatoire, commentaire si « Autre » | `models/stock_scrap.py` | Bloquant |
| 3 points de vente à stock séparé | `data/stock_location_data.xml` + `pos_config_data.xml` | Chaque caisse décrémente son propre emplacement |

## Phase 4 — Seuils minimums

Aucun code : `stock.warehouse.orderpoint` est natif et importable par CSV.

Procédure quand les seuils réels seront connus :

1. Inventaire ▸ Opérations ▸ Réapprovisionnement, créer une règle témoin.
2. Exporter la liste (colonnes `product_id`, `location_id`, `product_min_qty`,
   `product_max_qty`, `trigger`) avec « Je veux mettre à jour des données ».
3. Remplir, réimporter.

`qty_multiple` n'existe plus en 19.0 ; l'arrondi passe par `replenishment_uom_id`.

## Écarts assumés

- Unicité `default_code` non détectée face à une fiche **archivée**.
- Référence obligatoire appliquée aux fiches **mono-variante** uniquement : sur
  un template multi-variantes `default_code` vaut toujours False (miroir de la
  variante unique) et les variantes générées par attribut naissent sans
  référence. L'exiger bloquerait le mécanisme de variantes que le MDM
  recommande lui-même (4.4). Couvre la totalité du catalogue actuel.
- Traçabilité et péremption héritées **à la création seulement** : changer la
  catégorie d'un produit existant ne réajuste pas son `tracking`.
- « Café / Gaz », cité comme catégorie éligible au MDM 4.4, n'existe pas dans
  l'arborescence 4.1 — non repris.
- POS Restaurant en mode caisse standard : pas de plan de salle (Enterprise).
- LIFO non implémenté : Odoo ne le propose pas comme méthode de valorisation,
  et il est exclu sous IFRS/SCF.

## Recette

Les 9 scénarios Direction sont couverts par `tests/test_governance.py`, sauf
ceux qui exigent des mouvements réels, à dérouler manuellement :

| # | Exigence | Vérification |
|---|---|---|
| 1 | Magasins multiples | Réception sur `WH/Stock`, transferts vers les 3 points, vente POS Cafétéria ⇒ `WH/Restaurant` inchangé |
| 2 | Entrées/sorties | Réception fournisseur + vente POS, contrôle des mouvements |
| 3 | Inventaires | Comptage cyclique, écart, validation de l'ajustement |
| 4 | Seuils minimums | Stock sous seuil ⇒ suggestion de réapprovisionnement |
| 5 | Traçabilité | Lot de viande avec péremption, vente, traçabilité amont/aval |
| 6 | Mouvements historiques | Historique complet d'un produit |
| 7 | Reporting stock | Rapport par produit et par emplacement |
| 8 | Valorisation | Deux réceptions à prix différents sur un produit FIFO et un produit CUMP ⇒ Reporting ▸ Valorisation |
| 9 | Pertes/casse | Perte sans motif et motif « Autre » sans commentaire ⇒ bloqués ; rapport filtrable par emplacement de perte |
