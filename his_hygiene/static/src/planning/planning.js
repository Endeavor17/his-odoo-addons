import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { deserializeDate, today } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { memberColor, memberInk } from "../common/colors";

// La matrice : zones en lignes, chaque jour en colonne. Deux vues, comme un
// agenda : la semaine (grandes cases, prenoms en clair) et le mois (compact).
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
        this.state = useState({
            view: "week",
            focus: today(),
            data: null,
            brush: null,
            anchor: null,
            busy: false,
        });
        onWillStart(() => this.load());
        // Sur un telephone seuls quelques jours tiennent a l'ecran : le mois
        // s'ouvre sur aujourd'hui plutot que sur le 1er.
        this.scrollRef = useRef("scroll");
        useEffect(
            () => {
                this.scrollRef.el
                    ?.querySelector("thead .o_hyg_today")
                    ?.scrollIntoView({ block: "nearest", inline: "center" });
            },
            () => [this.state.data?.date_from, this.state.view]
        );
    }

    async load() {
        const [from, to] = this.range;
        this.state.data = await this.orm.call("his.hygiene.assignment", "get_range", [
            from.toISODate(),
            to.toISODate(),
        ]);
        this.state.anchor = null;
    }

    // La semaine commence le dimanche (vendredi et samedi chomes).
    get range() {
        const focus = this.state.focus;
        if (this.state.view === "week") {
            const start = focus.minus({ days: focus.weekday % 7 });
            return [start, start.plus({ days: 6 })];
        }
        const start = focus.startOf("month");
        return [start, start.endOf("month").startOf("day")];
    }

    // ------------------------------------------------------------------
    // Lecture
    // ------------------------------------------------------------------
    get title() {
        const [from, to] = this.range;
        if (this.state.view === "month") {
            return from.toFormat("LLLL yyyy");
        }
        const left = from.year === to.year ? from.toFormat("d LLL") : from.toFormat("d LLL yyyy");
        return `${left} – ${to.toFormat("d LLL yyyy")}`;
    }

    get isWeek() {
        return this.state.view === "week";
    }

    avatarUrl(member) {
        return `/web/image/hr.employee.public/${member.id}/avatar_128`;
    }

    firstName(member) {
        return member.name.split(" ")[0];
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

    weekdayLabel(day) {
        return deserializeDate(day.date).toFormat(this.isWeek ? "cccc" : "ccc");
    }

    member(id) {
        return this.state.data.members.find((m) => m.id === id);
    }

    cell(area, day) {
        return this.state.data.cells[`${area.id}|${day.date}`];
    }

    memberColorOf(member) {
        return memberColor(member.color);
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

    async setView(view) {
        if (view !== this.state.view) {
            this.state.view = view;
            await this.load();
        }
    }

    async goToday() {
        this.state.focus = today();
        await this.load();
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
                "Each working day takes the plan of the same weekday of last month. Days already planned and days off are skipped."
            ),
            confirmLabel: _t("Copy"),
            confirm: async () => {
                const count = await this.run(() =>
                    this.orm.call("his.hygiene.assignment", "copy_previous_month", [
                        this.state.focus.year,
                        this.state.focus.month,
                    ])
                );
                await this.load();
                this.notification.add(_t("%s cells copied.", count || 0), { type: "success" });
            },
            cancel: () => {},
        });
    }

    async move(delta) {
        this.state.focus = this.state.focus.plus(this.isWeek ? { weeks: delta } : { months: delta });
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
