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
 *
 * Chacune doit repondre a une question DIFFERENTE. « 30 derniers jours »
 * cohabitait avec « ce mois-ci » : passe le 20 du mois les deux couvraient
 * presque le meme intervalle et donnaient presque le meme chiffre, ce qui
 * oblige le lecteur a se demander laquelle il regarde. « Le mois dernier » le
 * remplace : une periode COMPLETE et close, la seule a laquelle on puisse
 * comparer sans reflechir.
 */
const PERIODES = {
    mois: {
        label: "Ce mois-ci",
        bornes: () => {
            const today = new Date();
            return [new Date(today.getFullYear(), today.getMonth(), 1), today];
        },
    },
    mois_dernier: {
        label: "Le mois dernier",
        bornes: () => {
            const today = new Date();
            return [
                new Date(today.getFullYear(), today.getMonth() - 1, 1),
                // Jour 0 du mois courant = dernier jour du mois precedent.
                new Date(today.getFullYear(), today.getMonth(), 0),
            ];
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
    static props = {
        ...standardActionServiceProps,
        // ActionContainer passe className="o_action" a TOUT composant d'action.
        // Ce n'est pas decoratif : c'est cette classe qui recoit la colonne
        // flex en hauteur pleine (.o_action_manager > .o_action), sans laquelle
        // le .o_content interieur n'a pas de hauteur contrainte et ne peut donc
        // pas defiler. Elle doit atterrir sur un element englobant le Layout —
        // voir le template.
        className: { type: String, optional: true },
    };

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

    /**
     * L'intervalle reellement interroge, en toutes lettres.
     *
     * Un libelle seul laisse deviner : « ce trimestre » commence-t-il en
     * juillet ou en aout ? Afficher les bornes retire la question, et rend
     * deux periodes impossibles a confondre.
     */
    get intervalle() {
        const [debut, fin] = PERIODES[this.state.periode].bornes();
        const format = { day: "numeric", month: "long" };
        const meme_annee = debut.getFullYear() === fin.getFullYear();
        return `${debut.toLocaleDateString("fr-FR", {
            ...format,
            year: meme_annee ? undefined : "numeric",
        })} — ${fin.toLocaleDateString("fr-FR", { ...format, year: "numeric" })}`;
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

    /**
     * Le donut, en une seule declaration CSS.
     *
     * conic-gradient plutot qu'une bibliotheque de graphiques : ces quatre
     * donuts sont des INSTANTANES, pas des series temporelles. Le README du
     * module a deja tranche contre Chart.js pour cette raison, et une
     * dependance pour dessiner quatre camemberts statiques serait une facon
     * couteuse de perdre un argument deja gagne. Le jour ou une courbe dans le
     * temps est demandee, une bibliotheque devient justifiee.
     *
     * Les couleurs sont des variables CSS, jamais des valeurs en dur : la
     * passe visuelle a venir ne touchera qu'a ces jetons.
     */
    gradientDonut(donut) {
        if (!donut.total) {
            return "conic-gradient(var(--his-donut-vide) 0 100%)";
        }
        const parts = [];
        let angle = 0;
        donut.segments.forEach((segment, index) => {
            const fin = angle + (segment.count / donut.total) * 100;
            parts.push(`${this.couleurSegment(index)} ${angle}% ${fin}%`);
            angle = fin;
        });
        return `conic-gradient(${parts.join(", ")})`;
    }

    /** La couleur d'une part, pour sa pastille de legende. */
    couleurSegment(index) {
        return `var(--his-donut-${index % 8})`;
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
