import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { HisAuthorizationDialog } from "./authorization_dialog";

// Procedure §4.3 : prix, remise et remboursement passent par le responsable
// (code PIN + motif). Seuls les gestes du caissier sont concernes : un prix
// pose par le code (tarif degressif Copy Center, repas sur credits) passe par
// setUnitPrice / setDiscount de la ligne, qu'on ne touche pas.
patch(PosStore.prototype, {
    hisNeedsApproval() {
        return Boolean(this.config.restrict_price_control);
    },
    // Le bouton Prix reste actif pour le caissier : c'est la fenetre
    // d'autorisation, pas le bouton grise, qui fait le controle.
    cashierHasPriceControlRights() {
        return this.hisNeedsApproval() || super.cashierHasPriceControlRights(...arguments);
    },
    // Prix et remise saisis d'un coup dans une fenetre, pas touche par touche :
    // sinon on demanderait le PIN a chaque chiffre.
    restrictLinePriceChange() {
        return this.hisNeedsApproval() || super.restrictLinePriceChange(...arguments);
    },
    restrictLineDiscountChange() {
        return this.hisNeedsApproval() || super.restrictLineDiscountChange(...arguments);
    },
    hisApprovalTitles() {
        return { price: _t("Price change"), discount: _t("Discount"), refund: _t("Refund") };
    },
    async hisAskApproval(kind) {
        const titles = this.hisApprovalTitles();
        const cashier = this.getCashier();
        const isManager = cashier?._role === "manager";
        const managers = this.config.module_pos_hr
            ? this.models["hr.employee"].getAll().filter((e) => e._role === "manager" && e._pin)
            : [];
        const result = await makeAwaitable(this.dialog, HisAuthorizationDialog, {
            title: titles[kind],
            managers,
            self: isManager ? cashier : null,
        });
        return result ? { ...result, kind } : null;
    },
    hisRecord(lines, approval) {
        const employee = this.config.module_pos_hr ? approval.employee : false;
        for (const line of lines) {
            // shortcut: a line keeps one approval; earlier ones stay as text in the
            // reason. A one2many if Finance needs to report on each of them.
            const before = line.his_authorization_kind
                ? ` | ${this.hisApprovalTitles()[line.his_authorization_kind]} (${
                      line.his_authorized_by_id?.name || "-"
                  }) : ${line.his_authorization_reason || ""}`
                : "";
            line.his_authorized_by_id = employee;
            line.his_authorization_reason = approval.reason + before;
            line.his_authorization_kind = approval.kind;
        }
    },
    async setDiscountFromUI(line) {
        if (!this.hisNeedsApproval()) {
            return super.setDiscountFromUI(...arguments);
        }
        const approval = await this.hisAskApproval("discount");
        if (!approval) {
            return;
        }
        await super.setDiscountFromUI(...arguments);
        this.hisRecord([line], approval);
    },
});

// Une quantite negative est un remboursement : sans la touche +/- , le
// caissier passe par l'ecran des tickets, ou le PIN du responsable est demande.
patch(ProductScreen.prototype, {
    getNumpadButtons() {
        const buttons = super.getNumpadButtons(...arguments);
        if (!this.pos.hisNeedsApproval() || this.pos.getCashier()?._role === "manager") {
            return buttons;
        }
        return buttons.map((b) => (b.value === "-" ? { ...b, disabled: true } : b));
    },
});

patch(OrderSummary.prototype, {
    async updateSelectedOrderline({ key }) {
        // le clavier physique aussi
        if (key === "-" && this.pos.hisNeedsApproval() && this.pos.getCashier()?._role !== "manager") {
            this.numberBuffer.reset();
            return;
        }
        return super.updateSelectedOrderline(...arguments);
    },
    async setLinePrice(line, price) {
        if (!this.pos.hisNeedsApproval()) {
            return super.setLinePrice(...arguments);
        }
        const approval = await this.pos.hisAskApproval("price");
        if (!approval) {
            return;
        }
        // Le geste de base, sans le refus de pos_hr : le responsable a autorise.
        line.price_type = "manual";
        line.setUnitPrice(price);
        this.pos.hisRecord([line], approval);
    },
});

patch(TicketScreen.prototype, {
    async onDoRefund() {
        if (!this.pos.hisNeedsApproval()) {
            return super.onDoRefund(...arguments);
        }
        const approval = await this.pos.hisAskApproval("refund");
        if (!approval) {
            return;
        }
        await super.onDoRefund(...arguments);
        const order = this.pos.getOrder();
        this.pos.hisRecord(
            (order?.lines || []).filter((l) => l.refunded_orderline_id && !l.his_authorization_kind),
            approval
        );
    },
});
