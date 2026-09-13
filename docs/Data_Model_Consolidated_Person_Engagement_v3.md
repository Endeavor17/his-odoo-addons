# Modèle de Données Personne / Engagement — v3 (état réel de l'implémentation Odoo)

**Statut :** régénéré le 2026-09-13 à partir du code de `his-odoo-addons`
(branche `feature/mdm-recruitment-convergence`, non encore fusionnée dans
`main`). Remplace la v2 « Consolidé + Addendum Odoo ».

**Pourquoi une v3 :** la v2 décrivait une spécification et un addendum
d'intention. Depuis, huit modules ont été construits sur le référentiel
(`his_person_core`, `his_hr_base`, `his_person_sync_sheets`,
`his_crm_identity_bridge`, `his_admission`, `his_meal_management`,
`campus_identity_bridge`, `insite_recruitment`, plus `his_academic_base`). Plusieurs
choix de la v2 ont été tranchés autrement sur preuve. Ce document décrit ce
qui **existe**, et signale chaque écart avec la spécification (repère
**[ÉCART]**) plutôt que de le masquer.

---

## 1. Principes directeurs

| Principe (v2) | État |
|---|---|
| Une personne existe une seule fois | **Tenu.** `his.person` est l'unique fiche ; Campus+, InSite, RH, Admission, import Sheets et Repas écrivent tous dedans. InSite avait créé une identité parallèle (`academic.person`) : supprimée en 19.0.3.0.0. |
| L'engagement est distinct de la personne | **Tenu, mais pas avec un modèle unique** — voir §7 et §8. |
| La création n'implique pas la propriété perpétuelle | **Tenu** par les droits d'accès (§11). |
| Séparation stricte des types de données | **[ÉCART] Partiellement.** `Guardian`, `AcademicBackground` et `Paiement` ne sont pas des entités (§9). |
| Rapprochement jamais automatique au-delà du déterministe | **Tenu.** Un seul algorithme, `his.person._find_or_flag_match` (§10). |
| Le volet Étudiant ne redéfinit pas `Person` | **Tenu.** |

**Principe ajouté — le matricule s'émet à l'engagement irréversible, pas à la
création de la fiche.** Un candidat entre dans le référentiel **sans**
matricule. Raison mesurée : le CRM réel perd 954 opportunités sur 1 558 ; émettre
au premier contact brûlait six numéros à vie sur dix. Voir §2.2.

---

## 2. Entité `Person` → `his.person` (module `his_person_core`)

`his.person` **délègue** à `res.partner` (`_inherits`) : chaque personne porte un
vrai contact Odoo, parce que la carte, le portefeuille repas et le POS
travaillent sur le contact. Contrainte : un contact porte au plus une personne.

| Champ spec (v2) | Champ Odoo | Type | Remarque |
|---|---|---|---|
| `id` | `id` | — | |
| `matricule_institutionnel` | `matricule_institutionnel` | Char, unique, readonly, jamais réémis (garde serveur) | Format §2.1. Vide pour un `candidat`. |
| — | `matricule_affiche` | Char calculé | Le matricule **sans** la clé de contrôle, pour l'écran. Recherche acceptée sous les deux formes. |
| `nom_latin` | `name` (du contact) | Char | |
| `nom_arabe` | `nom_arabe` | Char | |
| `email_institutionnel` | `email` (du contact) | Char | Le contact n'a qu'un email : il porte l'adresse officielle. |
| `email_personnel` | `email_personnel` | Char | Utilisé pour tout candidat externe (CRM, Campus+, InSite). |
| `telephone` | `phone` (du contact) | Char | Odoo 19 n'a plus de `mobile`. |
| `type_personne` | `type_personne` | Sélection : `employe` / `enseignant` / `etudiant` / `candidat` | **[ÉCART]** `employe` ajouté (la v2 l'annonçait comme « future valeur »). Statut courant, pas identité : un candidat devenu étudiant garde fiche et matricule. |
| — | `active` (du contact) | Booléen | Archiver la personne archive son contact. |
| — | `source_system` | Sélection : `odoo_hr` / `google_sheets` / `uniflow` / `manual`, étendue par `odoo_crm` et `campus_plus` | Provenance. |
| — | `external_ref` | Char | Identifiant dans la source ; clé déterministe avec `source_system`. |
| — | `match_method` | `deterministic` / `probabilistic` / `new` | |
| — | `matched_by`, `matched_on` | Utilisateur, Datetime | Audit d'un rapprochement confirmé à la main. |
| — | `numero_carte` | Char, unique | Badge RFID unique (repas, pointage, accès). Voir §9.5. |
| — | `engagement_ids` | One2many `his.engagement` | Parcours étudiant (§8). |

### 2.1 Format du matricule

**`HIS-AAAA-NNNNNN-C`**, ex. `HIS-2026-000042-7`.

- Séquence **unique** du groupe : code `his.person.matricule.institutionnel`,
  plages annuelles, portée exclusivement par `his_person_core`. L'ancienne
  séquence de `maintenance_university` a été retirée.
- `AAAA` : année de la plage. Pour un employé, **année d'entrée**
  (`date_start_working`), pas année de saisie.
- Clé de contrôle `C` : mod 11 sur les 6 chiffres, poids 2 à 7 de droite à
  gauche, reste 10 → `X`. **Stockée et transmise (carte, caisse), masquée à
  l'écran** : l'équipe la trouvait déroutante à la lecture.
- Une valeur reprise d'une source existante est stockée telle quelle, sans
  recalcul de clé ; seule l'unicité s'applique.

> **Décision ouverte (A4 de la v2) :** l'algorithme de la clé a été validé par
> l'équipe projet, **jamais par la Direction ni par Endeavor**. Il est isolé dans
> une seule fonction ; le changer après émission de matricules réels serait une
> migration sur un identifiant à vie.

### 2.2 Quand le matricule est émis

| Parcours | Création de la fiche | Émission du matricule |
|---|---|---|
| Employé (RH) | Création de `hr.employee` → `employe` | **À la création** |
| Étudiant (CRM → Admission) | Lead parvenu à **pré-admission** → `candidat` | **Encaissement des frais d'inscription** (`his.engagement._encaisser`) |
| Étudiant (import Google Sheets) | Ligne importée → `etudiant` | À la création |
| Enseignant Campus+ | Candidature parvenue à **Select** → `candidat` | **Embauche** → `enseignant` |
| Enseignant InSite | Soumission traitée → `candidat` externe | **Signature du contrat** → `enseignant` |

Un matricule soumis par un formulaire externe (InSite) **n'est jamais écrit** :
c'est une clé de recherche.

### 2.3 État civil et famille (ajoutés par `his_admission`)

Portés par la personne, pas par le dossier, parce qu'ils ne changent pas d'une
inscription à l'autre : `genre`, `date_naissance`, `commune_naissance`,
`wilaya_naissance`, `numero_identite`, `date_expiration_identite`, `etat_sante`
(texte libre, volontairement), `adresse_residence`.

> **[ÉCART] à arbitrer :** la v2 justifiait le matricule par « éviter la collecte
> du CNI national ». `numero_identite` est pourtant collecté, repris du classeur
> Admission. Ce n'est pas une contradiction technique, mais c'est une décision de
> conformité (Loi 18-07) qui n'a pas été prise explicitement.

---

## 3. Référentiel `Faculty` → `his.faculty` (module `his_academic_base`)

| Champ | Type |
|---|---|
| `code` | Char, unique (`MI`, `SEGC`, `DSP`, `SHS`, `ST`, `EDU`) |
| `name` | Char traduisible |
| `name_confirmed` | Booléen — `False` pour `EDU`, catalogue jamais reçu |
| `person_ids` | Many2many `his.person` (table `his_faculty_person_rel`) |
| `active` | Booléen |

Relation plusieurs-à-plusieurs, conforme à la v2. Les six facultés sont
semées par `his_meal_management`.

> **[ÉCART] à arbitrer :** l'Admission a son propre référentiel `his.domaine`
> (codes `MI`, `ST`, `SEGC`…, coefficients d'éligibilité) et `his.specialite`.
> Faculté et domaine partagent des codes sans être liés. Deux référentiels pour
> le même découpage finiront par diverger.

---

## 4. Volet Enseignant — champs spécifiques

| Champ spec | Champ Odoo | Remarque |
|---|---|---|
| `rang_academique` | `rang_academique` : `PROF` / `MCA` / `MCB` / `MAA` / `MAB` | Contrainte serveur : **uniquement** sur un `enseignant`. |
| `specialite` | `specialite` | Texte libre. Comparée (égalité) à la spécialité demandée par un besoin InSite pour le classement. |
| `statut` (`actif`/`inactif`/`archive`) | — | **[ÉCART] Non implémenté.** Seul `active` (archivage) existe. |
| — | `is_internal_teacher` : `internal` / `external` | Ajouté par InSite. Posé explicitement, jamais déduit ; une candidature InSite est refusée pour une personne non classée. |
| — | `campus_applicant_ids` | Candidatures Campus+ rattachées (`hr.applicant.his_person_id`). |

---

## 5. Entité `Module` → `campus.subject`

**[ÉCART] Implémentation minimale.** Le catalogue de modules est celui de
Campus+ : `name`, `code`, `level`, `language`. La structure de la v2 (Tronc
commun → Année → Semestre → Unité d'enseignement → Module, `type_unite`,
`decret_ref`, `eligible_campus_plus`) n'existe pas.

Limite mesurée : sur 1 204 lignes de matières des candidatures Campus+, **624
sont en texte libre** et ne pointent aucun module.

## 6. Entité `AcademicPeriod` → `academic.period`

`name`, `date_start`, `date_end`, `active`.

**[ÉCART]** ni `semestre` ni `piste_calendrier`.

---

## 7. Engagement — volet Enseignant

**[ÉCART] majeur : il n'y a pas un modèle `Engagement` enseignant, mais un
parcours par processus.** La v2 prévoyait un seul `Engagement` avec
`source = candidature_spontanee / sollicitation_institution`. Le code a gardé
les deux processus métier séparés, reliés par la même personne.

### 7.1 Campus+ (candidature spontanée) — `hr.applicant`

La candidature Odoo **est** le parcours. Pas de `his.engagement` : ses états
(prospect → inscrit) décrivent une admission étudiante.

`campus_hiring_state` : `not_selected` → `invited` (Select) → `meeting_1` →
`interview1_completed` → … → `subjects_selected` → `hired`.

- À `invited` (paramètre `campus_identity.trigger_state`, comparaison « parvenu
  à », pas « égal à ») : rapprochement et fiche `candidat`.
- À `hired` : l'employé créé reprend cette fiche, qui passe `enseignant` et
  reçoit son matricule.

### 7.2 InSite (sollicitation) — quatre modèles

| Modèle | Rôle | États |
|---|---|---|
| `insite.recruitment.need` | Le besoin : module, période, volume horaire, spécialité requise | `need` → recherche interne → recherche externe → … → `signed` → intégration → `module_assigned` → `published` / `cancelled` / `closed` |
| `insite.candidature` | Une personne tentée sur un besoin | `prospect` / `contacted` / `accepted` / `declined` / `superseded` |
| `insite.contract` | Le contrat | `draft` → `prepared` → `sent` → `accepted` → `signed` (+ `signature_date`) / `rejected` |
| `academic.engagement` | **L'assignation** personne × module × période | `draft` / `confirmed` / `active` / `completed` / `cancelled` ; `process` = `campus` / `insite` |

### 7.3 Correspondance avec les états de la v2

| État v2 | Réalité |
|---|---|
| `prospect` | Campus+ `not_selected` ; InSite candidature `prospect` |
| `candidat_actif` | Campus+ `invited` → `subjects_selected` ; InSite `contacted` / `accepted` |
| `sous_contrat` | Campus+ contrat joint ; InSite contrat `signed` |
| `actif` | `academic.engagement` `active` |
| `termine` | `academic.engagement` `completed` |
| `refuse` / `poste_non_pourvu` | InSite `declined`, contrat `rejected`, besoin `cancelled` |

> **Décision ouverte (v2 §12) :** personne déjà `actif` qui recandidate — non
> tranchée, rien ne la bloque aujourd'hui.

---

## 8. Engagement — volet Étudiant → `his.engagement`

Le **dossier d'admission est l'engagement**, pas un modèle de plus. Une
réinscription est un **second engagement** sur la même personne et le même
matricule (le classeur la rangeait à tort parmi les statuts).

### 8.1 États

| État | Déclencheur implémenté | Écart v2 |
|---|---|---|
| `prospect` | Lead CRM parvenu à pré-admission | Déclencheur v2 : « transmission Marketing ». Déplacé sur preuve (954 perdues / 1 558). |
| `candidat_soumis` | Transition Admission | |
| `admis` | Vérification Admission | |
| `blocage_administratif` | Dossier bloqué, candidat toujours intéressé | **Ajouté** (arrêt ≠ abandon) |
| `inscrit` | Inscription définitive ; exige frais d'inscription **et** de scolarité encaissés | |
| `abandonne` | Sortie | Remplace `refuse` / `rejet_paiement` |

**[ÉCART]** `candidat_valide`, `actif`, `termine` n'existent pas : rien n'est
implémenté après l'inscription (Pédagogie, soutenance).

### 8.2 Champs du dossier

- **Parcours :** `type_inscription` (`nouveau` / `reinscription`), `cycle`,
  `niveau` (L1…M2), `specialite_id`, `domaine_id`, `programme_qualifiant`,
  `langue_etude`, `numero_etudiant` (numéro libre actuel de l'Admission, distinct
  du matricule), `date_inscription`.
- **BAC et éligibilité :** `bac_numero`, `bac_session`, `bac_filiere`,
  `bac_moyenne`, `note_math`, `note_physique`, `type_lycee` ; `moyenne_ponderee`
  et `eligibilite` calculées depuis les coefficients de `his.domaine`.
- **Étapes :** `inscription_initiale`, `lettre_acceptation`,
  `inscription_definitive`, `lettre_definitive`.
- **Carte étudiant :** `carte_recue_it`, `carte_etudiant_informe`,
  `carte_date_remise`.
- **Origine :** `conseiller_id`, `lead_id`.

---

## 9. Entités spécifiques au volet Étudiant

### 9.1 `AcademicBackground` — **[ÉCART] non implémenté comme entité**

Les données BAC sont portées par l'engagement (§8.2). Pas d'université
d'origine pour un transfert.

### 9.2 `Guardian` — **[ÉCART] aplati sur la personne**

La v2 demandait une relation un-à-plusieurs. Le code porte des champs fixes
sur `his.person` : `pere_nom`, `pere_profession`, `pere_telephone`,
`pere_email`, `mere_nom`, `mere_prenom`, `mere_profession`, `tuteur_nom`,
`tuteur_relation`, `tuteur_telephone`, `tuteur_email`, `tuteur_adresse`.
Conséquence : un seul tuteur ; pas de `adresse_identique_etudiant`.

### 9.3 `Paiement` — **[ÉCART] trois booléens, pas une entité**

`frais_inscription_payes`, `frais_scolarite_payes`,
`droits_prog_qualifiant_payes` sur l'engagement. **Readonly côté serveur**,
écrits uniquement par `_encaisser()` (le guichet Finance n'a que la lecture sur
le dossier) ; chaque encaissement laisse une trace datée et signée dans
l'historique.

Absents : montants, `numero_bon`, `cachet_appose`, `mode_verification`,
statut `a_relancer` / `rejete`. Les montants de référence existent dans
`his.tarif` (spécialité × cycle), sans lien comptable.

### 9.4 `DocumentChecklist` → `his.admission.document`

Une ligne par pièce, conforme à l'intention v2 :

- `engagement_id`, `type_id`, `fourni`, `date_fourniture` (posée
  automatiquement), `note`.
- **`his.document.type`** porte l'applicabilité (`cycle`,
  `type_inscription`, `bac_filiere`, `obligatoire`). Une ligne n'existe que si
  la pièce **concerne** le dossier : c'est ce qui distingue « pas reçu » de « pas
  concerné ».

**[ÉCART]** `fourni` est un booléen : ni `valide` ni `rejete`.

### 9.5 Carte physique et portefeuille repas (module `his_meal_management`)

Hors v2, réalisé depuis :

- **`his.meal.card`** : `code` (UID RFID 10 chiffres), `partner_id`, `state`
  (`active` / `blocked` / `lost` / `replaced`), `replaced_card_id`. Une seule
  carte active par personne. `his.person.numero_carte` est **calculé** depuis la
  carte active ; changer de badge retire l'ancienne carte au lieu de l'écraser.
- **`his.meal.subscription`** et **`his.meal.transaction`** : grand livre en
  ajout seul (`purchase` / `consume` / `adjust` / `allowance`). Aucune carte ni
  aucun crédit sans `his.person`.
- `hr.employee.barcode` (badge de pointage) est un **reflet** du badge de la
  personne : une carte, trois usages.

### 9.6 Archivage réglementaire et soutenances — **[ÉCART] non implémentés**

---

## 10. Mécanisme de rapprochement → `his.person._find_or_flag_match`

**Un seul algorithme pour tout le groupe.** Chaque point d'entrée l'appelle ; aucun
ne le recopie. La porte `G_MATCH2` d'InSite avait sa propre version : supprimée.

**Niveau 1 — déterministe**

1. `matricule_institutionnel` exact. Si la fiche trouvée est d'un type
   incompatible avec la source → **conflit** signalé, rien n'est lié.
2. Sinon, couple (`external_ref`, `source_system`) : rejouer une source ne
   duplique rien.

**Niveau 2 — probabiliste**

| Critère | Poids | Règle |
|---|---|---|
| Nom | 0,40 | Égalité normalisée (sans accent ni ponctuation), sinon recouvrement de mots (« Ali Ben Salah » ≈ « Ben Salah Ali ») ; nom arabe identique = 1 |
| Email | 0,35 | Institutionnel ou personnel, insensible à la casse |
| Téléphone | 0,25 | 8 derniers chiffres |

- Seuil **0,75** : correspondance **proposée** à un humain, jamais liée.
- Nom seul (0,40) ou nom + téléphone (0,65) **ne suffisent pas** ; nom + email,
  oui.
- Présélection SQL sur email / téléphone / mot du nom avant tout scoring.

| Appelant | Types recherchés | Où l'humain tranche |
|---|---|---|
| Import Google Sheets | `etudiant`, `candidat` | Journal `his.person.sync.log` |
| Pont CRM | `etudiant`, `candidat` | Fiche du lead |
| Pont Campus+ | `candidat`, `enseignant`, `employe` | Fiche de la candidature |
| InSite | `enseignant`, `employe`, `candidat` | Assistant de rapprochement |

Particularité InSite : un matricule soumis qui ne correspond à **personne** fait
relancer la recherche sans lui, pour qu'une faute de frappe ne crée pas de
doublon.

---

## 11. Responsabilités et droits

| Acteur | Crée | Droits sur `his.person` |
|---|---|---|
| Gestionnaire Identité (`group_his_person_manager`) | — | Lecture, écriture, création ; **jamais suppression** |
| RH | `hr.employee` → personne `employe` | Via le serveur |
| Ventes (CRM) | Personne `candidat` + engagement `prospect` à la pré-admission | Via le serveur |
| Finance (guichet) | Encaissements → matricule étudiant | **Aucun** ; passe par `_encaisser()` |
| Admission | Dossier (`his.engagement`), pièces | Via le serveur |
| Recruteur Campus+ / InSite | — | **Lecture** |
| Manager Campus+ / InSite | — | **Lecture et écriture** (classement interne/externe), ni création ni suppression |
| Caisse repas | Cartes, crédits | Lecture via le contact |

Principe tenu : les créations de fiche passent par des méthodes serveur en
`sudo()`, jamais par un droit de création large donné aux métiers.

**Suppression :** `ondelete='restrict'` sur le contact. Supprimer un contact ne
détruit jamais une identité ni ne libère un matricule.

---

## 12. Effets hors référentiel à connaître

- **POS :** Odoo charge tous les contacts en caisse. Les contacts qui ne sont que
  candidats au recrutement (ni commande, ni utilisateur, ni employé, ni fiche
  autre que `candidat`) en sont **exclus** (`his_pos_partner_scope`). Rien
  n'est archivé : l'email et le téléphone des candidatures vivent sur ces
  contacts.
- **Protection du contact :** à la création d'une candidature, Odoo retrouve le
  contact par email et y recopiait le nom et le téléphone saisis. Pour un
  contact porteur d'une fiche personne, cette recopie est bloquée : un employé
  qui postule ne voit plus sa fiche renommée.
- **n8n** alimente Campus+ et le CRM sans connaître le référentiel : le
  rapprochement est entièrement côté serveur.

---

## 13. Décisions ouvertes

| # | Sujet | Pourquoi c'est à trancher |
|---|---|---|
| 1 | Clé de contrôle mod 11 | Validée par l'équipe projet, pas par la Direction / Endeavor (§2.1) |
| 2 | `numero_identite` collecté | Contredit la justification initiale du matricule (§2.3) |
| 3 | Faculté (`his.faculty`) vs domaine (`his.domaine`) | Deux référentiels pour le même découpage (§3) |
| 4 | `statut` enseignant | Non implémenté (§4) |
| 5 | Catalogue de modules | 624 / 1 204 matières en texte libre (§5) |
| 6 | Enseignant `actif` qui recandidate | Rien ne le bloque (§7.3) |
| 7 | Un seul engagement étudiant ouvert à la fois ? | Aucune contrainte aujourd'hui |
| 8 | Embauche Campus+ / signature InSite sur une fiche `employe` | Le type est écrasé en `enseignant` |
| 9 | `Guardian`, `Paiement`, `AcademicBackground` en entités | Aplatis aujourd'hui (§9) |
| 10 | Pédagogie : `actif`, `termine`, soutenances | Aucun module (§8.1) |
| 11 | Uniflow | Valeur de source prévue, adaptateur inexistant |
