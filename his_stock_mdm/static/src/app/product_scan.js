import { ProductTemplate } from "@point_of_sale/app/models/product_template";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

// The server no longer sends a scanned article the till may not sell (see
// load_product_from_pos). These two cover what is already in the till: a past
// ticket reloads the articles it sold, and core only checks available_in_pos.
patch(ProductTemplate.prototype, {
    get canBeDisplayed() {
        // !== false: a till kept open across the upgrade has no sale_ok yet, and
        // must not turn blank.
        return super.canBeDisplayed && this.sale_ok !== false;
    },
});

patch(ProductScreen.prototype, {
    async _getProductByBarcode(code) {
        const product = await super._getProductByBarcode(code);
        return product?.product_tmpl_id?.canBeDisplayed ? product : undefined;
    },
});
