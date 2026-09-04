# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""La grille tarifaire, pour le REPORTING et rien d'autre.

Ce modele ne facture pas, ne comptabilise pas et ne touche aucun modele
`account`. Il existe pour qu'un chiffre d'affaires attendu puisse etre DEDUIT
au lieu d'etre saisi.

C'est la lecon des donnees de GoHighLevel : 454 opportunites ouvertes sur 505
n'y portent aucun montant, parce qu'il fallait le taper a la main sur chaque
fiche. Un tarif se lit dans une grille — l'etablissement en a une — et un
chiffre deduit ne peut pas etre vide.

his.engagement garde ses booleens paye / non paye. Le jour ou les montants
comptent vraiment, c'est un chantier `account` ; ce fichier ne l'ouvre pas.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HisTarif(models.Model):
    _name = 'his.tarif'
    _description = "Tarif par specialite"
    _order = 'cycle, specialite_id'

    specialite_id = fields.Many2one(
        'his.specialite', string="Specialite", required=True,
        ondelete='cascade',
    )
    # Related et non recopie : le cycle vit sur la specialite, qui le porte
    # deja en champ requis. Le dupliquer donnerait deux verites.
    cycle = fields.Selection(
        related='specialite_id.cycle', string="Cycle", store=True, readonly=True,
    )
    frais_inscription = fields.Float(
        string="Frais d'inscription", digits=(12, 2),
        help="Les frais non remboursables. C'est leur encaissement qui gagne "
             "le lead.",
    )
    frais_scolarite = fields.Float(
        string="Frais de scolarite", digits=(12, 2),
    )
    active = fields.Boolean(default=True)

    @api.constrains('specialite_id', 'active')
    def _check_un_seul_tarif_actif(self):
        """Deux tarifs actifs pour la meme specialite donneraient deux revenus
        possibles, et le cockpit en choisirait un au hasard.

        Desactiver l'ancien plutot que le supprimer garde l'historique lisible :
        on saura ce qu'on facturait la rentree precedente.
        """
        for tarif in self:
            if not tarif.active:
                continue
            if self.search_count([
                ('specialite_id', '=', tarif.specialite_id.id),
                ('active', '=', True),
                ('id', '!=', tarif.id),
            ]):
                raise ValidationError(_(
                    "Un tarif actif existe deja pour « %(spec)s ». "
                    "Desactivez-le avant d'en creer un nouveau.",
                    spec=tarif.specialite_id.display_name,
                ))

    @api.model
    def _montant_pour(self, specialite):
        """Les frais d'inscription de cette specialite, ou 0.

        Zero et non une exception : une specialite non tarifee est une lacune
        de la grille, signalee par la file « Qualite des donnees ». Elle ne doit
        pas faire tomber le cockpit du directeur.
        """
        if not specialite:
            return 0.0
        tarif = self.search([('specialite_id', '=', specialite.id)], limit=1)
        return tarif.frais_inscription or 0.0
