# his_admission — le classeur Admissions devient un module

Remplace le classeur Excel de suivi des admissions : 9 feuilles, 55 colonnes,
~152 dossiers réels.

Le module reproduit l'expérience de travail actuelle **sans reprendre ses
défauts**. Les trois principaux sont documentés plus bas, chacun avec la règle
qui le ferme.

## Le dossier d'admission EST l'engagement

Pas de modèle « dossier » supplémentaire. `his.engagement`
([`his_person_core`](../his_person_core/)) porte déjà le parcours daté d'une
personne ; le dossier d'admission n'est que ce parcours vu par le back-office.

Ce n'est pas une économie de code. Le classeur rangeait **`Re-Registration`
parmi les statuts**, à côté de `Admis` et `Inscrit` — or une réinscription n'est
pas un état, c'est un second parcours sur la même personne et le même matricule.
Le module sépare donc les deux axes :

| Axe | Valeurs |
|---|---|
| `etat` | `prospect` → `candidat_soumis` → `admis` → `inscrit`, plus `blocage_administratif` et `abandonne` |
| `type_inscription` | `nouveau` / `reinscription` |

`admis` et `blocage_administratif` sont ajoutés par `selection_add`, sans
toucher `his_person_core`.

## Les trois défauts du classeur, et ce qui les ferme

### 1. Des cases vides sur des dossiers marqués « Inscrit »

Le classeur portait 21 colonnes à cocher. Rien n'obligeait à les remplir : des
dossiers y sont marqués Inscrit avec des pièces restées à `False`.

`@api.constrains` refuse le passage à **`inscrit`** tant qu'une pièce
obligatoire manque ou qu'un droit n'est pas encaissé. Contrainte serveur, pas
règle de vue — même discipline que le verrou d'approbation de
[`his_crm_pipeline`](../his_crm_pipeline/) et que la gouvernance de
`his_stock_mdm`. Une règle contournable par import ou par API n'est pas une
règle.

`admis` n'exige rien : le verrou porte sur l'inscription, pas sur l'admission.

### 2. « Pas encore reçu » et « pas concerné » s'écrivaient pareil

Une case vide pouvait signifier les deux, et personne ne pouvait dire laquelle.
Un dossier en équivalence n'a pas de relevé BAC — sa case restait donc vide à
jamais, indistinguable d'un document réellement manquant.

`his.document.type` porte l'**applicabilité** en donnée : `cycle`,
`type_inscription`, `bac_filiere`. Un critère vide signifie « quelle que soit la
valeur ». La ligne n'existe sur le dossier que si la pièce le concerne
vraiment.

Ouvrir ou fermer une pièce est de la **configuration**, pas une migration de
schéma.

Trois doublons ont été retirés au passage : le relevé BAC (colonnes 34 et 46),
la photo (36 et 49) et le relevé universitaire (37 et 48) y figuraient deux
fois. Le classeur a grandi par ajout de colonnes sans nettoyage ; garder les
doublons aurait figé la confusion dans le schéma.

Les lignes sont **ajoutées, jamais supprimées**. Une pièce déjà cochée garde sa
trace même si le dossier change de cycle : effacer la ligne effacerait la preuve
qu'un document a réellement été reçu.

### 3. Une formule d'éligibilité recopiée à la main — et fausse

La feuille `CALCULATEUR` calculait la moyenne pondérée par domaine :

```
MI : (BAC × 2 + Math) / 3          seuil 11
ST : (BAC × 2 + Math + Phys) / 4   seuil 11
```

**La branche ST était buguée.** Sa cellule `C20` compare `D18` — une cellule de
*texte* — au lieu de `C18` qui porte la moyenne. Excel juge tout texte supérieur
à tout nombre : cette branche répondait `ELIGIBLE` **quelle que soit la
moyenne**, et un dossier sous le seuil passait sans que personne le voie. Un
test reproduit le cas et vérifie qu'on répond `a_verifier`.

`moyenne_ponderee` et `eligibilite` sont **calculés**, jamais saisis. Le barème
vit sur `his.domaine` : coefficients BAC / maths / physique, seuil, planchers.
Un coefficient à zéro retire simplement la note du calcul.

> **Les planchers de note ne sont pas renseignés**, délibérément. Le classeur
> annote « Bac = 10, Math = 12/20 » et « Math = 10/20 » en face de G.E et
> SE+M+MT — mais son propre exemple MI (BAC 13,37 / Math 8,5) est déclaré
> ELIGIBLE, alors que 8,5 tomberait sous les deux planchers. Ces annotations
> désignent donc vraisemblablement des filières BAC d'origine, pas des domaines
> visés. Le mécanisme existe et il est testé ; seules les valeurs sont à zéro,
> donc sans effet. Les renseigner est une saisie, pas une livraison.

## Où vit quelle donnée

| Donnée | Modèle | Pourquoi |
|---|---|---|
| Nom, email, téléphone, matricule | `his.person` | L'identité, à vie |
| État civil, **parents et tuteur** | `his.person` | Les parents ne changent pas d'une réinscription à l'autre. Le classeur les recopiait sur chaque ligne, avec la divergence que toute recopie finit par produire |
| Cursus, notes, pièces, droits, carte | `his.engagement` | Propres au parcours |
| Barèmes, spécialités, pièces | Configuration XML | Jamais saisis à la main |

`numero_etudiant` est un champ **libre**. Ils numérotent aujourd'hui en
`260511001` (année + filière + spécialité + séquence) ; rien n'est vérifié ni
imposé. Le matricule institutionnel du groupe vit sur `his.person` et prendra le
relais plus tard — décision prise, pas oubli.

## Les 6 feuilles secondaires

Aucune ne devient un modèle : ce sont des **vues** de la même ligne
d'admission, avec des colonnes différentes pour des destinataires différents.
Un modèle par feuille aurait créé six copies à tenir en phase — exactement le
problème du classeur, où corriger un numéro de téléphone demandait de le faire
dans quatre onglets.

| Menu | Remplace | Filtre |
|---|---|---|
| Transmissions › Pédagogie | `Pedagogie n` | Admis et inscrits |
| Transmissions › Ministère | `mers` | Inscrits |
| Transmissions › Service national | `الخدمة الوطنية` | Inscrits **de sexe masculin** |
| Cartes étudiant | `carte etudiant` | Inscrits |
| Suivi des droits | `finance 26-27` | Admis, inscrits, bloqués |
| Parents et tuteurs | `PARENTS` | Étudiants et candidats |

L'export XLSX natif (sélection → Exporter) rend le fichier attendu par chaque
destinataire. `analytique` devient un simple regroupement pivot état × cycle sur
la vue Dossiers.

## Accès

Groupe **Admission** — seul à pouvoir écrire un dossier, avec son propre menu.
L'unité Admission est distincte des Ventes, le BPMN la pose ainsi et c'est elle
qui coche « frais payés » et « contrat signé ».

Les conseillères Ventes ont un accès **lecture seule** et ouvrent le dossier de
leur candidat depuis le lead. Elles répondent à ses questions sans pouvoir
valider à la place du back-office. Un test le vérifie.

## Raccord au CRM

Le pont d'identité ([`his_crm_identity_bridge`](../his_crm_identity_bridge/))
crée l'engagement à `prospect` au premier contact commercial. Quand le lead
atteint « Pré-admis », ce module le fait passer à **`admis`** et reprend la
conseillère qui a amené le candidat.

Un dossier déjà instruit ne redescend pas : repasser par « Pré-admis » après une
inscription ne défait pas le travail de l'Admission.

## Hors périmètre (assumé)

- **Les montants.** Payé / non payé seulement, comme le classeur. La caisse
  encaisse dans son propre outil, l'Admission coche. Le jour où les montants
  comptent, c'est un chantier `account`, pas trois champs de plus ici.
- **L'alimentation depuis le formulaire public.** Elle viendra par n8n. Les
  champs existent et sont écrivables par API ; rien n'est câblé.
- Édition de documents (lettres d'acceptation, attestations) : les jalons sont
  suivis, les documents ne sont pas générés.
- Soutenances et fin de cursus.

## Installation

```bash
docker compose run --rm odoo odoo -d <base> -i his_admission --stop-after-init
```

**Avant la mise en service** : relire les barèmes des domaines (A7) et le
caractère obligatoire de chaque pièce (A8) — les deux sont déduits du classeur,
aucun document de référence ne les fixe. Une pièce marquée obligatoire à tort
bloque une inscription réelle.

## Lancer les tests

```bash
docker compose stop odoo
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker compose run --rm odoo odoo \
  -d <base_test> --without-demo=all -i his_admission \
  --test-enable --test-tags /his_admission --stop-after-init
```
