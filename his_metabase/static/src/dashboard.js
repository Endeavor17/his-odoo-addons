import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Le tableau de bord Metabase d'une application, en pleine page. Le serveur
// signe l'URL a chaque ouverture (his_embed) : la cle ne vient jamais ici. Un
// reglage manquant revient en message, affiche a la place du tableau.
export class HisMetabaseDashboard extends Component {
    static template = "his_metabase.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        onWillStart(async () => {
            const code = this.props.action.params?.code;
            const result = await this.orm.call("his.metabase.dashboard", "his_embed", [code]);
            this.url = result.url;
            this.error = result.error;
        });
    }
}

registry.category("actions").add("his_metabase_dashboard", HisMetabaseDashboard);
