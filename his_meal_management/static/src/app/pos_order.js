import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    // An order the student eats entirely on credits: every line a meal, and not
    // one of them costing anything once its discount is applied. There is
    // nothing to pay, so the till skips the payment screen (pos_store.js).
    //
    // The same question as pos.order.line._his_is_credit_meal on the server,
    // asked the same way. That one decides what the credits do; this one only
    // decides which screen comes next, so getting it wrong shows the payment
    // screen, never a free meal.
    //
    // A single paid line - a drink next to the meal - is enough to make it an
    // ordinary sale with an ordinary payment screen.
    get isServedOnMealCredits() {
        return Boolean(
            this.lines.length &&
                this.getPartner() &&
                this.lines.every(
                    (line) =>
                        line.product_id.meal_credit_cost > 0 &&
                        this.currency.isZero(line.price_unit * (1 - (line.discount || 0) / 100))
                )
        );
    },

    // An order that moves a student's meal credits: a meal eaten on them, or a
    // plan that tops them up. Its invoice is how the student learns what their
    // card did, so the till ticks the invoice box (pos_store.js) and core emails
    // it - on a meal plus a drink, and on a top-up at the Copy Center, as much
    // as on a meal alone.
    //
    // `meal_credits` is loaded for this alone (product_template.py).
    get hisMovesMealCredits() {
        return Boolean(
            this.getPartner() &&
                this.lines.some(
                    (line) =>
                        line.product_id.meal_credits > 0 ||
                        (line.product_id.meal_credit_cost > 0 &&
                            this.currency.isZero(line.price_unit * (1 - (line.discount || 0) / 100)))
                )
        );
    },
});
