"""Controllers implementing the CyberSource payment flow."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import config

from CyberSource import PaymentsApi
from CyberSource.logging.log_configuration import LogConfiguration

_logger = logging.getLogger(__name__)


class CyberSourcePaymentController(http.Controller):
    """Expose the endpoint used by the website payment form."""

    _success_states = {"AUTHORIZED", "PENDING", "CAPTURED"}

    @http.route(
        "/payment/cybersource/process",
        type="json",
        auth="public",
        csrf=False,
    )
    def process_payment(self, **payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the incoming payload and call the CyberSource API."""
        try:
            reference = payload.get("reference")
            if not reference:
                raise ValidationError(_("The payment reference is missing."))

            values = payload.get("values") or {}
            partner = self._fetch_partner(values)
            currency = self._fetch_currency(values)
            amount = values.get("amount")
            if not amount:
                raise ValidationError(_("The transaction amount is missing."))

            card_data = self._prepare_card_data(payload.get("customer_input") or {})
            body = self._render_payload(reference, amount, currency.name, partner, card_data)
            client = PaymentsApi(self._prepare_configuration())

            _logger.info("Submitting CyberSource payment for reference %s", reference)
            response, status, _ = client.create_payment(body)
            response_dict = self._to_dict(response)
            _logger.debug("CyberSource response for %s: %s", reference, json.dumps(response_dict, indent=2))

            status_label = (response_dict.get("status") or "").upper()
            if status in {200, 201} and status_label in self._success_states:
                self._handle_success(reference, status_label)
                return {
                    "success": True,
                    "status": status_label,
                    "message": _("The payment has been authorized."),
                    "data": response_dict,
                }

            return self._prepare_error(status_label or "DECLINED", response_dict)
        except ValidationError as err:
            return {"success": False, "message": err.name or str(err)}
        except Exception:  # pylint: disable=broad-except
            _logger.exception("Unexpected error when processing CyberSource payment.")
            return {
                "success": False,
                "message": _("An unexpected error occurred while contacting CyberSource."),
            }

    def _fetch_partner(self, values: Dict[str, Any]):
        partner_id = values.get("partner")
        partner = request.env["res.partner"].sudo().browse(partner_id)
        if not partner:
            raise ValidationError(_("The customer related to this payment could not be found."))
        return partner

    def _fetch_currency(self, values: Dict[str, Any]):
        currency_id = values.get("currency")
        currency = request.env["res.currency"].sudo().browse(currency_id)
        if not currency:
            raise ValidationError(_("The currency configured for this payment is invalid."))
        return currency

    def _prepare_card_data(self, card: Dict[str, Any]) -> Dict[str, str]:
        number = (card.get("card_num") or "").replace(" ", "")
        month = str(card.get("exp_month") or "").zfill(2)
        year = str(card.get("exp_year") or "")
        cvv = str(card.get("cvv") or "").strip()

        if not all([number, month, year, cvv]):
            raise ValidationError(_("Please provide the complete card details (number, expiry and CVV)."))

        return {
            "number": number,
            "expirationMonth": month,
            "expirationYear": year,
            "securityCode": cvv,
            "type": card.get("type") or "001",  # Visa by default
        }

    def _render_payload(self, reference: str, amount: float, currency: str, partner, card: Dict[str, str]) -> str:
        first_name, *rest = (partner.name or "Customer").split(" ")
        last_name = rest[-1] if rest else first_name
        payload = {
            "clientReferenceInformation": {"code": reference},
            "processingInformation": {"capture": True, "commerceIndicator": "internet"},
            "paymentInformation": {"card": card},
            "orderInformation": {
                "amountDetails": {
                    "totalAmount": str(amount),
                    "currency": currency,
                },
                "billTo": {
                    "firstName": first_name,
                    "lastName": last_name,
                    "address1": partner.street or "N/A",
                    "locality": partner.city or "N/A",
                    "administrativeArea": partner.state_id.code or "N/A",
                    "postalCode": partner.zip or "00000",
                    "country": partner.country_id.code or "US",
                    "email": partner.email or "customer@example.com",
                    "phoneNumber": partner.phone or "0000000000",
                },
            },
        }
        return json.dumps(payload)

    def _prepare_configuration(self):
        provider = request.env["payment.provider"].sudo().search([("code", "=", "cybersource")], limit=1)
        if not provider:
            raise ValidationError(_("No CyberSource provider is configured."))
        missing_fields = [
            field
            for field in ("cyber_merchant", "cyber_key", "cyber_secret_key")
            if not provider[field]
        ]
        if missing_fields:
            raise ValidationError(
                _("The CyberSource provider is missing the following credentials: %s", ", ".join(missing_fields))
            )

        log_directory = os.path.join(config["data_dir"], "cybersource_logs")
        os.makedirs(log_directory, exist_ok=True)

        log_config = LogConfiguration()
        log_config.enable_log = True
        log_config.log_directory = log_directory
        log_config.log_file_name = "cybersource"
        log_config.log_maximum_size = 10_485_760
        log_config.log_level = "DEBUG"
        log_config.enable_masking = False

        return {
            "authentication_type": "http_signature",
            "run_environment": "apitest.cybersource.com",
            "merchantid": provider.cyber_merchant,
            "merchant_keyid": provider.cyber_key,
            "merchant_secretkey": provider.cyber_secret_key,
            "timeout": 60,
            "log_config": log_config,
        }

    def _handle_success(self, reference: str, status_label: str) -> None:
        tx_vals = {
            "reference": reference,
            "simulated_state": "pending" if status_label == "PENDING" else "AUTHORIZED",
        }
        request.env["payment.transaction"].sudo()._handle_notification_data("cybersource", tx_vals)

    def _prepare_error(self, status_label: str, response: Dict[str, Any]) -> Dict[str, Any]:
        error = response.get("error_information", {}) or {}
        message = error.get("message") or _("CyberSource declined the payment request.")
        reason = error.get("reason") or "N/A"
        _logger.warning("CyberSource rejected the payment: %s (%s)", message, reason)
        return {
            "success": False,
            "status": status_label,
            "reason": reason,
            "message": message,
            "data": response,
        }

    @staticmethod
    def _to_dict(response: Any) -> Dict[str, Any]:
        if hasattr(response, "to_dict"):
            return response.to_dict()
        if isinstance(response, dict):
            return response
        return {}

