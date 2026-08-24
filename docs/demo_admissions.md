# Démo — Parcours Admissions

**Durée** : 25 à 30 minutes · **Public** : Direction, Ventes, Admission, Finance

Ce qu'on montre : un candidat, de sa capture jusqu'à son inscription, en
passant par les quatre équipes qui le prennent en charge. Ce qui remplace
GoHighLevel et le classeur Excel.

---

## Avant de commencer

| | |
|---|---|
| **Adresse** | http://localhost:8069 — base `his_dev` |
| **Mot de passe** | `his2026` pour tous les comptes |
| **Navigateur** | Ouvrez **une fenêtre par rôle** et laissez-les ouvertes. Basculer de fenêtre est plus fluide que se déconnecter à chaque acte. |

> **« Fenêtre » = une session de navigateur connectée avec un compte donné.**
> Ce ne sont pas des pages différentes d'Odoo : ce sont les mêmes écrans, vus
> par des personnes différentes.
>
> Attention : dans Chrome et Edge, **tous les onglets privés partagent la même
> session** — deux onglets ne peuvent donc pas être connectés à deux comptes.
> Utilisez les **profils** du navigateur (un par rôle), **un navigateur
> différent par rôle** (Chrome, Firefox, Edge), ou les **onglets de conteneur**
> de Firefox.

Comptes à préparer :

| Fenêtre | Compte | Qui c'est |
|---|---|---|
| 1 | `marketing` | Capture les candidatures et les score |
| 2 | `asma` | Responsable Ventes — arbitre et affecte |
| 3 | `aicha` | Conseillère en admission |
| 4 | `orientation` | Cellule d'Orientation |
| 5 | `admission` | Back-office Admission |
| 6 | `finance` | Guichet paiements |
| 7 | `direction` | Direction — voit les deux processus, et les cockpits |

**Répétez la démo une fois avant de la jouer devant du monde.** Certains actes
créent des données définitives (une fiche personne, un matricule) qu'on ne
défait pas d'un clic.

---

## Le fil conducteur

> *Yasmine Haddad, 18 ans, bac sciences expérimentales avec 15,2 de moyenne,
> veut s'inscrire en informatique. Suivons-la.*

Gardez ce nom du début à la fin : c'est ce qui rend la démonstration
compréhensible pour quelqu'un qui ne connaît pas l'outil.

---

## Acte 1 — La capture et le score

**Fenêtre `marketing`** · *CRM › Admissions › Pipeline* · bouton **Nouveau**

Renseignez :

- Nom de l'opportunité : `Yasmine Haddad`
- Contact : `Yasmine Haddad`, email `yasmine.haddad@example.com`
- Onglet **Admissions** :
  - Spécialité visée : **Informatique - Systèmes d'information**
  - Moyenne du BAC : `15,2`
  - Note de maths : `13`
  - Pourquoi HIS ? : *« Recommandée par une amie diplômée »*

**Ce qu'il faut faire remarquer :**

> « Le champ *Note de physique* n'apparaît pas. L'informatique ne la demande
> pas. En électronique, il serait là — et obligatoire. »

> « Le score se calcule tout seul : **10 sur 10**. Et il s'explique :
> *BAC 15,20 : 6 pts + pondérée 14,10 : 3 pts + motivation : 1 pt*.
> Personne ne peut le forcer à la main. »

Créez un **second candidat** pour avoir une file : `Karim Belaid`,
spécialité **Sciences et Technologies - Électronique**, BAC `11`, maths `10`,
physique `9`, aucune motivation.

> « Là, la physique est demandée et obligatoire. Score : **4**. »

Laissez les deux tels quels et **ne les affectez à personne**.

---

## Acte 2 — La file d'attente

**Fenêtre `asma`** · *CRM › Admissions › Leads à affecter*

> « Voici la file. Yasmine à 10, Karim à 4 — **du meilleur score au moins
> bon**. Le Marketing ne choisit pas qui les traite : il les dépose ici. »

Cochez les deux lignes, modifiez **Commercial** sur l'une → les deux basculent
d'un coup.

Affectez Yasmine à **Aicha**, puis faites-la passer en **Pris en charge**.

> « À partir de maintenant, un chronomètre tourne. Si Aicha n'a pas appelé
> Yasmine dans les 4 heures, je reçois une relance — moi, pas Aicha. Elle sait
> déjà qu'elle a le dossier ; c'est justement le problème. »

---

## Acte 3 — Le premier contact, et l'identité qui naît

**Fenêtre `aicha`** · *CRM › Admissions › Pipeline*

> « Aicha ne voit que ses propres dossiers, plus la file de son équipe. Elle ne
> voit pas ceux de Rahma. »

Ouvrez Yasmine, passez-la en **Contact établi**.

**Le moment à souligner :**

> « Une fiche personne vient d'être créée. Regardez : »

*Identité › Personnes* → Yasmine y est, **Candidat**, source *Odoo CRM*, **avec
un matricule institutionnel**.

> « Ce matricule est à vie. Si Yasmine devient étudiante, puis enseignante chez
> nous dans dix ans, c'est le même. Une seule fiche par humain, pour tout le
> groupe. »

*Identité › Engagements* → un engagement à **Prospect**, qui a **déjà repris**
la spécialité, la moyenne et les notes saisies par le Marketing.

> « Rien n'a été retapé. Ce que le Marketing a saisi une fois suit le candidat
> jusqu'au bout. »

---

## Acte 4 — Le doublon *(optionnel, 2 minutes)*

Créez un lead avec **le même nom et le même email** que Yasmine, passez-le en
**Contact établi**.

> « Cette fois rien n'est rattaché. Le système dit : *une fiche existante
> ressemble à ce candidat, 75 % de similarité*, et propose deux boutons. C'est
> un humain qui tranche, jamais la machine. »

**À dire si on vous pose la question du même email dans une fratrie :**

> « Un email seul ne suffit pas à déclencher l'alerte. Deux frères qui
> candidatent la même année avec l'adresse des parents restent deux personnes
> distinctes. Il faut le nom **et** l'email pour qu'on vous demande de
> vérifier. »

---

## Acte 5 — La Cellule d'Orientation *(optionnel, 3 minutes)*

**Fenêtre `aicha`** : passez Yasmine en **Évaluation psychologique**.

**Fenêtre `orientation`** : *CRM › Admissions › Pipeline* → Yasmine apparaît.

> « La Cellule d'Orientation est une unité distincte des Ventes. Elle ne voit
> les candidats que **pendant** l'évaluation. Avant, rien. Après, rien. »

Remettez Yasmine en **Dossier et pré-admission** — elle disparaît de l'écran
d'`orientation`, sous leurs yeux.

> « Et si la Cellule prononce un refus, il se perd avec le motif *Hors quota
> commercial* : ce refus ne compte pas contre les objectifs des Ventes. »

---

## Acte 6 — La pré-admission, et ce qu'elle n'est pas

**Fenêtre `aicha`** : passez Yasmine en **Pré-admis**.

**Le moment fort de la démo.** Essayez de la glisser sur **Frais d'inscription
payés**. Le système refuse.

> *« Yasmine Haddad ne peut pas être gagnée : les frais d'inscription ne sont
> pas encaissés. »*

> « La pré-admission est une **décision**, pas une vente. Tant qu'un dinar n'est
> pas entré, le dossier n'est pas gagné — et l'équipe commerciale ne peut pas
> en décider elle-même. »

Cliquez **Ouvrir le dossier d'admission** → le dossier s'ouvre, à l'état
**Admis**, avec Aicha en conseillère. Essayez de cocher quelque chose :
**lecture seule**.

> « Aicha suit son candidat, répond à ses questions, mais ne valide rien à la
> place du back-office. »

---

## Acte 7 — L'instruction du dossier

**Fenêtre `admission`** · *Admission › Dossiers* → ouvrez Yasmine

**Onglet Dossier académique**

> « Les notes sont déjà là. Et l'éligibilité est calculée — **pas** avec la même
> formule que le score commercial. Le score sert à savoir qui rappeler en
> premier ; l'éligibilité, à savoir si le dossier tient académiquement. Deux
> questions, deux calculs. »

**Onglet Pièces** — le passage qui parle le plus aux utilisateurs.

> « Les pièces attendues sont déjà listées. Pas de certificat d'équivalence :
> Yasmine a un bac algérien. Pas d'attestation de licence : c'est une licence,
> pas un master. »

Pour montrer que la liste s'adapte : cochez d'abord **Pièce d'identité**, puis
passez le **Cycle** à **Master** → les deux pièces master apparaissent, et la
pièce d'identité **reste cochée**.

> « Une pièce déjà cochée garde sa trace. On n'efface jamais la preuve qu'un
> document a été reçu. »

> ⚠️ **Répétez ce passage avant la démo.** Changer le cycle vide le champ
> *Spécialité*, dont la liste dépend du cycle : resélectionnez-la avant de
> repasser en Licence, sinon vous perdez l'éligibilité affichée. Si vous
> préférez ne pas prendre le risque en public, décrivez l'effet sans le jouer.

Essayez de passer l'état à **Inscrit** → **refus**, avec la liste des pièces
manquantes.

> « Dans le fichier Excel, la colonne existait. Elle était vide sur presque
> toutes les lignes, y compris des dossiers marqués *Inscrit*. Ici, ce n'est
> plus possible. »

Cochez toutes les pièces obligatoires, réessayez → **refus à nouveau** : les
droits ne sont pas encaissés.

---

## Acte 8 — L'encaissement, et le gagné qui arrive tout seul

**Fenêtre `finance`**

> « Le guichet n'a **qu'une seule entrée de menu**. Pas de dossiers, pas de
> notes, pas de configuration. »

*Admission › Suivi des droits* → ligne de Yasmine → **Encaisser inscription**.

> « Il n'y a pas de case à cocher. Un encaissement s'enregistre, il ne se coche
> pas. »

**Revenez à la fenêtre `aicha`** et rechargez le lead.

> « Il est passé **tout seul** en *Frais d'inscription payés*, et Odoo le compte
> gagné. Personne aux Ventes ne l'y a mis. Le chiffre du pipeline, c'est de
> l'argent reçu — pas des intentions. »

C'est **le** message de la démonstration. Prenez le temps.

---

## Acte 9 — L'inscription définitive

**Fenêtre `finance`** : encaissez aussi la **scolarité**.

**Fenêtre `admission`** : passez le dossier à **Inscrit**. Cette fois, ça passe.

Renseignez le **numéro d'étudiant** (onglet Inscription).

---

## Acte 10 — Les transmissions

**Fenêtre `admission`** · *Admission › Transmissions*

Montrez les trois entrées, puis sur **Ministère** : tout sélectionner →
**Exporter** → XLSX.

> « C'est le fichier que vous envoyez aujourd'hui, avec les mêmes colonnes.
> Sauf qu'il n'y a plus d'onglet à tenir à jour à la main : c'est la même
> donnée, regardée autrement. »

Ouvrez **Service national**.

> « Celle-ci ne liste que les hommes. Le filtre est dans l'outil, plus dans la
> tête de celui qui prépare le fichier. »

Puis *Admission › Cartes étudiant* et *Parents et tuteurs*.

> « Six onglets du classeur, une seule donnée. Changer un numéro de téléphone
> se faisait dans quatre endroits ; maintenant dans un. »

---

## Acte 11 — Ce que la Direction regarde *(4 minutes)*

**Fenêtre `direction`** · application **Direction** › *Vue d'ensemble*

> « Jusqu'ici on a suivi une candidate. Voici le même processus vu de haut, et
> c'est un autre métier : le directeur ne traite pas les dossiers, il décide où
> mettre l'effort. »

**Les tuiles.** Candidatures reçues, inscriptions, taux de conversion, dossiers
complets, demandes de contenu. Chacune porte l'écart avec la période précédente.

**Cliquez sur « Candidatures reçues ».** Elle ouvre exactement les candidatures
qu'elle compte.

> « Un chiffre qu'on ne peut pas ouvrir, il faut le croire sur parole. Ici
> chaque nombre mène aux lignes qui le composent — et c'est aussi comme ça qu'on
> attrape un indicateur qui se trompe. »

**L'entonnoir.** Les huit étapes du parcours, avec le taux de passage de l'une à
la suivante.

> « Le taux se lit d'une marche à la suivante, pas depuis le début. C'est celui-là
> qui désigne l'endroit où l'on perd les candidats. »

**« À traiter ».** Candidatures non affectées, premier contact en retard,
candidatures en sommeil, dossiers incomplets, lettres non émises.

> « Ce ne sont pas des moyennes, ce sont des exceptions. Le retard du premier
> contact, c'est **exactement** la même définition que la relance automatique
> qui se pose dans les fiches — pas un second calcul qui dirait autre chose. »

Passez ensuite sur *Direction › Admissions* puis *Direction › Production
Contenu*.

> « Le même écran, trois périmètres. Et le responsable des admissions retrouve
> le sien directement dans son menu Admissions : chacun a ses indicateurs là où
> il travaille. »

**Le sélecteur de période** en haut change tout l'écran d'un coup.

### L'objectif — à préparer avant la démo

*Direction › Objectifs* → **Nouveau** : intitulé `Rentrée 2026`, axe
**Candidatures reçues**, cible `300`, du `01/01/2026` au `31/12/2026`.

Revenez sur la vue d'ensemble : la tuile affiche désormais l'atteinte, le rythme
qu'il reste à tenir et la projection de fin de période.

> « Sans cible, un tableau de bord ne fait que compter. Avec une cible, il dit
> s'il faut accélérer, et de combien. C'est la différence entre constater et
> décider. »

> **Ne sautez pas cette préparation.** Sans objectif saisi, les tuiles
> n'affichent que des compteurs nus — et c'est précisément l'effet qu'on veut
> montrer qui manque.

---

## Les trois phrases à retenir

1. **« Le score classe la file, il ne se négocie pas. »**
   Calculé depuis les notes, explicable, non modifiable.

2. **« On ne gagne pas un lead, on encaisse un paiement. »**
   La conversion est la conséquence d'un fait enregistré par une autre équipe.

3. **« Le dossier incomplet ne passe pas. »**
   Ce que le classeur laissait faire, l'outil le refuse.

---

## Questions qu'on vous posera

**« Et si je dois passer outre ? »**
Vous ne pouvez pas, et c'est voulu. Un dossier incomplet reste en *Admis* ou
part en *Blocage administratif* — un état qui se voit et se compte. Ce qui se
contourne ne protège personne.

**« On perd du temps par rapport au fichier Excel ? »**
On saisit une fois au lieu de quatre. Le score, l'éligibilité et les listes de
transmission ne se calculent plus à la main.

**« Et si un candidat abandonne après la pré-admission ? »**
Vous le perdez avec le motif *Paiement non confirmé*. C'est un geste manuel :
personne ne voulait qu'un délai automatique ferme des dossiers.

**« Qui peut voir quoi ? »**
Une conseillère voit ses dossiers et la file de son équipe. Le responsable voit
toute l'équipe. La Cellule d'Orientation ne voit un candidat que pendant son
évaluation. Le guichet Finance ne voit que les droits. L'Admission ne voit pas
le CRM.

**« Le formulaire du site alimente-t-il tout ça ? »**
Pas encore. Les champs sont prêts, le raccordement est un chantier à part.
**Ne le promettez pas comme fait.**

---

## Ce qui n'existe pas encore — à ne pas promettre

- Le raccordement du formulaire public (viendra par n8n)
- Les montants et la comptabilité : payé / non payé seulement
- L'édition automatique des lettres d'acceptation et attestations
- Les soutenances et la fin de cursus
- La reprise des données de GoHighLevel : **départ à neuf, aucun historique**
- L'analyse historique et pluriannuelle : les cockpits répondent sur la
  période en cours. Les cohortes, les comparaisons entre rentrées et les
  croisements avec d'autres sources sont le travail de l'outil de BI (Metabase),
  qui viendra ensuite

---

## Remise à zéro entre deux démos

Les fiches personne et leurs matricules **ne se suppriment pas** d'un clic —
c'est le principe d'un identifiant à vie. Pour une démo propre, demandez la
reconstruction d'une base de démonstration dédiée plutôt que de nettoyer à la
main.

En dépannage rapide : archivez les leads créés (*Action › Archiver*) et
laissez les fiches personne, elles ne gênent pas la démo suivante — sauf si
vous rejouez **exactement le même nom et le même email**, auquel cas le
rapprochement de doublon se déclenchera. C'est d'ailleurs une manière de
montrer l'acte 4 sans le préparer.
