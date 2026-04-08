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

import requests

from odoo import _, api, models

_logger = logging.getLogger(__name__)

TELEGRAM_API = 'https://api.telegram.org/bot{token}/sendMessage'
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
        name = (partner.display_name or _('Unknown')) if partner else _('Unknown')
        phone = (partner.phone or partner.mobile or '—') if partner else '—'
        text = (
            '🆕 *Новий тред* — %(provider)s\n'
            '👤 %(name)s\n'
            '📞 %(phone)s\n'
            '🔗 %(url)s'
        ) % {
            'provider': provider_label,
            'name': self._escape(name),
            'phone': self._escape(phone),
            'url': self._channel_url(channel),
        }
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
        name = (partner.display_name or _('Unknown')) if partner else _('Unknown')
        packet = self._handoff_packet(partner)
        is_priority = self._is_priority_reason(reason)
        title = '🚨 *PRIORITY*\\n🔺 *Ескалація* — потрібен менеджер' if is_priority else '🔺 *Ескалація* — потрібен менеджер'
        text = (
            '%(title)s\n'
            '👤 %(name)s\n'
            '💬 %(reason)s\n'
            '🧾 %(packet)s\n'
            '🔗 %(url)s'
        ) % {
            'title': title,
            'name': self._escape(name),
            'reason': self._escape(reason or _('клієнт запитав менеджера')),
            'packet': self._escape(packet),
            'url': self._channel_url(channel),
        }
        self._send(text, parse_mode='Markdown', priority=is_priority)

    @api.model
    def notify_problematic(self, channel, partner, note=''):
        """Проблемний клієнт/тред — прапорець виставлено."""
        if not self._flag_enabled('omnichannel_bridge.internal_notify_problem'):
            return
        if channel:
            channel = channel.sudo()
        if partner:
            partner = partner.sudo()
        name = (partner.display_name or _('Unknown')) if partner else _('Unknown')
        text = (
            '🚨 *PRIORITY*\n'
            '⚠️ *Проблемний тред*\n'
            '👤 %(name)s\n'
            '📝 %(note)s\n'
            '🔗 %(url)s'
        ) % {
            'name': self._escape(name),
            'note': self._escape(note or '—'),
            'url': self._channel_url(channel),
        }
        self._send(text, parse_mode='Markdown', priority=True)

    # ------------------------------------------------------------------
    # Внутрішнє
    # ------------------------------------------------------------------

    def _send(self, text, parse_mode='Markdown', priority=False):
        token, chat_id, priority_chat_id = self._credentials()
        if not token or not chat_id:
            _logger.debug(
                'omni_notify: internal_tg_bot_token or internal_tg_chat_id not set — skip.'
            )
            return
        url = TELEGRAM_API.format(token=token)
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
        return token, chat_id, priority_chat_id

    def _is_priority_reason(self, reason):
        txt = (reason or '').lower()
        if not txt:
            return False
        keys = (
            'термін', 'urgent', 'asap', 'конфлікт', 'агрес', 'скарг', 'ризик',
            'дитин', 'безпек', 'safety', 'medical', 'юрид', 'legal',
        )
        return any(k in txt for k in keys)

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

    @staticmethod
    def _escape(text):
        """Мінімальне екранування для Markdown v1."""
        return str(text).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')

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
