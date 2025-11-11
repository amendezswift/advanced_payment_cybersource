"""Extension of payment.provider with CyberSource credentials."""

from odoo import fields, models


class PaymentProvider(models.Model):
    """Expose the configuration fields required by CyberSource."""

    _inherit = "payment.provider"

    code = fields.Selection(
        selection_add=[("cybersource", "CyberSource")],
        ondelete={"cybersource": "set default"},
    )
    cyber_merchant = fields.Char(
        string="Merchant ID",
        help="Identifier assigned to your CyberSource merchant account.",
    )
    cyber_key = fields.Char(
        string="Key ID",
        help="Key identifier used when signing CyberSource requests.",
    )
    cyber_secret_key = fields.Char(
        string="Shared Secret",
        help="Secret key paired with the Key ID.",
    )

