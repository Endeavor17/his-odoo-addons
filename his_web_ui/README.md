# his_web_ui — Où l'on atterrit en se connectant

L'idée directrice, énoncée d'abord :

> **Atterrir quelque part est une décision, pas un ordre de tri.**

---

## 1. Le problème

Odoo Community n'a pas de page d'accueil. Sans action d'accueil, le client web
ouvre **le premier menu racine visible, trié par séquence**. Personne n'a choisi
cela : c'est un nombre dans un fichier XML qui gagne un tri.

Concrètement, `menu_direction_root` portait `sequence="2"`. Toute personne
portant le groupe Direction atterrissait donc sur le tableau de bord Direction
chaque matin, quel que soit son métier — et lorsque ce menu était masqué, sur
Discuss, qui n'était que le suivant dans le tri.

**Masquer un menu n'est pas un droit.** L'attribut `groups` d'un `menuitem`
retire le lien, pas l'action : l'URL résout toujours, et l'accès aux données
dépend d'ACL et de règles d'enregistrement séparées. C'est pourquoi un directeur
à qui l'on avait retiré le groupe continuait d'atterrir sur un écran qu'il ne
pouvait pas lire.

## 2. Ce que ce module possède, et ce qu'il ne possède pas

| | Propriétaire |
|---|---|
| Grille d'applications, menu plein écran, recherche | `web_responsive` (OCA, copié à la racine) — **pas ici** |
| Choix de la grille comme atterrissage par défaut | **ici** |
| Rattrapage de l'action d'accueil devenue orpheline | **ici** |
| Nom et séquence de l'application Direction | `his_crm_pipeline` — **pas ici** |

Ce module **ne réimplémente rien**. La grille vient de l'OCA ; ici on décide
seulement qu'elle est la page d'accueil de l'établissement.

## 3. La règle, énoncée en entier

`web_responsive` n'en écrit que la moitié :

```python
self.filtered("action_id").is_redirect_home = False
```

Il *efface* le drapeau quand une action d'accueil existe, et ne le pose jamais.
Le champ retombe donc sur `False`, et chaque utilisateur devrait cocher une case
pour obtenir la grille. L'autre moitié est écrite ici : **pas d'action d'accueil
⇒ la grille**.

D'où une surcharge de calcul plutôt qu'un enregistrement `ir.default` : sur un
champ calculé stocké, une valeur par défaut dépend de l'ordre dans lequel le
calcul s'exécute et assigne, alors que la surcharge est déterministe.

**Une action d'accueil l'emporte toujours sur la grille.** C'est la conception
d'amont et elle est conservée : qui ouvre le même écran tous les jours doit
pouvoir continuer.

## 4. Ce que fait l'installation

Le `post_init_hook` :

1. efface **une seule** action d'accueil, celle qui pointe sur le tableau de
   bord Direction, parce qu'elle avait survécu au groupe qui la justifiait.
   Effacer toutes les actions d'accueil détruirait des choix délibérés faits
   pour d'autres personnes ;
2. pose le drapeau sur les utilisateurs internes qui n'ont aucune action
   d'accueil — leur ligne portait encore le `False` stocké, le calcul ne se
   déclenchant qu'au changement de `action_id`.

À l'installation seulement. Une mise à jour ultérieure ne réécrit donc jamais ce
que quelqu'un a choisi depuis.

### Ce que l'installation a réellement trouvé sur `his_dev` (2026-08-29)

**Aucun utilisateur ne portait d'action d'accueil**, et l'étape 1 n'a donc rien
effacé : elle a posé le drapeau sur les 4 utilisateurs internes, rien de plus.
Le compte `bahriz` n'existe pas sur cette base et personne n'y porte le groupe
Direction — les profils de direction vivent sur l'autre instance
(`deploy/odoo-dev/`).

Cela dit quelque chose d'utile : sur cette base, le symptôme rapporté ne pouvait
venir que de `sequence="2"`, pas d'une action d'accueil. L'étape 1 reste écrite
parce que l'hypothèse n'a pas pu être vérifiée là où les directeurs existent —
elle y sera un rattrapage ou un non-événement, et son journal le dira.

## 5. Écarts assumés

- **La grille reste une dépendance tierce.** `web_responsive` est copié dans ce
  dépôt et non installé par `pip` : voir `web_responsive/VENDOR.md` pour le
  commit exact et la procédure de mise à jour.
- **Le nom « Direction » du groupe n'est pas touché** alors que le menu devient
  « Marketing & Sales Dashboard ». Le groupe nomme qui l'on est, le menu nomme
  ce que l'on ouvre.
