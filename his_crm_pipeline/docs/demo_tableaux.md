# Démo — Le pipeline, la boucle d'appel et le cockpit

**Durée** : 35 à 45 minutes · **Public** : Direction, Ventes/Admissions, Marketing

Ce qu'on montre : **le geste quotidien retrouvé, et ce que GoHighLevel ne
savait pas faire**. L'équipe travaillait sur un tableau — on y voit d'un coup
d'œil où en est chaque dossier et ce qui bloque. C'est ce tableau qui revient
ici, en natif, sans abonnement — plus trois choses que l'ancien outil laissait
filer : les appels sans réponse qu'on ne comptait pas, les pertes qu'on
n'expliquait pas, et un chiffre d'affaires que personne ne saisissait.

Ce qu'on ne montre **pas** ici : le parcours complet du dossier d'admission
(voir [`docs/demo_admissions.md`](../../docs/demo_admissions.md)) ni la chaîne
de production de contenu (voir
[`docs/demo_production_contenu.md`](../../docs/demo_production_contenu.md)).

> **Les trois arguments qui portent, si vous n'avez que cinq minutes :**
> 1. **626 pertes, 193 motifs** dans leur GoHighLevel — deux tiers des échecs
>    n'étaient expliqués nulle part. Ici, on ne peut plus perdre sans dire
>    pourquoi (acte 3).
> 2. **454 opportunités sur 505 sans montant** chez eux, parce qu'il fallait le
>    taper à la main. Ici, le chiffre se **déduit** d'une grille tarifaire, donc
>    il ne peut pas être vide (acte 6).
> 3. **Un identifiant à vie par candidature** : on ne le grave plus qu'au
>    paiement (acte 7).

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

Le second script **affiche ce qu'il vient de poser** : les tentatives d'appel,
le candidat dont le numéro est illisible, les motifs de perte et le contenu des
huit vues enregistrées. **Lisez cette sortie avant la séance** — elle vous dit
exactement quels noms citer.

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

| Fenêtre | Compte | Rôle | Ce qu'il voit |
|---|---|---|---|
| 1 | `marketing` | Acquisition + Production contenu | les 10 (il est dans les deux équipes) |
| 2 | `asma` | Responsable Admissions | les 6 candidatures + la file d'affectation |
| 3 | `aicha` | Conseillère | les siennes et la file d'attente |
| 4 | `rahma` | Conseillère | les siennes et la file d'attente |
| 5 | `orientation` | Cellule d'Orientation | **0 au départ** — voir l'acte 5 |
| 6 | `admission` | Instruction du dossier | le **pipeline partagé** + les dossiers |
| 7 | `finance` | Guichet | les dossiers, pour encaisser — **pas** le pipeline |
| 8 | `cherif` | Priorisation contenu | les 4 demandes de contenu |
| 9 | `direction` | Direction | les 10, les deux processus, le cockpit |
| 10 | `rh` | Demandeur | seulement ses propres demandes |

> **Changement récent, à ne pas rater** : `admission` **a désormais accès au
> pipeline**, en lecture et en écriture, à partir de « Contact établi ». C'est
> l'objet de l'acte 8. `finance`, lui, n'a toujours rien sur `crm.lead` : il
> encaisse sur le dossier, il ne travaille pas le pipeline commercial.

> `admin` est le **mauvais compte** pour cette démo : il n'appartient à aucune
> équipe, les règles d'enregistrement lui cachent donc tout, et Odoo affiche
> alors des cartes d'**exemple** générées automatiquement, avec des noms comme
> *John Miller* et des chiffres qui changent à chaque rechargement. On croit
> voir des données, ce sont des faux.

---

## Le fil conducteur

> *Six candidatures vivantes, cinq déjà perdues, quatre demandes de contenu, un
> mardi matin. Qui doit faire quoi, pourquoi les cinq sont-elles mortes, et
> combien vaut ce qui reste ?*

---

## Acte 1 — Le tableau des admissions

**Fenêtre `aicha`** · *CRM › Sales › Pipeline*

> **Le menu s'appelle « Sales », et c'est le seul.** Odoo en livrait un second,
> natif, dont l'entrée principale ne montre que *les leads affectés à
> l'utilisateur courant* — un responsable ou un directeur y voyait donc un
> tableau vide à côté d'un menu qui, lui, montrait tout. Deux portes vers le
> même modèle, dont une toujours fermée. On a gardé celle qui marche.

Le tableau s'ouvre sur les étapes du parcours candidat. À montrer, dans l'ordre :

1. **Les colonnes sont les étapes** — de « Nouveau (score) » à « Frais
   d'inscription payés ». On déplace une carte d'une colonne à l'autre à la
   souris : c'est le geste de GoHighLevel.

2. **Le chiffre en haut de chaque colonne** est la somme des scores des
   candidatures qui s'y trouvent.

   > **À dire au client, c'est important** : ce n'est **pas** un montant.
   > GoHighLevel affiche là une somme d'argent ; une candidature n'en porte pas
   > — les montants vivent dans la grille tarifaire et le dossier, pas sur la
   > carte. Ce chiffre sert à comparer deux colonnes entre elles. Le chiffre
   > d'affaires, lui, est à l'acte 6.

3. **La barre grise** au-dessus répartit les candidatures selon leur retard
   d'activité. Cliquer sur un segment filtre la colonne. C'est le même signal
   que la relance automatique des 4 heures : une colonne rouge ici veut dire
   exactement ce que dit l'e-mail que reçoit Asma.

4. **La carte** dit l'essentiel sans qu'on l'ouvre :
   - le **nom** du candidat ;
   - une **pastille étoile** : le score académique, calculé depuis le BAC et
     les notes, jamais saisi à la main ;
   - une **pastille téléphone** : les appels restés sans réponse (acte 2) ;
   - une **icône calendrier verte** quand la visite du campus a eu lieu ;
   - la **spécialité visée**, en gris — de quoi on va parler au téléphone ;
   - les **étiquettes** de couleur ;
   - l'**avatar** de la conseillère, ses activités, sa priorité ;
   - en bas, la **rangée d'action** : *Sans réponse*, *Joint*, *Perdu*, puis
     WhatsApp et téléphone.

---

## Acte 2 — La boucle d'appel *(nouveau)*

**Fenêtre `aicha`** · même écran

C'est l'acte qui change le quotidien. **Les conseillères composent le numéro sur
leur propre téléphone**, en regardant l'écran. Un bouton « cliquer pour
appeler » n'aurait donc rien à appeler : toute la valeur est dans ce qui se
passe **après** l'appel.

1. **Regardez les pastilles téléphone.** Sofiane porte `1`, Nour `2`, **Lina
   porte `3` en rouge**. Trois tentatives sans réponse, c'est le seuil de la
   *candidature fantôme*. Yacine, Amine et Rania n'ont aucune pastille : zéro
   tentative n'est pas une information, on ne l'affiche pas.

2. **Cliquez « Sans réponse »** sur une carte. Trois choses arrivent, et pas une
   de plus : le compteur monte, une note datée part dans le fil, et le rappel
   est repoussé d'un jour. **L'étape ne bouge pas** — une tentative n'est pas un
   contact, et faire avancer le lead sur un appel sans réponse gonflerait le
   pipeline de candidats que personne n'a jamais eus au téléphone.

3. **Un seul rappel à la fois.** Recliquez deux fois : le compteur monte, mais
   il n'y a toujours qu'**une** activité, repoussée. Poser une activité par
   tentative referait le défaut classique — une pile que le destinataire cesse
   de lire.

4. **Cliquez « Joint »** : la carte passe en *Contact établi*, le rappel
   disparaît, et **la fiche s'ouvre**. C'est le seul moment où la conseillère se
   souvient de ce qui vient d'être dit ; l'écran doit être devant elle sans
   qu'elle le cherche.

5. **Le bouton WhatsApp** ouvre l'application avec le numéro prêt et un message
   d'amorce. **Regardez Nour Cherifi : elle n'a ni WhatsApp ni téléphone.** Son
   numéro est « à rappeler chez la tante ». Le système refuse de fabriquer un
   lien qui ne mènerait nulle part.

> **La question qui vient toujours : « et l'inbox WhatsApp de GoHighLevel ? »**
> Elle n'existe pas ici, et il faut le dire franchement. Ce sont des **liens
> profonds**, pas une intégration : pas de message entrant, pas d'accusé de
> réception, pas de fil dans Odoo. Odoo 19 Community n'a ni téléphonie, ni SMS
> gratuit, ni WhatsApp. Une vraie intégration demanderait l'API Meta Business —
> à chiffrer à part, **ne pas la promettre en séance**.

> **Ce qu'on a refusé de faire** : perdre automatiquement un candidat au bout de
> N tentatives. Une machine qui déclare un candidat mort, c'est la même
> automatisation que la Direction a refusée pour l'affectation. La fiche
> propose, la conseillère décide.

---

## Acte 3 — Une perte ne peut plus être muette *(nouveau)*

**Fenêtre `aicha`** · une carte · bouton **Perdu**

C'est l'acte le plus vendeur. Commencez par le chiffre :

> **Dans leur GoHighLevel : 626 opportunités perdues, 193 motifs.** Les deux
> tiers des échecs ne disaient rien. Ce n'était pas de la négligence :
> consigner coûtait six gestes, sauter n'en coûtait aucun.

1. **Cliquez « Perdu » sur une carte sans historique d'appel**, puis validez
   sans choisir de motif. **Le serveur refuse.** Ce n'est pas une règle
   d'écran : le glisser-déposer, l'import et l'API passent tous par le même
   verrou.

2. **Ouvrez la liste des motifs.** Elle est **triée par fréquence réelle**, pas
   par ordre alphabétique : *Sans réponse*, *Candidature fantôme*, *Profil non
   adapté* en tête. Trois motifs couvrent environ 70 % des cas. Une clôture qui
   coûte cher est une clôture qu'on saute — l'ordre fait partie du dispositif.

3. **Choisissez « Autre — à préciser » sans écrire de note** : refusé aussi.

   > **Le point à faire passer** : un motif obligatoire **sans porte de sortie**
   > ne produit pas de meilleures données, il produit des mensonges confiants.
   > Qui ne sait pas choisit ce qui est le plus proche du curseur, et ce
   > motif-là est pire qu'un vide, parce qu'il ne s'en distingue pas.

4. **Maintenant cliquez « Perdu » sur Lina Hamadi** (3 tentatives) : le motif
   **« Candidature fantôme » est déjà sélectionné**. La fiche sait déjà ; elle
   ne demande pas. C'est ce qui rend le motif obligatoire supportable.

> **Le vocabulaire vient de chez eux.** *Ghost Application*, *No Answer*,
> *Wrong number*, *Old BAC*, *Too expensive*, *Not suitable* : ce sont leurs
> propres motifs, traduits. Deux corrections au passage — *No Answer* et
> *No answer* étaient **deux entrées distinctes** dans GoHighLevel et
> fusionnent ici (une fois réunies, c'est le motif n°1) ; *Unknown* n'est pas
> repris, il n'enregistre rien.

> Les trois motifs anglais d'Odoo (*Too expensive*…) sont **désactivés** : sans
> cela, un conseiller voyait deux entrées pour la même idée, dans deux langues.

---

## Acte 4 — Les étiquettes et les vues enregistrées

**Fenêtre `aicha`** · même écran

Les étiquettes portent ce que le dossier ne dit pas : « Bourse demandée »,
« Indécis programme », « Parent très impliqué », « Relance prioritaire ».

> **Ce qu'on n'a délibérément pas fait** : d'étiquette « HIS », « HTC » ou
> « IRA ». La marque est déjà un champ. Une étiquette qui répète un champ finit
> par le contredire — on aurait deux réponses à la même question.

**Fenêtre `asma`** · menu déroulant de la recherche, section **Favoris**

| Vue | Ce qu'elle sort | Sur ce jeu de démo |
|---|---|---|
| **SLA en retard** | pris en charge depuis plus de 4 h sans premier contact | Lina Hamadi |
| **Candidatures chaudes** | score ≥ 8, ni gagnée ni perdue | Yacine, Lina, Amine |
| **Pré-admis sans encaissement** | pré-admis depuis plus de 7 jours, non payé | Rania Bouzid |
| **Visite campus à programmer** | visite non faite, en contact ou en dossier | Nour Cherifi |

**Le point à faire passer** : « SLA en retard » utilise le **même seuil de 4
heures** que la relance automatique. Le tableau et les e-mails racontent la même
histoire — il n'y a pas deux définitions du retard.

**Fenêtre `asma`** · *CRM › Sales › **Leads à affecter***

Cette entrée n'existe que pour le **Responsable** (vérifiez : absente chez
`aicha`). La file est triée par score décroissant. Cochez plusieurs lignes,
modifiez « Commercial » sur l'une d'elles, Odoo propage à toutes.

> Aucune affectation automatique, aucun tourniquet : la Direction veut que
> l'arbitrage reste humain.

---

## Acte 5 — Le cloisonnement, montré et pas raconté

C'est l'acte qui rassure. Trois démonstrations rapides.

**a) Deux conseillères ne voient pas la même chose.**
Côte à côte, `aicha` et `rahma`. Chacune voit les siennes, plus la file
d'attente commune — d'où le chevauchement.

**b) La Cellule d'Orientation ne voit que ce qu'elle évalue.**
Ouvrez `orientation` : le pipeline est **vide**. Normal, aucun candidat n'est en
évaluation. Depuis `aicha`, glissez **Sofiane Meziane** dans *Évaluation
psychologique*. Rafraîchissez `orientation` : Sofiane apparaît, **et lui seul**.

**c) Le contenu et les admissions ne se croisent jamais.**
Ouvrez `cherif` : il n'a **pas d'application CRM du tout**, seulement
*Production Contenu*. Un graphiste n'a aucune raison d'accéder au carnet de
contacts ni aux candidatures.

---

## Acte 6 — Le cockpit *(largement nouveau)*

**Fenêtre `direction`** · *CRM › Sales › Cockpit*

### Les tuiles et l'entonnoir

*Candidatures reçues*, *Inscriptions*, *Taux de conversion*, *Délai moyen
d'affectation*, *Pré-admis sans encaissement*. **Chaque chiffre s'ouvre** :
cliquez, vous obtenez exactement les enregistrements comptés. Un nombre qu'on ne
peut pas ouvrir doit être cru sur parole.

L'entonnoir est **cumulatif** : chaque marche contient les suivantes, sinon le
taux de passage ne veut rien dire.

### Les quatre répartitions

C'est ce que le client reconnaît de son tableau de bord GoHighLevel.

| Donut | Ce qu'il répond | Sur ce jeu |
|---|---|---|
| **Candidats par score** | quelle qualité arrive | 6 candidats, scores 5 à 10 |
| **État du portefeuille** | où en est le stock | 6, répartis sur 5 étapes |
| **Motifs de perte** | **où l'on perd** | **5 pertes, 5 motifs différents** |
| **Acquisition par source** | d'où ils viennent | 6 sources, dont « Non renseigné » |

**Cliquez une part de légende** : elle ouvre exactement ce qu'elle compte.

> **À dire** : les trois premiers totalisent **6**, comme la tuile
> *Candidatures reçues*. Seul « Motifs de perte » en compte 5 — c'est la seule
> population qui parle légitimement des fiches archivées. Deux totaux
> différents côte à côte sur un même écran seraient illisibles.

> **Pas de bibliothèque de graphiques.** Ce sont des instantanés, pas des
> courbes : un donut tient en une déclaration CSS. Le jour où une évolution
> dans le temps est demandée, Odoo livre déjà de quoi la tracer.

### La qualité des données

Le bloc du bas est **la meilleure idée du tableau de bord GoHighLevel** — leur
panneau *Fix your forecast data* — et c'est celui qu'on cite en dernier parce
qu'il rend tout le reste crédible :

- **Sans téléphone ni email** — 0 ici ;
- **Sans spécialité visée** — 0 ;
- **Sans source d'acquisition** — **1, Nour Cherifi**, cliquable ;
- **Spécialités sans tarif** — les spécialités dont les candidatures ne peuvent
  pas être chiffrées.

> **Un tableau de bord qui ne dit pas ce qu'il ignore laisse croire qu'il sait
> tout.** C'est exactement ce que leur outil faisait : *505 opportunités
> ouvertes, 505 sans date de clôture*, et un onglet Prévisions qui affichait
> quand même un chiffre.

### Le revenu attendu

**Fenêtre `direction`** · *CRM › Sales › Cockpit* puis la **Vue d'ensemble**

La tuile **Revenu attendu** est calculée : candidatures ouvertes × tarif de leur
spécialité, lu dans *Admission › Configuration › Tarifs*.

> **L'argument le plus fort de la séance.** Chez eux : **454 opportunités
> ouvertes sur 505 n'ont aucun montant**, parce qu'il fallait le taper à la main
> sur chaque fiche. Ici personne ne tape rien — donc le chiffre ne peut pas être
> vide.

> **Videz la grille tarifaire et la tuile disparaît.** C'est voulu, et c'est un
> bon moment de démo : un chiffre d'affaires inventé est pire qu'un chiffre
> absent, parce qu'il se cite en réunion.

> **Les montants du jeu de démo sont des illustrations.** Le vrai barème doit
> venir de la Finance du client. Ne les présentez pas comme des prix.

---

## Acte 7 — Le matricule attend l'argent *(nouveau)*

**Fenêtre `admission`** puis **`finance`**

C'est l'acte pour un client qui a déjà un référentiel étudiant, ou qui va en
avoir un. Trois écrans, trois minutes.

1. **Ouvrez *Admission › Dossiers*** : il n'y a **qu'un seul dossier**, celui de
   Rania Bouzid — la seule candidate pré-admise. Les cinq autres candidatures
   vivantes n'ont **rien** dans le référentiel d'identité.

2. **Ouvrez sa fiche personne** : elle **n'a pas de matricule**.

3. **Fenêtre `finance`** · le même dossier · **Encaisser les frais
   d'inscription**. Le matricule s'affiche, `HIS-2026-000001-…`, et le lead
   passe tout seul en *Frais d'inscription payés*.

> **Pourquoi c'est important.** Le matricule est un identifiant **à vie**, tiré
> d'une séquence qui ne se recycle jamais : supprimer une fiche ne « libère »
> pas son numéro. L'émettre au premier contact revenait à en brûler un par
> candidature — et sur les chiffres réels du client, **954 opportunités perdues
> sur 1 558**, soit six numéros sur dix distribués à des gens qui ne seront
> jamais étudiants.
>
> Le dossier s'ouvre donc à la **pré-admission** — il faut bien un endroit où
> enregistrer le paiement — et le matricule à l'**encaissement**, parce que les
> frais d'inscription sont non remboursables : c'est le premier engagement
> irréversible des deux côtés.

---

## Acte 8 — Le pipeline partagé *(nouveau)*

**Fenêtres `admission` et `aicha`, côte à côte**

**Fenêtre `admission`** · *Admission › Pipeline*

Le même tableau, dans l'autre application. Il **démarre à « Contact établi »** :
avant cela, la candidature appartient aux Ventes et l'Admission n'a rien à en
connaître.

**Faites-le en direct** : déplacez une carte depuis la fenêtre `admission`, puis
rafraîchissez `aicha`. **La carte a bougé chez elle aussi.**

> **Il n'y a rien à synchroniser, parce qu'il n'y a qu'un enregistrement.**
> L'alternative — un second tableau, miroir du premier — aurait demandé de la
> recopie dans les deux sens et deux vérités pour une seule question : « où en
> est ce candidat ? »

> L'Admission peut **lire et déplacer**, mais **ni créer ni supprimer** : elle
> fait avancer un candidat, elle n'en invente pas et n'en efface pas.

---

## Acte 9 — Le tableau de la production de contenu

**Fenêtre `cherif`** · *Production Contenu › Demandes*

Le même outil, un tableau volontairement différent :

1. **Pas de barre de progression** — et c'est un choix, pas un oubli. Rien ne
   pose d'activité sur une demande de contenu ; la barre serait uniformément
   grise, donc muette.

2. **Pas de score, pas de boutons d'appel** : une demande de contenu ne se
   chiffre pas et ne se rappelle pas au téléphone.

3. **La carte** dit ce qui compte ici : le **département demandeur**, la
   **marque**, et l'**avancement des livrables** — pour « Vidéo témoignage
   master », **`1/2 approuvés - en retard`**.

   > Le retard est un **drapeau**, pas un compte : l'échéance est portée par la
   > demande et vaut pour tous ses livrables. L'information utile, c'est qu'elle
   > est dépassée.

4. **Les favoris de ce pipeline sont différents** : « Livrables en retard »,
   « Livrables non assignés », « En attente d'approbation », « Urgent ».
   Retournez chez `asma` : ces quatre vues **n'y sont pas**. Chaque vue est
   rattachée à son pipeline.

**Fenêtre `rh`** · il dépose une demande et suit **la sienne**. Ni le plan de
charge de l'équipe, ni les candidatures, ni les contacts.

---

## Acte 10 — Programmer une visite du campus

**Fenêtre `aicha`** · une carte · menu **⋮**

Cliquez **Programmer une visite** : l'agenda s'ouvre, **déjà rempli** du nom du
candidat, de son contact et de l'équipe.

> **À dire, la question vient toujours** : ce bouton ne coche **rien**. « Visite
> effectuée » reste une case que la conseillère coche après coup. Un rendez-vous
> pris n'est pas une visite faite — les absences sont courantes — et une case
> qui deviendrait vraie toute seule mentirait sur la moitié d'entre elles.

> Si le client demande un **lien public de réservation**, à la GoHighLevel : pas
> disponible en édition Community. Odoo Enterprise ou un module tiers. **À
> chiffrer à part, ne pas le promettre en séance.**

---

## Questions qui reviennent

**« Où est passé l'onglet Reporting d'Odoo ? »**
Fermé, délibérément. Ses quatre rapports mesurent un chiffre d'affaires porté
par la fiche du lead — que ce pipeline ne porte pas, par conception. Ils
traçaient correctement les étapes et n'y empilaient **que des zéros**. Un
graphique de zéros n'est pas un rapport vide : c'est un rapport qui ment par
omission, et qu'on finit par croire. Le cockpit répond aux mêmes questions avec
des chiffres justes.

**« Peut-on changer les couleurs, les espacements ? »**
Oui. Rien n'est figé en dur : les huit couleurs des donuts sont des variables,
tout le reste passe par les jetons de thème d'Odoo. Une passe visuelle ne
touchera que ceux-là.

**« Peut-on ajouter un motif de perte, une étiquette ? »**
Oui, sans livraison de code. Personne ne peut en *supprimer* : ils
disparaîtraient de tous les dossiers qui les portent, sans trace. On les
désactive.

**« Le total de colonne, c'est du chiffre d'affaires ? »**
Non — voir l'acte 1. C'est une somme de scores. Le chiffre d'affaires est la
tuile *Revenu attendu*, acte 6. **Ne pas laisser cette ambiguïté s'installer.**

**« Et la capture automatique depuis le site ? »**
Elle existe, par n8n, et remplit les champs d'acquisition qu'on voit dans le
quatrième donut. Elle n'est pas dans cette démo-ci : elle a son propre
dispositif et sa propre recette.

---

## Remise à zéro

Rejouer la démo : relancez les deux scripts de la section *Préparer la base*.
Ils sont idempotents — ils ne créent pas de doublon, mais reposent les rôles et
les mots de passe.

**Après un acte 3 ou un acte 7 joué en séance**, la base a bougé : une
candidature perdue, un matricule émis. Pour repartir strictement à l'identique,
supprimez la base et refaites l'installation complète — c'est deux minutes.

> Ces comptes sont des comptes de **recette** : mot de passe connu, adresses
> `@example.com`. À ne jamais semer sur une base de production.
