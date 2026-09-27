import { _t } from "@web/core/l10n/translation";
import { onMounted } from "@odoo/owl";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";

// A sale to a customer gets a ticket, not an invoice (loi 04-02, art. 10: an
// invoice only when the customer asks for one), and the ticket is emailed to
// them as soon as it is shown. It is core's own Email button, pressed for the
// cashier: the same rendered receipt, the same pos.order.action_send_receipt,
// which his_mail_async puts in the mail queue so the till does not wait on SMTP.
//
// Skipped when the order is invoiced (core already emails the invoice), when
// the customer has no address, and when the order is not on the server yet -
// offline, core's button would open an "Unsynced order" dialog; a ticket nobody
// asked for is not worth one.
//
// ponytail: remembered per page load, so reloading the browser on a receipt
// sends it again. Store it on the order if that ever happens in real use.
const sent = new Set();

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => this.hisEmailTicket());
    },

    async hisEmailTicket() {
        const order = this.currentOrder;
        const email = order.getPartner()?.email;
        if (!email || order.isToInvoice() || !order.isSynced || sent.has(order.uuid)) {
            return;
        }
        sent.add(order.uuid);
        await this.sendReceipt.call({ action: "action_send_receipt", destination: email, name: "Email" });
        if (this.sendReceipt.status === "success") {
            this.notification.add(_t("Ticket sent to %s", email), { type: "success" });
        }
    },
});
