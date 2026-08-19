# his_person_core — Socle Personnes & matricule institutionnel

Source **unique** de vérité de l'identité des personnes du Groupe HIS-HTC-IRA :
employés, enseignants, étudiants, candidats. Traduit le modèle de données
`Person` validé en un modèle Odoo 19.0 Community et une séquence unique.

## La règle de gouvernance

> **Ce module possède la seule séquence autorisée à émettre un
> `matricule_institutionnel`. Aucun autre module ne crée de séquence de
> matricule, et aucun autre module n'écrit ce champ directement.**

Un matricule est un identifiant **à vie**, partagé par tous les types de
personnes, sur lequel s'appuieront la carte RFID et le portefeuille repas. Deux
compteurs indépendants, c'est une collision garantie ; une collision sur cet
identifiant, c'est un solde de portefeuille attribué à la mauvaise personne.

Concrètement :

| Interdit | À la place |
|---|---|
| Un second `ir.sequence` de matricule dans un autre module | Appeler `his.person.create()` |
| `employee.matricule_institutionnel = '...'` | Créer la `his.person`, l'employé la reflète |
| Modifier un matricule après création | Impossible : bloqué serveur dans `write()` |
| Fusionner deux fiches sur un rapprochement automatique | Confirmation humaine explicite obligatoire |

La règle est appliquée par des **contraintes serveur** (`create`/`write`
surchargés, contrainte SQL d'unicité), jamais par de la validation côté vue :
une règle contournable par import ou par API n'est pas une règle.

## Une personne = un `res.partner`

`his.person` est en **héritage par délégation** (`_inherits`) vers `res.partner` :
chaque fiche porte un vrai contact Odoo, créé automatiquement.

```
his.person                          res.partner
┌────────────────────────┐         ┌──────────────────────┐
│ matricule_institutionnel│         │ name    (nom latin)  │
│ nom_arabe               │────────►│ email   (institution)│
│ email_personnel         │partner_ │ phone                │
│ type_personne           │   id    │ active               │
└────────────────────────┘         └──────────────────────┘
```

**Pourquoi pas un modèle autonome.** La carte RFID, le portefeuille repas et le
POS travaillent tous sur `partner_id`. Sans partenaire dessous, il faudrait
tenir deux fiches synchronisées par humain — exactement le problème de double
source de vérité que ce module existe pour supprimer.

**Pourquoi pas `_inherit` sur `res.partner`.** Cela poserait le matricule et le
type de personne sur **tous** les contacts, et mêlerait des milliers
d'étudiants aux contacts commerciaux dans chaque sélecteur, chaque portail et
chaque règle de sécurité du système.

La délégation évite les deux : `his.person` reste la surface de travail, avec
ses vues, sa sécurité et ses règles ; un partenaire suit pour tout ce qui, en
aval, en aura besoin.

### Champs délégués

| Sur `his.person` | Vient de |
|---|---|
| `name` | `res.partner.name` — le nom latin |
| `email` | `res.partner.email` — **l'adresse institutionnelle** |
| `phone` | `res.partner.phone` |
| `active` | `res.partner.active` — archiver une personne archive son contact |

`res.partner` n'a qu'un seul champ email, et **plus de `mobile` depuis 19.0**.
L'adresse institutionnelle est l'adresse officielle — celle que liront le
portail, les documents et le POS — elle occupe donc `email`. `email_personnel`
et `nom_arabe` restent des champs propres au référentiel : le partenaire n'a
pas d'équivalent.

### Deux règles portées par le schéma

- `partner_id` est `required=True, delegate=True, ondelete='restrict'`.
  `delegate` est **exigé** par l'ORM en 19.0. `restrict` — et non `cascade` —
  parce que supprimer un contact depuis l'application Contacts ne doit jamais
  détruire une identité ni libérer un matricule déjà distribué.
- `unique(partner_id)` : **un contact, une personne**.
  `hr.employee.work_contact_id` peut être partagé entre plusieurs employés
  (`res.partner.employee_ids` est un One2many, et le cœur d'Odoo teste
  explicitement `len(employee_ids) <= 1`). Sans cette contrainte, deux fiches
  pointeraient le même contact et l'ancrage d'identité cesserait d'être
  un-par-humain.

Chaque contact créé par une fiche personne reçoit l'étiquette
**« HIS — Identité institutionnelle »**. Elle ne restreint rien : elle donnera
aux Ventes et aux Achats de quoi écarter les étudiants de leurs sélecteurs de
contacts par défaut, quand ces modules arriveront.

## Format du matricule

```
HIS-AAAA-NNNNNN-C
 │    │     │     └── clé de contrôle (1 caractère : 0-9 ou X)
 │    │     └──────── compteur sur 6 chiffres, remis à 1 chaque année
 │    └────────────── année, issue de `matricule_sequence_date`
 └─────────────────── préfixe groupe (aucune information d'entité juridique)
```

L'année **ne vient pas** de la date de création de la fiche mais de la clé de
service `matricule_sequence_date` passée dans `vals` : une embauche antidatée
(saisie en retard) ou future (recrutement signé pour la rentrée) doit porter
l'année réelle. Cette clé est retirée de `vals` avant le `create()` réel — ce
n'est pas un champ.

### Clé de contrôle

Mod 11 sur les 6 chiffres séquentiels, poids 2..7 de droite à gauche ; reste 10
→ `X` (comme ISBN-10), pour garder la clé sur un seul caractère.

**Écart assumé — à reconfirmer.** Aucun document source ne spécifiait
l'algorithme : le format `HIS-AAAA-NNNNNN-C` était documenté, la clé ne l'était
pas, et le code précédent (`maintenance_university`) ne la générait pas du tout.
L'algorithme ci-dessus a été proposé puis confirmé pour cette branche. S'il est
corrigé plus tard, **seule** `_compute_matricule_checksum()` change : elle est
une fonction pure, sans accès ORM, testée isolément du modèle et de la séquence
(`tests/test_matricule.py::test_checksum_known_vectors`). Les matricules déjà
émis, eux, ne seront pas recalculés — ils sont distribués.

### Valeurs préexistantes

Si `matricule_institutionnel` est déjà présent dans `vals`, il est stocké **tel
quel** : pas de reformatage, pas de recalcul de clé, pas de rejet. C'est le
chemin utilisé par la reprise RH (`his_hr_base`) et par l'import Sheets
(`his_person_sync_sheets`). Une valeur antérieure à ce module peut n'avoir
aucune clé valide ; la refuser ferait perdre un matricule réel déjà distribué.
Seule l'unicité s'applique. Signaler ce qui est malformé est le travail de
l'import, pas du socle.

## Rapprochement (matching)

L'algorithme est porté par `his.person._find_or_flag_match()`, **pas** par
l'adaptateur qui l'appelle : un second adaptateur (Uniflow) doit exécuter
exactement le même calcul sans dépendre du premier. Un algorithme dupliqué
dérive, et deux fiches pour la même personne, c'est deux portefeuilles.

- Déterministe : matricule identique. Si la fiche trouvée est d'un
  `type_personne` incompatible avec la source, la ligne est **rejetée en
  conflit**, jamais fusionnée.
- Probabiliste : score pondéré nom (0,40) / email (0,35) / téléphone (0,25), sur les champs délégués,
  seuil 0,75. Au-dessus du seuil, la fiche est **proposée** à un humain —
  `_find_or_flag_match` ne lie rien. La confirmation explicite renseigne
  `match_method`, `matched_by`, `matched_on`.

## Sécurité

Lecture ouverte à tout utilisateur interne (`base.group_user`) : retrouver
quelqu'un par son matricule est une opération courante. Écriture et création
réservées au groupe **Identité : gestionnaire**.

Les modules qui doivent créer des fiches (`his_hr_base` à l'embauche) le font en
`sudo()` depuis leur logique serveur, **pas** en s'octroyant un droit de
création large : créer une fiche, c'est émettre un matricule à vie.

## Hors périmètre (assumé)

Cette branche pose le socle d'identité. Elle ne contient **volontairement** ni :

- modèle de carte RFID ni son cycle de vie ;
- abonnement repas, portefeuille, solde ;
- code ou vue Point de Vente, Restaurant, Copy Center ;
- intégration Uniflow (la couche de synchronisation est conçue pour l'accueillir
  comme second adaptateur, cf. `his_person_sync_sheets`).

Ces chantiers s'appuient sur ce module ; ils ne sont pas ici.

## Installation

```bash
docker compose run --rm odoo odoo -d <base> -i his_person_core --stop-after-init
```

## Lancer les tests

```bash
docker compose run --rm odoo odoo -d <base> -u his_person_core \
  --test-enable --test-tags /his_person_core --stop-after-init
```
