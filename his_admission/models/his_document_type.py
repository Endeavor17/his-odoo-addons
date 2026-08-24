# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models

from .his_specialite import CYCLE

# Filieres du baccalaureat, telles que le classeur les nomme. Selection et non
# modele : sept valeurs fixees par le systeme educatif national, pas par nous.
BAC_FILIERE = [
    ('se', "SE - Sciences experimentales"),
    ('tm', "TM - Technique mathematique"),
    ('ma', "MA - Mathematiques"),
    ('ge', "GE - Gestion et economie"),
    ('philo', "Philo - Lettres et philosophie"),
    ('langue', "Langue - Lettres et langues etrangeres"),
    ('equivalence', "Equivalence - Diplome etranger"),
]

TYPE_INSCRIPTION = [
    ('nouveau', "Nouvelle inscription"),
    ('reinscription', "Reinscription"),
]


class HisDocumentType(models.Model):
    """Piece attendue au dossier d'admission, et a quelles conditions.

    Le classeur portait une colonne par piece — vingt et une, dont trois
    doublons (le releve BAC, la photo et le releve universitaire y figuraient
    deux fois). Surtout, il ne savait pas dire QUELLES pieces s'appliquent :
    un dossier en equivalence n'a pas de releve BAC mais un certificat
    d'equivalence, et la case releve BAC restait vide sans que rien ne
    distingue « pas concerne » de « pas encore fourni ».

    Ici l'applicabilite est une donnee. Ouvrir ou fermer une piece est de la
    configuration, pas une migration de schema.
    """
    _name = 'his.document.type'
    _description = "Type de piece du dossier d'admission"
    _order = 'sequence, name'

    name = fields.Char(string="Piece", required=True, translate=True)
    name_arabe = fields.Char(string="Piece (arabe)")
    code = fields.Char(string="Code", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    obligatoire = fields.Boolean(
        string="Obligatoire", default=True,
        help="Une piece obligatoire manquante empeche le passage a l'etat "
             "« Inscrit ». Une piece facultative est suivie sans bloquer.",
    )

    # Trois filtres d'applicabilite, tous optionnels : vide = s'applique a tout.
    # Trois suffisent a couvrir les cas du classeur ; en ajouter un quatrième
    # « au cas ou » serait de la flexibilite morte.
    cycle = fields.Selection(
        CYCLE, string="Cycle concerne",
        help="Vide : toutes les pieces s'appliquent aux deux cycles.",
    )
    type_inscription = fields.Selection(
        TYPE_INSCRIPTION, string="Type d'inscription concerne",
        help="Vide : s'applique aux nouvelles inscriptions comme aux reinscriptions.",
    )
    bac_filiere = fields.Selection(
        BAC_FILIERE, string="Filiere BAC concernee",
        help="Vide : s'applique quelle que soit la filiere. Sert au certificat "
             "d'equivalence, qui ne concerne que les dossiers en equivalence.",
    )

    _code_unique = models.Constraint(
        'unique(code)', "Ce code de piece est deja utilise.",
    )

    def _applicable(self, cycle, type_inscription, bac_filiere):
        """Les pieces de self qui concernent un dossier ayant ces caracteristiques.

        Un critere vide sur la piece signifie « peu importe ». Un critere vide
        sur le DOSSIER ne retient que les pieces sans exigence sur ce critere :
        tant que la filiere BAC n'est pas saisie, on ne reclame pas un
        certificat d'equivalence dont on ignore s'il s'applique.
        """
        return self.filtered(lambda d: (
            (not d.cycle or d.cycle == cycle)
            and (not d.type_inscription or d.type_inscription == type_inscription)
            and (not d.bac_filiere or d.bac_filiere == bac_filiere)
        ))
