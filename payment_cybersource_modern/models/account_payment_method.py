"""Extension of account.payment.method for CyberSource."""

from odoo import api, models


class AccountPaymentMethod(models.Model):
    """Register the CyberSource payment method for journals."""

    _inherit = "account.payment.method"

    @api.model
    def _get_payment_method_information(self):
        information = super()._get_payment_method_information()
        information["cybersource"] = {
            "mode": "multi",
            "domain": [("type", "=", "bank")],
        }
        return information

