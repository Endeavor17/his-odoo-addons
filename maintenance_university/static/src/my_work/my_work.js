import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";

// The worker's day, above the worker's jobs.
//
// This is presence, not task time: it keeps running between jobs and through a
// break, which is exactly what makes it different from the per-request timers
// on the cards below. The two are meant to disagree - the gap is travel and
// idle time.
//
// The server owns the state. Every button round-trips and the reply redraws the
// banner, so a second tab, a reload or a phone cannot show a different day from
// the one actually recorded. Only the ticking counter runs locally.

function formatDuration(seconds) {
    const total = Math.max(0, Math.floor(seconds));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    return `${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`;
}

export class WorkdayBanner extends Component {
    static template = "maintenance_university.WorkdayBanner";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ day: null, busy: false });

        onWillStart(async () => {
            this.state.day = await this.orm.call(
                "maintenance.university.workday", "get_my_day", []
            );
        });

        // Local tick only. It moves the counter between round-trips; it never
        // decides anything.
        this.ticker = setInterval(() => {
            const day = this.state.day;
            if (!day || !day.state || day.state === "done") {
                return;
            }
            if (day.state === "paused") {
                day.paused_seconds += 1;
            } else {
                day.worked_seconds += 1;
            }
        }, 1000);
        onWillUnmount(() => clearInterval(this.ticker));
    }

    get hasEmployee() {
        return this.state.day?.has_employee;
    }

    get dayState() {
        // No record today yet reads the same as "not started".
        return this.state.day?.state || false;
    }

    get startedAt() {
        const raw = this.state.day?.date_start;
        if (!raw) {
            return "";
        }
        // Stored UTC, shown in the user's own time - a worker reading "05:30"
        // for an 08:30 start would not trust the thing. deserializeDateTime is
        // core's own converter; the bare `luxon` global is not an API to lean
        // on here.
        return deserializeDateTime(raw).toFormat("HH:mm");
    }

    get workedLabel() {
        return formatDuration(this.state.day?.worked_seconds || 0);
    }

    get pausedLabel() {
        return formatDuration(this.state.day?.paused_seconds || 0);
    }

    get primaryLabel() {
        switch (this.dayState) {
            case "working":
                return _t("Take a break");
            case "paused":
                return _t("Back to work");
            case "done":
                return _t("Day finished");
            default:
                return _t("Start working");
        }
    }

    async callDay(method) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const id = this.state.day?.id;
            const args = id ? [[id]] : [];
            this.state.day = await this.orm.call(
                "maintenance.university.workday", method, args
            );
        } finally {
            this.state.busy = false;
        }
    }

    onPrimary() {
        switch (this.dayState) {
            case "working":
                return this.callDay("action_pause");
            case "paused":
                return this.callDay("action_resume");
            case "done":
                return undefined;
            default:
                return this.callDay("action_start_day");
        }
    }

    onEndDay() {
        return this.callDay("action_end_day");
    }
}

export class MyWork extends Component {
    static template = "maintenance_university.MyWork";
    static components = { WorkdayBanner, View };
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.viewProps = null;

        onWillStart(async () => {
            // Read the kanban and search views off the existing act_window
            // rather than restating them here: it stays the single definition
            // of what My Work lists.
            const action = await this.action.loadAction(
                "maintenance_university.action_maintenance_university_request_my_work"
            );
            this.viewProps = {
                resModel: action.res_model,
                type: "kanban",
                views: action.views,
                context: action.context || {},
                domain: action.domain || [],
                searchViewId: action.search_view_id ? action.search_view_id[0] : false,
                display: { controlPanel: { layoutActions: false } },
            };
        });
    }
}

registry.category("actions").add("maintenance_university_my_work", MyWork);
