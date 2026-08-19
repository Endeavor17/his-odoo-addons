import { _t } from "@web/core/l10n/translation";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";

// This button is a convenience, not a control. It shows the cashier who the
// student is and what they have left, then drops a zero-priced meal line on the
// order. The credit itself is taken server-side in pos.order._apply_meal_credits
// when the order is validated, so nothing here can be tricked into granting a
// meal that the student cannot pay for.
patch(ControlButtons.prototype, {
    get mealProduct() {
        const configured = this.pos.config.meal_product_id;
        if (!configured) {
            return null;
        }
        // Depending on how the config was loaded this is either the record or
        // its bare id.
        const id = typeof configured === "object" ? configured.id : configured;
        return this.pos.models["product.product"].get(id) || null;
    },

    async clickStudentMeal() {
        const order = this.pos.getOrder();
        const partner = order.getPartner();
        if (!partner) {
            this.dialog.add(AlertDialog, {
                title: _t("No student"),
                body: _t("Scan the student's card first, or pick the student from the customer list."),
            });
            return;
        }

        const product = this.mealProduct;
        if (!product) {
            this.dialog.add(AlertDialog, {
                title: _t("Not configured"),
                body: _t("No student meal product is set on this point of sale."),
            });
            return;
        }

        const balance = await this.pos.data.call("res.partner", "get_meal_balance", [
            [partner.id],
        ]);

        if (!balance.credits) {
            this.dialog.add(AlertDialog, {
                title: _t("No meal credits"),
                body: _t(
                    "%s has no credits left. Sell the meal at its normal price, or sell a new plan at the student centre.",
                    balance.name
                ),
            });
            return;
        }

        this.dialog.add(ConfirmationDialog, {
            title: balance.name,
            body: _t(
                "%(plan)s — %(credits)s credit(s) left, until %(expires)s.\n\nServe the meal?",
                {
                    plan: balance.plan,
                    credits: balance.credits,
                    expires: balance.expires,
                }
            ),
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
