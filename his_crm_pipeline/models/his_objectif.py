# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Les cibles chiffrees de la Direction.

Un tableau de bord sans objectif n'affiche que des compteurs : « 142
candidatures » ne dit pas si la campagne va bien. Avec une cible, le meme
chiffre devient « 142 sur 300, il reste 39 jours, il faut 4,1 par jour » — et
la question « que faire » a une reponse.

Un objectif est de la CONFIGURATION, saisie par la Direction, pas une constante
de code : les cibles changent chaque rentree, et personne ne devrait attendre
une livraison pour les corriger.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Ce qu'on sait compter. Chaque axe est mis en oeuvre par his.dashboard : en
# ajouter un ici sans l'y traiter donnerait un objectif qu'aucune tuile ne
# reprend, donc un chiffre saisi pour rien.
AXE_OBJECTIF = [
    ('candidatures', "Candidatures recues"),
    ('inscriptions', "Inscriptions (frais encaisses)"),
    ('publications', "Contenus publies"),
]


class HisObjectif(models.Model):
    _name = 'his.objectif'
    _description = "Objectif chiffre"
    _order = 'date_debut desc, id desc'

    name = fields.Char(string="Intitule", required=True)
    axe = fields.Selection(AXE_OBJECTIF, string="Ce qu'on compte", required=True)
    valeur_cible = fields.Float(string="Cible", required=True)

    date_debut = fields.Date(string="Du", required=True)
    date_fin = fields.Date(string="Au", required=True)

    # Filtres facultatifs. Vides, l'objectif porte sur tout le groupe — c'est le
    # cas courant. Renseignes, il ne s'applique qu'au perimetre nomme, ce qui
    # permet une cible par marque sans multiplier les axes.
    marque = fields.Selection(
        selection=[('his', "HIS"), ('htc', "HTC"), ('ira', "IRA")],
        string="Marque",
    )
    team_id = fields.Many2one('crm.team', string="Equipe")
    active = fields.Boolean(string="Actif", default=True)

    @api.constrains('date_debut', 'date_fin')
    def _check_periode(self):
        for objectif in self:
            if objectif.date_fin < objectif.date_debut:
                raise ValidationError(_(
                    "« %(nom)s » se termine avant de commencer.",
                    nom=objectif.name,
                ))

    @api.constrains('valeur_cible')
    def _check_cible(self):
        for objectif in self:
            if objectif.valeur_cible <= 0:
                raise ValidationError(_(
                    "Une cible de zero ou moins ne mesure rien."
                ))

    @api.model
    def _pour(self, axe, date_from, date_to, marque=None, team=None):
        """L'objectif qui couvre cette periode et ce perimetre, s'il existe.

        Le chevauchement suffit — on ne demande pas que les bornes coincident.
        Un directeur qui regarde « ce mois-ci » veut voir sa cible annuelle
        s'appliquer, pas disparaitre parce que les dates ne tombent pas juste.

        Le plus recent gagne quand plusieurs conviennent : une cible revisee en
        cours d'annee doit remplacer celle qu'elle corrige.
        """
        domaine = [
            ('axe', '=', axe),
            ('date_debut', '<=', date_to),
            ('date_fin', '>=', date_from),
        ]
        domaine += [('marque', '=', marque)] if marque else [('marque', '=', False)]
        domaine += [('team_id', '=', team)] if team else [('team_id', '=', False)]
        return self.search(domaine, limit=1)
