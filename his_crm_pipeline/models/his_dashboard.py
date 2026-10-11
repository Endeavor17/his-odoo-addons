# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le service qui calcule les indicateurs des cockpits.

UN SEUL endroit ou une definition de KPI est ecrite. C'est la regle qui compte
dans ce fichier : « taux de conversion » doit vouloir dire la meme chose sur
l'ecran du directeur, dans un test, et demain dans l'outil de BI. Une definition
recopiee dans un composant JavaScript se met a deriver le jour ou quelqu'un
corrige l'une des deux copies.

Le composant qui affiche tout cela ne sait rien du metier : il recoit une
specification — des tuiles, un entonnoir, des listes — et la dessine. C'est ce
qui permet a quatre cockpits de partager un seul composant.

Aucun SQL, aucune table d'agregat : uniquement _read_group et search_count sur
des colonnes deja stockees. L'outil de BI qui viendra lira les memes colonnes
directement, sans que rien ici ne soit a defaire.

CHAQUE CHIFFRE PORTE SON ACTION. Une tuile qu'on ne peut pas ouvrir laisse le
lecteur devant un nombre qu'il doit croire sur parole ; c'est aussi ce qui rend
une definition fausse indetectable.
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Au-dela, un dossier pre-admis qui n'a pas paye merite qu'on rappelle.
JOURS_PRE_ADMIS_SANS_ENCAISSEMENT = 7
# Au-dela, une demande de contenu stagne en production.
JOURS_CONTENU_BLOQUE = 10
# Ce qu'on montre d'une liste avant de renvoyer vers la liste complete.
APERCU = 5


class HisDashboard(models.AbstractModel):
    """Sans table : ce modele ne stocke rien, il repond a des questions."""

    _name = "his.dashboard"
    _description = "Cockpit Indicators"

    # ======================= Outils de construction ==========================

    @staticmethod
    def _periode_precedente(date_from, date_to):
        """La periode de meme duree qui precede immediatement celle-ci.

        Comparer a « le mois dernier » plutot qu'a une date fixe : c'est ce qui
        rend un ecart lisible sans que le lecteur ait a calculer.
        """
        duree = (date_to - date_from) + timedelta(days=1)
        return date_from - duree, date_from - timedelta(days=1)

    def _action(self, name, model, domain, views=None, context=None):
        # Un pivot ou un graphe sans groupby s'ouvre sur une seule case
        # « Total » : le chiffre est juste, mais la question posee par le
        # libelle (« par personne », « par marque ») reste sans reponse.
        # C'est le context qui la porte.
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "domain": domain,
            "views": views or [[False, "list"], [False, "form"]],
            "target": "current",
            "context": context or {},
        }

    def _tuile(
        self, cle, label, valeur, action=None, precedent=None, unite=None, axe=None, date_from=None, date_to=None
    ):
        """Une tuile, avec son ecart et son objectif s'il en existe un."""
        tuile = {
            "cle": cle,
            "label": label,
            "valeur": valeur,
            "unite": unite,
            "precedent": precedent,
            "action": action,
        }
        if precedent is not None:
            tuile["ecart"] = self._ecart(valeur, precedent)
        if axe and date_from and date_to:
            tuile.update(self._objectif(axe, valeur, date_from, date_to))
        return tuile

    @staticmethod
    def _ecart(valeur, precedent):
        """L'ecart en %, ou None quand la periode precedente est vide.

        Renvoyer 100 % quand on passe de 0 a 5 serait faux : on ne peut pas
        exprimer en pourcentage une progression depuis rien. Mieux vaut ne rien
        afficher qu'un chiffre qui ment.
        """
        if not precedent:
            return None
        return round((valeur - precedent) / precedent * 100, 1)

    def _objectif(self, axe, valeur, date_from, date_to):
        """Atteinte, rythme requis et projection de fin de periode.

        La projection extrapole le rythme constate sur ce qui reste a courir.
        C'est une droite, pas une prevision — les inscriptions arrivent par
        vagues autour des dates de rentree. Elle repond a « si rien ne change »,
        ce qui suffit a declencher une decision.
        """
        # sudo() : une cible est un chiffre affiche, pas une donnee reservee.
        # Sans cela il faudrait une ligne d'ACL par role susceptible d'ouvrir un
        # cockpit — et le jour ou l'on en ajoute un, la tuile leverait une
        # erreur de droits au lieu d'afficher son objectif. L'ECRITURE reste
        # reservee a la Direction, c'est la que se joue le controle.
        objectif = self.env["his.objectif"].sudo()._pour(axe, date_from, date_to)
        if not objectif:
            return {}

        aujourdhui = min(max(fields.Date.context_today(self), objectif.date_debut), objectif.date_fin)
        total = (objectif.date_fin - objectif.date_debut).days + 1
        ecoules = (aujourdhui - objectif.date_debut).days + 1
        restants = total - ecoules

        reste_a_faire = max(objectif.valeur_cible - valeur, 0)
        return {
            "cible": objectif.valeur_cible,
            "cible_nom": objectif.name,
            "atteinte": round(valeur / objectif.valeur_cible * 100, 1),
            "jours_restants": restants,
            "rythme_requis": round(reste_a_faire / restants, 2) if restants > 0 else 0,
            "projection": round(valeur / ecoules * total) if ecoules else 0,
        }

    def _a_traiter(self, label, model, domain):
        """Une file d'exception : ce qui demande un geste, pas un agregat.

        C'est la moitie du tableau de bord qui fait travailler. Un compteur dit
        que quelque chose ne va pas ; cette liste dit quoi ouvrir.

        display_name et non name : tous les modeles n'ont pas de champ `name`.
        his.engagement n'en a pas — un engagement se nomme par la personne et
        son parcours, pas par une chaine saisie.
        """
        Model = self.env[model]
        enregistrements = Model.search(domain, limit=APERCU)
        return {
            "label": label,
            "count": Model.search_count(domain),
            "apercu": [{"id": rec.id, "nom": rec.display_name or "#%s" % rec.id} for rec in enregistrements],
            "action": self._action(label, model, domain),
        }

    def _donut(self, label, model, domain, groupby):
        """Une repartition : un tout, decoupe en parts qui le somment.

        Un seul _read_group sur une colonne deja stockee. Aucun SQL, aucune
        table d'agregat, comme partout dans ce fichier.

        Les parts sont triees par effectif decroissant : une legende dans
        l'ordre de la base fait chercher la plus grosse part a l'oeil.

        Chaque part porte SON action, comme chaque tuile : cliquer une part
        doit ouvrir exactement les enregistrements qu'elle compte. C'est ce qui
        rend une definition fausse detectable au lieu de simplement fausse — un
        test le verifie part par part.
        """
        Model = self.env[model]
        groupes = Model._read_group(domain, groupby=[groupby], aggregates=["__count"])

        segments = []
        total = 0
        for valeur, compte in groupes:
            total += compte
            # _read_group rend un recordset pour un Many2one, la valeur brute
            # pour un entier ou une selection, et False pour un groupe vide.
            if hasattr(valeur, "display_name"):
                nom = valeur.display_name or _("Not set")
                critere = valeur.id
            else:
                nom = str(valeur) if valeur or valeur == 0 else _("Not set")
                critere = valeur
            segments.append(
                {
                    "label": nom,
                    "count": compte,
                    "action": self._action(
                        "%s : %s" % (label, nom),
                        model,
                        [*domain, (groupby, "=", critere)],
                    ),
                }
            )

        segments.sort(key=lambda s: s["count"], reverse=True)
        for segment in segments:
            segment["pourcentage"] = round(segment["count"] / total * 100, 1) if total else 0
        return {"label": label, "total": total, "segments": segments}

    # ============================= Admissions ================================

    @api.model
    def get_admissions(self, date_from, date_to):
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        prec_from, prec_to = self._periode_precedente(date_from, date_to)

        Lead = self.env["crm.lead"]
        equipes = self._equipes_admissions()
        base = [("team_id", "in", equipes.ids)]

        recues = base + self._entre(date_from, date_to)
        recues_prec = base + self._entre(prec_from, prec_to)

        nb_recues = Lead.search_count(recues)
        nb_gagnees = Lead.search_count([*recues, ("stage_id.is_won", "=", True)])
        nb_recues_prec = Lead.search_count(recues_prec)

        etape_pre_admis = self.env.ref(
            "his_crm_pipeline.stage_vente_pre_admis",
            raise_if_not_found=False,
        )
        limite_pre_admis = fields.Datetime.now() - timedelta(
            days=JOURS_PRE_ADMIS_SANS_ENCAISSEMENT,
        )

        tuiles = [
            self._tuile(
                "candidatures",
                _("Applications Received"),
                nb_recues,
                action=self._action(_("Applications Received"), "crm.lead", recues),
                precedent=nb_recues_prec,
                axe="candidatures",
                date_from=date_from,
                date_to=date_to,
            ),
            self._tuile(
                "inscriptions",
                _("Enrolments"),
                nb_gagnees,
                action=self._action(
                    _("Enrolments"),
                    "crm.lead",
                    [*recues, ("stage_id.is_won", "=", True)],
                ),
                precedent=Lead.search_count(
                    [*recues_prec, ("stage_id.is_won", "=", True)],
                ),
                axe="inscriptions",
                date_from=date_from,
                date_to=date_to,
            ),
            self._tuile(
                "conversion",
                _("Conversion Rate"),
                round(nb_gagnees / nb_recues * 100, 1) if nb_recues else 0,
                unite="%",
            ),
            self._tuile(
                "delai_affectation",
                _("Average Assignment Time"),
                self._moyenne(Lead, recues, "day_open"),
                unite=_("d"),
            ),
        ]

        if etape_pre_admis:
            attente = [*base, ("stage_id", "=", etape_pre_admis.id), ("date_last_stage_update", "<", limite_pre_admis)]
            tuiles.append(
                self._tuile(
                    "pre_admis_sans_encaissement",
                    _("Pre-admitted, Not Paid"),
                    Lead.search_count(attente),
                    action=self._action(
                        _("Pre-admitted, Not Paid"),
                        "crm.lead",
                        attente,
                    ),
                )
            )

        return {
            "titre": _("Admissions Cockpit"),
            "tiles": tuiles,
            "funnel": self._entonnoir(equipes, date_from, date_to),
            "donuts": self._admissions_donuts(equipes, date_from, date_to),
            "qualite": self._admissions_qualite(equipes),
            "attention": self._admissions_a_traiter(base, equipes),
            "explore": self._admissions_explorer(equipes),
        }

    def _admissions_donuts(self, equipes, date_from, date_to):
        """Les quatre repartitions du cockpit GoHighLevel.

        Elles repondent a quatre questions DIFFERENTES : quelle qualite de
        candidats arrive, ou en est le portefeuille, ou l'on perd, et d'ou
        vient l'acquisition. Une cinquieme ferait double emploi.

        active_test=False sur « Motifs de perte » SEULEMENT : une candidature
        perdue EST une fiche desactivee (crm/models/crm_lead.py:1122), donc
        sans cela ce donut serait vide en permanence — la seule chose plus
        inutile qu'un motif faux.

        Les trois autres restent sur les fiches actives, comme les tuiles.
        C'est une correction vue a l'ecran : « Acquisition par source »
        totalisait 13 quand « Candidatures recues » en annoncait 7, deux
        populations differentes cote a cote sur le meme ecran. Le lecteur ne
        peut pas deviner laquelle il regarde, et c'est exactement ce que la
        regle « un indicateur, une definition » existe pour empecher.
        """
        base = [("team_id", "in", equipes.ids), *self._entre(date_from, date_to)]

        return [
            self._donut(
                _("Applicants by Score"),
                "crm.lead",
                base,
                "score_academique",
            ),
            self._donut(
                _("Portfolio Status"),
                "crm.lead",
                base,
                "stage_id",
            ),
            self.with_context(active_test=False)._donut(
                _("Lost Reasons"),
                "crm.lead",
                [*base, ("lost_reason_id", "!=", False)],
                "lost_reason_id",
            ),
            self._donut(
                _("Acquisition by Source"),
                "crm.lead",
                base,
                "source_id",
            ),
        ]

    def _admissions_qualite(self, equipes):
        """Ce qui manque, et qu'on peut aller corriger.

        C'est la meilleure idee du cockpit GoHighLevel — son panneau « Fix your
        forecast data » — et la mecanique existe deja ici : _a_traiter rend un
        libelle, un compte, un apercu de cinq lignes et une action. C'est
        exactement le meme objet, donc quelques appels et rien de plus.

        C'est aussi ce qui rend les autres chiffres de l'ecran dignes de
        confiance : un tableau de bord qui ne dit pas ce qu'il ignore laisse
        croire qu'il sait tout.

        Pas de « date de cloture manquante » ici, contrairement a GHL ou les
        505 opportunites ouvertes en manquent toutes : signaler un champ que
        personne ne remplit et que rien n'utilise n'est pas de la qualite de
        donnee, c'est du bruit.
        """
        base = [("team_id", "in", equipes.ids), ("active", "=", True)]
        files = [
            self._a_traiter(
                _("No Phone or Email"),
                "crm.lead",
                [*base, ("phone", "=", False), ("email_from", "=", False)],
            ),
            self._a_traiter(
                _("No Acquisition Source"),
                "crm.lead",
                [*base, ("source_id", "=", False)],
            ),
        ]
        # specialite_id vient de his_admission, situe en aval : le pipeline
        # doit rester installable seul.
        if "specialite_id" in self.env["crm.lead"]._fields:
            files.insert(
                1,
                self._a_traiter(
                    _("No Target Specialty"),
                    "crm.lead",
                    [*base, ("specialite_id", "=", False)],
                ),
            )
        return files

    def _entonnoir(self, equipes, date_from, date_to):
        """Les etapes du parcours, effectif et taux de passage.

        Le taux se lit d'une etape a la suivante, pas depuis le debut : c'est
        celui-la qui designe l'endroit ou l'on perd les candidats.
        """
        Lead = self.env["crm.lead"]
        etapes = self.env["crm.stage"].search(
            [("team_ids", "in", equipes.ids)],
            order="sequence",
        )
        domaine_base = [("team_id", "in", equipes.ids), *self._entre(date_from, date_to)]

        marches = []
        precedent = None
        for etape in etapes:
            # Cumulatif : un candidat parvenu a l'etape 5 est passe par la 3.
            # Compter les seuls presents dans l'etape ferait un entonnoir qui
            # remonte, illisible.
            domaine = [*domaine_base, ("stage_id.sequence", ">=", etape.sequence)]
            compte = Lead.search_count(domaine)
            marches.append(
                {
                    "label": etape.name,
                    "count": compte,
                    "conversion": (round(compte / precedent * 100, 1) if precedent else None),
                    "action": self._action(etape.name, "crm.lead", domaine),
                }
            )
            precedent = compte
        return marches

    def _admissions_a_traiter(self, base, equipes):
        from .crm_lead import SLA_PREMIER_CONTACT_HEURES

        files = []
        etape_nouveau = self.env.ref(
            "his_crm_pipeline.stage_vente_nouveau",
            raise_if_not_found=False,
        )
        etape_pris = self.env.ref(
            "his_crm_pipeline.stage_vente_pris_en_charge",
            raise_if_not_found=False,
        )

        if etape_nouveau:
            files.append(
                self._a_traiter(
                    _("Unassigned Applications"),
                    "crm.lead",
                    [*base, ("stage_id", "=", etape_nouveau.id), ("user_id", "=", False)],
                )
            )
        if etape_pris:
            # Le MEME domaine que le cron de relance SLA. Deux definitions du
            # retard donneraient un tableau de bord qui contredit les activites
            # posees dans les fiches.
            limite = fields.Datetime.now() - timedelta(
                hours=SLA_PREMIER_CONTACT_HEURES,
            )
            files.append(
                self._a_traiter(
                    _("First Contact Overdue"),
                    "crm.lead",
                    [*base, ("stage_id", "=", etape_pris.id), ("date_last_stage_update", "<", limite)],
                )
            )

        # is_rotting est natif en Odoo 19 (mail.tracking.duration.mixin) : rien
        # a calculer, le serveur sait deja quel enregistrement dort.
        if "is_rotting" in self.env["crm.lead"]._fields:
            files.append(
                self._a_traiter(
                    _("Dormant Applications"),
                    "crm.lead",
                    [*base, ("is_rotting", "=", True)],
                )
            )
        return files

    def _admissions_explorer(self, equipes):
        base = [("team_id", "in", equipes.ids)]
        return [
            {
                "label": _("By Advisor and Stage"),
                "action": self._action(
                    _("By Advisor and Stage"),
                    "crm.lead",
                    base,
                    views=[[False, "pivot"], [False, "list"]],
                    context={"pivot_row_groupby": ["user_id"], "pivot_column_groupby": ["stage_id"]},
                ),
            },
            {
                "label": _("Applications Over Time"),
                "action": self._action(
                    _("Applications Over Time"),
                    "crm.lead",
                    base,
                    views=[[False, "graph"], [False, "list"]],
                    context={"graph_groupbys": ["create_date:month"], "graph_mode": "line"},
                ),
            },
        ]

    # ========================= Production Contenu ============================

    @api.model
    def get_contenu(self, date_from, date_to):
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        prec_from, prec_to = self._periode_precedente(date_from, date_to)

        Lead = self.env["crm.lead"]
        Livrable = self.env["his.content.deliverable"]
        equipe = self.env.ref(
            "his_crm_pipeline.crm_team_contenu",
            raise_if_not_found=False,
        )
        base = [("team_id", "=", equipe.id)] if equipe else []

        recues = base + self._entre(date_from, date_to)
        publiees = [*recues, ("stage_id.is_won", "=", True)]

        tuiles = [
            self._tuile(
                "demandes",
                _("Requests Received"),
                Lead.search_count(recues),
                action=self._action(_("Requests Received"), "crm.lead", recues),
                precedent=Lead.search_count(base + self._entre(prec_from, prec_to)),
            ),
            self._tuile(
                "publications",
                _("Published Content"),
                Lead.search_count(publiees),
                action=self._action(_("Published Content"), "crm.lead", publiees),
                precedent=Lead.search_count(
                    base + self._entre(prec_from, prec_to) + [("stage_id.is_won", "=", True)],
                ),
                axe="publications",
                date_from=date_from,
                date_to=date_to,
            ),
            self._tuile(
                "livrables_retard",
                _("Late Deliverables"),
                Livrable.search_count([("en_retard", "=", True)]),
                action=self._action(
                    _("Late Deliverables"),
                    "his.content.deliverable",
                    domain=[("en_retard", "=", True)],
                ),
            ),
        ]

        etape_approbation = self.env.ref(
            "his_crm_pipeline.stage_contenu_approbation",
            raise_if_not_found=False,
        )
        if etape_approbation:
            # La file du directeur lui-meme : ce qui attend SA signature.
            attente = [*base, ("stage_id", "=", etape_approbation.id)]
            tuiles.append(
                self._tuile(
                    "attente_approbation",
                    _("Awaiting Approval"),
                    Lead.search_count(attente),
                    action=self._action(
                        _("Awaiting Approval"),
                        "crm.lead",
                        attente,
                    ),
                )
            )

        return {
            "titre": _("Content Production Cockpit"),
            "tiles": tuiles,
            "funnel": [],
            "attention": self._contenu_a_traiter(base),
            "explore": [
                {
                    "label": _("Workload per Person"),
                    "action": self._action(
                        _("Workload per Person"),
                        "his.content.deliverable",
                        [],
                        views=[[False, "pivot"], [False, "list"]],
                        context={"pivot_row_groupby": ["assignee_id"], "pivot_column_groupby": ["statut"]},
                    ),
                },
                {
                    "label": _("Throughput per Brand"),
                    "action": self._action(
                        _("Throughput per Brand"),
                        "his.content.deliverable",
                        [],
                        views=[[False, "graph"], [False, "list"]],
                        context={"graph_groupbys": ["marque", "statut"]},
                    ),
                },
            ],
        }

    def _contenu_a_traiter(self, base):
        files = [
            self._a_traiter(
                _("Unassigned Deliverables"),
                "his.content.deliverable",
                domain=[("assignee_id", "=", False), ("statut", "!=", "approuve")],
            ),
            self._a_traiter(
                _("Late Deliverables"),
                "his.content.deliverable",
                domain=[("en_retard", "=", True)],
            ),
        ]
        etape_production = self.env.ref(
            "his_crm_pipeline.stage_contenu_production",
            raise_if_not_found=False,
        )
        if etape_production:
            limite = fields.Datetime.now() - timedelta(days=JOURS_CONTENU_BLOQUE)
            files.append(
                self._a_traiter(
                    _("Requests Stuck in Production"),
                    "crm.lead",
                    [*base, ("stage_id", "=", etape_production.id), ("date_last_stage_update", "<", limite)],
                )
            )
        return files

    # ============================== Direction ================================

    @api.model
    def get_direction(self, date_from, date_to):
        """Compose les tetes de gondole des trois cockpits.

        Une methode qui compose, pas un quatrieme jeu de definitions : un
        chiffre de la vue Direction et le meme chiffre dans son cockpit
        doivent etre le meme calcul, sans quoi le directeur arbitrera entre
        deux ecrans qui se contredisent.
        """
        cockpits = self._cockpits_direction(date_from, date_to)

        # Une liste de cles et non de modules : un cockpit en aval peut donc
        # faire remonter une tuile a la Direction sans que ce fichier ait a le
        # connaitre. « revenu_attendu » vient de his_admission ; sans cette
        # ligne la tuile existait mais n'etait affichee nulle part, le cockpit
        # Dossiers n'ayant aucune action a lui.
        retenues = {
            "candidatures",
            "inscriptions",
            "conversion",
            "dossiers_complets",
            "demandes",
            "publications",
            "revenu_attendu",
        }
        return {
            "titre": _("Management"),
            "tiles": [tuile for cockpit in cockpits for tuile in cockpit["tiles"] if tuile["cle"] in retenues],
            "funnel": cockpits[0]["funnel"] if cockpits else [],
            # Ce qui reclame un arbitrage, pas les files de chaque metier :
            # une file vide n'est pas une information, c'est une ligne de plus
            # a parcourir avant de trouver celle qui compte.
            "attention": [file for cockpit in cockpits for file in cockpit["attention"] if file["count"]],
            "explore": [lien for cockpit in cockpits for lien in cockpit["explore"]],
        }

    def _methodes_cockpits(self):
        """Les cockpits que la vue Direction agrege, par NOM DE METHODE.

        Un point d'extension et non une liste en dur : his_admission ajoute le
        sien en heritant de ce modele. Le module qui apporte un metier apporte
        aussi ses indicateurs — his_crm_pipeline ne connait pas his.engagement,
        qui vit dans un module situe en aval de lui.

        Des noms et non des resultats deja calcules : c'est ce qui permet a
        _cockpits_direction d'entourer chaque appel. La liste etait auparavant
        construite en appelant les methodes directement, et le premier metier
        qu'un role n'avait pas le droit de lire faisait tomber TOUTE la vue
        d'ensemble.
        """
        return ["get_admissions", "get_contenu"]

    def _cockpits_direction(self, date_from, date_to):
        """Les cockpits que cet utilisateur-la peut reellement lire.

        Un metier hors de sa portee DISPARAIT de l'ecran ; il ne le fait pas
        tomber, et ne lui montre rien non plus. C'est la meme regle que partout
        ailleurs dans ce fichier — un cockpit ne montre que ce que
        l'utilisateur peut voir — appliquee au moment de l'agregation.

        Le defaut etait reel et visible : des que his_admission etait installe
        aux cotes de ce module, ouvrir « Vue d'ensemble » avec un role
        Direction ou Production Contenu levait une erreur d'acces sur
        his.person, atteinte par le display_name des dossiers. Deux roles sur
        trois ne pouvaient pas ouvrir leur propre tableau de bord.

        On n'attrape PAS l'erreur en sudo() : cela afficherait a un demandeur
        de contenu les noms des candidats a l'admission. Se taire est la bonne
        reponse, la montrer quand meme serait une fuite.
        """
        cockpits = []
        for nom in self._methodes_cockpits():
            try:
                cockpits.append(getattr(self, nom)(date_from, date_to))
            except AccessError:
                continue
        return cockpits

    # =============================== Communs =================================

    @staticmethod
    def _entre(date_from, date_to):
        """create_date est un Datetime : la borne haute doit inclure le jour.

        Comparer a date_to seul le ramene a minuit, et tout ce qui a ete cree
        dans la journee tombe hors de la periode. Le symptome est un cockpit
        qui affiche zero pour « aujourd'hui » alors que le travail est la.
        """
        return [
            ("create_date", ">=", fields.Datetime.to_datetime(date_from)),
            (
                "create_date",
                "<",
                fields.Datetime.to_datetime(
                    date_to + timedelta(days=1),
                ),
            ),
        ]

    def _equipes_admissions(self):
        equipes = self.env["crm.team"]
        for xmlid in ("crm_team_ventes", "crm_team_orientation"):
            equipe = self.env.ref(
                "his_crm_pipeline.%s" % xmlid,
                raise_if_not_found=False,
            )
            if equipe:
                equipes |= equipe
        return equipes

    @staticmethod
    def _moyenne(Model, domain, champ):
        groupes = Model._read_group(domain, aggregates=["%s:avg" % champ])
        valeur = groupes[0][0] if groupes else None
        return round(valeur, 1) if valeur else 0
