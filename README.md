# his-odoo-addons

Modules Odoo 19.0 Community développés pour le **Groupe HIS-HTC-IRA**.

Ce dépôt ne contient **que les modules custom**. Odoo lui-même n'est pas
versionné ici : il est fourni par l'image Docker officielle `odoo:19.0`. Il n'y
a donc aucun fork du code source Odoo à maintenir.

## Modules

| Module | Domaine | État |
|---|---|---|
| [`his_stock_mdm`](his_stock_mdm/) | Stock / Inventaire / POS — gouvernance du catalogue produit, multi-points de vente, valorisation, pertes | Développé, 20 tests |
| _(à venir)_ | Achats | Autre intervenant |
| _(à venir)_ | Point de Vente avancé | Autre intervenant |

Chaque module documente ses propres règles et écarts assumés dans son
`README.md`.

## Démarrer l'environnement

Prérequis : Docker Desktop.

```bash
docker compose up -d
```

Odoo écoute sur http://localhost:8069. Le dépôt est monté dans le conteneur
comme répertoire d'addons supplémentaires, donc **toute modification du code
est prise en compte après un simple redémarrage** :

```bash
docker compose restart odoo
```

## Installer un module

`his_stock_mdm` se rattache à une arborescence de catégories qui doit
**déjà exister** en base (il n'en crée aucune, cf. son README). Sur une base de
développement vierge, créez-la d'abord :

```bash
docker compose exec odoo odoo shell -d <base> --no-http < tools/seed_categories.py
docker compose exec odoo odoo -d <base> -i his_stock_mdm --stop-after-init
```

Sur la base de production, les catégories existent déjà : seule la seconde
commande est nécessaire.

## Lancer les tests

```bash
docker compose exec odoo odoo -d <base> -u his_stock_mdm \
  --test-enable --test-tags /his_stock_mdm --stop-after-init
```

## Branches

- `main` — base commune, socle du dépôt.
- `inventory` — module Stock/Inventaire/POS (`his_stock_mdm`).
- Les autres chantiers (Achats, POS avancé) partent de `main` sur leur propre
  branche et fusionnent dans `main`.

## Convention de contribution

Les règles de gouvernance sont appliquées par des **contraintes serveur**
(`@api.constrains`, surcharges `create`/`write`), jamais par de la validation
côté vue : une règle contournable par import ou par API n'est pas une règle.
La configuration (catégories, attributs, emplacements, motifs) est chargée en
**données XML versionnées**, jamais saisie à la main dans l'UI.
