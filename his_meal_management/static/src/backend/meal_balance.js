import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { deserializeDate, formatDate } from "@web/core/l10n/dates";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";

// The desk's balance screen, opened from its tile on the Point of Sale
// dashboard (meal_balance.xml). Staff scan a card, or type a name or a
// matricule, and turn the screen to the student: plan, credits used and left.
//
// Read-only. The figures come from get_meal_balance, the same sudo read the
// tills use, behind the same who-is-asking check; search_meal_holders only
// says who a card or a name points to.
//
// An RFID reader types the card's UID then Enter, so the search box IS the
// scanner input: it holds the focus on open and after every lookup.
export class MealBalance extends Component {
    static template = "his_meal_management.MealBalance";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ query: "", holders: [], balance: null, notFound: "" });
        // mobile: true, or a touchscreen desk would open with no focus and the
        // first scan would type nowhere. The reader is this screen's keyboard.
        this.searchRef = useAutofocus({ refName: "search", mobile: true });
    }

    async lookup() {
        const query = this.state.query.trim();
        // Cleared at once, so the next scan types into an empty box.
        this.state.query = "";
        if (!query) {
            return;
        }
        const holders = await this.orm.call("res.partner", "search_meal_holders", [query]);
        this.state.balance = null;
        this.state.notFound = holders.length ? "" : query;
        this.state.holders = holders.length > 1 ? holders : [];
        if (holders.length === 1) {
            await this.show(holders[0].id);
        }
    }

    async show(partnerId) {
        this.state.holders = [];
        this.state.balance = await this.orm.call("res.partner", "get_meal_balance", [[partnerId]]);
        this.searchRef.el?.focus();
    }

    // A 300 DA meal takes half a credit, so balances are not whole numbers.
    credits(value) {
        return formatFloat(value, { digits: [16, 2], trailingZeros: false });
    }

    get usedPercent() {
        const { credits_total, credits_used } = this.state.balance;
        return credits_total ? Math.min(100, (100 * credits_used) / credits_total) : 0;
    }

    get expires() {
        return formatDate(deserializeDate(this.state.balance.expires));
    }
}

registry.category("actions").add("his_meal_balance", MealBalance);
