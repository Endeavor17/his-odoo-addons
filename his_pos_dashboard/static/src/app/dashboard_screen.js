import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

// The Metabase dashboard, full screen under the navbar. "Register" goes back to
// selling, and the POS screensaver goes back there too after 5 idle minutes.
//
// The URL is signed by the server on every opening (pos_config.py): the key
// never reaches the browser, and a reopened page always carries a fresh token.
// A failure (offline, parameters missing) shows its message in place of the
// dashboard rather than breaking the screen.
export class DashboardScreen extends Component {
    static template = "his_pos_dashboard.DashboardScreen";
    static storeOnOrder = false;
    static props = [];

    setup() {
        this.pos = usePos();
        onWillStart(async () => {
            try {
                this.url = await this.pos.data.call("pos.config", "his_dashboard_url", []);
            } catch (error) {
                this.error = error.data?.message || _t("The dashboard could not be loaded.");
            }
        });
    }
}

registry.category("pos_pages").add("HisDashboardScreen", {
    name: "HisDashboardScreen",
    component: DashboardScreen,
    route: `/pos/ui/${odoo.pos_config_id}/dashboard`,
    params: {},
});
