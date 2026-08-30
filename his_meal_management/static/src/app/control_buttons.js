import { _t } from "@web/core/l10n/translation";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";

// These buttons are a convenience, not a control. They show the cashier who the
// student is and what they have left, then drop a zero-priced meal line on the
// order. The credits themselves are taken server-side in
// pos.order._apply_meal_credits when the order is validated, so nothing here can
// be tricked into serving a meal the student cannot pay for.
patch(ControlButtons.prototype, {
    // Every meal loaded into this till, cheapest first. A meal is a product
    // carrying a credit cost - there is no per-shop configuration any more,
    // which is what lets the Cafeteria serve meals at all.
    get mealProducts() {
        return this.pos.models["product.product"]
            .filter((product) => product.meal_credit_cost > 0)
            .sort((a, b) => a.meal_credit_cost - b.meal_credit_cost);
    },

    async clickStudentMeal(product) {
        const order = this.pos.getOrder();
        const partner = order.getPartner();
        if (!partner) {
            this.dialog.add(AlertDialog, {
                title: _t("No student"),
                body: _t("Scan the student's card first, or pick the student from the customer list."),
            });
            return;
        }

        const balance = await this.pos.data.call("res.partner", "get_meal_balance", [
            [partner.id],
        ]);

        // Against this meal's own cost, not merely "has some credit": with a
        // 300 and a 600 meal sharing one wallet, half a credit is enough for
        // one of them and not the other.
        const cost = product.meal_credit_cost;
        if (balance.credits < cost) {
            this.dialog.add(AlertDialog, {
                title: _t("Not enough meal credits"),
                body: _t(
                    "%(name)s has %(credits)s credit(s) left and %(meal)s costs %(cost)s. Sell the meal at its normal price, or sell a new plan at the student centre.",
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

        // Credits no longer expire by default, so the date is only mentioned
        // when there actually is one.
        const body = balance.expires
            ? _t(
                  "%(plan)s — %(credits)s credit(s) left, until %(expires)s.\n\nServe %(meal)s for %(cost)s credit(s)?",
                  {
                      plan: balance.plan,
                      credits: balance.credits,
                      expires: balance.expires,
                      meal: product.display_name,
                      cost: cost,
                  }
              )
            : _t("%(plan)s — %(credits)s credit(s) left.\n\nServe %(meal)s for %(cost)s credit(s)?", {
                  plan: balance.plan,
                  credits: balance.credits,
                  meal: product.name,
                  cost: cost,
              });

        this.dialog.add(ConfirmationDialog, {
            title: balance.name,
            body: body,
            confirmLabel: _t("Serve meal"),
            confirm: async () => {
                await this.pos.addLineToCurrentOrder(
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
