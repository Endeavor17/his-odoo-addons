import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import { patch } from "@web/core/utils/patch";

// Un fonds compte different du solde de la veille s'explique a l'ouverture.
patch(OpeningControlPopup.prototype, {
    get hisNeedsNote() {
        if (!this.env.utils.isValidFloat(this.state.openingCash)) {
            return false;
        }
        // montant affiche formate (« 5,000.00 ») : le parseFloat natif lirait 5
        const difference =
            this.env.utils.parseValidFloat(this.state.openingCash) - (this.pos.session.cash_register_balance_start || 0);
        return !this.pos.currency.isZero(difference) && !this.state.notes.trim();
    },
});
