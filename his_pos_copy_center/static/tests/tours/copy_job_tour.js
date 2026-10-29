/** @odoo-module */

import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Order from "@point_of_sale/../tests/generic_helpers/order_widget_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import { registry } from "@web/core/registry";

// Copies & Prints, driven the way a cashier drives it, on the real grid
// (tests/copy_grid.py).

const click = (content, trigger) => ({ content, trigger, run: "click" });

// One document through the dialog. `color` null: the paper carries none, and
// the colour row must not even be shown.
export function addCopies({ service, paper, color, sides, copies }) {
    return [
        click("Open Copies & Prints", ".js_copy_job"),
        click(`Service ${service}`, `.js_copy_service[data-service='${service}']`),
        click(`Paper ${paper}`, `.js_copy_paper[data-paper='${paper}']`),
        ...(color
            ? [click(`Colour ${color}`, color === "bw" ? ".js_copy_bw" : ".js_copy_color")]
            : [{ content: "No colour asked for this paper", trigger: ".his-copy-job:not(:has(.js_copy_bw))" }]),
        click(`Sides ${sides}`, sides === "duplex" ? ".js_copy_duplex" : ".js_copy_recto"),
        { content: `${copies} copies`, trigger: ".his-count", run: `edit ${copies}` },
        click("Add to order", ".js_copy_job_add"),
    ];
}

registry.category("web_tour.tours").add("his_copy_job_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            click("Open Copies & Prints", ".js_copy_job"),
            click("Print", ".js_copy_service[data-service='impression']"),
            click("Sticker paper", ".js_copy_paper[data-paper='sticker']"),
            {
                content: "Sticker prints carry no colour: the row is gone",
                trigger: ".his-copy-job:not(:has(.js_copy_bw))",
            },
            {
                content: "Sticker prints are single-sided only: duplex is disabled",
                trigger: ".js_copy_duplex:disabled",
            },
            { content: "Three copies", trigger: ".his-count", run: "edit 3" },
            click("Add to order", ".js_copy_job_add"),
            ProductScreen.selectedOrderlineHas("Impression Papier Autocollant", "3"),
        ].flat(),
});

// A combination nobody configured must refuse, say so, and add nothing. The
// test archives Photocopie N&B Recto-verso for this.
registry.category("web_tour.tours").add("his_copy_job_missing_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            click("Open Copies & Prints", ".js_copy_job"),
            click("Photocopy", ".js_copy_service[data-service='photocopie']"),
            click("Black and white", ".js_copy_bw"),
            {
                content: "Double-sided B&W photocopy no longer exists: disabled",
                trigger: ".js_copy_duplex:disabled",
            },
            Order.doesNotHaveLine(),
        ].flat(),
});

// The price above 20 pages, decided over the whole order (copy_bulk_pricing.js).
registry.category("web_tour.tours").add("his_copy_bulk_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            // 1. 20 pages: usual price.
            addCopies({ service: "impression", paper: "normal", color: "bw", sides: "recto", copies: 20 }),
            Order.hasLine({ productName: "Impression N&B Recto", quantity: "20", priceUnit: "10" }),
            // 2. A second document takes the order to 21 pages: both drop.
            addCopies({ service: "impression", paper: "normal", color: "bw", sides: "recto", copies: 1 }),
            Order.hasLine({ productName: "Impression N&B Recto", quantity: "20", priceUnit: "8" }),
            Order.hasLine({ productName: "Impression N&B Recto", quantity: "1", priceUnit: "8" }),
            // 3. Colour never drops.
            addCopies({ service: "impression", paper: "normal", color: "color", sides: "recto", copies: 5 }),
            Order.hasLine({ productName: "Impression Couleur Recto", quantity: "5", priceUnit: "30" }),
            // 4. Remove the 1-page document: back to 20 pages, back to 10.
            ProductScreen.clickOrderline("Impression N&B Recto", "1"),
            ProductScreen.clickNumpad("⌫"),
            ProductScreen.clickNumpad("⌫"),
            Order.hasLine({ productName: "Impression N&B Recto", quantity: "20", priceUnit: "10" }),
        ].flat(),
});

// 11 double-sided sheets are 22 pages; photocopies never count nor drop.
registry.category("web_tour.tours").add("his_copy_bulk_duplex_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            // 5. 11 double-sided sheets = 22 pages: 10 DA.
            addCopies({ service: "impression", paper: "normal", color: "bw", sides: "duplex", copies: 11 }),
            Order.hasLine({ productName: "Impression N&B Recto-verso", quantity: "11", priceUnit: "10" }),
            // 6. 30 B&W photocopies: 5 DA, and the order's prints do not move.
            addCopies({ service: "photocopie", paper: "normal", color: "bw", sides: "recto", copies: 30 }),
            Order.hasLine({ productName: "Photocopie N&B Recto", quantity: "30", priceUnit: "5" }),
            Order.hasLine({ productName: "Impression N&B Recto-verso", quantity: "11", priceUnit: "10" }),
        ].flat(),
});
