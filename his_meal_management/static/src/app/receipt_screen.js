import { _t } from "@web/core/l10n/translation";
import { onMounted, onWillStart } from "@odoo/owl";
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
// Sent once per tab, reloads included: remembered in sessionStorage. Not on
// pos.order.email - core COMPUTES that from the customer, so it is set on every
// order with a customer whether anything was sent or not. The Email button
// stays there for a resend on request.
const SENT_KEY = "his_meal_management.tickets_sent";

function readSent() {
    try {
        return JSON.parse(sessionStorage.getItem(SENT_KEY) || "[]");
    } catch {
        return [];
    }
}

function markSent(uuid) {
    try {
        // The last 200 are plenty to cover a reload; the list never grows past it.
        sessionStorage.setItem(SENT_KEY, JSON.stringify([...readSent(), uuid].slice(-200)));
    } catch {
        // Storage refused (private mode, quota): at worst a reload resends.
    }
}

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        // Before the first render, so the ticket on screen AND the image
        // emailed right after both carry the balance.
        onWillStart(() => this.hisLoadMealBalance());
        onMounted(() => this.hisEmailTicket());
    },

    // What the student has left, printed on the ticket (receipt_screen.xml): a
    // meal at 0 DA raises the question, the balance answers it. Asked of the
    // server once the order is synced, so the credits this order took are
    // already gone. Only for a customer who holds a plan or owes allowance
    // meals; offline, or on any error, the ticket simply goes without it.
    async hisLoadMealBalance() {
        const order = this.currentOrder;
        const partner = order.getPartner();
        if (!partner || !order.isSynced) {
            return;
        }
        try {
            const balance = await this.pos.data.call("res.partner", "get_meal_balance", [[partner.id]]);
            if (balance.plan || balance.credits > 0 || balance.allowance_debt > 0) {
                order.hisMealBalance = balance;
            }
        } catch {
            // The balance is a courtesy; a missing one must never block a ticket.
        }
    },

    async hisEmailTicket() {
        const order = this.currentOrder;
        const email = order.getPartner()?.email;
        if (!email || order.isToInvoice() || !order.isSynced || readSent().includes(order.uuid)) {
            return;
        }
        markSent(order.uuid);
        await this.sendReceipt.call({ action: "action_send_receipt", destination: email, name: "Email" });
        if (this.sendReceipt.status === "success") {
            this.notification.add(_t("Ticket sent to %s", email), { type: "success" });
        }
    },
});
