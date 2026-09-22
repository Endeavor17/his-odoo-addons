# Fiches de réapprovisionnement — notice de remplissage

> **Cafétéria : fiche remplacée le 2026-09-21.** Faute de retour des
> responsables, les niveaux de départ sont imposés par famille par
> `tools/seed_reappro_cafeteria.py` (649 règles sur `his_dev`, famille « Divers »
> exclue). La fiche Cafétéria ne sert plus qu'à transmettre une correction si un
> responsable envoie un jour des chiffres ; on corrige alors dans l'écran
> Réapprovisionnement (procédure dans le README de `his_stock_mdm`). Les fiches
> Restaurant et Copy Center restent le canal prévu.

Un fichier par point de vente, à faire remplir par son responsable :

| Fichier | Point de vente | Articles |
|---|---|---|
| `reappro_cafeteria.csv` | Cafétéria | 75 |
| `reappro_restaurant.csv` | Restaurant | 135 |
| `reappro_copy_center.csv` | Copy Center | 129 |

Généré par `tools/generer_fiches_reappro.py`. Les 9 articles Ménage & Nettoyage
n'y sont pas : ils sont consommés sur tout le campus, pas vendus par une caisse,
et restent au stock central tant que personne n'a tranché qui en est responsable.

## Ce qu'on demande au responsable

Trois colonnes, dans cet ordre de priorité :

- **`Stocker_ici_ON`** — pré-rempli à `O`. Mettre `N` pour tout article qui n'a
  rien à faire dans ce point de vente. C'est la colonne la plus utile : elle
  élague la liste avant qu'on chiffre quoi que ce soit.
- **`Conso_Hebdo_Estimee`** — combien on en consomme en une semaine normale, dans
  l'unité de l'article (kg, litre, pièce). **C'est la seule vraie question.** Un
  responsable sait répondre à « combien j'en passe par semaine » ; il ne sait pas
  répondre à « quel est mon stock minimum ». Laisser vide si on ne sait pas
  encore : mieux vaut un blanc qu'un chiffre inventé.
- **`Commentaire`** — saisonnalité, article de dépannage, contrainte de
  péremption, fournisseur unique… tout ce qui explique un chiffre inhabituel.

`Niveau_Min` et `Niveau_Cible` sont **facultatifs** : on les calcule à partir de
la consommation hebdomadaire. Ne les remplir que pour forcer une valeur qu'on
sait juste.

## Colonnes à ne pas toucher

`Reference` (INV-…), `Article`, `Categorie`. La référence est ce qui permet de
réinjecter le fichier dans Odoo — si elle est modifiée, la ligne est perdue.

## `Conditionnement`

Simple aide à la saisie, extraite du nom de l'article (`C/10` = carton de 10,
`F/12` = fardeau de 12, `BT25` = boîte de 25). Un niveau cible de 7 quand le
carton en contient 12 donne des commandes iningérables : arrondir au
conditionnement. La colonne est indicative, elle n'est pas toujours détectée.

## Comment les niveaux seront calculés

À partir de la consommation hebdomadaire, avec une couverture par famille :

| Famille | Couverture | Pourquoi |
|---|---|---|
| Viandes, produits laitiers, fruits & légumes | 2–3 jours | Périssable, lot + péremption |
| Boissons, chocolat, biscuits, snacks | 1 semaine | Non périssable, rotation rapide |
| Emballage, épices, alimentaire sec | 2 semaines | Non périssable, rotation lente |
| Articles bureautique | 1 mois | Consommation régulière et faible |

`Niveau_Min` = consommation sur la période de couverture.
`Niveau_Cible` = `Niveau_Min` + une période de réassort, arrondi au conditionnement.

## Après remplissage

Les fichiers deviennent des règles `stock.warehouse.orderpoint` (Inventaire ▸
Opérations ▸ Réapprovisionnement), une par article et par emplacement
(`WH/Stock/Cafétéria`, `WH/Stock/Restaurant`, `WH/Stock/Copy Center` — créés par
`his_stock_mdm`). À partir de là, Odoo propose les transferts internes tout seul,
chaque jour : le magasinier exécute une liste, il n'arbitre plus des demandes.

**Ces chiffres sont une première estimation, pas un engagement.** Ils seront
faux, et c'est normal : personne n'a encore de données de vente. On les corrige
après 3–4 semaines de ventes réelles, quand le POS aura produit de l'historique.
Le but du premier tour est d'arrêter les ruptures, pas d'optimiser le stock.

## Régénérer

Après tout ajout au catalogue (la liste biscuits attendue) :

```
docker compose exec -T odoo odoo shell -c /etc/odoo/odoo.conf -d his_dev \
    --no-http < tools/generer_fiches_reappro.py
```

Les fichiers sont réécrits à neuf : **recopier les colonnes déjà remplies avant
de relancer**, sinon la saisie des responsables est perdue.
