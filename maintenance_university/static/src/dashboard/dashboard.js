import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

// The month's recap, drawn in the DOM rather than on a canvas.
//
// It used to be three Chart.js charts, the first of them a radar comparing
// workers on hours, tasks and findings at once. A radar has one radial scale,
// so those had to be normalised to 0-100 against each axis's own maximum before
// they could share it — which means the shape it drew was an artefact of the
// normalisation, not of the data. Two workers with identical polygons could
// have nothing in common. Hours and counts do not belong on one scale.
//
// So: hours are bars on a single shared scale, counts are figures, and the two
// breakdowns are ordinary bars scaled to their own largest value. Every number
// is on screen as text, which is also why the visually-hidden tables that used
// to stand in for the canvases are gone — there is nothing left to stand in for,
// and no chart library to load.

export class MaintenanceUniversityDashboard extends Component {
    static template = "maintenance_university.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: true, refreshing: false, data: null, monthOffset: 0 });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        // Only the very first load shows the full-page spinner (state.data is
        // still null then) — a month-nav click keeps the last render mounted
        // and shows a small inline spinner instead, so paging through months
        // doesn't feel like the page reloading each time.
        if (this.state.data) {
            this.state.refreshing = true;
        } else {
            this.state.loading = true;
        }
        this.state.data = await this.orm.call(
            "maintenance.university.dashboard",
            "get_recap_data",
            [this.state.monthOffset]
        );
        this.state.loading = false;
        this.state.refreshing = false;
    }

    async goToPreviousMonth() {
        this.state.monthOffset -= 1;
        await this.loadData();
    }

    async goToNextMonth() {
        this.state.monthOffset += 1;
        await this.loadData();
    }

    // One scale for every hour bar on the screen, so a worker's two bars and
    // any two workers' bars are all directly comparable. The scale's top is
    // stated in the card's subtitle rather than drawn as an axis: five rows do
    // not need gridlines to be read.
    get workerRows() {
        const workers = this.state.data?.workers || [];
        const max = this.hoursScale;
        return workers.map((worker) => ({
            ...worker,
            hoursPct: (worker.hours / max) * 100,
            presentPct: (worker.hours_present / max) * 100,
        }));
    }

    get hoursScale() {
        const workers = this.state.data?.workers || [];
        return Math.max(1, ...workers.map((w) => Math.max(w.hours, w.hours_present)));
    }

    // Findings the recap calls out but the totals do not carry: the server
    // returns them per worker, so the month's figure is their sum.
    get criticalTotal() {
        return (this.state.data?.workers || []).reduce((n, w) => n + w.findings_critical, 0);
    }

    // Time on site that never reached a request — travel and idle. Negative
    // would mean more booked than clocked, which is a data problem rather than
    // a fact about the month, so the caption is simply dropped in that case.
    get offTaskHours() {
        const totals = this.state.data.totals;
        return totals.hours_present - totals.hours;
    }

    // Each breakdown is scaled to its own largest bar. The two answer different
    // questions and share no axis, so nothing is gained by scaling them alike.
    breakdownRows(breakdown) {
        const max = Math.max(1, ...breakdown.map((row) => row.count));
        return breakdown.map((row) => ({ ...row, pct: (row.count / max) * 100 }));
    }

    get categoryRows() {
        return this.breakdownRows(this.state.data.category_breakdown);
    }

    get buildingRows() {
        return this.breakdownRows(this.state.data.building_breakdown);
    }
}

registry.category("actions").add("maintenance_university_dashboard", MaintenanceUniversityDashboard);
