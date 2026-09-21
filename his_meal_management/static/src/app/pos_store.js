import { _t } from "@web/core/l10n/translation";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { ServeMealDialog } from "./serve_meal_dialog";

// Serving a student meal is a convenience, not a control. It shows the cashier
// who the student is and what they have left, then drops a zero-priced meal line
// on the order. The credits themselves are taken server-side in
// pos.order._apply_meal_credits when the order is validated, so nothing here can
// be tricked into serving a meal the student cannot pay for.
//
// The product grid is the only way in (product_screen.js): there are no
// per-meal control buttons, a meal is served by tapping it on the menu.
patch(PosStore.prototype, {
    // Payment on an order eaten entirely on credits has nothing to take: Cash,
    // Card and Customer Account would all be asked to record 0 DA. So the order
    // is validated from here, invoiced, and the till goes straight to the
    // receipt. It runs through the very OrderPaymentValidation the payment
    // screen uses - the same checks, the same sync, the same receipt - exactly
    // as core's validateOrderFast does, only without a payment line to add.
    //
    // Anything else takes the ordinary road: a paid line on the order, no
    // student, or a till with no invoice journal (the invoice could not be
    // made, and a blocked till is worse than one extra screen).
    async pay() {
        const order = this.getOrder();
        if (!order?.isServedOnMealCredits || !this.config.canInvoice) {
            return super.pay(...arguments);
        }
        // The payment screen guards its Validate button with an async lock; this
        // is the same guard for the Payment button, so a second tap while the
        // first order syncs does not validate it twice.
        if (this.hisMealValidationInProgress) {
            return;
        }
        this.hisMealValidationInProgress = true;
        const wasToInvoice = order.isToInvoice();
        try {
            order.setToInvoice(true);
            await new OrderPaymentValidation({ pos: this, orderUuid: order.uuid }).validateOrder(false);
            // Still a draft means it did not go through - a check refused it, or
            // the server did, and either one has said why. The order is still
            // being edited, and a drink added next should not find the invoice
            // box ticked on its payment screen. (Offline, the order is "paid"
            // and queued, and keeps its invoice for when it syncs.)
            if (order.state === "draft") {
                order.setToInvoice(wasToInvoice);
            }
        } finally {
            this.hisMealValidationInProgress = false;
        }
    },

    async serveStudentMeal(product) {
        const order = this.getOrder();
        const partner = order.getPartner();
        if (!partner) {
            this.dialog.add(AlertDialog, {
                title: _t("No student"),
                body: _t("Scan the student's card first, or pick the student from the customer list."),
            });
            return;
        }

        const balance = await this.data.call("res.partner", "get_meal_balance", [[partner.id]]);

        // Against this meal's own cost, not merely "has some credit": with a
        // 300 and a 600 meal sharing one wallet, half a credit is enough for
        // one of them and not the other.
        const cost = product.meal_credit_cost;
        // Short of credits is no longer the end of it: a student who has bought
        // a plan carries two meals of allowance, and the till serves them behind
        // a warning rather than turning the person away. Only when that is spent
        // too does the refusal below stand.
        const onAllowance = balance.credits < cost;
        if (onAllowance && balance.allowance_left < 1) {
            this.dialog.add(AlertDialog, {
                title: _t("Not enough meal credits"),
                body: _t(
                    "%(name)s has %(credits)s credit(s) left and %(meal)s costs %(cost)s. The two allowance meals are already used. Sell the meal at its normal price, or sell a new plan at the student centre.",
                    {
                        name: balance.name,
                        credits: balance.credits,
                        meal: product.display_name,
                        cost: cost,
                    }
                ),
            });
            return;
        }

        // The dialog lays the facts out itself rather than being handed a
        // formatted paragraph. `expires` is passed through as it comes: credits
        // no longer expire by default, so it is usually the empty string, and
        // the dialog says "no expiry" rather than naming a date there isn't one
        // of.
        //
        // display_name throughout, never `name`: the POS product.product only
        // delegates methods and getters to its template (enhanceProductTemplate
        // in core's product_product.js), never plain loaded fields, and core
        // does not load `name` on the variant. It reads undefined.
        this.dialog.add(ServeMealDialog, {
            name: balance.name,
            cardCode: partner.barcode || "",
            plan: balance.plan,
            expires: balance.expires,
            credits: balance.credits,
            mealName: product.display_name,
            cost: cost,
            onAllowance: onAllowance,
            allowanceLeft: balance.allowance_left,
            allowanceDebt: balance.allowance_debt,
            confirm: async () => {
                await this.addLineToCurrentOrder(
                    {
                        product_tmpl_id: product.product_tmpl_id,
                        product_id: product,
                        price_unit: 0,
                    },
                    {}
                );
            },
        });
    },
});
