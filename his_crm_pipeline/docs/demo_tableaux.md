# Démo — Les tableaux, les étiquettes et les vues enregistrées

**Durée** : 20 à 25 minutes · **Public** : Direction, Ventes/Admissions, Marketing

Ce qu'on montre : **le geste quotidien retrouvé**. L'équipe travaillait sur un
tableau dans GoHighLevel — on y voit d'un coup d'œil où en est chaque dossier,
ce qu'il vaut, et ce qui bloque. C'est ce tableau qui revient ici, en natif,
sans abonnement.

Ce qu'on ne montre **pas** dans cette démo : le parcours complet du candidat
(voir [`docs/demo_admissions.md`](../../docs/demo_admissions.md)) ni la chaîne
de production de contenu (voir
[`docs/demo_production_contenu.md`](../../docs/demo_production_contenu.md)).
Celle-ci porte sur la **lecture** du pipeline, pas sur son déroulé.

---

## Avant de commencer

| | |
|---|---|
| **Adresse** | http://localhost:8069 — base `crm_demo` |
| **Mot de passe** | `his2026` pour **tous** les comptes |
| **Navigateur** | Ouvrez **une fenêtre par rôle** et laissez-les ouvertes. |

> Dans Chrome et Edge, **tous les onglets privés partagent la même session** :
> deux onglets ne peuvent pas être connectés à deux comptes. Utilisez les
> **profils** du navigateur (un par rôle), **un navigateur différent par rôle**,
> ou les **onglets de conteneur** de Firefox.

### Préparer la base

```bash
docker compose stop odoo
docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS crm_demo;"

MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker compose run --rm odoo odoo \
  -d crm_demo --without-demo=True \
  -i his_person_core,his_hr_base,his_crm_pipeline,his_crm_identity_bridge,his_admission,his_access_base \
  --stop-after-init

docker compose run --rm -T odoo odoo shell -d crm_demo --no-http < tools/seed_test_users.py
docker compose run --rm -T odoo odoo shell -d crm_demo --no-http < his_crm_pipeline/docs/seed_demo_tableaux.py

docker compose up -d odoo
```

> `--without-demo=True` et **non** `=all` : depuis Odoo 19, `all` n'est pas une
> valeur booléenne valide — Odoo l'ignore avec un simple avertissement et
> **charge les données de démonstration**, qui viennent alors polluer les
> tableaux avec des dizaines de faux leads.

> **N'utilisez pas `his_dev` pour cette démo.** Cette base porte aussi les
> modules de la branche `main` (`his_web_ui`, `web_responsive`,
> `campus_teacher_management`, `insite_recruitment`). Sur la branche CRM ces
> répertoires n'existent pas : Odoo refuse de les charger et l'interface peut
> casser.

### Les comptes

Un compte par **rôle**, pas par personne : « Conseiller » est un rôle, il peut
être porté par trois personnes ou par aucune.

| Fenêtre | Compte | Rôle | Ce qu'il voit du pipeline |
|---|---|---|---|
| 1 | `marketing` | Acquisition + Production contenu | les 10 (il est dans les deux équipes) |
| 2 | `asma` | Responsable Admissions | les 6 candidatures + la file d'affectation |
| 3 | `aicha` | Conseillère | 4 — les siennes et la file d'attente |
| 4 | `rahma` | Conseillère | 3 — les siennes et la file d'attente |
| 5 | `orientation` | Cellule d'Orientation | **0 au départ** — voir l'acte 4 |
| 6 | `cherif` | Priorisation contenu | les 4 demandes de contenu |
| 7 | `direction` | Direction | les 10, les deux processus |
| 8 | `rh` | Demandeur | seulement ses propres demandes |

Comptes complémentaires, utiles pour le parcours complet mais **pas pour cette
démo-ci** : `contenu`, `design`, `video` (production), `approbation`,
`admission` et `finance`.

> `admission` et `finance` n'ont **aucun accès à `crm.lead`** — c'est voulu :
> ils travaillent sur le dossier (`his.engagement`), pas sur le pipeline
> commercial. Ne leur faites pas ouvrir un tableau, ils obtiendraient une erreur
> de droits qui aurait l'air d'un bug.

> `admin` est le **mauvais compte** pour cette démo : il n'appartient à aucune
> équipe, les règles d'enregistrement lui cachent donc tout, et Odoo affiche
> alors des cartes d'**exemple** générées automatiquement. On croit voir des
> données, ce sont des faux.

---

## Le fil conducteur

> *Six candidatures et quatre demandes de contenu, un mardi matin. Qui doit
> faire quoi, et comment le voit-on sans ouvrir un seul dossier ?*

---

## Acte 1 — Le tableau des admissions

**Fenêtre `aicha`** · *CRM › Admissions › Pipeline*

Le tableau s'ouvre sur les étapes du parcours candidat. À montrer, dans l'ordre :

1. **Les colonnes sont les étapes** — de « Nouveau (score) » à « Frais
   d'inscription payés ». On déplace une carte d'une colonne à l'autre à la
   souris : c'est le geste de GoHighLevel.

2. **Le chiffre en haut de chaque colonne** est la somme des scores des
   candidatures qui s'y trouvent.

   > **À dire au client, c'est important** : ce n'est **pas** un montant.
   > GoHighLevel affiche là une somme d'argent ; une candidature n'en porte pas
   > — les montants vivent dans le dossier d'admission, pas dans le pipeline.
   > Ce chiffre sert à comparer deux colonnes entre elles : « il y a plus de
   > valeur bloquée en *Contact établi* qu'en *Dossier* ».

3. **La barre grise** au-dessus répartit les candidatures selon leur retard
   d'activité. Cliquer sur un segment filtre la colonne. C'est le même signal
   que la relance automatique des 4 heures : une colonne rouge ici veut dire
   exactement ce que dit l'e-mail que reçoit Asma.

4. **La carte** dit l'essentiel sans qu'on l'ouvre :
   - le **nom** du candidat ;
   - une **pastille avec une étoile** : le score académique, calculé depuis le
     BAC et les notes, jamais saisi à la main ;
   - une **icône calendrier verte** quand la visite du campus a eu lieu
     (Sofiane, Amine, Rania) ;
   - la **spécialité visée**, en gris — de quoi on va parler au téléphone ;
   - les **étiquettes** de couleur ;
   - l'**avatar** de la conseillère, ses activités, sa priorité.

---

## Acte 2 — Les étiquettes

**Fenêtre `aicha`** · même écran

Les étiquettes portent ce que le dossier ne dit pas : « Bourse demandée »,
« Indécis programme », « Parent très impliqué », « Relance prioritaire ».

Ouvrez une candidature, ajoutez ou retirez une étiquette, revenez au tableau :
la pastille suit.

> **Ce qu'on n'a délibérément pas fait** : d'étiquette « HIS », « HTC » ou
> « IRA ». La marque est déjà un champ. Une étiquette qui répète un champ finit
> par le contredire — on aurait deux réponses à la même question.

---

## Acte 3 — Les vues enregistrées (les « smart lists »)

**Fenêtre `asma`** · *CRM › Admissions › Pipeline* · menu déroulant de la
recherche, section **Favoris**

Quatre vues prêtes à l'emploi, côté Admissions :

| Vue | Ce qu'elle sort | Sur ce jeu de démo |
|---|---|---|
| **SLA en retard** | pris en charge depuis plus de 4 h sans premier contact | Lina Hamadi |
| **Candidatures chaudes** | score ≥ 8, ni gagnée ni perdue | Amine, Lina, Yacine |
| **Pré-admis sans encaissement** | pré-admis depuis plus de 7 jours, non payé | Rania Bouzid |
| **Visite campus à programmer** | visite non faite, en contact ou en dossier | Nour Cherifi |

**Le point à faire passer** : « SLA en retard » utilise le **même seuil de 4
heures** que la relance automatique. Le tableau et les e-mails de relance
racontent la même histoire — il n'y a pas deux définitions du retard.

**Fenêtre `asma`** · *CRM › Admissions › **Leads à affecter***

Cette entrée de menu n'existe que pour le **Responsable** (vérifiez : elle est
absente chez `aicha` et chez `marketing`). La file est triée par score
décroissant. Cochez plusieurs lignes, modifiez « Commercial » sur l'une d'elles,
Odoo propage à toutes.

> Aucune affectation automatique, aucun tourniquet : la Direction veut que
> l'arbitrage reste humain.

---

## Acte 4 — Le cloisonnement, montré et pas raconté

C'est l'acte qui rassure. Trois démonstrations rapides.

**a) Deux conseillères ne voient pas la même chose.**
Côte à côte, `aicha` (4 candidatures) et `rahma` (3). Chacune voit les siennes,
plus la file d'attente commune — d'où le chevauchement.

**b) La Cellule d'Orientation ne voit que ce qu'elle évalue.**
Ouvrez la fenêtre `orientation` : le pipeline est **vide**. C'est normal, aucun
candidat n'est en évaluation.
Depuis `aicha`, glissez **Sofiane Meziane** dans la colonne *Évaluation
psychologique*. Rafraîchissez `orientation` : Sofiane apparaît, **et lui seul**.

**c) Le contenu et les admissions ne se croisent jamais.**
Ouvrez la fenêtre `cherif` : il n'a **pas d'application CRM du tout**, seulement
*Production Contenu*. Un graphiste n'a aucune raison d'accéder au carnet de
contacts ni aux candidatures.

---

## Acte 5 — Le tableau de la production de contenu

**Fenêtre `cherif`** · *Production Contenu › Demandes*

Le même outil, un tableau volontairement différent :

1. **Pas de barre de progression** — et c'est un choix, pas un oubli. Rien ne
   pose d'activité sur une demande de contenu ; la barre serait uniformément
   grise, donc muette. Le **compteur par colonne** reste, lui : `(1) (0) (2) (1) (0)`.

2. **Pas de score non plus** : une demande de contenu ne se chiffre pas.

3. **La carte** dit ce qui compte ici :
   - le **département demandeur** et la **marque** ;
   - une ligne d'**avancement des livrables** : `0/2 approuvés`,
     `2/2 approuvés`, et pour « Vidéo témoignage master » →
     **`1/2 approuvés - en retard`**.

   > Le retard est un **drapeau**, pas un compte, parce que l'échéance est
   > portée par la demande et vaut donc pour tous ses livrables. Compter les
   > retards reviendrait à réécrire « total moins approuvés » — l'information
   > utile, c'est que l'échéance est dépassée.

4. **Les favoris de ce pipeline sont différents** : « Livrables en retard »,
   « Livrables non assignés », « En attente d'approbation », « Urgent ».

   Retournez dans la fenêtre `asma` et rouvrez les favoris : les quatre vues du
   contenu **n'y sont pas**. Chaque vue est rattachée à son pipeline.

**Fenêtre `rh`** (demandeur) · *Production Contenu › Demandes*
Il dépose une demande et suit **la sienne**. Il n'a ni le plan de charge de
l'équipe, ni les candidatures, ni les contacts.

---

## Acte 6 — Programmer une visite du campus

**Fenêtre `aicha`** · une carte du tableau · menu **⋮** de la carte

Cliquez **Programmer une visite** : l'agenda s'ouvre, **déjà rempli** du nom du
candidat, de son contact et de l'équipe. Le même bouton existe dans le
formulaire, onglet *Admissions*, encadré « Visite du campus ».

> **À dire, c'est une question qui vient toujours** : ce bouton ne coche
> **rien**. « Visite effectuée » reste une case que la conseillère coche après
> coup. Un rendez-vous pris n'est pas une visite faite — les absences sont
> courantes — et une case qui deviendrait vraie toute seule mentirait sur la
> moitié d'entre elles. **Programmer** et **constater** sont deux gestes
> distincts.

> Si le client demande un **lien public de réservation**, à la GoHighLevel : ce
> n'est pas disponible en édition Community. Cela demanderait Odoo Enterprise ou
> un module tiers. À chiffrer à part, ne pas le promettre en séance.

---

## Acte 7 — La vue de la Direction

**Fenêtre `direction`** · *CRM › Admissions › Pipeline*, puis *Cockpit*

La Direction voit **les deux processus** (10 enregistrements) alors qu'elle
n'est membre d'**aucune** équipe — volontairement, pour rester hors de la
rotation d'affectation.

Elle ne porte pas non plus le rôle de gestionnaire commercial d'Odoo : elle ne
peut **pas supprimer** une candidature. Une candidature se marque *perdue* avec
un motif, elle ne s'efface pas.

---

## Questions qui reviennent

**« Peut-on changer les couleurs, les espacements ? »**
Oui. Rien n'est figé en dur : tout passe par les composants et les jetons de
thème d'Odoo. Une passe visuelle ne touchera que ceux-là. Elle attend une
capture de l'instance GoHighLevel du client pour caler les teintes exactes.

**« Peut-on ajouter une étiquette ? »**
Oui, sans livraison de code. Côté contenu, c'est la **Priorisation** qui définit
la taxonomie — elle trie les demandes, c'est son métier. Personne ne peut
*supprimer* une étiquette : elle disparaîtrait de tous les dossiers qui la
portent, sans trace.

**« Et si on veut une autre vue enregistrée ? »**
Un utilisateur enregistre ses propres favoris depuis la recherche. Les huit
livrées ne sont qu'un point de départ ; elles ne seront pas réécrasées à la
prochaine mise à jour.

**« Le total de colonne, c'est du chiffre d'affaires ? »**
Non. Voir l'acte 1 — c'est une somme de scores. Ne pas laisser cette
ambiguïté s'installer.

---

## Remise à zéro

Rejouer la démo : relancez les deux scripts de la section *Préparer la base*.
Ils sont idempotents — ils ne créent pas de doublon, mais reposent les rôles et
les mots de passe.

Pour repartir totalement propre, supprimez la base et refaites l'installation.

> Ces comptes sont des comptes de **recette** : mot de passe connu, adresses
> `@example.com`. À ne jamais semer sur une base de production.
