# his_pos_copy_center — Copies et impressions au Copy Center

Un écran pour composer une copie au comptoir, au lieu d'une fenêtre par
dimension et par document.

L'idée directrice, énoncée d'abord :

> **Les dimensions sont des champs, pas des attributs, et c'est `his_stock_mdm`
> qui l'a décidé.** Ce module ne modifie aucune règle du MDM : il s'y plie et
> étiquette les produits que le MDM impose de créer séparément.

---

## 1. Pourquoi des champs et non des attributs

Une copie se tarife par ses dimensions — nombre, format, couleur, recto/verso —
et il serait naturel d'en faire des attributs produit. C'est interdit ici.

`his_stock_mdm` applique sa **règle MDM 6** dans
`product_template_attribute_line._check_mdm_categ_eligible` : un attribut n'est
utilisable que sur les catégories listées dans son `allowed_categ_ids`, et la
violation lève une `ValidationError`. Or l'attribut `Format` est réservé aux
catégories Café, Restaurant et Ménage — **aucune catégorie Copy n'y figure**.
Une fiche Photocopie portant Format/Couleur/Recto-verso en attributs refuserait
tout simplement de s'enregistrer.

Le message d'erreur du MDM prescrit lui-même l'alternative :

> « En dehors de ces catégories, une variation physique doit être portée par une
> fiche produit distincte. »

Donc **Impression N&B Recto et Impression Couleur Recto-verso sont deux produits**, chacun avec
son prix et son coût. C'est le catalogue que ce module doit servir, et discuter
la règle reviendrait à amender la gouvernance d'un autre module pour arranger
une interface.

Les quatre champs (`copy_service`, `copy_format`, `copy_color`, `copy_sides`)
n'ajoutent aucun attribut et ne créent aucune variante : ils **étiquettent** un
produit avec ce qu'il représente déjà, pour qu'une caisse le retrouve par sa
description au lieu de son nom.

Un test épingle la règle du MDM elle-même. Si une évolution future autorisait
`Format` sur les catégories Copy, ce test échoue — et cet échec est le signal
qu'il faut reconsidérer la conception. Sans lui, la raison de ce choix se
transformerait discrètement en folklore.

## 2. Le piège qui aurait coûté cher

`product.product` publie une **liste blanche** de champs vers le POS
(`_load_pos_data_fields`), contrairement à `pos.config` qui est lu en entier.

Un champ absent de cette liste ne lève rien : il n'arrive simplement jamais dans
le navigateur. Le builder ne trouve alors aucun produit alors que tout paraît
parfaitement configuré en back-office. Le module surcharge donc cette liste, et
un test l'épingle — parce que cette panne-là est silencieuse.

## 3. Ce que fait le dialogue « Copies et impressions »

La grille est celle de l'affiche du comptoir (2026-10-29) : service
(photocopie / impression), **papier** (normal, A5, Bristol, autocollant, glacé,
luxe, photo), couleur, faces. Il n'y a pas d'A3.

- Il résout **un** produit et ajoute une ligne de commande ordinaire ; la
  quantité est le nombre de copies. « Ajouter un autre document » valide la
  ligne et réarme le formulaire. **Il n'y a pas de modèle de travail** : la
  commande *est* le travail (un client arrive, demande ses copies, paie, part).
- Une dimension qu'un produit laisse vide **n'est pas demandée** pour lui :
  l'autocollant, le glacé, le luxe et la photo n'ont pas de couleur.
- Un choix qu'aucun produit n'offre avec les autres choix est **grisé**.

### Le prix au-delà de 20 pages

Règle de Mohamed (2026-10-29) : les pages d'**impression N&B sur papier
normal** s'additionnent sur **toute la commande** ; au-delà de 20, **toutes**
ces pages passent au prix réduit (8 DA recto, 10 DA recto-verso). Un
recto-verso compte deux pages : 11 feuilles suffisent. **La couleur et les
photocopies n'ont jamais de remise**, et leurs pages ne comptent pas.

Une liste de prix Odoo ne sait pas le dire (sa quantité minimale se lit ligne
par ligne). `static/src/app/copy_bulk_pricing.js` porte la règle, en fonctions
pures ; `pos_order_patch.js` la rejoue à chaque ajout, changement de quantité
ou suppression de ligne, dans les deux sens. **La caisse ne calcule aucun
prix** : elle choisit entre les deux prix stockés sur le produit (`list_price`
et `copy_bulk_price`). Un prix saisi à la main par le caissier n'est jamais
touché.

## 4. Le papier sort du stock

Chaque produit dit ce qu'il consomme : `copy_paper_product_id` (l'article
papier, un par type, toutes marques confondues) et `copy_sheets_per_unit`
(1 pour une copie, recto-verso compris ; 500 pour la rame vendue telle quelle).

À la création des transferts de caisse (vente en temps réel **ou** clôture de
session, même porte d'entrée), `stock_picking.py` ajoute un transfert du papier
depuis l'emplacement de la caisse :

| Ligne | Destination |
|---|---|
| copie ou impression | « Consommation Copy Center » (une par société, créée au premier besoin) |
| rame vendue au comptoir | le client, comme toute vente |
| remboursement | rien : les feuilles ont été imprimées |

Une validation qui échoue ne bloque jamais la vente (même règle que le cœur).
Le papier s'achète à la rame : unité « Rame (500 feuilles) ».
Où le voir : **Inventaire › Rapports › Consommation de papier** (par papier et
par semaine), et le stock de l'article papier. L'écart au comptage est la
gâche.

## 5. Quand ça refuse

| Situation | Comportement |
|---|---|
| combinaison inexistante | le choix est grisé ; « No such copy » reste le dernier recours d'un catalogue incomplet |
| produit sans prix | refus d'ajouter la ligne ; un zéro donnerait les copies |
| aucun produit de copie sur cette caisse | le bouton n'apparaît que sur une caisse Copy Center |

## 6. Peupler une base

1. Catalogue : `tools/convertir_listes_seed.py` puis `tools/import_seed_catalogue.py`
   (il crée les articles papier issus de la fusion Copy Center,
   `tools/fusion_copy_center.py`).
2. Services : `tools/seed_copy_products.py` lit `tools/seed/copy_services.csv`
   (16 services + la rame), relie chacun à son papier ; il s'arrête si un papier
   manque.

```bash
docker compose run --rm -T odoo odoo shell -d <base> --no-http < tools/seed_copy_products.py
```

## 7. Tests

Les tests Python couvrent les champs, la liste blanche POS, la règle du MDM et
la sortie du papier (vente, clôture de session, rame, remboursement, stock
négatif, emplacement par société, réception à la rame).

Quatre tours POS (`his_copy_job_tour`, `his_copy_job_missing_tour`,
`his_copy_bulk_tour`, `his_copy_bulk_duplex_tour`) couvrent le dialogue et la
remise. **Ils ne s'exécutent pas dans l'image `odoo:19.0`** (ni navigateur ni
`websocket-client`) : ils sont *skipped*, et un test ignoré n'est pas un test
réussi. Le 2026-10-29 les six cas de la remise ont été rejoués dans Chrome.

```bash
docker compose run --rm -T odoo odoo -d <base> -u his_pos_copy_center     --test-enable --test-tags /his_pos_copy_center --stop-after-init
```
