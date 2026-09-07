import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

// The one screen a cashier reads before spending someone's credit.
//
// This was core's ConfirmationDialog with a formatted string. That put the
// student's name, their plan, what they have left and what the meal costs into
// one paragraph, which is a lot to parse with a queue waiting. Here the same
// facts are laid out: who, what is left, what this takes, what remains.
//
// The bar is the balance in hand, not the plan that was bought — the gold slice
// is what this meal takes and the teal is what survives it. Drawing it against
// the plan's total would have meant one more field over the wire from
// get_meal_balance for no better answer to "can they eat".

export class ServeMealDialog extends Component {
    static template = "his_meal_management.ServeMealDialog";
    static components = { Dialog };
    // Kept in step with ALLOWANCE_MEALS in models/meal_subscription.py by hand.
    // The server is what enforces it; this is only how the number is worded on
    // screen, and a mismatch shows as wrong wording, never as a wrong balance.
    static ALLOWANCE_MEALS = 2;
    static props = {
        close: Function,
        confirm: Function,
        name: String,
        cardCode: { type: String, optional: true },
        plan: { type: String, optional: true },
        // Always a string from get_meal_balance — empty when the credits never
        // expire, which the dialog reads as "no expiry" rather than as a
        // missing date.
        expires: { type: String, optional: true },
        credits: Number,
        mealName: String,
        cost: Number,
        // The empty-card case. The meal is still served — the student has bought
        // a plan, and two meals of allowance come with that — but the cashier
        // has to see plainly that there is nothing on the card.
        onAllowance: { type: Boolean, optional: true },
        allowanceLeft: { type: Number, optional: true },
        allowanceDebt: { type: Number, optional: true },
    };

    setup() {
        this.busy = false;
    }

    get initials() {
        return this.props.name
            .split(/\s+/)
            .filter((part) => part)
            .slice(0, 2)
            .map((part) => part[0].toUpperCase())
            .join("");
    }

    get after() {
        return this.props.credits - this.props.cost;
    }

    // Which of the two allowance meals this one is: "meal 1 of 2" reads better
    // at a till than "1 left".
    get allowanceMealNumber() {
        return this.constructor.ALLOWANCE_MEALS - (this.props.allowanceLeft ?? 0) + 1;
    }

    get allowanceTotal() {
        return this.constructor.ALLOWANCE_MEALS;
    }

    // What the student will owe once this meal is served, taken off their next
    // top-up. Only part of the meal may be on the allowance: half a credit left
    // on a plan pays half of a Meal 600.
    get owedAfter() {
        const alreadyOwed = this.props.allowanceDebt ?? 0;
        const takenNow = Math.max(0, this.props.cost - this.props.credits);
        return Math.round((alreadyOwed + takenNow) * 100) / 100;
    }

    get spentPct() {
        if (!this.props.credits) {
            return 100;
        }
        return Math.min(100, (this.props.cost / this.props.credits) * 100);
    }

    get keptPct() {
        return 100 - this.spentPct;
    }

    // A second tap must not drop a second meal line on the order.
    async onConfirm() {
        if (this.busy) {
            return;
        }
        this.busy = true;
        try {
            await this.props.confirm();
        } finally {
            this.props.close();
        }
    }
}
