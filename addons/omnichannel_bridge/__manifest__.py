# -*- coding: utf-8 -*-
{
    'name': 'Omnichannel Bridge',
    'summary': 'Aggregate messengers into Discuss; webhooks, CRM partner match, AI/sales hooks',
    'version': '17.0.1.0.0',
    'category': 'Productivity/Discuss',
    'author': 'Fajna',
    'license': 'LGPL-3',
    'depends': [
        'base_setup',
        'mail',
        'crm',
        'sale_management',
        'stock',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/omni_ai_job_cron.xml',
        'views/omni_integration_views.xml',
        'views/res_config_settings_views.xml',
        'views/mail_channel_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/omni_ops_views.xml',
    ],
    'external_dependencies': {
        'python': ['requests', 'pytz'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
