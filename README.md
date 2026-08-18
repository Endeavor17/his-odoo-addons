# his-odoo-addons

Modules Odoo 19.0 Community développés pour le **Groupe HIS-HTC-IRA**.

Ce dépôt ne contient **que les modules custom**. Odoo lui-même n'est pas
versionné ici : il est fourni par l'image Docker officielle `odoo:19.0`. Il n'y
a donc aucun fork du code source Odoo à maintenir.

## Modules

| Module | Domaine | État |
|---|---|---|
| [`his_stock_mdm`](his_stock_mdm/) | Stock / Inventaire / POS — gouvernance du catalogue produit, multi-points de vente, valorisation, pertes | Développé, 20 tests |
| [`his_person_core`](his_person_core/) | Socle Identité — fiche personne et matricule institutionnel unique, tous types de personnes | Développé, 13 tests |
| [`his_hr_base`](his_hr_base/) | Socle RH — rattache `hr.employee` au référentiel Personnes, reprise des matricules existants | Développé, 12 tests |
| [`his_person_sync_sheets`](his_person_sync_sheets/) | Import — export Google Sheets (Sales/Admission) vers le référentiel Personnes | Développé, 17 tests |
| [`maintenance_university`](maintenance_university/) | Maintenance universitaire — demandes, inspections, constats, tableau de bord | Développé ; ne possède plus le matricule (v19.0.2.0.0) |
| _(à venir)_ | Achats | Autre intervenant |
| _(à venir)_ | Point de Vente avancé | Autre intervenant |
| _(à venir)_ | Carte RFID, portefeuille repas, Restaurant, Copy Center | Autre intervenant, s'appuie sur `his_person_core` |

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
docker compose run --rm -T odoo odoo shell -d <base> --no-http < tools/seed_categories.py
docker compose run --rm odoo odoo -d <base> -i his_stock_mdm --stop-after-init
```

Sur la base de production, les catégories existent déjà : seule la seconde
commande est nécessaire.

### Socle Identité — séquencement obligatoire

Les deux nouveaux modules d'identité s'installent et `maintenance_university`
se met à jour dans la **même commande** :

```bash
docker compose run --rm odoo odoo -d <base> \
  -i his_person_core,his_hr_base -u maintenance_university --stop-after-init
```

**Ne pas** installer puis mettre à jour en deux commandes séparées contre une
base réelle : Odoo doit résoudre le graphe de dépendances en une passe, sinon
s'ouvre une fenêtre où deux définitions du champ `matricule_institutionnel`
coexistent. `his_hr_base` capture les matricules déjà attribués avant de
redéfinir le champ, puis les rattache à des fiches `his.person` portant
exactement la même valeur (cf. [`his_hr_base/README.md`](his_hr_base/README.md)).

Migration **à un coup sur un identifiant à vie** : la répéter d'abord contre une
copie de la base de production. Il n'y a pas de retour arrière propre si elle se
passe mal sur des matricules déjà distribués.

`his_person_sync_sheets` s'installe séparément, quand il est utile :

```bash
docker compose run --rm odoo odoo -d <base> -i his_person_sync_sheets --stop-after-init
```

## Lancer les tests

```bash
docker compose run --rm odoo odoo -d <base> -u his_stock_mdm \
  --test-enable --test-tags /his_stock_mdm --stop-after-init
```

> Utilisez `docker compose run --rm`, **pas** `exec` : le service `odoo` publie
> déjà le port 8069, et une seconde instance lancée dans le même conteneur
> échouerait sur `Address already in use` (`--no-http` ne suffit pas en 19.0).
> `run --rm` démarre un conteneur jetable sans port publié.

## Branches

- `main` — base commune, socle du dépôt.
- `inventory` — module Stock/Inventaire/POS (`his_stock_mdm`).
- `maintenance` — module Maintenance universitaire (`maintenance_university`).
- `feature/his-person-identity-foundation` — socle Identité (`his_person_core`,
  `his_hr_base`, `his_person_sync_sheets`) et correction de
  `maintenance_university`, partie de `maintenance`.
- Les autres chantiers (Achats, POS avancé) partent de `main` sur leur propre
  branche et fusionnent dans `main`.

## Convention de contribution

Les règles de gouvernance sont appliquées par des **contraintes serveur**
(`@api.constrains`, surcharges `create`/`write`), jamais par de la validation
côté vue : une règle contournable par import ou par API n'est pas une règle.
La configuration (catégories, attributs, emplacements, motifs) est chargée en
**données XML versionnées**, jamais saisie à la main dans l'UI.
