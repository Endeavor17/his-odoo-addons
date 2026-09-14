import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";

// One button per meal. The serving itself is PosStore.serveStudentMeal
// (pos_store.js), shared with a meal tapped in the product grid.
patch(ControlButtons.prototype, {
    // Every meal loaded into this till, cheapest first. A meal is a product
    // carrying a credit cost - there is no per-shop configuration any more,
    // which is what lets the Cafeteria serve meals at all.
    get mealProducts() {
        return this.pos.models["product.product"]
            .filter((product) => product.meal_credit_cost > 0)
            .sort((a, b) => a.meal_credit_cost - b.meal_credit_cost);
    },

    clickStudentMeal(product) {
        return this.pos.serveStudentMeal(product);
    },
});
