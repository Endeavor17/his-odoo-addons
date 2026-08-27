# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command


class UniversityBesoinAchat(models.Model):
    _name = 'university.besoin.achat'
    _description = "Besoin d'Achat"
    _order = 'id desc'

    name = fields.Char(
        string="Référence d'achat", required=True, copy=False,
        readonly=True, index=True, default=lambda self: _('New'))

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('offer_selection', 'Sélection des offres'),
        ('done', 'Fait'),
    ], string="Statut", default='draft', required=True, copy=False, index=True)

    condition = fields.Selection([
        ('revente', 'Achat Pour Revente'),
        ('stock', 'Achat Pour Stock'),
    ], string="Condition", default='stock', required=True)

    demandeur_id = fields.Many2one(
        'res.users', string="Demandeur", required=True,
        default=lambda self: self.env.user)

    structure = fields.Char(string="Structure")

    type_besoin = fields.Selection([
        ('bon_commande', 'Bon de commande'),
        ('cash', 'Cash'),
        ('contract', 'Contract'),
        ('urgent', 'Urgent (archivé)'),
    ], string="Type de Besoin", default='bon_commande', required=True)

    date_limite_reponse = fields.Date(string="Date Limite de Réponse")
    date_livraison = fields.Date(string="Date de livraison")

    fournisseur_ids = fields.Many2many(
        'res.partner', 'university_besoin_achat_fournisseur_rel',
        'besoin_achat_id', 'partner_id',
        string="Fournisseurs sollicités par",
        domain="[('supplier_rank', '>', 0)]")

    client_id = fields.Many2one('res.partner', string="Service")

    line_ids = fields.One2many(
        'university.besoin.achat.line', 'besoin_achat_id', string="Produits")

    company_id = fields.Many2one(
        'res.company', string="Société",
        default=lambda self: self.env.company)

    purchase_order_ids = fields.One2many(
        'purchase.order', 'besoin_achat_id', string="Demandes de prix / Commandes")
    purchase_order_count = fields.Integer(compute='_compute_purchase_order_count')

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_order_ids)

    @api.constrains('date_limite_reponse', 'state')
    def _check_date_limite_reponse(self):
        for rec in self:
            if rec.state != 'draft' and not rec.date_limite_reponse:
                raise ValidationError(_(
                    "La Date Limite de Réponse est obligatoire pour confirmer un Besoin d'achat."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'university.besoin.achat') or _('New')
        records = super().create(vals_list)
        if not self.env.context.get('skip_pack_sync'):
            records._sync_pack_lines()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'line_ids' in vals and not self.env.context.get('skip_pack_sync'):
            self._sync_pack_lines()
        return res

    def _get_pack_sync_commands(self):
        """Return the Command list needed to align generated pack-component
        lines with the pack summary lines currently in line_ids.
        Existing generated lines (identified by pack_origin_id) are updated
        in place, never duplicated."""
        self.ensure_one()
        commands = []
        all_lines = self.line_ids
        pack_ids = set(all_lines.filtered('is_pack_line').ids)

        # Drop components whose parent pack line was removed by the user.
        for line in all_lines:
            if line.pack_origin_id and line.pack_origin_id.id not in pack_ids:
                commands.append(Command.delete(line.id))

        for pack_line in all_lines.filtered('is_pack_line'):
            existing = all_lines.filtered(lambda l: l.pack_origin_id.id == pack_line.id)
            qty_pack = pack_line.product_uom_qty or 0.0
            pack_components = (
                pack_line.product_id.product_tmpl_id.pack_line_ids if qty_pack > 0
                else self.env['product.pack.line'])
            desired = {
                pl.product_id.id: (pl.product_qty * qty_pack, pl.product_uom_id.id)
                for pl in pack_components
            }
            existing_by_product = {l.product_id.id: l for l in existing}

            for product_id, (qty, uom_id) in desired.items():
                comp = existing_by_product.get(product_id)
                if comp:
                    if comp.product_uom_qty != qty or comp.product_uom_id.id != uom_id:
                        commands.append(Command.update(comp.id, {
                            'product_uom_qty': qty,
                            'product_uom_id': uom_id,
                        }))
                else:
                    commands.append(Command.create({
                        'product_id': product_id,
                        'description': self.env['product.product'].browse(product_id).name,
                        'product_uom_qty': qty,
                        'product_uom_id': uom_id,
                        'pack_origin_id': pack_line.id,
                    }))
            for product_id, comp in existing_by_product.items():
                if product_id not in desired:
                    commands.append(Command.delete(comp.id))
        return commands

    def _sync_pack_lines(self):
        for rec in self:
            commands = rec._get_pack_sync_commands()
            if commands:
                rec.with_context(skip_pack_sync=True).write({'line_ids': commands})

    @api.onchange('line_ids')
    def _onchange_line_ids_sync_packs(self):
        commands = self._get_pack_sync_commands()
        if commands:
            self.line_ids = commands

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_select_offers(self):
        self.write({'state': 'offer_selection'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_create_rfq(self):
        self.ensure_one()
        if not self.fournisseur_ids:
            raise UserError(_("Veuillez renseigner au moins un fournisseur sollicité."))
        if not self.line_ids:
            raise UserError(_("Veuillez ajouter au moins un produit."))
        # Un Pack est une structure de regroupement : seuls ses composants
        # (déjà décomposés dans line_ids) représentent un achat réel.
        purchase_lines = self.line_ids.filtered(lambda l: not l.is_pack_line)
        if not purchase_lines:
            raise UserError(_("Aucun produit achetable à envoyer en demande de prix."))
        order = self.env['purchase.order'].create({
            'partner_id': self.fournisseur_ids[0].id,
            'origin': self.name,
            'besoin_achat_id': self.id,
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'name': line.description or line.product_id.name,
                'product_qty': line.product_uom_qty,
                'product_uom_id': line.product_uom_id.id or line.product_id.uom_id.id,
                'date_planned': fields.Datetime.to_datetime(self.date_livraison) or fields.Datetime.now(),
            }) for line in purchase_lines],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': order.id,
        }

    def action_view_purchase_orders(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _("Demandes de prix / Commandes"),
            'res_model': 'purchase.order',
            'domain': [('besoin_achat_id', '=', self.id)],
            'view_mode': 'list,form',
        }
        if self.purchase_order_count == 1:
            action.update({'view_mode': 'form', 'res_id': self.purchase_order_ids.id})
        return action


class UniversityBesoinAchatLine(models.Model):
    _name = 'university.besoin.achat.line'
    _description = "Ligne de Besoin d'Achat"
    _order = 'sequence, id'

    besoin_achat_id = fields.Many2one(
        'university.besoin.achat', string="Besoin d'Achat",
        required=True, ondelete='cascade')

    sequence = fields.Integer(string="Séquence", default=10)

    product_id = fields.Many2one('product.product', string="Produit", required=True)
    description = fields.Text(string="Description")
    product_uom_qty = fields.Float(string="Quantité", default=1.0, required=True)
    product_uom_id = fields.Many2one('uom.uom', string="Unité de mesure")

    is_pack_line = fields.Boolean(
        string="Est un Pack", related='product_id.product_tmpl_id.is_pack', store=False)
    pack_origin_id = fields.Many2one(
        'university.besoin.achat.line', string="Issu du Pack",
        readonly=True, copy=False, ondelete='cascade')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.name
                line.product_uom_id = line.product_id.uom_id

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('skip_pack_sync'):
            lines.mapped('besoin_achat_id')._sync_pack_lines()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_pack_sync') and (
                'product_uom_qty' in vals or 'product_id' in vals):
            self.mapped('besoin_achat_id')._sync_pack_lines()
        return res

    def unlink(self):
        parents = self.env['university.besoin.achat']
        if not self.env.context.get('skip_pack_sync'):
            parents = self.mapped('besoin_achat_id')
        res = super().unlink()
        if parents:
            parents._sync_pack_lines()
        return res
