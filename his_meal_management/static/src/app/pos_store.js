import { _t } from "@web/core/l10n/translation";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
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
