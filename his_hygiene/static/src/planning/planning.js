import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { deserializeDate, today } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { memberColor, memberInk } from "../common/colors";

// La matrice du mois : zones en lignes, chaque jour en colonne.
//
// Le geste principal est le pinceau : on choisit une salariee dans la palette,
// puis chaque clic sur une case l'ajoute ou la retire. Maj+clic sur la meme
// ligne recopie la derniere case cliquee jusqu'a celle-ci (jours off sautes).
// Le serveur fait foi : chaque geste repart avec la case telle qu'enregistree.

export class HygienePlanning extends Component {
    static template = "his_hygiene.Planning";
    static props = ["*"];

    // L'arabe se lit de droite a gauche : le coeur pose o_rtl sur le body
    // mais pas la direction du texte de nos ecrans.
    get dir() {
        return localization.direction || "ltr";
    }

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        const now = today();
        this.state = useState({
            year: now.year,
            month: now.month,
            data: null,
            brush: null,
            anchor: null,
            busy: false,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.data = await this.orm.call("his.hygiene.assignment", "get_matrix", [
            this.state.year,
            this.state.month,
        ]);
        this.state.anchor = null;
    }

    // ------------------------------------------------------------------
    // Lecture
    // ------------------------------------------------------------------
    get monthLabel() {
        return this.firstOfMonth.toFormat("LLLL yyyy");
    }

    get firstOfMonth() {
        const month = String(this.state.month).padStart(2, "0");
        return deserializeDate(`${this.state.year}-${month}-01`);
    }

    get buildings() {
        const groups = [];
        for (const area of this.state.data.areas) {
            let group = groups.at(-1);
            if (!group || group.name !== area.building) {
                group = { name: area.building, areas: [] };
                groups.push(group);
            }
            group.areas.push(area);
        }
        return groups;
    }

    weekdayLetter(day) {
        return deserializeDate(day.date).toFormat("ccc");
    }

    member(id) {
        return this.state.data.members.find((m) => m.id === id);
    }

    cell(area, day) {
        return this.state.data.cells[`${area.id}|${day.date}`];
    }

    chipStyle(member) {
        return `background-color: ${memberColor(member.color)}; color: ${memberInk(member.color)};`;
    }

    isAbsent(member, day) {
        return `${member.id}|${day.date}` in this.state.data.absences;
    }

    cellClass(area, day) {
        const cell = this.cell(area, day);
        return {
            o_hyg_off: day.off,
            o_hyg_today: day.today,
            o_hyg_done: cell?.done,
            o_hyg_uncovered: cell?.uncovered,
            o_hyg_anchor:
                this.state.anchor?.areaId === area.id && this.state.anchor?.date === day.date,
        };
    }

    // ------------------------------------------------------------------
    // Gestes
    // ------------------------------------------------------------------
    pickBrush(member) {
        this.state.brush = this.state.brush === member.id ? null : member.id;
    }

    async onCellClick(area, day, ev) {
        if (this.state.busy || !this.state.data.can_edit) {
            return;
        }
        const anchor = this.state.anchor;
        if (ev.shiftKey && anchor && anchor.areaId === area.id && anchor.date !== day.date) {
            const source = this.cell(area, { date: anchor.date });
            await this.run(() =>
                this.orm.call("his.hygiene.assignment", "fill_range", [
                    area.id,
                    anchor.date,
                    day.date,
                    source?.employee_ids || [],
                ])
            );
            await this.load();
            return;
        }
        if (!this.state.brush) {
            this.notification.add(_t("Pick a worker in the palette first, then click the cells."), {
                type: "info",
            });
            return;
        }
        const current = this.cell(area, day)?.employee_ids || [];
        const next = current.includes(this.state.brush)
            ? current.filter((id) => id !== this.state.brush)
            : [...current, this.state.brush];
        const saved = await this.run(() =>
            this.orm.call("his.hygiene.assignment", "set_cell", [area.id, day.date, next])
        );
        if (saved === undefined) {
            return;
        }
        const key = `${area.id}|${day.date}`;
        const extra = this.state.data.cells[key]?.extra || 0;
        if (saved.id || extra) {
            this.state.data.cells[key] = { ...saved, extra, employee_ids: saved.employee_ids || [] };
        } else {
            delete this.state.data.cells[key];
        }
        this.state.anchor = { areaId: area.id, date: day.date };
    }

    async onAbsenceClick(member, day) {
        if (this.state.busy || !this.state.data.can_edit) {
            return;
        }
        const ok = await this.run(() =>
            this.orm.call("his.hygiene.assignment", "toggle_absence", [member.id, day.date])
        );
        if (ok !== undefined) {
            // Une absence change la couverture de toutes les zones du jour.
            await this.load();
        }
    }

    copyPreviousMonth() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Copy the previous month"),
            body: _t(
                "Each day of last month is copied to the same day of this month. Days already planned, days off and days that do not exist are skipped."
            ),
            confirmLabel: _t("Copy"),
            confirm: async () => {
                const count = await this.run(() =>
                    this.orm.call("his.hygiene.assignment", "copy_previous_month", [
                        this.state.year,
                        this.state.month,
                    ])
                );
                await this.load();
                this.notification.add(_t("%s cells copied.", count || 0), { type: "success" });
            },
            cancel: () => {},
        });
    }

    async changeMonth(delta) {
        const next = this.firstOfMonth.plus({ months: delta });
        this.state.year = next.year;
        this.state.month = next.month;
        this.state.brush = null;
        await this.load();
    }

    async run(fn) {
        this.state.busy = true;
        try {
            return await fn();
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("his_hygiene_planning", HygienePlanning);
