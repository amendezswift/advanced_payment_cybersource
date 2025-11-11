# -*- coding: utf-8 -*-
###############################################################################
#
#   Integración Odoo ↔ CyberSource (REST API)
#   Versión final estable - incluye manejo de errores controlado y CVV
#
###############################################################################
import json
import os
import logging

from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request

from CyberSource import PaymentsApi
from CyberSource.logging.log_configuration import LogConfiguration

_logger = logging.getLogger(__name__)


class WebsiteSaleFormCyberSource(http.Controller):
    """ Controlador para procesar pagos directos con CyberSource (REST API) """

    @http.route('/payment/cybersource/simulate_payment', type='json', auth='public')
    def payment_with_flex_token(self, **post):
        """Procesa el pago directo enviando JSON plano a CyberSource."""
        try:
            # ---- 📦 Extraer datos del POST ----
            values = post.get('values', {}) or {}
            card = post.get('customer_input', {}) or {}
            reference = post.get('reference')

            if not reference:
                return {"success": False, "message": "Referencia de pago no recibida."}

            partner = request.env['res.partner'].sudo().browse(values.get('partner'))
            if not partner:
                return {"success": False, "message": "Cliente no encontrado para el pago."}

            currency = request.env['res.currency'].sudo().browse(values.get('currency'))
            if not currency:
                return {"success": False, "message": "Moneda no encontrada para el pago."}

            amount = values.get('amount')
            if not amount:
                return {"success": False, "message": "Monto no recibido para el pago."}

            # ---- 💳 Validaciones básicas de la tarjeta ----
            card_number = (card.get('card_num') or '').replace(' ', '')
            exp_month = (card.get('exp_month') or '').zfill(2)
            exp_year = str(card.get('exp_year') or '')
            cvv = (card.get('cvv') or '').strip()

            if not card_number or not exp_month or not exp_year or not cvv:
                return {"success": False, "message": "Faltan datos de tarjeta (número, vencimiento o CVV)."}

            card_type = "001"  # Visa

            # ---- 🧾 Armar payload exacto ----
            payload = {
                "clientReferenceInformation": {"code": reference},
                "processingInformation": {"capture": True, "commerceIndicator": "internet"},
                "paymentInformation": {
                    "card": {
                        "number": card_number,
                        "expirationMonth": exp_month,
                        "expirationYear": exp_year,
                        "securityCode": cvv,
                        "type": card_type,
                    }
                },
                "orderInformation": {
                    "amountDetails": {
                        "totalAmount": str(amount),
                        "currency": currency.name,
                    },
                    "billTo": {
                        "firstName": (partner.name or "Cliente").split(' ')[0],
                        "lastName": (partner.name or "Cliente").split(' ')[-1],
                        "address1": partner.street or "N/A",
                        "locality": partner.city or "N/A",
                        "administrativeArea": partner.state_id.code or "N/A",
                        "postalCode": partner.zip or "00000",
                        "country": partner.country_id.code or "GT",
                        "email": partner.email or "cliente@example.com",
                        "phoneNumber": partner.phone or "00000000",
                    }
                }
            }

            body = json.dumps(payload)
            _logger.info("🔹 Enviando pago CyberSource para %s", reference)
            _logger.debug("Payload enviado a CyberSource: %s", body)

            # ---- 🔐 Configuración del cliente ----
            client_config = self.get_configuration()
            api_instance = PaymentsApi(client_config)

            # ---- 🚀 Enviar a CyberSource ----
            return_data, status, response_body = api_instance.create_payment(body)
            _logger.info("🔹 Respuesta CyberSource (%s): %s", status, return_data)

            # ---- ✅ Convertir respuesta a diccionario ----
            if hasattr(return_data, "to_dict"):
                return_dict = return_data.to_dict()
            else:
                return_dict = return_data if isinstance(return_data, dict) else {}

            _logger.debug("Respuesta convertida a dict: %s", json.dumps(return_dict, indent=2))

            # ---- ✅ Evaluar respuesta ----
            cyb_status = (return_dict.get("status") or "").upper()

            if status in (200, 201) and cyb_status in ("AUTHORIZED", "PENDING", "CAPTURED"):
                tx_vals = {
                    'reference': reference,
                    'simulated_state': 'AUTHORIZED' if cyb_status != "PENDING" else 'pending',
                }
                request.env['payment.transaction'].sudo()._handle_notification_data('cybersource', tx_vals)

                return {
                    "success": True,
                    "status": cyb_status,
                    "message": "Pago autorizado exitosamente.",
                    "data": return_dict,
                }

            else:
                # ⚠️ Devolver error JSON controlado, no ValidationError
                error_info = return_dict.get("error_information", {}) or {}
                error_msg = error_info.get("message", "Error desconocido en CyberSource")
                reason = error_info.get("reason", "N/A")

                _logger.warning("❌ Pago rechazado por CyberSource: %s (%s)", error_msg, reason)

                return {
                    "success": False,
                    "status": cyb_status or "DECLINED",
                    "reason": reason,
                    "message": error_msg,
                    "data": return_dict,
                }

        except Exception as e:
            _logger.exception("❌ Error al procesar pago CyberSource: %s", e)
            return {"success": False, "message": str(e)}

    def get_configuration(self):
        """Lee credenciales desde payment.provider (code='cybersource')."""
        record = request.env['payment.provider'].sudo().search(
            [('code', '=', 'cybersource')], limit=1
        )
        if not record:
            raise ValidationError(_("No se encontró el proveedor CyberSource configurado."))

        if not (record.cyber_merchant and record.cyber_key and record.cyber_secret_key):
            raise ValidationError(_("Faltan credenciales en el proveedor CyberSource."))

        config = {
            "authentication_type": "http_signature",
            "run_environment": "apitest.cybersource.com",  # Cambiar a apitest.visanetcybersource.com si aplica
            "merchantid": record.cyber_merchant,
            "merchant_keyid": record.cyber_key,
            "merchant_secretkey": record.cyber_secret_key,
            "timeout": 1000,
        }

        log_config = LogConfiguration()
        log_config.enable_log = True
        log_config.log_directory = os.path.join(os.getcwd(), "Logs")
        log_config.log_file_name = "cybs"
        log_config.log_maximum_size = 10487560
        log_config.log_level = "DEBUG"
        log_config.enable_masking = False
        config["log_config"] = log_config

        return config
