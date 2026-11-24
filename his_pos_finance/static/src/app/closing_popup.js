import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";

// Procedure Finance (decision 1) : tout ecart de caisse s'explique avant de fermer.
patch(ClosePosPopup.prototype, {
    hisNeedsNote() {
        const cash = this.props.default_cash_details;
        if (!this.pos.config.cash_control || !cash) {
            return false;
        }
        const difference = this.getDifference(cash.id);
        return !isNaN(difference) && !this.pos.currency.isZero(difference) && !this.state.notes.trim();
    },
    canConfirm() {
        return super.canConfirm() && !this.hisNeedsNote();
    },
});
