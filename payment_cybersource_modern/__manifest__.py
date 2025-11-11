{
    "name": "CyberSource Payment Gateway (Modernized)",
    "version": "17.0.1.0.0",
    "category": "Accounting/Payment Providers",
    "summary": "Accept online payments through CyberSource with an improved configuration UI.",
    "description": """Modernized CyberSource payment provider for Odoo 17.""",
    "author": "Nova Payment Labs",
    "website": "https://example.com",
    "license": "LGPL-3",
    "depends": ["payment", "website_sale"],
    "data": [
        "data/payment_method_data.xml",
        "data/payment_provider_data.xml",
        "views/payment_provider_views.xml",
        "views/payment_templates.xml",
        "views/payment_transaction_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "payment_cybersource_modern/static/src/js/payment_form.js",
        ],
    },
    "external_dependencies": {"python": ["cybersource-rest-client-python"]},
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
