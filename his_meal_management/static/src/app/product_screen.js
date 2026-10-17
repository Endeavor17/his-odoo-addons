import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype, {
    // A meal tapped in the grid for a student is a student meal: it goes through
    // PosStore.serveStudentMeal, so credits are taken on validation. With no
    // customer on the order it is a walk-in, sold at its normal price.
    //
    // A formula (a combo priced 0) goes the same way; core's
    // addLineToCurrentOrder then opens its combo window.
    //
    // The grid hands over a product.template; meal_credit_cost is only loaded on
    // the variant (see product_template.py), and a meal has exactly one.
    async addProductToOrder(product) {
        const variant = product.product_variant_ids?.[0];
        // A formula has no cash price (D1, 2026-10-15): it is only ever eaten on
        // credits, so without a student it still goes to serveStudentMeal,
        // which asks for the card instead of opening the combo window.
        const creditOnly = variant?.meal_credit_cost > 0 && this.pos.currency.isZero(variant.lst_price);
        if (variant?.meal_credit_cost > 0 && (this.pos.getOrder()?.getPartner() || creditOnly)) {
            return this.pos.serveStudentMeal(variant);
        }
        return super.addProductToOrder(...arguments);
    },
});
