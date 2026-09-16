# his_pos_numbering — Le numero d'operation affiche en caisse

Les onglets de commande affichent **1, 2, 3 …** par caisse, au lieu de `5001`,
`4001`, `6003`.

---

## 1. D'ou venait « 5001 »

Le coeur compose `tracking_number` ainsi (`pos_store.js:1432` cote navigateur,
`pos_config.py:216` cote serveur) :

```
identifiant_de_peripherique + (numero % 1000) sur trois chiffres
```

Le chiffre de tete n'est pas la caisse. C'est un compteur de **navigateurs**
enregistres pour cette caisse (`pos.config.device_seq_id`, sans rembourrage) :

| Caisse | `device_seq_id` | ce qu'on voyait |
|---|---|---|
| Cafétéria | 7 | `7xxx` au prochain navigateur |
| Restaurant | 6 | `6001`, `6002`, `6003` |
| Copy Center | 8 | `8xxx` au prochain navigateur |

D'ou l'impression d'arbitraire : vider les donnees de site d'une caisse lui
donne un nouveau chiffre de tete sans que rien de metier ait bouge, et le
Restaurant affichait `6xxx` alors qu'il est la caisse n° 2. Au dixieme
navigateur, l'affichage passerait meme a cinq caracteres (`10001`).

## 2. Ce qui est affiche maintenant

`sequence_number`, que le coeur pose **deja** sur chaque commande depuis
`pos.config.order_seq_id` : une sequence **par caisse**, en `no_gap`, qui ne se
reinitialise jamais. Le 1, 2, 3 attendu existait donc deja en base — ce module
ne fait que le montrer.

Ordre de preference, le premier qui repond gagne :

1. **`floating_order_name`** — le nom qu'un caissier a donne a la commande.
   Une intention humaine explicite passe devant un compteur.
2. **`sequence_number`** — le numero d'operation de cette caisse.
3. **`…`** — la commande n'est pas encore synchronisee.

### Pourquoi un marqueur et pas le numero local

Le numero d'operation est attribue par le **serveur**, a la creation de la
commande. Avant la synchronisation il n'existe pas. Afficher a la place le
compteur local du navigateur donnerait un numero qui **change** ensuite : un
caissier qui l'a annonce a voix haute aurait dit faux. Le module prefere
avouer l'attente. `isSynced` (`related_models/base.js`) est
`typeof id === "number"` : c'est exactement « la commande a-t-elle atteint le
serveur ».

## 3. Ce que ce module ne touche pas

- **`tracking_number` est intact.** Il reste en base et continue d'alimenter
  les remboursements, les tickets imprimes et `pos_self_order`. Rien n'est
  renumerote, rien n'est migre.
- Aucun champ, aucune vue, aucun appel serveur, aucune migration.
- « (Refund) » continue d'etre ajoute par `getName()` du coeur : ce module
  n'etend que le getter que `getName()` appelle.

## 4. La recherche suit l'affichage

L'ecran des tickets construit un domaine serveur depuis une liste etroite
(`_getSearchFields`, entree « Reference »). `sequence_number` y est ajoute,
**devant** les deux champs d'origine qui sont conserves : une commande creee
avant ce module reste retrouvable par son ancien numero.

## 5. Pourquoi un module separe

`his_pos_ui` promet dans son README de ne contenir que du CSS et une classe, et
de ne patcher aucun composant — c'est cette promesse qui le rend sans danger
sur une caisse qui encaisse deja. La numerotation est un **comportement** :
elle vit donc chez elle, s'installe et se retire seule.

## 6. Remise des compteurs a 1

Les trois sequences etaient a 3 (Cafétéria), 10 (Restaurant) et 2 (Copy
Center) : la numerotation aurait donc commence la, et non a 1. Elles ont ete
remises a 1 **une seule fois**, a la main, sur un serveur de test.

Ce n'est deliberement **pas** une migration : une migration rejouerait la
remise a chaque deploiement et effacerait la numerotation reelle. Et sur une
base portant de vraies ventes, remettre une sequence a 1 reattribue des numeros
deja emis — a ne pas refaire sans y penser.
