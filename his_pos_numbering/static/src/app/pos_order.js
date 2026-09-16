import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// Ce que le caissier lit sur l'onglet d'une commande.
//
// `getName()` du coeur (models/pos_order.js) renvoie `floatingOrderName` et y
// ajoute « (Refund) » pour un remboursement : en n'etendant que le getter, ce
// suffixe continue de fonctionner sans qu'on le recopie.
//
// Ordre de preference, le premier qui repond gagne :
//
//   1. `floating_order_name` — le nom qu'un caissier a donne a la commande.
//      Il passe devant tout : c'est une intention humaine explicite.
//   2. `sequence_number` — le numero d'operation de CETTE caisse, pose par le
//      serveur depuis `pos.config.order_seq_id` (sequence `no_gap`, par
//      caisse, jamais reinitialisee). C'est le 1, 2, 3 attendu.
//   3. un marqueur provisoire — la commande n'est pas encore synchronisee,
//      donc son numero d'operation n'existe pas encore : le serveur l'attribue
//      a la creation. Afficher ici le compteur local du navigateur donnerait
//      un numero qui CHANGE apres synchronisation ; un caissier qui l'a
//      annonce a voix haute aurait dit faux. Mieux vaut avouer l'attente.
//
// `isSynced` (related_models/base.js) est `typeof this.id === "number"` : une
// commande non synchronisee porte un id local textuel, une commande passee par
// le serveur porte son id entier. C'est donc exactement « a-t-elle atteint le
// serveur », et pas une approximation.
//
// `tracking_number` n'est deliberement plus lu ici. Il reste intact en base et
// continue de servir les remboursements, les tickets et pos_self_order.
patch(PosOrder.prototype, {
    get floatingOrderName() {
        if (this.floating_order_name) {
            return this.floating_order_name;
        }
        if (this.sequence_number) {
            return this.sequence_number.toString();
        }
        // Volontairement pas un chiffre : rien ne doit ressembler a un numero
        // d'operation tant que le serveur n'en a pas attribue un.
        return _t("…");
    },
});
