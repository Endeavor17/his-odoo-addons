import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { CopyJobDialog } from "./copy_job_dialog";

// The same patch pattern his_meal_management already uses for its Student Meal
// button. One house pattern for adding a POS control button, not two.
patch(ControlButtons.prototype, {
    // Hidden unless this till actually sells copies, so the button never opens
    // onto an empty form. A Cafeteria register loads no copy products and
    // therefore never sees it, without either module knowing about the other.
    get hasCopyProducts() {
        return this.pos.models["product.product"].some((p) => p.copy_service);
    },

    clickCopyJob() {
        this.dialog.add(CopyJobDialog, {});
    },
});
