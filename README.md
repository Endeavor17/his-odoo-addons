# his-odoo-addons

Modules Odoo 19.0 Community développés pour le **Groupe HIS-HTC-IRA**.

Ce dépôt contient **les modules custom du Groupe, plus les modules tiers
copiés** dont ils dépendent. Odoo lui-même n'est pas versionné ici : il est
fourni par l'image Docker officielle `odoo:19.0`. Il n'y a donc aucun fork du
code source Odoo à maintenir.

Un module tiers copié porte toujours un `VENDOR.md` donnant son origine, sa
version et le commit exact, parce qu'une copie sans provenance devient un
mystère à la première mise à jour. Le déploiement n'ayant aucune étape de build
(l'image officielle est lancée telle quelle, ce dépôt monté en volume), la copie
est ce qui arrive avec un simple `git pull` — voir `web_responsive/VENDOR.md`.

## Modules

| Module | Domaine | État |
|---|---|---|
| [`his_stock_mdm`](his_stock_mdm/) | Stock / Inventaire / POS — gouvernance du catalogue produit, multi-points de vente, valorisation, pertes | Développé, 20 tests |
| [`his_person_core`](his_person_core/) | Socle Identité — fiche personne et matricule institutionnel unique, délégué à `res.partner` | Développé, 13 tests |
| [`his_hr_base`](his_hr_base/) | Socle RH — rattache `hr.employee` au référentiel Personnes, reprise des matricules et réutilisation des contacts | Développé, 16 tests |
| [`his_person_sync_sheets`](his_person_sync_sheets/) | Import — export Google Sheets (Sales/Admission) vers le référentiel Personnes | Développé, 19 tests |
| [`his_crm_pipeline`](his_crm_pipeline/) | CRM — pipeline Ventes/Admissions et pipeline Production Contenu, cloisonnés par équipe et par étapes (remplace GoHighLevel) | Développé, 16 tests |
| [`his_crm_identity_bridge`](his_crm_identity_bridge/) | Pont CRM → Identité — crée la fiche personne du candidat au premier contact | Développé, 12 tests |
| [`his_admission`](his_admission/) | Admission — dossier candidat, pièces justificatives, éligibilité et transmissions Ministère / service national (remplace le classeur Excel) | Développé, 32 tests |
| [`campus_teacher_management`](campus_teacher_management/) | Recrutement Campus+ — candidatures enseignants, évaluation CAR, classement, entretiens, contrat et tournage | Développé, 129 tests |
| [`insite_recruitment`](insite_recruitment/) | Recrutement InSite — besoin, candidats internes/externes, contrat, intégration, affectation de module ; partage l'identité `academic.person` avec Campus+ | Développé, 22 tests |
| [`maintenance_university`](maintenance_university/) | Maintenance universitaire — demandes, inspections, constats, tableau de bord | Développé ; ne possède plus le matricule (v19.0.2.0.0) |
| [`his_pos_ui`](his_pos_ui/) | POS — habillage partagé des trois caisses, identité par point de vente, ergonomie tactile | Développé, 3 tests |
| [`his_pos_copy_center`](his_pos_copy_center/) | POS Copy Center — composition d'un travail de copie en un seul écran | Développé, 5 tests + 2 tours |
| [`his_web_ui`](his_web_ui/) | Interface web — atterrissage sur la grille d'applications plutôt que sur le premier menu trié | Développé, 3 tests |
| [`web_responsive`](web_responsive/) | **Tiers (OCA)** — grille d'applications plein écran, absente d'Odoo Community | Copié, `19.0.1.1.0` |
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

### CRM — Ventes/Admissions et Production Contenu

`his_crm_pipeline` ne dépend que de `crm` et s'installe seul :

```bash
docker compose run --rm odoo odoo -d <base> -i his_crm_pipeline --stop-after-init
```

Le pont vers le référentiel Personnes est un module distinct, à installer
seulement si le socle Identité est en place :

```bash
docker compose run --rm odoo odoo -d <base> -i his_crm_identity_bridge --stop-after-init
```

Deux menus séparés apparaissent sous CRM — **Admissions** et **Production
Contenu** — chacun filtré sur son équipe.

**Avant la mise en service** : l'équipe Ventes / Admissions est livrée avec Asma
(responsable), Aicha et Rahma ; **si ces personnes ont déjà un compte Odoo,
retirer `data/crm_team_member_data.xml` du manifeste avant d'installer**, sinon
des comptes en double sont créés. Les membres de la Cellule d'Orientation et de
Production Contenu restent à renseigner. La visibilité des leads et les relances
SLA dépendent de ces appartenances, cf.
[`his_crm_pipeline/README.md`](his_crm_pipeline/README.md).

### Admission — dossier candidat

Le dossier d'admission remplace le classeur Excel de suivi. Il dépend du socle
Identité et du pont CRM :

```bash
docker compose run --rm odoo odoo -d <base> -i his_admission --stop-after-init
```

Un menu **Admission** apparaît, réservé au groupe du même nom : dossiers, suivi
des droits, cartes étudiant, parents et transmissions (Pédagogie, Ministère,
service national). Les conseillères Ventes y ont un accès en lecture seule.

**Avant la mise en service** : relire les barèmes d'éligibilité et le caractère
obligatoire de chaque pièce — les deux sont déduits du classeur, aucun document
de référence ne les fixe, cf.
[`his_admission/README.md`](his_admission/README.md).

### Recrutement — Campus+ et InSite

`insite_recruitment` dépend de `campus_teacher_management` : les deux
s'installent donc en **une seule commande**, Odoo résolvant l'ordre lui-même.

```bash
docker compose run --rm odoo odoo -d <base> \
  -i campus_teacher_management,insite_recruitment --stop-after-init
```

Installer d'abord Campus+ seul puis InSite fonctionne aussi, mais rien ne le
justifie : InSite n'est utilisable qu'avec Campus+ en place.

`campus_teacher_management` tire `hr_recruitment` comme dépendance. Sur une base
où il n'était pas installé, **l'application Recrutement apparaît** avec ses
propres menus, en plus des menus Campus+ — c'est attendu, pas un effet de bord.

Campus+ pose une règle d'enregistrement **globale** sur `hr.applicant` : une
candidature rattachée à un processus Campus+ n'est visible que par les
utilisateurs disposant de la permission `can_view` sur ce processus
(`campus.process.permission`). Les candidatures hors Campus+
(`campus_process_id` vide) restent visibles de tous les recruteurs. À
l'installation, le `post_init_hook` accorde les trois permissions (voir,
exécuter, valider) sur tous les processus à chaque membre du groupe **Campus+ /
Manager**, qui contient `base.user_root` et `base.user_admin` — l'administrateur
ne peut donc pas se verrouiller dehors. Le reste de la matrice se règle ensuite
depuis Configuration > Process Permissions.

**Tout module qui ajoute des `campus.process` doit porter son propre
`post_init_hook`.** Celui de Campus+ s'exécute quand *Campus+* finit de
s'installer : les processus déclarés par un module installé après lui n'existent
pas encore à ce moment-là et n'obtiennent donc aucune permission. La matrice
étant *opt-in* (aucune ligne = refusé, cf.
`campus.process.permission._has_process_permission`), ces processus seraient
fermés à tout le monde sauf au superutilisateur uid 1 — l'administrateur inclus.
C'est pourquoi `insite_recruitment` déclare
`_insite_grant_manager_process_permissions`, qui rappelle le grant de Campus+ ;
celui-ci est idempotent et ne fait que compléter les processus manquants.

Les deux fichiers `data/campus_demo_*.xml` (poste et 5 candidats de
démonstration) ne sont **référencés par aucun manifeste** : ils ne se chargent
pas. C'est délibéré — les charger sèmerait de fausses candidatures dans une base
qui porte les vraies.

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
- `identity` — socle Identité (`his_person_core`,
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
