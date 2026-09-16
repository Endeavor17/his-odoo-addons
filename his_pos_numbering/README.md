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

Le numero porte par **`pos_reference`**, que le coeur pose des la **creation**
de la commande : `{AA}{peripherique}-{caisse}-{numero}`, par exemple
« 266-1-000003 ». Son troisieme segment est le numero, non rembourre et sans
repli modulo. Le coeur le lit lui-meme ainsi
(`extractNumberFromReference` dans `utils/devices_identifier_sequence.js`) :
ce module reutilise sa lecture au lieu de deviner un format.

Ordre de preference, le premier qui repond gagne :

1. **`floating_order_name`** — le nom qu'un caissier a donne a la commande.
   Une intention humaine explicite passe devant un compteur.
2. **le numero tire de `pos_reference`** — disponible immediatement et
   inchange par la synchronisation.
3. **`sequence_number`** — repli, si une commande arrive sans reference
   exploitable.
4. **`…`** — aucun numero connu. Jamais un chiffre : rien ne doit ressembler a
   un numero d'operation quand il n'y en a pas.

### Pourquoi pas `sequence_number` en premier

C'etait le plan initial, et **le rendu l'a dementi**. `sequence_number` est
pose par le SERVEUR a la creation de l'enregistrement ; il vaut 0 tant que la
commande n'est pas synchronisee, et une commande POS ne se synchronise qu'a la
validation. En ouvrant une vraie caisse, les deux onglets affichaient donc
« … » cote a cote la ou le caissier attend 1 et 2 — pendant toute la saisie,
c'est-a-dire tout le temps qui compte.

`pos_reference` n'a pas ce defaut : il est attribue en meme temps que la
commande, le serveur le conserve tel quel a la synchronisation
(`_process_order` cree l'enregistrement avec les valeurs du navigateur), donc
le numero annonce a voix haute par le caissier ne change jamais.

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
