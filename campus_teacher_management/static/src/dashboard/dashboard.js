/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Campus+ recruitment dashboard.
 *
 * Deliberately thin: every number comes from ordinary ORM reads rather than a
 * bespoke endpoint, so record rules still apply and a recruiter can never see a
 * figure they could not have reached through a list view.
 */
export class CampusDashboard extends Component {
    static template = "campus_teacher_management.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            versions: [],
            versionId: null,
            kpis: this._emptyKpis(),
            ranking: [],
        });

        onWillStart(async () => {
            await this.loadVersions();
            await this.loadDashboard();
            this.state.loading = false;
        });
    }

    _emptyKpis() {
        return {
            total: 0,
            evaluated: 0,
            pending: 0,
            accepted: 0,
            refused: 0,
            avgScore: 0,
            maxScore: 0,
        };
    }

    async loadVersions() {
        const versions = await this.orm.searchRead(
            "campus.evaluation.version",
            [],
            ["id", "display_name", "state"],
            { order: "version desc, id desc" }
        );
        this.state.versions = versions;
        const published = versions.find((v) => v.state === "published");
        this.state.versionId = published ? published.id : versions.length ? versions[0].id : null;
    }

    get versionDomain() {
        return this.state.versionId
            ? [["campus_version_id", "=", this.state.versionId]]
            : [["campus_version_id", "!=", false]];
    }

    get evaluatedDomain() {
        return this.versionDomain.concat([["campus_state", "in", ["evaluated", "locked"]]]);
    }

    async loadDashboard() {
        const domain = this.versionDomain;
        const kpis = this._emptyKpis();

        // One grouped read for every status count rather than five search_counts.
        const byState = await this.orm.formattedReadGroup(
            "hr.applicant",
            domain,
            ["campus_state"],
            ["__count"]
        );
        for (const group of byState) {
            const count = group.__count || 0;
            kpis.total += count;
            if (["evaluated", "locked"].includes(group.campus_state)) {
                kpis.evaluated += count;
            } else {
                kpis.pending += count;
            }
        }

        const aggregates = await this.orm.formattedReadGroup(
            "hr.applicant",
            this.evaluatedDomain,
            [],
            ["campus_final_score:avg", "campus_final_score:max"]
        );
        if (aggregates.length) {
            kpis.avgScore = aggregates[0]["campus_final_score:avg"] || 0;
            kpis.maxScore = aggregates[0]["campus_final_score:max"] || 0;
        }

        // Accepted and refused come from the standard recruitment status, so
        // these figures always agree with what the Recruitment app reports.
        //
        // Counted rather than grouped: application_status is a NON-STORED
        // computed field. It carries a search method so it works in a domain,
        // but grouping compiles to SQL over a column that does not exist and
        // raises "Cannot convert ... to SQL because it is not stored".
        [kpis.accepted, kpis.refused] = await Promise.all([
            this.orm.searchCount("hr.applicant", domain.concat([["application_status", "=", "hired"]])),
            this.orm.searchCount("hr.applicant", domain.concat([["application_status", "=", "refused"]])),
        ]);

        this.state.ranking = await this.orm.searchRead(
            "hr.applicant",
            this.evaluatedDomain,
            [
                "id",
                "campus_rank",
                "partner_name",
                "email_from",
                "campus_final_score",
                "campus_scientific_rank",
                "stage_id",
            ],
            { limit: 25, order: "campus_final_score desc, id asc" }
        );
        this.state.kpis = kpis;
    }

    async onVersionChange(ev) {
        const value = ev.target.value;
        this.state.versionId = value ? parseInt(value, 10) : null;
        this.state.loading = true;
        await this.loadDashboard();
        this.state.loading = false;
    }

    openApplicant(applicantId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.applicant",
            res_id: applicantId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openFiltered(extraDomain, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "hr.applicant",
            domain: this.versionDomain.concat(extraDomain),
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    }

    openAll() {
        this.openFiltered([], _t("Applications"));
    }

    openEvaluated() {
        this.openFiltered([["campus_state", "in", ["evaluated", "locked"]]], _t("Evaluated"));
    }

    openPending() {
        this.openFiltered(
            [["campus_state", "in", ["not_started", "submitted"]]],
            _t("Pending Evaluation")
        );
    }

    openAccepted() {
        this.openFiltered([["application_status", "=", "hired"]], _t("Accepted"));
    }

    openRefused() {
        this.openFiltered([["application_status", "=", "refused"]], _t("Refused"));
    }

    formatScore(value) {
        return (value || 0).toFixed(2);
    }
}

registry.category("actions").add("campus_teacher_dashboard", CampusDashboard);
