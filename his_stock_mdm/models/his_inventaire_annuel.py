# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class HisInventaireAnnuel(models.Model):
    _name = 'his.inventaire.annuel'
    _description = "Inventaire physique annuel"
    _order = 'name desc'

    _name_company_uniq = models.Constraint(
        'unique(name, company_id)',
        "Un inventaire annuel de ce nom existe déjà pour cette société.",
    )

    # Pas d'etat 'brouillon' : sans lien stocke entre stock.quant et une
    # campagne, une ouverture separee de la creation n'apporterait rien.
    # create_uid/create_date natifs repondent deja a "ouvert par, quand".
    name = fields.Char(required=True, default="Nouvel inventaire")
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection(
        [('en_cours', "En cours"), ('cloture', "Clôturé")],
        default='en_cours', required=True)
    date_cloture = fields.Date(readonly=True)
    cloture_par_id = fields.Many2one('res.users', string="Clôturé par", readonly=True)
    note = fields.Text()

    # --- Cloture : reservee au Manager, verrouillee une fois faite ----------

    def action_cloturer(self):
        if not (self.env.su or self.env.user.has_group('stock.group_stock_manager')):
            raise AccessError("Seul un Manager Stock peut clôturer un inventaire annuel.")
        self.write({
            'state': 'cloture',
            'date_cloture': fields.Date.context_today(self),
            'cloture_par_id': self.env.user.id,
        })

    # --- Garde-fou serveur : declenche quel que soit le chemin d'ecriture ---
    #
    # Meme discipline que his_admission._check_dossier_complet_avant_inscription :
    # la regle vit ici, pas dupliquee dans action_cloturer(), pour rester
    # valable face a un import ou une ecriture ORM directe.
    @api.constrains('state')
    def _check_cloture_sans_comptage_en_attente(self):
        for inventaire in self:
            if inventaire.state != 'cloture':
                continue
            pending = self.env['stock.quant'].search_count([
                ('company_id', '=', inventaire.company_id.id),
                ('location_id.usage', '=', 'internal'),
                ('inventory_quantity_set', '=', True),
            ])
            if pending:
                raise ValidationError(
                    "Impossible de clôturer « %s » : %d comptage(s) restent "
                    "saisis mais non appliqués aux livres. Appliquez-les "
                    "d'abord (Inventaire ▸ Ajustements)." % (inventaire.name, pending))

    # --- Immutabilite apres cloture ------------------------------------------

    def write(self, vals):
        if not self.env.su:
            for inventaire in self:
                if inventaire.state == 'cloture':
                    raise AccessError(
                        "L'inventaire « %s » est clôturé : il ne peut plus être "
                        "modifié." % inventaire.name)
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            for inventaire in self:
                if inventaire.state == 'cloture':
                    raise AccessError(
                        "L'inventaire « %s » est clôturé : il ne peut pas être "
                        "supprimé." % inventaire.name)
        return super().unlink()
