/* global Sha1 */
import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

// Le responsable choisit son nom, tape son code PIN et donne le motif.
// Verification du PIN dans le navigateur, comme la connexion pos_hr.
export class HisAuthorizationDialog extends Component {
    static template = "his_pos_finance.HisAuthorizationDialog";
    static components = { Dialog };
    static props = {
        title: String,
        managers: Array,
        self: { type: [Object, { value: null }], optional: true },
        getPayload: Function,
        close: Function,
    };

    setup() {
        this.state = useState({ manager: this.props.self, pin: "", reason: "", error: false });
    }
    get canConfirm() {
        return Boolean(this.state.manager && this.state.reason.trim() && (this.props.self || this.state.pin));
    }
    confirm() {
        const manager = this.state.manager;
        if (!this.props.self && manager._pin && manager._pin !== Sha1.hash(this.state.pin)) {
            this.state.error = true;
            this.state.pin = "";
            return;
        }
        this.props.getPayload({ employee: manager, reason: this.state.reason.trim() });
        this.props.close();
    }
}
