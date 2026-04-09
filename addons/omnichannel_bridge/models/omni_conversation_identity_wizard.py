# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class OmniConversationIdentityWizard(models.TransientModel):
    """
    Ідентифікація клієнта для омніканального треду (аналог картки розмови SendPulse):
    пошук існуючого partner за email/телефоном → прив'язка до discuss.channel + identity;
    або створення нового контакту.
    """
    _name = 'omni.conversation.identity.wizard'
    _description = 'Omnichannel thread: identify / link client'

    channel_id = fields.Many2one(
        'discuss.channel',
        string='Тред Discuss',
        required=True,
        readonly=True,
        ondelete='cascade',
    )

    search_email = fields.Char(string='Email для пошуку')
    search_phone = fields.Char(string='Телефон для пошуку')

    search_done = fields.Boolean(default=False)
    found_partner_ids = fields.Many2many(
        'res.partner',
        'omni_conv_identity_wizard_partner_rel',
        'wizard_id',
        'partner_id',
        string='Знайдені клієнти',
    )
    selected_partner_id = fields.Many2one('res.partner', string='Обраний клієнт')
    found_count = fields.Integer(
        string='Знайдено',
        compute='_compute_found_count',
    )

    @api.depends('found_partner_ids')
    def _compute_found_count(self):
        for rec in self:
            rec.found_count = len(rec.found_partner_ids)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        cid = vals.get('channel_id') or self.env.context.get('default_channel_id')
        if cid:
            channel = self.env['discuss.channel'].sudo().browse(int(cid))
            if channel.exists():
                p = channel.omni_customer_partner_id
                if p:
                    vals.setdefault('search_email', p.email or '')
                    vals.setdefault('search_phone', p.phone or p.mobile or '')
        return vals

    def action_search(self):
        self.ensure_one()
        domain = []
        if self.search_email and self.search_email.strip():
            term = self.search_email.strip()
            domain = ['|', ('email', 'ilike', term), ('name', 'ilike', term)]
        elif self.search_phone and self.search_phone.strip():
            clean = self.search_phone.strip().replace(' ', '').replace('-', '')
            domain = [
                '|',
                '|',
                ('phone', 'ilike', clean),
                ('mobile', 'ilike', clean),
                ('name', 'ilike', clean),
            ]

        if domain:
            partners = self.env['res.partner'].search(
                domain + [('active', '=', True)],
                limit=20,
            )
        else:
            partners = self.env['res.partner']

        self.write({
            'found_partner_ids': [(6, 0, partners.ids)],
            'selected_partner_id': partners[0].id if len(partners) == 1 else False,
            'search_done': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_link_partner(self):
        self.ensure_one()
        if not self.selected_partner_id:
            raise UserError(_('Оберіть клієнта зі списку знайдених.'))
        self.env['discuss.channel'].sudo().omni_bind_partner_to_channel(
            self.channel_id.id,
            self.selected_partner_id.id,
        )
        self.env['omni.inbox.thread'].sudo()._sync_from_discuss_channels(self.channel_id)
        return {'type': 'ir.actions.act_window_close'}

    def action_create_and_link(self):
        self.ensure_one()
        vals = {'name': self.channel_id.name or _('Клієнт чату')}
        if self.search_email and self.search_email.strip():
            vals['email'] = self.search_email.strip()
        if self.search_phone and self.search_phone.strip():
            vals['phone'] = self.search_phone.strip()
        if 'email' not in vals and 'phone' not in vals:
            raise UserError(_('Вкажіть email або телефон для нового контакту.'))
        partner = self.env['res.partner'].create(vals)
        self.env['discuss.channel'].sudo().omni_bind_partner_to_channel(
            self.channel_id.id,
            partner.id,
        )
        self.env['omni.inbox.thread'].sudo()._sync_from_discuss_channels(self.channel_id)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': partner.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_partner(self):
        self.ensure_one()
        partner = self.selected_partner_id or (
            self.found_partner_ids[0] if self.found_partner_ids else None
        )
        if not partner:
            raise UserError(_('Спочатку оберіть клієнта зі списку.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': partner.id,
            'view_mode': 'form',
            'target': 'new',
        }
