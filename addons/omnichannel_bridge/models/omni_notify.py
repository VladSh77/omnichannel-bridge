# -*- coding: utf-8 -*-
"""
omni_notify — внутрішній Telegram-канал менеджера/керівника.

Надсилає сповіщення в окремий bot + chat_id (не плутати з клієнтським ботом):
  - новий тред (перше повідомлення від нового клієнта)
  - ескалація до менеджера (бот не справляється / явний запит)
  - прапорець «проблемний» на каналі або партнері

Конфігурація (Settings → Omnichannel → Internal notifications):
  ir.config_parameter:
    omnichannel_bridge.internal_tg_bot_token   — токен окремого внутрішнього бота
    omnichannel_bridge.internal_tg_chat_id     — ID чату/групи/каналу менеджера
    omnichannel_bridge.internal_notify_new     — bool: сповіщати про нові треди
    omnichannel_bridge.internal_notify_escalate — bool: сповіщати про ескалацію
    omnichannel_bridge.internal_notify_problem  — bool: сповіщати про проблемних
"""
import logging
from datetime import timedelta

import requests

from odoo import _, api, models
from odoo.fields import Datetime

_logger = logging.getLogger(__name__)

_NOTIFY_TIMEOUT = 10  # секунд — короткий, щоб не блокувати worker


class OmniNotify(models.AbstractModel):
    _name = 'omni.notify'
    _description = 'Internal Telegram notifications for managers'

    # ------------------------------------------------------------------
    # Public API — викликати з omni_bridge / omni_sales_intel
    # ------------------------------------------------------------------

    @api.model
    def notify_new_thread(self, channel, partner, provider):
        """Новий тред: перше повідомлення від клієнта."""
        if not self._flag_enabled('omnichannel_bridge.internal_notify_new'):
            return
        if channel:
            channel = channel.sudo()
        if partner:
            partner = partner.sudo()
        provider_label = self._provider_label(provider)
        phone = (partner.phone or partner.mobile or '—') if partner else '—'
        text = self._event_summary_text(
            event='new_thread',
            channel=channel,
            partner=partner,
            provider_label=provider_label,
            lines=[
                '📞 %s' % self._escape(phone),
            ],
        )
        self._send(text, parse_mode='Markdown')

    @api.model
    def notify_escalation(self, channel, partner, reason=''):
        """Ескалація: бот передає розмову менеджеру."""
        if not self._flag_enabled('omnichannel_bridge.internal_notify_escalate'):
            return
        if channel:
            channel = channel.sudo()
        if partner:
            partner = partner.sudo()
        is_priority = self._is_priority_reason(reason)
        text = self._event_summary_text(
            event='escalation',
            channel=channel,
            partner=partner,
            lines=[
                '💬 %s' % self._escape(reason or _('клієнт запитав менеджера')),
                '🧾 %s' % self._escape(self._handoff_packet(partner)),
            ],
            priority=is_priority,
        )
        self._send(text, parse_mode='Markdown', priority=is_priority)
        self._notify_manager_direct(
            channel=channel,
            partner=partner,
            subject='Escalation',
            summary=reason or _('клієнт запитав менеджера'),
        )

    @api.model
    def notify_problematic(self, channel, partner, note=''):
        """Проблемний клієнт/тред — прапорець виставлено."""
        if not self._flag_enabled('omnichannel_bridge.internal_notify_problem'):
            return
        if channel:
            channel = channel.sudo()
        if partner:
            partner = partner.sudo()
        text = self._event_summary_text(
            event='problematic',
            channel=channel,
            partner=partner,
            lines=['📝 %s' % self._escape(note or '—')],
            priority=True,
        )
        self._send(text, parse_mode='Markdown', priority=True)
        self._notify_manager_direct(
            channel=channel,
            partner=partner,
            subject='Problematic thread',
            summary=note or 'problematic',
        )

    @api.model
    def notify_stage_change(self, channel, partner, old_stage, new_stage, reason=''):
        if not channel or not partner or old_stage == new_stage:
            return
        channel = channel.sudo()
        partner = partner.sudo()
        stage_labels = dict(partner._fields['omni_sales_stage'].selection)
        old_lbl = stage_labels.get(old_stage, old_stage or '—')
        new_lbl = stage_labels.get(new_stage, new_stage or '—')
        text = self._event_summary_text(
            event='stage_change',
            channel=channel,
            partner=partner,
            lines=[
                '📈 %s → %s' % (self._escape(old_lbl), self._escape(new_lbl)),
                '💬 %s' % self._escape(reason or 'auto'),
            ],
        )
        self._send(text, parse_mode='Markdown')

    @api.model
    def notify_purchase_intent(self, channel, partner, user_text=''):
        if not channel or not partner:
            return
        channel = channel.sudo()
        partner = partner.sudo()
        snippet = (user_text or '').strip()
        if len(snippet) > 180:
            snippet = snippet[:180] + '...'
        text = self._event_summary_text(
            event='purchase_intent',
            channel=channel,
            partner=partner,
            lines=[
                '🛒 Готовність до оплати / бронювання',
                '💬 %s' % self._escape(snippet or '—'),
            ],
            priority=True,
        )
        self._send(text, parse_mode='Markdown', priority=True)
        self._notify_manager_direct(
            channel=channel,
            partner=partner,
            subject='Purchase intent',
            summary=snippet or 'purchase_intent',
        )

    @api.model
    def notify_purchase_confirmed(
        self,
        partner,
        order=None,
        source='sale_order',
        order_ref='',
        amount_line='',
    ):
        if not partner:
            return
        partner = partner.sudo()
        channel = self._find_channel_for_partner(partner)
        if not channel:
            return
        amount = amount_line or '—'
        ref = order_ref or '—'
        if order:
            currency = (order.currency_id.name or '').strip() if hasattr(order, 'currency_id') else ''
            total = getattr(order, 'amount_total', 0.0) or 0.0
            amount = '%s %s' % (total, currency)
            ref = order.name or ref
        amount_norm = str(amount).strip()
        ref_norm = str(ref or '').strip()
        cp = partner.commercial_partner_id.sudo()
        if self._is_purchase_notify_duplicate(cp, ref_norm, amount_norm):
            return
        text = self._event_summary_text(
            event='purchase_confirmed',
            channel=channel,
            partner=partner,
            lines=[
                '✅ Підтверджене замовлення/оплата',
                '🧾 %s' % self._escape(ref_norm or '—'),
                '💳 %s' % self._escape(amount_norm or '—'),
                '🔎 %s' % self._escape(source),
            ],
            priority=True,
        )
        self._send(text, parse_mode='Markdown', priority=True)
        self._notify_manager_direct(
            channel=channel,
            partner=partner,
            subject='Purchase confirmed',
            summary='%s / %s' % (ref_norm or '—', amount_norm or '—'),
        )
        partner.omni_set_sales_stage(
            'handoff',
            channel=channel,
            reason='payment_confirmed',
            source=source,
        )
        cp.write({
            'omni_last_purchase_notify_at': Datetime.now(),
            'omni_last_purchase_notify_ref': ref_norm,
            'omni_last_purchase_notify_amount': amount_norm,
            'omni_purchase_confirmed_at': Datetime.now(),
        })

    # ------------------------------------------------------------------
    # Внутрішнє
    # ------------------------------------------------------------------

    def _send(self, text, parse_mode='Markdown', priority=False):
        token, chat_id, priority_chat_id, api_base, allowed_user_ids = self._credentials()
        if not token or not chat_id:
            _logger.debug(
                'omni_notify: internal_tg_bot_token or internal_tg_chat_id not set — skip.'
            )
            return
        base = (api_base or 'https://api.telegram.org').rstrip('/')
        url = '%s/bot%s/sendMessage' % (base, token)
        if allowed_user_ids and not self._allowed_users_membership_ok(base, token, chat_id, allowed_user_ids):
            _logger.warning('omni_notify: approved user policy check failed; skip internal send')
            return
        target_chats = [chat_id]
        if priority and priority_chat_id and priority_chat_id != chat_id:
            target_chats.append(priority_chat_id)
        try:
            for target_chat in target_chats:
                resp = requests.post(
                    url,
                    json={
                        'chat_id': target_chat,
                        'text': text,
                        'parse_mode': parse_mode,
                        'disable_web_page_preview': True,
                    },
                    timeout=_NOTIFY_TIMEOUT,
                )
                if not resp.ok:
                    _logger.warning(
                        'omni_notify: Telegram sendMessage failed: %s %s',
                        resp.status_code,
                        resp.text[:200],
                    )
        except Exception as exc:
            # Ніколи не ламаємо основний flow через notify
            _logger.warning('omni_notify: exception sending notification: %s', exc)

    def _credentials(self):
        ICP = self.env['ir.config_parameter'].sudo()
        token = ICP.get_param('omnichannel_bridge.internal_tg_bot_token', '').strip()
        chat_id = ICP.get_param('omnichannel_bridge.internal_tg_chat_id', '').strip()
        priority_chat_id = ICP.get_param('omnichannel_bridge.internal_tg_priority_chat_id', '').strip()
        api_base = ICP.get_param('omnichannel_bridge.internal_tg_api_base', 'https://api.telegram.org').strip()
        allowed_raw = ICP.get_param('omnichannel_bridge.internal_tg_allowed_user_ids', '').strip()
        allowed_user_ids = [x.strip() for x in allowed_raw.split(',') if x.strip()]
        return token, chat_id, priority_chat_id, api_base, allowed_user_ids

    def _allowed_users_membership_ok(self, base, token, chat_id, allowed_user_ids):
        try:
            for uid in allowed_user_ids:
                if not uid.lstrip('-').isdigit():
                    continue
                url = '%s/bot%s/getChatMember' % (base, token)
                resp = requests.get(url, params={'chat_id': chat_id, 'user_id': int(uid)}, timeout=_NOTIFY_TIMEOUT)
                if not resp.ok:
                    return False
                data = resp.json() or {}
                status = (((data.get('result') or {}).get('status')) or '').lower()
                if status not in ('creator', 'administrator', 'member', 'restricted'):
                    return False
            return True
        except Exception:
            return False

    def _is_priority_reason(self, reason):
        txt = (reason or '').lower()
        if not txt:
            return False
        keys = [
            'термін', 'urgent', 'asap', 'конфлікт', 'агрес', 'скарг', 'ризик',
            'дитин', 'безпек', 'safety', 'medical', 'юрид', 'legal',
        ]
        extra = (
            self.env['ir.config_parameter'].sudo()
            .get_param('omnichannel_bridge.internal_notify_priority_keywords', '')
            .strip()
        )
        if extra:
            keys.extend([k.strip().lower() for k in extra.split(',') if k.strip()])
        return any(k in txt for k in keys)

    def _event_summary_text(self, event, channel, partner, lines=None, priority=False, provider_label=''):
        lines = list(lines or [])
        title_map = {
            'new_thread': '🆕 *Новий тред*',
            'escalation': '🔺 *Ескалація*',
            'problematic': '⚠️ *Проблемний тред*',
            'stage_change': '🧭 *Зміна етапу*',
            'purchase_intent': '🛒 *Purchase intent*',
            'purchase_confirmed': '✅ *Purchase confirmed*',
        }
        title = title_map.get(event, 'ℹ️ *Подія*')
        if provider_label:
            title = '%s — %s' % (title, self._escape(provider_label))
        prefix = '🚨 *PRIORITY*\\n' if priority else ''
        name = self._partner_min_name(partner)
        pid = partner.id if partner else 0
        body = [
            '%s%s' % (prefix, title),
            '👤 %s (id:%s)' % (self._escape(name), pid),
        ]
        body.extend(lines)
        body.append('🔗 %s' % self._channel_url(channel))
        return '\n'.join(body)

    def _flag_enabled(self, key):
        val = self.env['ir.config_parameter'].sudo().get_param(key, 'False')
        return val in ('True', '1', 'true')

    @staticmethod
    def _provider_label(provider):
        labels = {
            'meta': 'Meta (FB/IG)',
            'telegram': 'Telegram',
            'viber': 'Viber',
            'whatsapp': 'WhatsApp',
        }
        return labels.get(provider, provider)

    def _channel_url(self, channel):
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', 'https://campscout.eu'
        )
        return '%s/web#action=mail.action_discuss&active_id=discuss.channel_%s' % (
            base.rstrip('/'),
            channel.id,
        )

    def _find_channel_for_partner(self, partner):
        partner = partner.sudo()
        p = partner.commercial_partner_id
        return self.env['discuss.channel'].sudo().search(
            [
                ('omni_customer_partner_id', 'child_of', p.id),
                ('omni_provider', '!=', False),
            ],
            order='write_date desc, id desc',
            limit=1,
        )

    def _default_manager_user(self):
        ICP = self.env['ir.config_parameter'].sudo()
        user_id_raw = (ICP.get_param('omnichannel_bridge.default_manager_user_id') or '').strip()
        if not user_id_raw.isdigit():
            return self._pick_online_manager_user()
        user = self.env['res.users'].sudo().browse(int(user_id_raw))
        return user if user.exists() else self._pick_online_manager_user()

    def _pick_online_manager_user(self):
        users = self.env['res.users'].sudo().search([
            ('share', '=', False),
            ('active', '=', True),
            ('im_status', '=', 'online'),
        ], limit=1)
        return users[:1] if users else self.env['res.users']

    def _notify_manager_direct(self, channel, partner, subject, summary):
        manager = self._default_manager_user()
        if not manager:
            return
        partner = partner.sudo() if partner else partner
        partner_name = (partner.display_name if partner else 'Unknown')
        url = self._channel_url(channel) if channel else ''
        note = '%s\nClient: %s\nThread: %s' % (subject, partner_name, url or '—')
        # Direct owner assignment on partner card for one-manager flow.
        if partner and partner.user_id != manager:
            partner.write({'user_id': manager.id})
        # Persistent in-app task visible in Activities.
        if partner:
            self.env['mail.activity'].sudo().create({
                'res_model_id': self.env['ir.model']._get_id('res.partner'),
                'res_id': partner.id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': '[Omni] %s' % subject,
                'note': note,
                'user_id': manager.id,
            })
        ICP = self.env['ir.config_parameter'].sudo()
        send_email = str(
            ICP.get_param('omnichannel_bridge.internal_notify_email_manager', 'False')
        ).lower() in ('1', 'true', 'yes')
        if send_email and manager.partner_id.email:
            self.env['mail.mail'].sudo().create({
                'subject': '[Omni] %s' % subject,
                'body_html': '<p>%s</p><p>%s</p><p><a href="%s">Open thread</a></p>' % (
                    self._escape(summary or '—'),
                    self._escape(partner_name),
                    url or '#',
                ),
                'email_to': manager.partner_id.email,
            }).send()

    def _is_purchase_notify_duplicate(self, partner, ref_norm, amount_norm):
        """Dedupe cross-layer events (sale/payment/invoice) in a short window."""
        partner = partner.sudo()
        last_at = partner.omni_last_purchase_notify_at
        if not last_at:
            return False
        icp = self.env['ir.config_parameter'].sudo()
        try:
            dedup_min = int(icp.get_param('omnichannel_bridge.purchase_dedup_minutes', '20'))
        except ValueError:
            dedup_min = 20
        dedup_min = max(5, dedup_min)
        # A short window prevents burst duplicates from multiple model hooks.
        if (Datetime.now() - last_at) > timedelta(minutes=dedup_min):
            return False
        same_ref = bool(ref_norm and ref_norm == (partner.omni_last_purchase_notify_ref or ''))
        same_amount = bool(amount_norm and amount_norm == (partner.omni_last_purchase_notify_amount or ''))
        return same_ref or same_amount

    @staticmethod
    def _escape(text):
        """Мінімальне екранування для Markdown v1."""
        return str(text).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')

    def _partner_min_name(self, partner):
        if not partner:
            return _('Unknown')
        name = (partner.display_name or '').strip()
        if not name:
            return _('Unknown')
        parts = [p for p in name.split(' ') if p]
        if len(parts) == 1:
            return parts[0][:1] + '.'
        return '%s %s.' % (parts[0][:1], parts[-1][:1])

    @api.model
    def _handoff_packet(self, partner):
        if not partner:
            return 'age:—; period:—; city:—; budget:—; stage:handoff'
        partner = partner.sudo()
        age = partner.omni_child_age or '—'
        period = partner.omni_preferred_period or '—'
        city = partner.omni_departure_city or '—'
        budget = (
            '%s %s' % (partner.omni_budget_amount, partner.omni_budget_currency or '')
            if partner.omni_budget_amount else '—'
        )
        stage = partner.omni_sales_stage or 'handoff'
        return 'age:%s; period:%s; city:%s; budget:%s; stage:%s' % (
            age,
            period,
            city,
            budget.strip(),
            stage,
        )
