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

**Prérequis comptable — non satisfait à ce jour, et c'est une bombe à retardement.**

Les 19 catégories sont en valorisation `real_time` (perpétuelle) et **aucune ne
porte de compte de valorisation ni de journal de stock** (vérifié le
2026-09-09). Rien n'a encore échoué pour une seule raison : **les 1175 articles
ont un coût de 0**, et un mouvement à valeur nulle ne génère aucune écriture.
La première réception portant un coût réel échouera sur *« You don't have any
stock valuation account defined on your product category »*.

Le plan comptable algérien (`l10n_dz`) est installé et contient les comptes
candidats — `300000` Inventories of goods, `380000` Stored goods, `603000`
Changes in inventory — ainsi qu'un journal `STJ « Inventory Valuation »` créé
exactement pour cet usage. **Le choix appartient à la comptabilité**, pas à ce
module : il n'est donc volontairement pas fait ici. Deux issues, à trancher
avant la première réception valorisée : renseigner ces comptes, ou basculer les
catégories en valorisation périodique.

**Stock négatif : rien n'est bloqué, et c'est délibéré.** Le POS vend même à
quantité nulle, et Odoo Community n'offre aucun réglage natif pour l'empêcher.
Une caisse qui refuse un article physiquement présent sur l'étagère est pire que
le quant négatif qu'elle évite. Le remède est le réassort par règles
(`stock.warehouse.orderpoint`, Phase 4) et l'inventaire tournant, pas un
verrou en caisse.

## Ce que le module applique

| Règle MDM | Où | Comportement |
|---|---|---|
| Référence interne obligatoire et unique | `models/product_product.py` | Bloquant à l'écriture |
| Catégorie terminale obligatoire | `models/product_template.py` | Bloquant |
| Prix de vente obligatoire si stockable + vendable | `models/product_template.py` | Bloquant |
| Attributs Format/Variante restreints par catégorie | `models/product_template_attribute_line.py` | Bloquant. Éligibilité = donnée (`allowed_categ_ids`), vide = sans restriction |
| Traçabilité par catégorie | `models/product_category.py` + `product_template.py` | Mécanisme en place, **plus aucune catégorie ne l'active** (cf. Écarts) |
| Valorisation FIFO / CUMP par catégorie | `data/product_category_data.xml` | Donnée |
| Motif de perte obligatoire, commentaire si « Autre » | `models/stock_scrap.py` | Bloquant |
| 3 points de vente à stock séparé | `data/stock_location_data.xml` + `pos_config_data.xml` | Chaque caisse décrémente son propre emplacement |
| Un comptoir se réapprovisionne depuis le magasin | `data/stock_route_data.xml` | Une règle min/max sur un comptoir crée un transfert `WH/Stock → comptoir`, jamais un achat |
| Séparation des tâches : Collaborateur propose, Manager valide | `models/stock_scrap.py` + `models/stock_quant.py` | Bloquant sur `do_scrap()` et `action_apply_inventory()` (natifs `stock.group_stock_user`/`stock.group_stock_manager`) |
| Inventaire physique annuel : clôture bloquée si comptage non appliqué | `models/his_inventaire_annuel.py` | Bloquant à la clôture, quel que soit le chemin d'écriture |

## Séparation des tâches (Manager / Collaborateur)

Aucun rôle propre au module : réutilisation directe de `stock.group_stock_user`
(Collaborateur) et `stock.group_stock_manager` (Manager, implique le premier)
— l'échelle native correspond déjà exactement à l'organisation actuelle. Un
rôle personnalisé n'apporterait aucune capacité supplémentaire tant que
« peut valider un ajustement » et « peut configurer l'entrepôt » restent
portés par la même personne ; à séparer plus tard si un vrai besoin apparaît.

Un Collaborateur peut créer/modifier une perte en brouillon et saisir un
comptage (`inventory_quantity`) ; seul un Manager peut la valider
(`do_scrap()`) ou l'appliquer aux livres (`action_apply_inventory()`, ce qui
couvre aussi bien le bouton « Appliquer » que l'assistant « Tout appliquer »).

**À faire avant la mise en production :** ce contrôle change qui peut
finaliser un ajustement dès l'installation. Vérifier dans Réglages ▸
Utilisateurs que `stock.group_stock_manager` est bien porté par la ou les
bonnes personnes — ça ne peut pas se déduire du code.

## Inventaire physique annuel

`his.inventaire.annuel` (Inventaire ▸ Configuration ▸ Inventaires annuels,
Manager uniquement) formalise l'obligation légale d'un comptage physique
annuel réconcilié aux livres avant clôture d'exercice. Pas de reprise de
l'existant Odoo : `stock.quant` ne garde aucun lien stocké vers une
« campagne », donc pas d'état brouillon distinct — la création EST
l'ouverture, `create_uid`/`create_date` natifs suffisent pour savoir qui l'a
ouvert et quand.

La clôture (`action_cloturer()`, Manager uniquement) est bloquée tant qu'il
reste un `stock.quant` de la société avec un comptage saisi mais non appliqué
(`inventory_quantity_set = True`) sur un emplacement interne — la règle vit en
`@api.constrains`, donc elle se déclenche aussi sur un import ou une écriture
ORM directe, pas seulement via le bouton. Une fois clôturé, l'enregistrement
est verrouillé (aucune modification ni suppression) : c'est une pièce d'audit,
pas un document de travail.

## Phase 4 — Réapprovisionnement des comptoirs

Une règle min/max (`stock.warehouse.orderpoint`) posée sur un comptoir tire
désormais du magasin : la route **Réappro comptoirs**
(`data/stock_route_data.xml`) porte trois règles `WH/Stock → comptoir`, chacune
sur son type « Réappro … ». **Sans elle, Odoo remontait au parent WH/Stock et
créait une réception fournisseur vers le comptoir**, stock du magasin ignoré.
`tests/test_reappro_comptoirs.py` garde ce cas, la rupture au magasin (le
transfert attend, aucun achat) et le double clic.

Déclenchement **manuel**, une fois par semaine : Inventaire ▸ Opérations ▸
Réapprovisionnement, filtrer l'emplacement, *Commander* → un seul transfert
« Réappro … » pour la semaine. Commander est réservé au **Manager** Inventaire :
le Collaborateur lit les règles sans pouvoir les exécuter (droits natifs).

Niveaux de départ de la Cafétéria : `tools/seed_reappro_cafeteria.py`, une
valeur par famille, à corriger après 3–4 semaines de ventes. Pour corriger en
masse :

1. Réapprovisionnement, filtrer l'emplacement, tout sélectionner, exporter
   (colonnes `product_id`, `location_id`, `product_min_qty`, `product_max_qty`,
   `trigger`) avec « Je veux mettre à jour des données ».
2. Corriger, réimporter.

`qty_multiple` n'existe plus en 19.0 ; l'arrondi passe par `replenishment_uom_id`.

## Écarts assumés

- Unicité `default_code` non détectée face à une fiche **archivée**.
- Référence obligatoire appliquée aux fiches **mono-variante** uniquement : sur
  un template multi-variantes `default_code` vaut toujours False (miroir de la
  variante unique) et les variantes générées par attribut naissent sans
  référence. L'exiger bloquerait le mécanisme de variantes que le MDM
  recommande lui-même (4.4). Couvre la totalité du catalogue actuel.
- **Traçabilité par lot retirée le 2026-09-09** (migration `19.0.1.3.0`). Le MDM
  Phase 5 l'imposait sur le frais Restaurant ; à l'usage elle ne pesait qu'à la
  réception — **aucun article alimentaire n'est vendu en caisse** — où elle
  exigeait un numéro de lot et une date sur chaque sac de farine. Le mécanisme
  d'héritage catégorie → produit reste en place et `product_expiry` reste en
  dépendance : réactiver un suivi, sur une catégorie ou un produit, ne demande
  aucun code. La valorisation FIFO du frais n'a pas bougé, c'est une décision de
  coût et non de traçabilité.
- L'héritage ne joue qu'**à la création** : changer la catégorie d'un produit
  existant ne réajuste pas son `tracking`.
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
| 3 | Inventaires | Comptage cyclique par le Collaborateur, application par le Manager (`do_scrap`/`action_apply_inventory` refusent au Collaborateur), clôture annuelle via Inventaire ▸ Configuration ▸ Inventaires annuels |
| 4 | Seuils minimums | Stock sous seuil ⇒ suggestion de réapprovisionnement |
| 5 | Traçabilité | *Sans objet depuis le 2026-09-09* — plus aucun produit n'est suivi par lot |
| 6 | Mouvements historiques | Historique complet d'un produit |
| 7 | Reporting stock | Rapport par produit et par emplacement |
| 8 | Valorisation | Deux réceptions à prix différents sur un produit FIFO et un produit CUMP ⇒ Reporting ▸ Valorisation |
| 9 | Pertes/casse | Perte sans motif et motif « Autre » sans commentaire ⇒ bloqués ; rapport filtrable par emplacement de perte |
