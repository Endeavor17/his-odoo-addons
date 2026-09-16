import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// Le numero d'operation porte par la reference de la commande.
//
// `pos_reference` vaut `{AA}{peripherique}-{caisse}-{numero}` (par exemple
// « 266-1-000003 »), pose des la CREATION de la commande — cote navigateur par
// `setNextOrderRefs` (pos_store.js), cote serveur par `_get_next_order_refs`
// (pos_config.py). Son troisieme segment est le numero, non rembourre et sans
// repli modulo : c'est le 1, 2, 3 cherche.
//
// Le coeur lui-meme le lit ainsi (`extractNumberFromReference` dans
// utils/devices_identifier_sequence.js) : on ne devine pas un format, on
// reutilise sa lecture.
function numeroDepuisReference(reference) {
    const segments = String(reference || "").split("-");
    if (segments.length < 3) {
        return 0;
    }
    const numero = parseInt(segments[2], 10);
    return Number.isFinite(numero) ? numero : 0;
}

// Ce que le caissier lit sur l'onglet d'une commande.
//
// `getName()` du coeur renvoie `floatingOrderName` et y ajoute « (Refund) »
// pour un remboursement : en n'etendant que le getter, ce suffixe continue de
// fonctionner sans etre recopie.
//
// Ordre de preference, le premier qui repond gagne :
//
//   1. `floating_order_name` — le nom qu'un caissier a donne a la commande.
//      Une intention humaine explicite passe devant un compteur.
//   2. le numero tire de `pos_reference` — disponible IMMEDIATEMENT, des la
//      creation, et inchange par la synchronisation.
//   3. `sequence_number` — repli : le numero d'operation que le serveur pose
//      depuis `pos.config.order_seq_id`. Utile si une commande arrive un jour
//      sans reference exploitable.
//   4. un marqueur, jamais un chiffre : rien ne doit ressembler a un numero
//      quand aucun n'est connu.
//
// Pourquoi PAS `sequence_number` en premier, contrairement au plan initial :
// il vaut 0 tant que la commande n'est pas synchronisee, et une commande POS
// ne se synchronise qu'a la validation. L'onglet affichait donc « … » pendant
// toute la saisie — verifie en ouvrant une vraie caisse, deux onglets « … »
// cote a cote la ou le caissier attend 1 et 2.
//
// `tracking_number` reste intact en base et continue de servir les
// remboursements, les tickets et pos_self_order ; il n'est simplement plus ce
// que l'onglet affiche, parce que son chiffre de tete est un compteur de
// navigateurs et non la caisse.
patch(PosOrder.prototype, {
    get floatingOrderName() {
        if (this.floating_order_name) {
            return this.floating_order_name;
        }
        const numero = numeroDepuisReference(this.pos_reference);
        if (numero) {
            return numero.toString();
        }
        if (this.sequence_number) {
            return this.sequence_number.toString();
        }
        return _t("…");
    },
});
