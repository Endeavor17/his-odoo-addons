/** @odoo-module */

import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

// Payment on a meal served on credits, the way a cashier does it: pick the
// student, tap the meal, confirm it, press Payment. The Python side of each tour
// (tests/test_meal_credit_invoice.py) then reads the order back and checks it
// was invoiced, paid by nothing, and charged to the credits once.

function serveMealTo(partnerName) {
    return [
        Chrome.startPoS(),
        Dialog.confirm("Open Register"),
        ProductScreen.clickPartnerButton(),
        ProductScreen.clickCustomer(partnerName),
        ProductScreen.clickDisplayedProduct("Tour Repas 600"),
        {
            content: "Serve the meal on the student's credits",
            trigger: ".his_serve_meal_confirm",
            run: "click",
        },
        ProductScreen.selectedOrderlineHas("Tour Repas 600", "1"),
    ].flat();
}

// A trigger that fails the tour if the payment screen was ever mounted between
// Payment and the receipt would be racy; the receipt being reached while the
// order carries no payment line (checked in Python) is the same fact, stated
// without a timing assumption.
registry.category("web_tour.tours").add("his_meal_credit_payment_email_tour", {
    steps: () =>
        [
            serveMealTo("AAA Tour Email"),
            ProductScreen.clickPayButton(false),
            ReceiptScreen.isShown(),
            {
                content: "The cashier is told where the invoice went",
                trigger: ".o_notification:contains('Invoice sent to tour.email@his.edu.dz')",
            },
        ].flat(),
});

registry.category("web_tour.tours").add("his_meal_credit_payment_no_email_tour", {
    steps: () =>
        [serveMealTo("AAA Tour Sans Email"), ProductScreen.clickPayButton(false), ReceiptScreen.isShown()].flat(),
});

// Something to pay on the order - a juice next to the meal - and the payment
// screen is back, exactly as before.
registry.category("web_tour.tours").add("his_meal_credit_payment_mixed_tour", {
    steps: () =>
        [
            serveMealTo("AAA Tour Email"),
            ProductScreen.clickDisplayedProduct("Tour Jus"),
            ProductScreen.clickPayButton(true),
            PaymentScreen.isShown(),
        ].flat(),
});
