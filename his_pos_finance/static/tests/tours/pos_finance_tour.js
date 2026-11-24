/** @odoo-module */

import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as NumberPopup from "@point_of_sale/../tests/generic_helpers/number_popup_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import * as PosHr from "@pos_hr/../tests/tours/utils/pos_hr_helpers";
import { registry } from "@web/core/registry";

// Procedure Finance, cote caisse : un caissier « basique » change un prix avec
// le PIN du responsable, verse ses especes a la Finance et ferme sa caisse en
// expliquant l'ecart.
registry.category("web_tour.tours").add("his_pos_finance_tour", {
    steps: () =>
        [
            Chrome.clickBtn("Open Register"),
            PosHr.loginScreenIsShown(),
            PosHr.login("Pos Employee1", "2580"),
            Dialog.confirm("Open Register"),

            ProductScreen.addOrderline("Desk Pad", "1"),
            ProductScreen.clickNumpad("Price"),
            // en mode restreint, la premiere touche ouvre la saisie du prix
            ProductScreen.clickNumpad("5"),
            NumberPopup.enterValue("5"),
            Dialog.confirm(),
            { content: "pick the manager", trigger: ".his-approval-manager:contains('Test Manager 1')", run: "click" },
            { content: "manager PIN", trigger: ".his-approval-pin", run: "edit 5651" },
            { content: "reason", trigger: ".his-approval-reason", run: "edit Prix affiche errone" },
            { content: "authorize", trigger: ".his-approval-confirm:enabled", run: "click" },
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.clickNextOrder(),

            Chrome.clickMenuOption("Hand over to Finance"),
            Dialog.confirm(),

            Chrome.clickMenuOption("Close Register"),
            { content: "count one dinar too many", trigger: ".modal .cash-input input", run: "edit 1" },
            {
                content: "closing is blocked without an explanation",
                trigger: ".modal-footer button.btn-primary:contains('Close Register'):disabled",
            },
            { content: "explain", trigger: "#closingNotes", run: "edit Un dinar trouve sous le tiroir" },
            { content: "close", trigger: ".modal-footer button.btn-primary:contains('Close Register'):enabled", run: "click" },
            {
                content: "accept the difference",
                trigger: ".modal:not(.o_inactive_modal) .modal-footer .btn-primary:contains('Proceed Anyway')",
                run: "click",
                expectUnloadPage: true,
            },
        ].flat(),
});
