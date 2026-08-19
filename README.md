# his-odoo-addons

Modules Odoo 19.0 Community développés pour le **Groupe HIS-HTC-IRA**.

Ce dépôt ne contient **que les modules custom**. Odoo lui-même n'est pas
versionné ici : il est fourni par l'image Docker officielle `odoo:19.0`. Il n'y
a donc aucun fork du code source Odoo à maintenir.

## Modules

| Module | Domaine | État |
|---|---|---|
| [`his_stock_mdm`](his_stock_mdm/) | Stock / Inventaire / POS — gouvernance du catalogue produit, multi-points de vente, valorisation, pertes | Développé, 20 tests |
| [`his_person_core`](his_person_core/) | Socle Identité — fiche personne et matricule institutionnel unique, délégué à `res.partner` | Développé, 13 tests |
| [`his_hr_base`](his_hr_base/) | Socle RH — rattache `hr.employee` au référentiel Personnes, reprise des matricules et réutilisation des contacts | Développé, 16 tests |
| [`his_person_sync_sheets`](his_person_sync_sheets/) | Import — export Google Sheets (Sales/Admission) vers le référentiel Personnes | Développé, 19 tests |
| [`his_meal_management`](his_meal_management/) | Carte RFID, portefeuille repas, Restaurant — cartes étudiants et crédits repas prépayés consommés en caisse | Développé, 45 tests |
| [`maintenance_university`](maintenance_university/) | Maintenance universitaire — demandes, inspections, constats, tableau de bord | Développé ; ne possède plus le matricule (v19.0.2.0.0) |
| _(à venir)_ | Achats | Autre intervenant |
| _(à venir)_ | Point de Vente avancé | Autre intervenant |

Chaque module documente ses propres règles et écarts assumés dans son
`README.md`, à l'exception de `his_meal_management` et
`maintenance_university`, qui se documentent pour l'instant via leur
`__manifest__.py` et les commentaires du code.

## Démarrer l'environnement

Prérequis : Docker Desktop.

```bash
docker compose up -d
```

Odoo écoute sur **http://localhost:8072** (le port 8069 est déjà occupé par un
autre conteneur sur le poste de développement, cf. `docker-compose.yml` : le
mapping est `8072:8069`, Odoo écoute toujours sur 8069 *dans* le conteneur).
Le dépôt est monté dans le conteneur
comme répertoire d'addons supplémentaires, donc **toute modification du code
Python est prise en compte après un simple redémarrage** :

```bash
docker compose restart odoo
```

Une modification de vues ou de données XML exige en revanche une mise à jour du
module (`-u`, cf. plus bas) : un redémarrage seul ne recharge pas les fichiers
de données.

## Base de travail

La base de recette s'appelle **`his`** : elle porte les trois modules installés
et les données de démonstration (points de vente configurés, cartes réelles,
historique de crédits repas, tournées de maintenance).

Elle provient d'un ancien poste de travail séparé (`D:\Point_of_sell`, base
`meal_credits`, port 8071) qui ne contenait que `his_meal_management`. Ce poste
a été **retiré** : son code faisait doublon avec celui de ce dépôt. Ses volumes
Docker sont conservés en l'état comme filet de sécurité, mais **ce dépôt est
désormais l'unique source de vérité du code**.

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

`his_meal_management` n'a aucun prérequis de données ; il dépend en revanche du
socle Identité, qui doit donc être installé avant lui :

```bash
docker compose run --rm odoo odoo -d <base> -i his_meal_management --stop-after-init
```

> `maintenance_university` **désactive deux règles d'enregistrement du module
> Maintenance natif** dans son `post_init_hook`, et retire Discuss / Employés /
> Paramètres de la barre d'applications pour tout utilisateur interne qui n'est
> pas Manager de maintenance. C'est délibéré et documenté dans le module, mais
> c'est un effet de bord qui dépasse ses propres utilisateurs.

## Lancer les tests

```bash
docker compose run --rm odoo odoo -d <base> -u his_stock_mdm \
  --test-enable --test-tags /his_stock_mdm --stop-after-init

docker compose run --rm odoo odoo -d <base> -u his_meal_management \
  --test-enable --test-tags /his_meal_management --stop-after-init
```

Lancez-les de préférence sur une base jetable plutôt que sur `his` : les
séquences PostgreSQL ne sont pas transactionnelles, une campagne de tests
consomme donc des numéros `INV-` réels.

> Utilisez `docker compose run --rm`, **pas** `exec` : le conteneur `odoo` déjà
> lancé occupe le port 8069 en interne, et une seconde instance dans le même
> conteneur échouerait sur `Address already in use` (`--no-http` ne suffit pas
> en 19.0). `run --rm` démarre un conteneur jetable sans port publié.

## Branches

- `main` — base commune, socle du dépôt.
- `inventory` — module Stock/Inventaire/POS (`his_stock_mdm`).
- `maintenance` — module Maintenance universitaire (`maintenance_university`).
- `identity` — socle Identité (`his_person_core`,
  `his_hr_base`, `his_person_sync_sheets`) et correction de
  `maintenance_university`, partie de `maintenance`.
- `meal` — carte RFID et portefeuille repas (`his_meal_management`).
- Les autres chantiers (Achats, POS avancé) partent de `main` sur leur propre
  branche et fusionnent dans `main`.

## Convention de contribution

Les règles de gouvernance sont appliquées par des **contraintes serveur**
(`@api.constrains`, surcharges `create`/`write`), jamais par de la validation
côté vue : une règle contournable par import ou par API n'est pas une règle.
La configuration (catégories, attributs, emplacements, motifs) est chargée en
**données XML versionnées**, jamais saisie à la main dans l'UI.
