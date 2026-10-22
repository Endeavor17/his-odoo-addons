import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { formatHours, memberColor, memberInk } from "../common/colors";

// « Ma journee », pense pour le telephone d'une salariee qui n'est pas a
// l'aise avec l'informatique : un seul gros bouton d'horloge a la fois, une
// carte par zone avec un gros « Fait », et « Signaler un probleme ».
//
// La responsable a le meme ecran, avec en tete le choix de la salariee : pointer
// pour quelqu'un est exactement le meme geste que pointer pour soi.

const CLOCK = {
    false: { action: "start", label: _t("Start the day"), icon: "fa-play" },
    working: { action: "pause", label: _t("Take a break"), icon: "fa-coffee" },
    paused: { action: "resume", label: _t("Back to work"), icon: "fa-play" },
};

function formatClock(seconds) {
    return formatHours((seconds || 0) / 3600);
}

export class HygieneMyDay extends Component {
    static template = "his_hygiene.MyDay";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            data: null,
            employeeId: false,
            tab: "today",
            month: null,
            monthOffset: 0,
            busy: false,
            report: null,
        });
        onWillStart(() => this.load());
        // Le compteur avance localement entre deux allers-retours ; il ne
        // decide jamais rien.
        this.ticker = setInterval(() => {
            const day = this.state.data?.day;
            if (day?.state === "working") {
                day.worked_seconds += 1;
            } else if (day?.state === "paused") {
                day.paused_seconds += 1;
            }
        }, 1000);
        onWillUnmount(() => clearInterval(this.ticker));
    }

    async load() {
        this.state.data = await this.orm.call("his.hygiene.recap", "get_today", [this.state.employeeId]);
        if (this.state.data.employee) {
            this.state.employeeId = this.state.data.employee.id;
        }
        if (this.state.tab === "month") {
            await this.loadMonth();
        }
    }

    async loadMonth() {
        this.state.month = await this.orm.call("his.hygiene.recap", "get_month", [
            this.state.employeeId,
            this.state.monthOffset,
        ]);
    }

    // ------------------------------------------------------------------
    // Lecture
    // ------------------------------------------------------------------
    get clock() {
        return CLOCK[this.state.data.day.state || false];
    }

    get worked() {
        return formatClock(this.state.data.day.worked_seconds);
    }

    get paused() {
        return formatClock(this.state.data.day.paused_seconds);
    }

    chipStyle(member) {
        return `background-color: ${memberColor(member.color)}; color: ${memberInk(member.color)};`;
    }

    hours(value) {
        return value === null || value === undefined ? "" : formatHours(value);
    }

    // ------------------------------------------------------------------
    // Gestes
    // ------------------------------------------------------------------
    async pickEmployee(member) {
        this.state.employeeId = member.id;
        this.state.report = null;
        await this.load();
    }

    async clockAction(action) {
        await this.run(async () => {
            this.state.data.day = await this.orm.call("maintenance.university.workday", "his_hygiene_clock", [
                this.state.employeeId,
                action,
            ]);
        });
    }

    async toggleDone(assignment) {
        await this.run(async () => {
            await this.orm.call(
                "his.hygiene.assignment",
                assignment.done ? "action_mark_undone" : "action_mark_done",
                [[assignment.id]]
            );
            assignment.done = !assignment.done;
        });
    }

    async showTab(tab) {
        this.state.tab = tab;
        if (tab === "month") {
            await this.loadMonth();
        }
    }

    async changeMonth(delta) {
        this.state.monthOffset += delta;
        await this.loadMonth();
    }

    openReport(areaId = false) {
        this.state.report = { kind: false, areaId: areaId || this.state.data.assignments[0]?.area_id || false, text: "", image: false, imageName: "" };
    }

    onPhoto(ev) {
        const file = ev.target.files[0];
        if (!file) {
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            this.state.report.image = reader.result.split(",")[1];
            this.state.report.imageName = file.name;
        };
        reader.readAsDataURL(file);
    }

    get canSend() {
        const r = this.state.report;
        return r && r.kind && r.areaId && r.text.trim();
    }

    async sendReport() {
        const r = this.state.report;
        await this.run(async () => {
            await this.orm.create("his.hygiene.finding", [
                {
                    area_id: Number(r.areaId),
                    kind: r.kind,
                    description: r.text.trim(),
                    image: r.image || false,
                    employee_id: this.state.employeeId,
                },
            ]);
            this.state.report = null;
            this.notification.add(
                r.kind === "repair"
                    ? _t("Thank you. The maintenance team has been told.")
                    : _t("Thank you. The manager has been told."),
                { type: "success" }
            );
        });
    }

    async run(fn) {
        this.state.busy = true;
        try {
            await fn();
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("his_hygiene_my_day", HygieneMyDay);
