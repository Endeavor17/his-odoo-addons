# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HrEmployeePublic(models.Model):
    """Le profil public de l'employe, ce qu'un utilisateur sans droits RH lit.

    hr.employee.public est une vue SQL : son init() selectionne chaque champ
    stocke declare ici depuis hr_employee (`_get_fields`), et la colonne
    matricule_institutionnel y existe deja - c'est un related stocke. Meme
    patron que work_email dans le coeur. La vue est recreee a chaque -u.

    Tout champ stocke ajoute a hr.employee doit, soit etre declare ici, soit
    porter un groups= : test_employee_public_profile le verifie pour tous les
    modules installes.
    """

    _inherit = "hr.employee.public"

    matricule_institutionnel = fields.Char(string="Matricule institutionnel", readonly=True)
