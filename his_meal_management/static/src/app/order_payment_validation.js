import { _t } from "@web/core/l10n/translation";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";

// An order moving meal credits is invoiced (PosStore.pay sets the box), and core
// then emails the invoice itself: pos.order._generate_pos_order_invoice ends in
// invoice._generate_and_send(), whose default sending method is email, sent to
// the invoice partner's `email` when there is one. Nothing here sends mail.
//
// What changes is only what the till does with the PDF. Core downloads it after
// every invoiced order; for a student whose invoice has just gone to their
// inbox that is a PDF popping up in front of a queue for nothing, so it is left
// out and the cashier is told where it went instead. With no email on file the
// download stays, and the invoice is shown the way it always was.
//
// `email` and not `invoice_emails`: the receipt screen pre-fills the latter, but
// the invoice mail goes to move.partner_id.email and nowhere else.
function emailsTheInvoice(order) {
    return Boolean(order.hisMovesMealCredits && order.getPartner()?.email);
}

patch(OrderPaymentValidation.prototype, {
    shouldDownloadInvoice() {
        if (emailsTheInvoice(this.order)) {
            return false;
        }
        return super.shouldDownloadInvoice(...arguments);
    },

    async afterOrderValidation() {
        const result = await super.afterOrderValidation(...arguments);
        // account_move is only set once the server has invoiced the order, so an
        // offline validation - synced later - claims nothing it has not done.
        if (emailsTheInvoice(this.order) && this.order.isToInvoice() && this.order.raw.account_move) {
            this.pos.notification.add(
                _t("Invoice sent to %s", this.order.getPartner().email),
                { type: "success" }
            );
        }
        return result;
    },
});
