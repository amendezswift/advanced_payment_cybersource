# -*- coding: utf-8 -*-
import json
import os
import logging
import time
import uuid

from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request

from CyberSource import PaymentsApi
from CyberSource.logging.log_configuration import LogConfiguration

_logger = logging.getLogger(__name__)


class WebsiteSaleFormCyberSource(http.Controller):

    @http.route('/payment/cybersource/simulate_payment', type='json', auth='public')
    def payment_with_flex_token(self, **post):
        flow_id = str(uuid.uuid4())[:8]  # ID único para rastreo
        start_time = time.time()

        _logger.info(f"🔵 [{flow_id}] ⟶ INICIO flujo CyberSource simulate_payment")
        _logger.debug(f"🔵 [{flow_id}] Payload recibido desde frontend: {json.dumps(post, indent=4)}")

        try:
            # ================================
            # 1) OBTENER DATOS PRINCIPALES
            # ================================
            _logger.info(f"🔵 [{flow_id}] Extrayendo datos principales (values, card, reference)")
            values = post.get('values', {}) or {}
            card = post.get('customer_input', {}) or {}
            reference = post.get('reference')

            _logger.debug(f"🔵 [{flow_id}] values: {values}")
            _logger.debug(f"🔵 [{flow_id}] card_data: {card}")
            _logger.debug(f"🔵 [{flow_id}] reference: {reference}")

            _logger.info(f"🔵 [{flow_id}] Buscando partner, currency y amount en Odoo…")

            partner = request.env['res.partner'].sudo().browse(values.get('partner'))
            currency = request.env['res.currency'].sudo().browse(values.get('currency'))
            amount = values.get('amount')

            if not partner:
                _logger.error(f"🔴 [{flow_id}] Partner no encontrado → ID: {values.get('partner')}")
                return {"success": False, "message": "Cliente no encontrado"}

            if not currency:
                _logger.error(f"🔴 [{flow_id}] Moneda no encontrada → ID: {values.get('currency')}")
                return {"success": False, "message": "Moneda no válida"}

            if not amount:
                _logger.error(f"🔴 [{flow_id}] Monto no válido")
                return {"success": False, "message": "Monto no válido"}

            _logger.info(f"🟢 [{flow_id}] Partner, currency y amount validados correctamente")

            # ================================
            # 2) VALIDAR TARJETA
            # ================================
            _logger.info(f"🔵 [{flow_id}] Validando tarjeta…")

            card_number = (card.get('card_num') or '').replace(' ', '')
            exp_month = (card.get('exp_month') or '').zfill(2)
            exp_year = str(card.get('exp_year') or '')
            cvv = (card.get('cvv') or '').strip()

            _logger.debug(f"🔵 [{flow_id}] Card Number: {card_number}")
            _logger.debug(f"🔵 [{flow_id}] Exp Month: {exp_month}")
            _logger.debug(f"🔵 [{flow_id}] Exp Year: {exp_year}")
            _logger.debug(f"🔵 [{flow_id}] CVV: {cvv}")

            if not card_number or not exp_month or not exp_year or not cvv:
                _logger.warning(f"🟡 [{flow_id}] Faltan datos de tarjeta")
                return {"success": False, "message": "Datos de tarjeta incompletos."}

            card_type = self.detect_card_type(card_number)
            _logger.info(f"🟢 [{flow_id}] Tipo de tarjeta detectado: {card_type}")

            # ================================
            # 3) CONSTRUIR JSON
            # ================================
            _logger.info(f"🔵 [{flow_id}] Construyendo payload JSON para CyberSource…")

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
                        "firstName": partner.name or "Customer",
                        "lastName": partner.name or "Customer",
                        "address1": partner.street or "N/A",
                        "locality": partner.city or "N/A",
                        "administrativeArea": partner.state_id.code or "N/A",
                        "postalCode": partner.zip or "00000",
                        "country": partner.country_id.code or "GT",
                        "email": partner.email or "customer@example.com",
                        "phoneNumber": partner.phone or "00000000",
                    }
                }
            }

            _logger.info(f"📦 [{flow_id}] Payload listo (enviado a CyberSource):")
            _logger.info(json.dumps(payload, indent=4))

            # ================================
            # 4) OBTENER CONFIGURACIÓN
            # ================================
            _logger.info(f"🔵 [{flow_id}] Obteniendo configuración del proveedor CyberSource…")
            client_config = self.get_configuration()

            _logger.info(f"🛠️ [{flow_id}] Configuración final:")
            _logger.info(json.dumps({
                "merchantid": client_config["merchantid"],
                "keyid": client_config["merchant_keyid"],
                "environment": client_config["run_environment"],
            }, indent=4))

            # ================================
            # 5) ENVIAR A CYBERSOURCE
            # ================================
            _logger.info(f"🟦 [{flow_id}] ⟶ Enviando solicitud a CyberSource.create_payment()")

            api_instance = PaymentsApi(client_config)
            return_data, status, response_body = api_instance.create_payment(json.dumps(payload))

            _logger.info(f"🔵 [{flow_id}] Respuesta cruda desde CyberSource (status HTTP {status})")
            _logger.debug(response_body)

            # ================================
            # 6) PARSEAR RESPUESTA
            # ================================
            _logger.info(f"🔵 [{flow_id}] Procesando respuesta…")

            if hasattr(return_data, "to_dict"):
                return_dict = return_data.to_dict()
            else:
                return_dict = return_data if isinstance(return_data, dict) else {}

            _logger.info(f"📥 [{flow_id}] Respuesta convertida:")
            _logger.info(json.dumps(return_dict, indent=4))

            cyb_status = (return_dict.get("status") or "").upper()
            _logger.info(f"🔵 [{flow_id}] Estado interpretado: {cyb_status}")

            # ================================
            # 7) ÉXITO
            # ================================
            if status in (200, 201) and cyb_status in ("AUTHORIZED", "PENDING", "CAPTURED"):
                _logger.info(f"🟢 [{flow_id}] PAGO APROBADO por CyberSource → {cyb_status}")

                tx_vals = {
                    "reference": reference,
                    "simulated_state": "AUTHORIZED"
                }
                _logger.info(f"🔵 [{flow_id}] Notificando a Odoo (_handle_notification_data)")
                request.env['payment.transaction'].sudo()._handle_notification_data("cybersource", tx_vals)

                return {
                    "success": True,
                    "status": cyb_status,
                    "message": "Pago aprobado.",
                    "data": return_dict
                }

            # ================================
            # 8) DECLINADO
            # ================================
            _logger.warning(f"🟡 [{flow_id}] Pago DECLINADO por CyberSource")

            error_info = return_dict.get("error_information", {}) or {}
            error_msg = error_info.get("message", "Declinado por CyberSource")
            reason = error_info.get("reason", "UNKNOWN")

            _logger.warning(f"🟡 [{flow_id}] Motivo → {reason}: {error_msg}")

            tx_vals = {
                "reference": reference,
                "simulated_state": "DECLINED",
                "message": error_msg,
            }
            _logger.info(f"🔵 [{flow_id}] Notificando DECLINE a Odoo (_handle_notification_data)")
            request.env['payment.transaction'].sudo()._handle_notification_data("cybersource", tx_vals)

            return {
                "success": False,
                "status": "DECLINED",
                "reason": reason,
                "message": error_msg,
            }

        except Exception as e:
            _logger.exception(f"🔴 [{flow_id}] ERROR inesperado: {e}")
            return {"success": False, "message": f"Error interno: {str(e)}"}

        finally:
            total = round(time.time() - start_time, 3)
            _logger.info(f"🔚 [{flow_id}] FIN flujo simulate_payment (duración: {total}s)")


    # =========================================
    # UTILIDADES
    # =========================================
    def detect_card_type(self, number):
        if number.startswith('4'):
            return "001"
        if number.startswith(('51', '52', '53', '54', '55')):
            return "002"
        if number.startswith(('34', '37')):
            return "003"
        return "000"

    def get_configuration(self):
        rec = request.env['payment.provider'].sudo().search([('code', '=', 'cybersource')], limit=1)
        if not rec:
            _logger.error("❌ No se encontró el proveedor 'cybersource'.")
            raise ValidationError("No hay proveedor CyberSource configurado.")

        _logger.info("🧩 Configuración del proveedor extraída correctamente.")

        return {
            "authentication_type": "http_signature",
            "run_environment": "apitest.cybersource.com",
            "merchantid": rec.cyber_merchant,
            "merchant_keyid": rec.cyber_key,
            "merchant_secretkey": rec.cyber_secret_key,
            "timeout": 1000,
        }
