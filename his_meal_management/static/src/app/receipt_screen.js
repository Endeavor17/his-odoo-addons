import { onWillStart } from "@odoo/owl";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";
import { formatCredits } from "./pos_store";

// The ticket is emailed by the server when the paid order is saved
// (pos.order._his_send_ticket): it used to be sent from here, as a picture of
// this screen, and a reload lost it (recette P-05). Core's Email button stays
// for a resend on request.
patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        // Before the first render, so the ticket on screen carries the balance.
        onWillStart(() => this.hisLoadMealBalance());
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
                order.hisMealBalance = {
                    credits: formatCredits(balance.credits),
                    allowance_debt: balance.allowance_debt > 0 && formatCredits(balance.allowance_debt),
                };
            }
        } catch {
            // The balance is a courtesy; a missing one must never block a ticket.
        }
    },
});
