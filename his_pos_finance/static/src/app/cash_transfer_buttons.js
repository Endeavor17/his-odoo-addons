import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { parseFloat } from "@web/views/fields/parsers";

// Le pave numerique tape « 1500,50 » en francais : le parseFloat natif lirait 1500.
function hisAmount(value) {
    if (value === undefined || value === null || value === "") {
        return NaN;
    }
    try {
        return parseFloat(`${value}`);
    } catch {
        return NaN;
    }
}

// Versement du soir a la Finance et reception d'especes, depuis la caisse
// (procedure §4.4) : la sortie d'especes libre d'Odoo est fermee.
patch(Navbar.prototype, {
    setup() {
        super.setup();
        this.hisReport = useService("report");
    },
    async hisHandOver() {
        const session = this.pos.session;
        const proposal = await this.pos.data.call("pos.session", "his_handover_proposal", [session.id]);
        const value = await makeAwaitable(this.dialog, NumberPopup, {
            title: _t("Hand over to Finance"),
            startingValue: proposal,
        });
        const amount = hisAmount(value);
        if (!value || isNaN(amount)) {
            return;
        }
        const transferId = await this.pos.data.call("pos.session", "his_handover", [session.id, amount, ""]);
        await this.hisReport.doAction("his_pos_finance.action_report_cash_transfer", [transferId]);
    },
    async hisReceiveCash() {
        const session = this.pos.session;
        const pending = await this.pos.data.call("pos.session", "his_pending_transfers", [session.id]);
        if (!pending.length) {
            this.dialog.add(AlertDialog, { title: _t("Receive cash"), body: _t("No cash is waiting for this till.") });
            return;
        }
        let transfer = pending[0];
        if (pending.length > 1) {
            transfer = await makeAwaitable(this.dialog, SelectionPopup, {
                title: _t("Receive cash"),
                list: pending.map((t) => ({
                    id: t.id,
                    label: `${t.name} — ${this.env.utils.formatCurrency(t.amount_sent)}`,
                    item: t,
                })),
            });
            if (!transfer) {
                return;
            }
        }
        const value = await makeAwaitable(this.dialog, NumberPopup, {
            title: _t("Amount counted"),
            startingValue: transfer.amount_sent,
        });
        const amount = hisAmount(value);
        if (isNaN(amount)) {
            return;
        }
        await this.pos.data.call("pos.session", "his_receive_transfer", [session.id, transfer.id, amount]);
    },
});
