# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models

from .his_specialite import CYCLE

# Filieres du baccalaureat, telles que le classeur les nomme. Selection et non
# modele : sept valeurs fixees par le systeme educatif national, pas par nous.
BAC_FILIERE = [
    ("se", "SE - Experimental Sciences"),
    ("tm", "TM - Mathematical Techniques"),
    ("ma", "MA - Mathematics"),
    ("ge", "GE - Management and Economics"),
    ("philo", "Philo - Literature and Philosophy"),
    ("langue", "Languages - Literature and Foreign Languages"),
    ("equivalence", "Equivalence - Foreign Diploma"),
]

TYPE_INSCRIPTION = [
    ("nouveau", "New Enrolment"),
    ("reinscription", "Re-enrolment"),
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

    _name = "his.document.type"
    _description = "Admission File Document Type"
    _order = "sequence, name"

    name = fields.Char(string="Document", required=True, translate=True)
    name_arabe = fields.Char(string="Document (Arabic)")
    code = fields.Char(string="Code", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    obligatoire = fields.Boolean(
        string="Required",
        default=True,
        help='A missing required document prevents moving to the "Enrolled" state. An '
        "optional document is tracked without blocking.",
    )

    # Trois filtres d'applicabilite, tous optionnels : vide = s'applique a tout.
    # Trois suffisent a couvrir les cas du classeur ; en ajouter un quatrième
    # « au cas ou » serait de la flexibilite morte.
    cycle = fields.Selection(
        CYCLE,
        string="Applicable Cycle",
        help="Empty: all documents apply to both cycles.",
    )
    type_inscription = fields.Selection(
        TYPE_INSCRIPTION,
        string="Applicable Enrolment Type",
        help="Empty: applies to new enrolments and re-enrolments alike.",
    )
    bac_filiere = fields.Selection(
        BAC_FILIERE,
        string="Applicable Baccalaureate Stream",
        help="Empty: applies whatever the stream. Used for the equivalence "
        "certificate, which only concerns equivalence files.",
    )

    _code_unique = models.Constraint(
        "unique(code)",
        "This document code is already used.",
    )

    def _applicable(self, cycle, type_inscription, bac_filiere):
        """Les pieces de self qui concernent un dossier ayant ces caracteristiques.

        Un critere vide sur la piece signifie « peu importe ». Un critere vide
        sur le DOSSIER ne retient que les pieces sans exigence sur ce critere :
        tant que la filiere BAC n'est pas saisie, on ne reclame pas un
        certificat d'equivalence dont on ignore s'il s'applique.
        """
        return self.filtered(
            lambda d: (
                (not d.cycle or d.cycle == cycle)
                and (not d.type_inscription or d.type_inscription == type_inscription)
                and (not d.bac_filiere or d.bac_filiere == bac_filiere)
            )
        )
