# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models, tools

# Etape a partir de laquelle un candidat entre dans le referentiel. « Select »
# est le moment ou l'institution se prononce sur lui ; avant, c'est une ligne
# de formulaire parmi 249. Parametre et non constante : le choix peut bouger
# sans modifier le code.
PARAM_ETAPE_DECLENCHEUSE = "campus_identity.trigger_state"
ETAPE_DECLENCHEUSE_DEFAUT = "invited"

TYPES_RAPPROCHABLES = ("candidat", "enseignant", "employe")


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    his_person_id = fields.Many2one(
        "his.person",
        string="Fiche personne",
        readonly=True,
        copy=False,
        index="btree_not_null",
        help="Fiche du referentiel Identite rattachee a cette candidature.",
    )
    his_person_candidate_id = fields.Many2one(
        "his.person",
        string="Fiche proposee",
        readonly=True,
        copy=False,
        help="Meilleure correspondance trouvee dans le referentiel. Tant "
        "qu'elle n'est pas confirmee par un humain, RIEN n'est rattache.",
    )
    his_person_match_score = fields.Float(
        string="Score de rapprochement",
        digits=(3, 2),
        readonly=True,
        copy=False,
    )

    # --- Protection de l'identite -------------------------------------------

    def _inverse_partner_email(self):
        """N'ecrit jamais par-dessus le contact d'une fiche personne.

        Le coeur retrouve le contact par email a la creation de la candidature,
        puis y recopie le nom et le telephone saisis dans le formulaire. Un
        employe qui postule avec son adresse verrait donc sa fiche contact
        renommee par ce qu'il a tape sur Campus+ — avant meme que le pont ne
        s'execute. Ces candidatures gardent leur propre email et telephone
        (champs stockes) ; le contact, lui, appartient au referentiel.
        """
        protegees = self.browse()
        for applicant in self:
            partner = applicant.partner_id
            email = tools.email_normalize(applicant.email_from or "")
            if not partner and email:
                partner = applicant._partner_find_from_emails_single(
                    [applicant.email_from],
                    no_create=True,
                )
            if partner and partner.sudo().his_person_ids:
                applicant.partner_id = partner
                protegees |= applicant
        return super(HrApplicant, self - protegees)._inverse_partner_email()

    # --- Declencheur ---------------------------------------------------------

    def _his_etape_atteinte(self):
        """« PARVENU a l'etape », pas « pose exactement dessus ».

        Meme lecon que le pont CRM : une egalite stricte laisse passer sans
        fiche tout candidat qui saute l'etape. L'ordre est celui de la
        selection, qui est l'ordre du parcours.
        """
        self.ensure_one()
        etapes = [key for key, _label in self._fields["campus_hiring_state"].selection]
        declencheuse = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                PARAM_ETAPE_DECLENCHEUSE,
                ETAPE_DECLENCHEUSE_DEFAUT,
            )
        )
        if declencheuse not in etapes or self.campus_hiring_state not in etapes:
            return False
        return etapes.index(self.campus_hiring_state) >= etapes.index(declencheuse)

    @api.model_create_multi
    def create(self, vals_list):
        applicants = super().create(vals_list)
        applicants._his_creer_ou_rapprocher_personne()
        return applicants

    def write(self, vals):
        res = super().write(vals)
        if "campus_hiring_state" in vals:
            self._his_creer_ou_rapprocher_personne()
        return res

    def _his_creer_ou_rapprocher_personne(self):
        """Rapproche ou cree la fiche personne des candidatures parvenues a l'etape.

        Idempotent : fiche deja posee ou proposition en attente, rien n'est
        refait. Le contexte campus_identity_force saute le controle d'etape :
        InSite s'en sert quand un humain a reconnu ce candidat.
        """
        force = self.env.context.get("campus_identity_force")
        Person = self.env["his.person"].sudo()
        for applicant in self:
            if applicant.his_person_id or applicant.his_person_candidate_id:
                continue
            if not force and not applicant._his_etape_atteinte():
                continue

            # Deterministe : le contact porte deja une fiche (le coeur l'a
            # retrouve par email a la creation de la candidature).
            existante = applicant.partner_id.sudo().his_person_ids[:1]
            if existante:
                applicant._his_lier(existante)
                continue

            match = Person._find_or_flag_match(
                applicant._his_candidate_vals(),
                types=TYPES_RAPPROCHABLES,
            )
            if match["conflict"]:
                applicant._his_signaler(match["conflict"])
                continue
            if match["method"] == "probabilistic":
                applicant.write(
                    {
                        "his_person_candidate_id": match["person"].id,
                        "his_person_match_score": match["score"],
                    }
                )
                applicant._his_signaler(
                    _(
                        "Correspondance probable (%(score)d%%) avec « %(fiche)s » : "
                        "a confirmer ou refuser depuis la candidature. Aucune fiche "
                        "n'a ete rattachee.",
                        score=round(match["score"] * 100),
                        fiche=match["person"].display_name,
                    )
                )
                continue
            if match["person"]:
                applicant._his_lier(match["person"])
            else:
                applicant.his_person_id = applicant._his_creer_personne(match["method"])

    # --- Construction et rattachement --------------------------------------

    def _his_candidate_vals(self):
        """email_personnel : un candidat externe n'a aucun compte dans l'institution."""
        self.ensure_one()
        return {
            "name": self.partner_name or self.partner_id.name,
            "nom_arabe": self.campus_name_ar,
            "email_personnel": self.email_from,
            "phone": self.partner_phone,
            "source_system": "campus_plus",
            "external_ref": str(self.id),
        }

    def _his_creer_personne(self, method):
        self.ensure_one()
        vals = dict(self._his_candidate_vals(), type_personne="candidat", match_method=method)
        # Reprendre le contact de la candidature : sans cela la delegation en
        # cree un second, et l'humain a deux fiches contact.
        partner = self.partner_id
        if partner and not partner.sudo().his_person_ids:
            vals["partner_id"] = partner.id
        person = self.env["his.person"].sudo().create(vals)
        person.message_post(
            body=_(
                "Fiche creee depuis la candidature Campus+ « %(applicant)s ».",
                applicant=self.display_name,
            )
        )
        return person

    def _his_lier(self, person):
        """Rattache sans jamais modifier la fiche existante.

        email_from et partner_phone sont calcules depuis partner_id : repointer
        le contact vers celui de la fiche changerait l'adresse de la
        candidature. On ne le fait donc que si les deux adresses sont la meme ;
        sinon la candidature garde son contact et seul le lien est pose.
        """
        self.ensure_one()
        vals = {"his_person_id": person.id}
        partner = person.sudo().partner_id
        if self.partner_id != partner:
            if self.partner_id.email_normalized and self.partner_id.email_normalized == partner.email_normalized:
                vals["partner_id"] = partner.id
            else:
                self.message_post(
                    body=_(
                        "Rattachee a la fiche « %(fiche)s ». Adresses differentes : la "
                        "candidature garde son propre contact.",
                        fiche=person.display_name,
                    )
                )
        self.write(vals)

    def _his_signaler(self, message):
        self.ensure_one()
        self.message_post(body=message)
        if self.user_id:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                summary="Rapprochement Identite a arbitrer",
                note=message,
                user_id=self.user_id.id,
            )

    # --- Arbitrage humain ----------------------------------------------------

    def action_confirm_person_match(self):
        for applicant in self:
            person = applicant.his_person_candidate_id
            if not person:
                continue
            person.sudo().write(
                {
                    "match_method": "probabilistic",
                    "matched_by": self.env.user.id,
                    "matched_on": fields.Datetime.now(),
                }
            )
            applicant.his_person_candidate_id = False
            applicant._his_lier(person)
            applicant.message_post(
                body=_(
                    "Rapprochement (%(score)d%%) confirme par %(user)s.",
                    score=round(applicant.his_person_match_score * 100),
                    user=self.env.user.display_name,
                )
            )

    def action_reject_person_match(self):
        for applicant in self:
            if not applicant.his_person_candidate_id:
                continue
            applicant.his_person_candidate_id = False
            applicant.his_person_id = applicant._his_creer_personne("new")
            applicant.message_post(
                body=_(
                    "Rapprochement refuse par %(user)s : fiche distincte creee.",
                    user=self.env.user.display_name,
                )
            )
