import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// The Metabase dashboard, full page under Maintenance > Dashboard.
//
// The URL is signed by the server on every opening (get_metabase_url): the key
// never reaches the browser, and reopening always carries a fresh token. A
// failure (parameters missing, Metabase unreachable) shows its message in place
// of the dashboard.
export class MaintenanceMetabaseDashboard extends Component {
    static template = "maintenance_university.MetabaseDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        onWillStart(async () => {
            try {
                this.url = await this.orm.call("maintenance.university.dashboard", "get_metabase_url", []);
            } catch (error) {
                this.error = error.data?.message || _t("The dashboard could not be loaded.");
            }
        });
    }
}

registry.category("actions").add("maintenance_university_metabase", MaintenanceMetabaseDashboard);
