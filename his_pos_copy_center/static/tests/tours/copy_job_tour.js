/** @odoo-module */

import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import { registry } from "@web/core/registry";

// The builder, driven the way a cashier drives it.
//
// The assertion that matters is the last one: the order line carries the
// product the chips described, at the quantity typed. If that holds, the dialog
// is a face over the catalogue and nothing more — which is the whole design.
registry.category("web_tour.tours").add("his_copy_job_tour", {
    steps: () => [
        Chrome.startPoS(),
        Dialog.confirm("Open Register"),
        {
            content: "Open the copy job builder",
            trigger: ".js_copy_job",
            run: "click",
        },
        {
            content: "The builder opens on a resolvable combination",
            trigger: ".his-copy-job .his-copy-job-amount",
        },
        {
            content: "Colour instead of black and white",
            trigger: ".js_copy_color",
            run: "click",
        },
        {
            content: "The colour chip is now the selected one",
            trigger: ".js_copy_color.his-chip-on",
        },
        {
            content: "Twenty-four copies",
            trigger: ".his-copy-count",
            run: "edit 24",
        },
        {
            content: "Add the job to the order",
            trigger: ".js_copy_job_add",
            run: "click",
        },
        // 24 copies of the A4 colour recto product, priced by the product and
        // not by the browser.
        ProductScreen.selectedOrderlineHas("Photocopie A4 Couleur Recto", "24"),
    ],
});

// The other path that matters: a combination nobody configured must refuse,
// say so, and add nothing.
registry.category("web_tour.tours").add("his_copy_job_missing_tour", {
    steps: () => [
        Chrome.startPoS(),
        Dialog.confirm("Open Register"),
        {
            content: "Open the copy job builder",
            trigger: ".js_copy_job",
            run: "click",
        },
        {
            content: "Ask for A3, which this till has no product for",
            trigger: ".js_copy_a3",
            run: "click",
        },
        {
            content: "The gap is stated where the price would have been",
            trigger: ".his-copy-job-missing",
        },
        {
            content: "Try to add it anyway",
            trigger: ".js_copy_job_add",
            run: "click",
        },
        {
            content: "It refuses, and names the combination",
            trigger: ".modal:contains('No such copy')",
        },
    ],
});
