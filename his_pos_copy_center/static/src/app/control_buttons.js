import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { CopyJobDialog } from "./copy_job_dialog";

// The same patch pattern his_meal_management already uses for its Student Meal
// button. One house pattern for adding a POS control button, not two.
patch(ControlButtons.prototype, {
    // Shown on any till declared a Copy Center, and on any till that actually
    // loaded copy products.
    //
    // It used to require the products alone, which failed badly the first time
    // it met a real database: the till had limit_categories set, no copy
    // product reached the browser, and the button vanished. A missing button
    // teaches the cashier the feature does not exist. An open dialog saying
    // "nothing is configured for this combination" names the real problem and
    // sends them to the person who can fix it.
    get hasCopyProducts() {
        return (
            this.pos.config.his_pos_theme === "copy_center" ||
            this.pos.models["product.product"].some((p) => p.copy_service)
        );
    },

    clickCopyJob() {
        this.dialog.add(CopyJobDialog, {});
    },
});
