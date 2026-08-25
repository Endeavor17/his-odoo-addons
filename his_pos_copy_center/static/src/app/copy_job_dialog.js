import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";

// One dialog instead of one popup per dimension.
//
// It resolves a product and adds an ordinary order line. It never computes a
// price: the figure on screen is read off the product POS already loaded, so
// the total the cashier reads and the total the server charges cannot drift
// apart — there is only ever one number, and it is the product's own.
//
// The dimensions are fields rather than attributes because his_stock_mdm's MDM
// rule 6 forbids the Format attribute on the copy categories. See
// models/product_template.py for the whole argument.
export class CopyJobDialog extends Component {
    static template = "his_pos_copy_center.CopyJobDialog";
    static components = { Dialog };
    static props = {
        close: Function,
    };

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
        this.state = useState({
            service: this.defaultService,
            format: "a4",
            color: "bw",
            sides: "recto",
            copies: 1,
        });
    }

    // Odoo portals dialogs to the document body, outside the .pos root — so a
    // dialog inherits neither the theme's custom properties nor any rule scoped
    // under .his-pos, and renders as a stock white modal with dark chips
    // floating in it. Passing the theme classes down through contentClass puts
    // the tokens back in scope.
    get themeClass() {
        const theme = this.pos.config.his_pos_theme;
        return theme ? `his-pos his-theme-${theme}` : "";
    }

    get copyProducts() {
        return this.pos.models["product.product"].filter((p) => p.copy_service);
    }

    get availableServices() {
        return [...new Set(this.copyProducts.map((p) => p.copy_service))];
    }

    get defaultService() {
        return this.availableServices[0] || "photocopie";
    }

    // The one product matching all four chips, or nothing at all.
    get matchedProduct() {
        return this.copyProducts.find(
            (p) =>
                p.copy_service === this.state.service &&
                p.copy_format === this.state.format &&
                p.copy_color === this.state.color &&
                p.copy_sides === this.state.sides
        );
    }

    get unitPrice() {
        return this.matchedProduct ? this.matchedProduct.lst_price : 0;
    }

    get total() {
        return this.unitPrice * this.state.copies;
    }

    get formattedUnitPrice() {
        return this.env.utils.formatCurrency(this.unitPrice);
    }

    get formattedTotal() {
        return this.env.utils.formatCurrency(this.total);
    }

    get serviceLabel() {
        return {
            photocopie: _t("Photocopie"),
            impression: _t("Impression"),
        };
    }

    pick(dimension, value) {
        this.state[dimension] = value;
    }

    isPicked(dimension, value) {
        return this.state[dimension] === value;
    }

    addCopies(n) {
        this.state.copies = Math.max(1, this.state.copies + n);
    }

    setCopies(ev) {
        const value = parseInt(ev.target.value, 10);
        this.state.copies = Number.isFinite(value) && value > 0 ? value : 1;
    }

    // A copy job is rarely one sheet. The common run sizes are one tap instead
    // of five on a stepper or a trip to the numpad.
    setCopiesTo(n) {
        this.state.copies = n;
    }

    // Returns true when a line was actually added, so the caller knows whether
    // to close the dialog or leave it standing for a correction.
    async addLine() {
        const product = this.matchedProduct;

        if (!product) {
            this.dialog.add(AlertDialog, {
                title: _t("No such copy"),
                body: _t(
                    "No product is configured for %(format)s / %(color)s / %(sides)s.\n\n" +
                        "Tell the Copy Center manager: this is a gap in the catalogue, " +
                        "not a mistake at the till.",
                    {
                        format: this.state.format.toUpperCase(),
                        color: this.state.color === "bw" ? _t("N&B") : _t("Couleur"),
                        sides:
                            this.state.sides === "recto" ? _t("Recto") : _t("Recto-verso"),
                    }
                ),
            });
            return false;
        }

        // A zero here would silently give the copies away. Refuse instead: a
        // priceless product is a configuration error, and the till is where it
        // gets noticed.
        if (!product.lst_price) {
            this.dialog.add(AlertDialog, {
                title: _t("No price"),
                body: _t(
                    "%s carries no price, so it cannot be sold. Set its price before using it.",
                    product.display_name
                ),
            });
            return false;
        }

        await this.pos.addLineToCurrentOrder(
            {
                product_tmpl_id: product.product_tmpl_id,
                product_id: product,
                qty: this.state.copies,
            },
            {}
        );
        return true;
    }

    async onAddAndClose() {
        if (await this.addLine()) {
            this.props.close();
        }
    }

    // A job is several documents, so the form resets and stays open. Each
    // document is one ordinary order line.
    //
    // ponytail: no his.copy.job model. Add one only if a saved, referenced
    // multi-document job turns out to be a real need — today the order itself
    // is the job, and it already prints, refunds and reports.
    async onAddAnother() {
        if (await this.addLine()) {
            this.state.copies = 1;
        }
    }
}
