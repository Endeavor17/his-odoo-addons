# his_pos_copy_center — Composition d'un travail de copie

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

Donc **A4 N&B Recto et A3 Couleur Recto-verso sont deux produits**, chacun avec
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

## 3. Ce que fait le dialogue, et ce qu'il ne fait pas

Il résout **un** produit à partir des quatre choix et appelle
`addLineToCurrentOrder`, exactement comme un clic sur une vignette produit. La
quantité est le nombre de copies.

**Il lit un prix, il n'en calcule aucun.** Le montant affiché est celui du
produit déjà chargé par le POS : un aperçu de ce que dira la ligne de commande,
pas un calcul. Si les deux pouvaient diverger, le prix aurait deux sources de
vérité dont l'une serait du JavaScript — précisément l'erreur que
`his_meal_management` documente avoir évitée pour les crédits.

« Ajouter un autre document » valide la ligne courante et réarme le formulaire :
un travail de cinq documents fait cinq lignes de commande ordinaires. **Il n'y a
pas de modèle de travail** ; la commande *est* le travail, et elle s'imprime, se
rembourse et se reporte déjà. Un commentaire `ponytail:` porte la décision : un
`his.copy.job` s'ajoutera le jour où un travail multi-documents enregistré et
référencé sera un vrai besoin.

Bureautique, Flexy et Scan restent des vignettes ordinaires : aucune dimension
ne justifie un écran.

## 4. Quand ça refuse

| Situation | Comportement |
|---|---|
| aucun produit pour la combinaison | fenêtre nommant la combinaison manquante — c'est une lacune du catalogue, pas une erreur de caisse, et le message le dit |
| produit sans prix | refus d'ajouter la ligne ; un zéro donnerait les copies |
| aucun produit de copie sur cette caisse | le bouton n'apparaît pas, plutôt que d'ouvrir un formulaire vide |

## 5. Essayer

Les catégories Copy sont vides sur une base neuve, donc le bouton reste caché.
Pour peupler une base de développement :

```bash
docker compose run --rm -T odoo odoo shell -d <base> --no-http \
    < tools/seed_copy_products.py
```

Le script crée les huit combinaisons de photocopie et thématise la caisse Copy
Center. Les prix y sont des exemples : **le vrai catalogue appartient au MDM.**

## 6. Tests

Cinq tests Python couvrent les champs, la liste blanche POS et la règle du MDM.

Deux tours POS (`his_copy_job_tour`, `his_copy_job_missing_tour`) couvrent le
chemin nominal et le refus. **Ils ne s'exécutent pas dans l'image `odoo:19.0`
telle quelle** : les tours `HttpCase` exigent `websocket-client` et un
navigateur, absents de l'image. Sur un environnement qui les fournit :

```bash
docker compose run --rm -T odoo odoo -d <base> -u his_pos_copy_center \
    --test-enable --test-tags /his_pos_copy_center --stop-after-init
```

Sans navigateur, ces deux tests sont *skipped* — et un test ignoré n'est pas un
test réussi.
