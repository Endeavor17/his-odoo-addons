/** @odoo-module **/
/**
 * Le composant des cockpits.
 *
 * Il ne sait RIEN du metier. Il recoit une specification — des tuiles, un
 * entonnoir, des files, des liens — et la dessine. Les quatre cockpits
 * partagent donc ce seul fichier, et une definition d'indicateur ne peut pas
 * deriver entre le serveur et l'ecran : elle n'existe qu'a un endroit,
 * models/his_dashboard.py.
 *
 * Le nom de la methode a appeler vient des parametres de l'action, ce qui rend
 * un nouveau cockpit realisable sans toucher a ce fichier.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

/**
 * Les periodes proposees. Les bornes sont calculees dans le fuseau du
 * navigateur puis envoyees en AAAA-MM-JJ : le serveur ne recoit jamais
 * d'horodatage, donc jamais de decalage d'un jour.
 */
const PERIODES = {
    mois: {
        label: "Ce mois-ci",
        bornes: () => {
            const today = new Date();
            return [new Date(today.getFullYear(), today.getMonth(), 1), today];
        },
    },
    trimestre: {
        label: "Ce trimestre",
        bornes: () => {
            const today = new Date();
            const debut = Math.floor(today.getMonth() / 3) * 3;
            return [new Date(today.getFullYear(), debut, 1), today];
        },
    },
    annee: {
        label: "Cette annee",
        bornes: () => {
            const today = new Date();
            return [new Date(today.getFullYear(), 0, 1), today];
        },
    },
    trente: {
        label: "30 derniers jours",
        bornes: () => {
            const today = new Date();
            const debut = new Date(today);
            debut.setDate(debut.getDate() - 29);
            return [debut, today];
        },
    },
};

function enIso(date) {
    // toISOString() convertit en UTC et peut reculer d'un jour selon le
    // fuseau. On formate donc a la main sur les composantes locales.
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const jj = String(date.getDate()).padStart(2, "0");
    return `${date.getFullYear()}-${mm}-${jj}`;
}

export class HisDashboard extends Component {
    static template = "his_crm_pipeline.Dashboard";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.periodes = PERIODES;

        this.state = useState({
            periode: "mois",
            spec: null,
            chargement: true,
        });

        onWillStart(() => this.charger());
    }

    get methode() {
        // « admissions » -> get_admissions. Ajouter un cockpit est une action
        // et une methode serveur, pas une modification de ce composant.
        return `get_${this.props.action.params?.kpi || "direction"}`;
    }

    async charger() {
        this.state.chargement = true;
        const [debut, fin] = PERIODES[this.state.periode].bornes();
        this.state.spec = await this.orm.call("his.dashboard", this.methode, [
            enIso(debut),
            enIso(fin),
        ]);
        this.state.chargement = false;
    }

    changerPeriode(ev) {
        this.state.periode = ev.target.value;
        this.charger();
    }

    ouvrir(action) {
        if (action) {
            this.action.doAction(action);
        }
    }

    /** La largeur d'une marche d'entonnoir, en % de la premiere. */
    largeurMarche(marche) {
        const premiere = this.state.spec.funnel[0]?.count || 0;
        return premiere ? Math.max((marche.count / premiere) * 100, 1) : 0;
    }

    /** L'atteinte plafonnee a 100 pour la jauge — la valeur reste affichee. */
    largeurJauge(tuile) {
        return Math.min(tuile.atteinte || 0, 100);
    }

    classeEcart(ecart) {
        if (!ecart) {
            return "";
        }
        return ecart > 0 ? "his_hausse" : "his_baisse";
    }

    /**
     * Le rythme constate suffit-il ? La projection repond « si rien ne
     * change » — c'est ce qui transforme un compteur en decision.
     */
    tientLeRythme(tuile) {
        return tuile.projection >= tuile.cible;
    }
}

registry.category("actions").add("his_dashboard", HisDashboard);
