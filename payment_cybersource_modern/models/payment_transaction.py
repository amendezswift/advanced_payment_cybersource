"""Extensions of payment.transaction specific to CyberSource."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PaymentTransaction(models.Model):
    """Handle CyberSource specific states and notifications."""

    _inherit = "payment.transaction"

    capture_manually = fields.Boolean(
        string="Capture Manually",
        related="provider_id.capture_manually",
        help="Indicates if the CyberSource transaction requires a manual capture step.",
    )

    def action_cybersource_set_done(self):
        """Convenience action used from the form view to mark the tx as done."""
        self._simulate_notification("AUTHORIZED")

    def action_cybersource_set_canceled(self):
        """Convenience action used from the form view to cancel the tx."""
        self._simulate_notification("DECLINED")

    def action_cybersource_set_error(self):
        """Convenience action used from the form view to mark the tx as errored."""
        self._simulate_notification("error")

    def _simulate_notification(self, simulated_state: str) -> None:
        self.ensure_one()
        if self.provider_code != "cybersource":
            return
        notification_data = {"reference": self.reference, "simulated_state": simulated_state}
        self._handle_notification_data("cybersource", notification_data)

    @api.model
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        transaction = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != "cybersource" or transaction:
            return transaction

        reference = notification_data.get("reference")
        if not reference:
            raise ValidationError(_("CyberSource: the notification is missing the transaction reference."))

        transaction = self.search([
            ("reference", "=", reference),
            ("provider_code", "=", "cybersource"),
        ])
        if not transaction:
            raise ValidationError(
                _("CyberSource: no transaction found matching reference %s.", reference)
            )
        return transaction

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        if self.provider_code != "cybersource":
            return

        self.provider_reference = f"cybersource-{self.reference}"
        simulated_state = notification_data.get("simulated_state")
        if simulated_state == "pending":
            self._set_pending()
            return

        if simulated_state == "AUTHORIZED":
            if self.capture_manually and not notification_data.get("manual_capture"):
                self._set_authorized()
            else:
                self._set_done()
                if self.operation == "refund":
                    self.env.ref("payment.cron_post_process_payment_tx")._trigger()
            return

        if simulated_state == "DECLINED":
            message = notification_data.get("message", "")
            formatted_message = message or _("Payment canceled by CyberSource.")
            self._set_canceled(state_message=formatted_message)
            return

        self._set_error(_("CyberSource returned the state: %s", simulated_state))

