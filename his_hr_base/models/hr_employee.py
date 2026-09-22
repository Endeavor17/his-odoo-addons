# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    person_id = fields.Many2one(
        "his.person",
        string="Fiche personne",
        # restrict : supprimer une fiche personne encore rattachee a un employe
        # detacherait un matricule deja distribue de son porteur.
        ondelete="restrict",
        copy=False,
        index=True,
        # Regle du coeur (tete de hr/models/hr_employee.py) : un champ present
        # sur hr.employee et absent de hr.employee.public porte
        # groups="hr.group_hr_user". Sans lui, le prefetch le charge pour un
        # utilisateur sans droits RH, _check_private_fields refuse la lecture
        # ENTIERE, et le moindre acces a un employe echoue - une caisse avec
        # pos_hr restait blanche pour tout caissier non RH. La vue le masquait
        # deja a ce groupe ; c'est desormais l'ORM qui le fait.
        groups="hr.group_hr_user",
    )
    # Miroir, pas source. Le nom du champ est conserve a l'identique : la vue
    # hr_employee_views.xml de maintenance_university le reference par ce nom
    # et continue de fonctionner sans modification.
    #
    # PUBLIC, et declare comme tel sur hr.employee.public
    # (hr_employee_public.py) : le matricule est imprime sur le badge, tout
    # utilisateur interne peut le lire, comme le nom ou le poste.
    matricule_institutionnel = fields.Char(
        string="Matricule institutionnel",
        related="person_id.matricule_institutionnel",
        store=True,
        readonly=True,
        index=True,
    )
    # Forme affichee, sans la cle de controle : c'est ce que voit l'equipe RH.
    # La valeur complete reste dans matricule_institutionnel, pour la carte
    # RFID et la caisse. Cf. his_person_core pour le raisonnement.
    matricule_affiche = fields.Char(
        string="Matricule",
        related="person_id.matricule_affiche",
        readonly=True,
    )
    # Une seule carte physique par personne, employe ou etudiant : pointage,
    # acces aux locaux et repas. Le « Badge ID » natif d'Odoo DEVIENT donc le
    # badge RFID, au lieu d'etre un second numero a tenir en phase.
    #
    # related stocke plutot qu'une synchronisation ecrite a la main : deux
    # champs qu'on recopie l'un dans l'autre finissent toujours par diverger, et
    # ici diverger voudrait dire une carte reconnue a la caisse mais refusee au
    # pointage. readonly=False : la saisie reste possible des deux cotes, elle
    # atterrit toujours sur la fiche personne.
    #
    # Consequence assumee : on ne peut plus donner a un employe un Badge ID
    # different de son badge RFID. C'est le but.
    #
    # hr_attendance lit ce champ pour son lecteur de badge, et pos_hr pour
    # connecter un caissier. La contrainte native reste active
    # (alphanumerique, 18 caracteres max) : un numero non conforme echoue
    # bruyamment au lieu d'etre ignore.
    barcode = fields.Char(
        related="person_id.numero_carte",
        store=True,
        readonly=False,
        help="Badge RFID de la personne. Meme carte physique pour le pointage, "
        "l'acces aux locaux et les repas. Se saisit sur la fiche personne "
        "ou ici, indifféremment.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        # super() D'ABORD, contrairement a la version precedente de ce fichier.
        # hr.employee.create() ne cree le work_contact_id qu'a sa DERNIERE
        # ligne (`employees.filtered(...)._create_work_contacts()`), donc avant
        # super() ce partenaire n'existe pas encore. Creer la fiche personne
        # avant, c'est garantir un SECOND partenaire pour le meme humain —
        # exactement le probleme que la delegation existe pour eviter.
        employees = super().create(vals_list)
        # Pas de sudo() pour lire ou ecrire person_id (reserve aux RH) : le
        # coeur exige deja les droits RH pour creer un employe - son create()
        # lit version_ids, lui-meme groups="hr.group_hr_user". Le seul
        # createur sans ces droits, l'assistant de maintenance_university,
        # passe deja par sudo().
        for employee in employees:
            if not employee.person_id:
                employee.person_id = employee._create_his_person()
        return employees

    def _create_his_person(self):
        """Cree la fiche personne d'un employe, en reutilisant son partenaire."""
        self.ensure_one()
        partner = self.sudo().work_contact_id

        if partner:
            # res.partner.employee_ids est un One2many : un meme contact
            # professionnel peut servir plusieurs employes, et le coeur d'Odoo
            # le prevoit (`if len(...employee_ids) <= 1`). Un ancrage
            # d'identite, lui, doit rester un-par-humain : on signale, on ne
            # partage pas en silence.
            others = partner.sudo().employee_ids - self
            if others:
                raise ValidationError(
                    _(
                        "Le contact « %(contact)s » sert deja %(count)s autre(s) employe(s) "
                        "(%(names)s). Un matricule identifie une seule personne : rattachez "
                        "d'abord chaque employe a son propre contact.",
                        contact=partner.display_name,
                        count=len(others),
                        names=", ".join(others.mapped("name")),
                    )
                )
            existing = (
                self.env["his.person"]
                .sudo()
                .with_context(
                    active_test=False,
                )
                .search([("partner_id", "=", partner.id)], limit=1)
            )
            if existing:
                raise ValidationError(
                    _(
                        "Le contact « %(contact)s » porte deja la fiche personne %(matricule)s. "
                        "Deux fiches sur un meme contact rendraient le matricule ambigu.",
                        contact=partner.display_name,
                        matricule=existing.matricule_institutionnel,
                    )
                )

        # L'annee du matricule vient de la date d'entree, pas de la date de
        # creation de la fiche : une embauche saisie en retard ou signee pour
        # la rentree doit porter son annee reelle. Comportement repris a
        # l'identique du code de maintenance_university remplace ici.
        # date_start_working appartient a maintenance_university : absent si ce
        # module n'est pas installe.
        vals = {
            "type_personne": "employe",
            "source_system": "odoo_hr",
            "match_method": "new",
            "matricule_sequence_date": self.date_start_working if "date_start_working" in self._fields else False,
        }
        if partner:
            # Reutilisation : la delegation se rattache au partenaire existant
            # au lieu d'en creer un second.
            vals["partner_id"] = partner.id
        else:
            # Aucun partenaire (contexte salary_simulation, ou cas limite) :
            # la delegation en cree un, ce qui est correct ici. Le cas a eviter
            # est d'en creer un second quand il en existe deja un.
            vals["name"] = self.name or "Employe"
        return self.env["his.person"].sudo().create(vals)
