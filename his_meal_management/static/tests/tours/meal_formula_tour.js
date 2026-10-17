/** @odoo-module */

import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ComboPopup from "@point_of_sale/../tests/pos/tours/utils/combo_popup_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

// A formula served the way a cashier does it: student, formula, serve dialog,
// combo window (dish then bottle), Payment -> straight to the receipt.
// tests/test_meal_formulas.py reads the order back.

function openWithStudent() {
    return [
        Chrome.startPoS(),
        Dialog.confirm("Open Register"),
        ProductScreen.clickPartnerButton(),
        ProductScreen.clickCustomer("AAA Tour Formule"),
    ].flat();
}

const serve = { content: "Serve on credits", trigger: ".his_serve_meal_confirm", run: "click" };
const confirmCombo = { content: "Confirm the combo", trigger: ".modal footer button.confirm", run: "click" };

registry.category("web_tour.tours").add("his_meal_formula_tour", {
    steps: () =>
        [
            openWithStudent(),
            ProductScreen.clickDisplayedProduct("Tour Pack 600"),
            serve,
            ComboPopup.select("Tour Box Riz"),
            ComboPopup.select("Tour Ifri PM"),
            confirmCombo,
            ProductScreen.selectedOrderlineHas("Tour Pack 600", "1"),
            ProductScreen.clickPayButton(false),
            ReceiptScreen.isShown(),
            {
                content: "The ticket lists what was inside",
                trigger: ".pos-receipt:contains('Tour Box Riz'):contains('Tour Ifri PM')",
            },
            {
                content: "The ticket does not claim a value of zero",
                trigger: ".pos-receipt .customer-note:contains('Paid with 1 meal credit(s) per meal'):not(:contains('value'))",
            },
        ].flat(),
});

// Review Focus 1: the combo window closed without choosing.
registry.category("web_tour.tours").add("his_meal_formula_cancel_tour", {
    steps: () =>
        [
            openWithStudent(),
            ProductScreen.clickDisplayedProduct("Tour Pack 600"),
            serve,
            { content: "Close the combo window", trigger: ".modal .btn-close", run: "click" },
            ProductScreen.orderIsEmpty(),
        ].flat(),
});

// D1: no student, no formula.
registry.category("web_tour.tours").add("his_meal_formula_walkin_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Tour Pack 600"),
            { content: "The till asks for the card", trigger: ".modal:contains('No student')" },
            Dialog.confirm(),
            ProductScreen.orderIsEmpty(),
        ].flat(),
});
