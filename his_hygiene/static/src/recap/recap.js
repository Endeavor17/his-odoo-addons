import { localization } from "@web/core/l10n/localization";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { formatHours, memberColor, memberInk } from "../common/colors";

// Le recapitulatif du mois, pour la responsable : chaque salariee, chaque zone,
// et l'equite (jours passes par chacune dans chaque zone). Que des tableaux :
// chaque nombre est lisible tel quel.

export class HygieneRecap extends Component {
    static template = "his_hygiene.Recap";
    static props = ["*"];

    // L'arabe se lit de droite a gauche : le coeur pose o_rtl sur le body
    // mais pas la direction du texte de nos ecrans.
    get dir() {
        return localization.direction || "ltr";
    }

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: null, monthOffset: 0, busy: false });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call("his.hygiene.recap", "get_recap", [this.state.monthOffset]);
        } finally {
            this.state.busy = false;
        }
    }

    async changeMonth(delta) {
        this.state.monthOffset += delta;
        await this.load();
    }

    hours(value) {
        return formatHours(value);
    }

    get fairnessMax() {
        return Math.max(1, ...this.state.data.fairness.rows.flatMap((r) => r.counts));
    }

    // Plus la salariee a passe de jours dans la zone, plus la case est foncee.
    heatStyle(count) {
        if (!count) {
            return "";
        }
        const alpha = 0.12 + 0.6 * (count / this.fairnessMax);
        return `background-color: rgba(0, 56, 116, ${alpha.toFixed(2)}); color: ${alpha > 0.45 ? "#fff" : "inherit"};`;
    }

    chipStyle(color) {
        return `background-color: ${memberColor(color)}; color: ${memberInk(color)};`;
    }
}

registry.category("actions").add("his_hygiene_recap", HygieneRecap);
