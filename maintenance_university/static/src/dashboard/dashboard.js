import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, useRef, onWillStart, useEffect } from "@odoo/owl";

// A fixed palette cycled by worker index, rather than random colors: keeps
// a given worker's polygon the same color across re-renders (month nav,
// data refresh) instead of reshuffling every time.
const WORKER_COLORS = [
    "#2E6E62", "#B45A3C", "#3B6FA0", "#A0522D", "#5B7F3F", "#8E4585", "#C08A2E", "#3E7C7C",
];

const RADAR_AXES = [
    { key: "hours", label: _t("Hours Worked") },
    { key: "tasks_done", label: _t("Tasks Completed") },
    { key: "findings_logged", label: _t("Findings Logged") },
    { key: "findings_critical", label: _t("Critical/High Findings") },
];

export class MaintenanceUniversityDashboard extends Component {
    static template = "maintenance_university.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: true, refreshing: false, data: null, monthOffset: 0 });
        this.radarRef = useRef("radarCanvas");
        this.categoryRef = useRef("categoryCanvas");
        this.buildingRef = useRef("buildingCanvas");
        this.charts = {};

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadData();
        });

        useEffect(
            () => {
                if (this.state.data) {
                    this.renderCharts();
                }
                return () => this.destroyCharts();
            },
            () => [this.state.data]
        );
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

    destroyCharts() {
        for (const chart of Object.values(this.charts)) {
            chart.destroy();
        }
        this.charts = {};
    }

    renderCharts() {
        this.destroyCharts();
        this.renderRadarChart();
        this.renderBreakdownChart(this.categoryRef, this.state.data.category_breakdown, "category");
        this.renderBreakdownChart(this.buildingRef, this.state.data.building_breakdown, "building");
    }

    renderRadarChart() {
        if (!this.radarRef.el) {
            return;
        }
        const workers = this.state.data.workers;
        // Each axis is normalized to 0-100 against that axis's own max across
        // workers this month: hours (often 100+) and findings (often single
        // digits) live on wildly different scales, so plotting raw values
        // would flatten the smaller axes to invisible slivers. The real
        // number is still shown via the tooltip callback below.
        const axisMax = {};
        for (const axis of RADAR_AXES) {
            axisMax[axis.key] = Math.max(1, ...workers.map((w) => w[axis.key]));
        }
        const datasets = workers.map((worker, index) => {
            const color = WORKER_COLORS[index % WORKER_COLORS.length];
            return {
                label: worker.name,
                data: RADAR_AXES.map((axis) => (worker[axis.key] / axisMax[axis.key]) * 100),
                rawValues: RADAR_AXES.map((axis) => worker[axis.key]),
                borderColor: color,
                backgroundColor: color + "33",
                pointBackgroundColor: color,
            };
        });
        this.charts.radar = new Chart(this.radarRef.el, {
            type: "radar",
            data: {
                labels: RADAR_AXES.map((axis) => axis.label.toString()),
                datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: { min: 0, max: 100, ticks: { display: false } },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const raw = context.dataset.rawValues[context.dataIndex];
                                return `${context.dataset.label}: ${raw}`;
                            },
                        },
                    },
                },
            },
        });
    }

    renderBreakdownChart(ref, breakdown, key) {
        if (!ref.el) {
            return;
        }
        this.charts[key] = new Chart(ref.el, {
            type: "bar",
            data: {
                labels: breakdown.map((row) => row.name),
                datasets: [
                    {
                        label: _t("Requests"),
                        data: breakdown.map((row) => row.count),
                        backgroundColor: "#2E6E62",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: "y",
                plugins: { legend: { display: false } },
                scales: { x: { ticks: { precision: 0 } } },
            },
        });
    }
}

registry.category("actions").add("maintenance_university_dashboard", MaintenanceUniversityDashboard);
