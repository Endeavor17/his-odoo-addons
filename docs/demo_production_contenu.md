# Démo — Production de contenu

**Durée** : 15 à 20 minutes · **Public** : Marketing, production de contenu, Direction

Ce qu'on montre : une demande de contenu, de l'idée jusqu'à la publication, avec
trois livrables qui avancent en parallèle et une approbation qu'on ne peut plus
oublier.

---

## Avant de commencer

| | |
|---|---|
| **Adresse** | http://localhost:8069 — base `his_dev` |
| **Mot de passe** | `his2026` pour tous les comptes |
| **Navigateur** | Une fenêtre privée par rôle, toutes ouvertes en même temps |

> **« Fenêtre » = une fenêtre de navigation privée**, connectée avec un compte
> donné, et qu'on laisse ouverte pendant toute la démo. Ce ne sont pas des
> pages différentes d'Odoo : ce sont les mêmes écrans, vus par des personnes
> différentes. Basculer d'une fenêtre à l'autre revient à changer de bureau.
>
> Dans Chrome et Edge, une seule fenêtre privée est partagée par tous les
> onglets — deux onglets privés ne peuvent donc pas être connectés à deux
> comptes. Utilisez plutôt les **profils** du navigateur (un profil par rôle),
> ou **un navigateur différent par rôle** (Chrome, Firefox, Edge), ou les
> **onglets de conteneur** de Firefox.

| Fenêtre | Compte | Qui c'est |
|---|---|---|
| 1 | `marketing` | Dépose les demandes |
| 2 | `cherif` | Priorisation — trie, affecte les livrables, arbitre |
| 3 | `contenu` | Rédaction (copywriting) |
| 4 | `design` | Design |
| 5 | `video` | Vidéo |
| 6 | `direction` | Direction — approuve, et regarde le cockpit |
| 7 | `aicha` | *Une conseillère Ventes — sert uniquement à l'acte 6* |

> **`marketing` dépose mais ne priorise pas.** Il porte les rôles *Acquisition*
> et *Production*, pas *Priorisation* : affecter un livrable ou faire avancer
> une demande avant la production appartient à `cherif`. Ce n'est pas une
> limite d'écran, c'est le serveur qui refuse — et c'est précisément ce que
> l'acte 6 démontre.

---

## Le fil conducteur

> *La rentrée approche. Les Admissions demandent une campagne : un texte, trois
> visuels et une vidéo, pour la marque HIS.*

---

## Acte 1 — La demande

**Fenêtre `marketing`** · *Production Contenu › Demandes* · **Nouveau**

- Nom : `Campagne rentrée 2026 — Licence Informatique`
- Date limite : **dans une semaine** *(elle sert au suivi des retards)*
- Onglet **Production contenu** :
  - Département demandeur : **Ventes / Admissions**
  - Marque : **HIS**
  - Dans la liste **Livrables**, ajoutez trois lignes : **Copywriting**,
    **Design**, **Video**

> « N'importe quel département dépose ici : les Ventes, les RH, la Pédagogie, le
> Marketing lui-même. Aujourd'hui ça arrive par message, par mail, de vive voix
> — et ça se perd. »

> « Une ligne par livrable, et **seulement** pour ceux qui sont demandés. Une
> demande sans vidéo n'a pas de ligne vidéo — l'outil sait donc dire
> *« pas concerné »*, et pas seulement *« pas encore fait »*. »

Laissez la demande en **Demande / Idée**.

---

## Acte 2 — La priorisation

**Fenêtre `cherif`** *(Priorisation)* · ouvrez la demande, passez-la en
**Priorisation**, puis affectez chaque livrable dans la liste :

| Livrable | Assigné à |
|---|---|
| Copywriting | **Redaction (copywriting)** |
| Design | **Design** |
| Video | **Video** |

Passez en **Production**.

> « Une demande, trois personnes, en même temps. C'est là que le tableur
> craquait : une seule ligne, une seule colonne de statut, et trois métiers qui
> ne vont pas au même rythme. »

*Si vous voulez le montrer :* tentez la même affectation depuis la fenêtre
`marketing` — refus. *« Affecter un livrable demande le rôle Priorisation. »*
Le tri est un arbitrage, il a un propriétaire.

---

## Acte 3 — Trois rythmes différents *(le cœur de la démo)*

**Ouvrez d'abord la même demande dans les trois fenêtres** `contenu`, `design`
et `video` — *Production Contenu › Demandes*, puis la campagne de rentrée,
onglet **Production contenu**. Les trois regardent le même dossier.

Puis, en basculant de l'une à l'autre devant le public, chacun change le statut
**de sa propre ligne** :

| Fenêtre | Ligne | Statut |
|---|---|---|
| `contenu` | Copywriting | **Approuve** |
| `design` | Design | **Revision interne** |
| `video` | Video | **En cours** |

Enregistrez à chaque fois, puis rechargez une des fenêtres.

> « Trois personnes, un seul dossier, et chacune ne touche que son livrable. »

**Montrez le refus** : en `design`, essayez de changer le statut de la ligne
*Copywriting*.

> *« Le livrable Copywriting n'est pas le vôtre. Seule la personne à qui il est
> assigné fait avancer son statut, ou le rôle Priorisation qui arbitre. »*

> « La règle ne tient pas à des groupes, elle tient à la donnée : c'est
> l'assignation qui décide. Deux designers se partagent un livrable en changeant
> l'assignation, pas les droits. »

*Si jongler entre trois fenêtres vous gêne en public* : faites tout depuis la
fenêtre `cherif`, qui arbitre et peut modifier les trois statuts. Vous perdez la
démonstration du travail en parallèle, mais le propos sur les trois rythmes
tient toujours.

> « Le texte est approuvé. Le design est en révision. La vidéo n'est pas
> finie. Les trois sont vrais **en même temps** — et c'est exactement ce
> qu'une case unique ne sait pas dire. »

---

## Acte 4 — Le verrou d'approbation *(le moment fort)*

**Fenêtre `direction`** : essayez de faire passer la demande en **Approbation**.

Le système refuse :

> *« Campagne rentrée 2026 ne peut pas passer en Approbation : le ou les
> livrables suivants ne sont pas approuvés — Design, Video. »*

**Ce qu'il faut dire :**

> « Dans le fichier de suivi actuel, il y a une colonne *Approval Status*. Elle
> est vide sur presque toutes les lignes réelles — parce que rien n'obligeait à
> la remplir. Ici, on ne peut pas aller plus loin sans elle. »

> « Et ce n'est pas un blocage de l'écran : c'est le serveur qui refuse. Passer
> par un import, par le kanban ou par l'API ne change rien. Une règle qu'on
> contourne n'est pas une règle. »

Faites approuver le design (`design`) et la vidéo (`video`), puis
retentez en `direction` → **ça passe**.

---

## Acte 5 — Approbation, planification, publication

**Fenêtre `direction`** : la demande est en **Approbation**.

Montrez les deux issues :

- **Perdu** avec le motif **Retour production nécessaire**
  > « Un refus n'est pas une perte sèche, c'est un renvoi en production. »
- ou avancer vers **Planification et publication**

Passez-la en **Planification et publication**.

> « La marque est portée par la demande depuis le début — HIS, HTC ou IRA. Le
> plan éditorial sait pour qui il publie. »

---

## Acte 6 — Le cloisonnement

**Fenêtre `aicha`** *(conseillère Ventes)* : cherchez l'application
**Production Contenu**.

> « Elle n'existe pas. Ce n'est pas une liste vide avec un message poli : il n'y
> a pas d'application du tout. »

Et en `contenu` *(Design ou Vidéo font aussi bien)* : cherchez le **CRM**.

> « Pas de CRM non plus. Un graphiste n'a aucun accès aux candidatures — donc
> aucun accès aux contacts, à la fusion de leads, au calendrier commercial. Ce
> n'est pas un menu masqué : le rôle ne porte tout simplement aucun groupe
> commercial. »

Puis en `aicha` : *CRM › Admissions › Pipeline* → ses candidats.

> « Deux processus sans rapport dans le même outil, et personne ne voit le
> travail de l'autre. »

**Fenêtre `marketing`** : les **deux** applications sont là.

> « Le Marketing est la seule équipe présente des deux côtés : il capte les
> candidatures **et** produit le contenu. C'était déjà son double rôle. »

---

## Acte 7 — Ce que la Direction regarde *(3 minutes)*

**Fenêtre `direction`** · *Production Contenu › Cockpit*

Ce n'est pas une liste groupée : c'est l'écran qui répond avant qu'on demande.

**Les tuiles** — demandes reçues, contenus publiés, livrables en retard, et
**en attente d'approbation**.

> « Cette dernière tuile, c'est ma propre file : ce qui attend ma signature.
> Le tableau de bord ne me dit pas seulement comment va l'équipe, il me dit ce
> que je bloque. »

**Cliquez sur une tuile.** Elle ouvre exactement les demandes qu'elle compte.

> « Un chiffre qu'on ne peut pas ouvrir, il faut le croire sur parole. Ici
> chaque nombre mène aux lignes qui le composent. »

**« À traiter »** — livrables non assignés, livrables en retard, demandes
bloquées en production depuis plus de dix jours.

> « Ce ne sont pas des moyennes, ce sont des exceptions. C'est la moitié de
> l'écran qui fait travailler. »

**« Explorer »** → *Charge par personne* : qui a combien de travail, en un
clic.

> « Cette question n'avait pas de réponse avant : le statut vivait dans trois
> colonnes d'une même ligne, et trois colonnes ne se groupent pas entre elles.
> Un livrable est devenu une ligne, et la question s'est résolue toute seule. »

**Le sélecteur de période** en haut change tout l'écran d'un coup.

> **Si un objectif a été saisi** *(Direction › Objectifs)*, la tuile
> *Contenus publiés* affiche l'atteinte, le rythme qu'il reste à tenir et la
> projection de fin de période. Sans objectif, elle n'affiche qu'un compteur —
> **saisissez-en un avant la démo**, c'est ce qui fait la différence entre
> constater et décider.

---

## Les trois phrases à retenir

1. **« Une demande, trois livrables, trois rythmes. »**
   Ce qu'une colonne de statut ne pouvait pas exprimer.

2. **« On ne passe pas l'approbation avec un livrable non approuvé. »**
   Le trou du tableur, fermé par construction.

3. **« Chacun ne voit que son processus. »**
   Deux workflows, un seul outil, aucun mélange.

---

## Questions qu'on vous posera

**« Pourquoi nos demandes de contenu sont-elles des "opportunités" ? »**
Réponse honnête : c'est le même moteur que les admissions, réglé autrement. On
récupère gratuitement le tableau kanban, les activités, les pièces jointes, les
relances et l'historique de discussion. Un modèle séparé aurait voulu dire
réécrire ces cinq mécaniques pour une dizaine de demandes par semaine.
Contrepartie : il faut filtrer par équipe dans les rapports de revenu, sans quoi
les demandes de contenu s'y mélangeraient.

**« Peut-on ajouter un type de livrable — un podcast, une affiche ? »**
Oui. C'est une petite évolution, pas une refonte : la mécanique d'approbation et
l'écran suivent automatiquement.

**« Et si deux designers travaillent sur la même demande ? »**
Un seul est désigné aujourd'hui. Le tableur en montrait deux, interchangeables ;
dites-le si vous voulez pouvoir en désigner plusieurs.

**« Peut-on planifier la date de publication ? »**
Pas encore. L'étape existe, le calendrier éditorial est un chantier à part.

**« Est-ce que ça publie sur Facebook et Instagram ? »**
Non, et ce n'est pas prévu dans ce périmètre. **Ne le promettez pas.**

---

## Ce qui n'existe pas encore — à ne pas promettre

- Publication automatique sur les réseaux sociaux
- Calendrier éditorial et programmation des dates
- Suivi du temps passé par livrable *(les dates de démarrage et de fin sont
  posées, mais personne ne saisit d'heures)*
- Dépendances entre livrables *(« la vidéo attend le texte »)*
- Stockage des fichiers produits — le chatter accepte les pièces jointes, mais
  ce n'est pas une médiathèque

---

## Remise à zéro entre deux démos

Les demandes de contenu sont sans conséquence : archivez-les
(*Action › Archiver*) ou supprimez-les. Contrairement au parcours Admissions,
rien ici ne crée d'identité ni de matricule.
