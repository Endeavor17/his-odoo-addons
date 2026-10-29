import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { bulkUnitPrice, copyBulkState, isBulkEligible } from "./copy_bulk_pricing";

patch(PosOrder.prototype, {
    // Re-price the eligible print lines from the whole order, both ways: past
    // 20 pages they take the lower price, back under it they return to the
    // usual one. A price the cashier typed by hand (price_type "manual") is
    // left alone. Idempotent: it only ever chooses between two stored prices.
    hisApplyCopyBulkPrices() {
        const lines = this.lines.filter(
            (line) => isBulkEligible(line.product_id) && line.price_type !== "manual"
        );
        if (!lines.length) {
            return;
        }
        const { active } = copyBulkState(
            this.lines.map((line) => ({ product: line.product_id, qty: line.getQuantity() }))
        );
        for (const line of lines) {
            const product = line.product_id;
            const price =
                bulkUnitPrice(product, active) ??
                product.product_tmpl_id.getPrice(
                    this.pricelist_id,
                    line.getQuantity(),
                    line.getPriceExtra(),
                    false,
                    product
                );
            if (line.price_unit !== price) {
                line.setUnitPrice(price);
            }
        }
    },

    removeOrderline() {
        const result = super.removeOrderline(...arguments);
        this.hisApplyCopyBulkPrices();
        return result;
    },

    // The core re-prices every "original" line from the pricelist, straight
    // through setUnitPrice. It runs on every customer change (setPartner),
    // so picking the student to email the ticket undid the price above 20
    // pages. Re-apply it afterwards.
    setPricelist() {
        const result = super.setPricelist(...arguments);
        this.hisApplyCopyBulkPrices();
        return result;
    },
});

patch(PosOrderline.prototype, {
    // setUnitPrice does not call setQuantity, so this cannot loop.
    setQuantity() {
        const result = super.setQuantity(...arguments);
        this.order_id?.hisApplyCopyBulkPrices?.();
        return result;
    },
});

patch(PosStore.prototype, {
    async addLineToOrder(vals, order) {
        const line = await super.addLineToOrder(...arguments);
        order?.hisApplyCopyBulkPrices?.();
        return line;
    },
});
