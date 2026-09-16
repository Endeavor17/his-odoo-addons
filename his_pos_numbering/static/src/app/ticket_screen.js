import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";

// La recherche doit porter sur ce qui est AFFICHE.
//
// `_getSearchFields()` du coeur declare pour « Reference » une liste etroite
// (`["tracking_number", "floating_order_name"]`) qui construit un domaine
// serveur (ticket_screen.js, lignes ~797-803). Comme l'onglet et la liste des
// tickets affichent desormais `sequence_number`, une recherche qui ne
// l'interroge pas ne trouverait pas la commande que le caissier a sous les
// yeux : il taperait « 7 » et n'obtiendrait rien.
//
// Les deux champs d'origine sont conserves : les commandes creees AVANT ce
// module restent retrouvables par leur ancien numero, et un nom de commande
// donne a la main continue de repondre.
patch(TicketScreen.prototype, {
    _getSearchFields() {
        const fields = super._getSearchFields();
        if (fields.REFERENCE) {
            fields.REFERENCE.modelFields = [
                "sequence_number",
                ...fields.REFERENCE.modelFields,
            ];
        }
        return fields;
    },
});
