/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { jsonrpc } from "@web/core/network/rpc_service";
import { patch } from "@web/core/utils/patch";
import { PaymentForm } from "@payment/js/payment_form";

const CYBERSOURCE_FIELDS = {
    number: "cybersource_card_number",
    holder: "cybersource_card_holder",
    month: "cybersource_exp_month",
    year: "cybersource_exp_year",
    cvv: "cybersource_cvv",
};

patch(PaymentForm.prototype, "payment_cybersource_modern", {
    async _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== "cybersource") {
            return await super._processRedirectFlow(...arguments);
        }

        const cardNumber = this._readField(CYBERSOURCE_FIELDS.number).replaceAll(" ", "");
        const holderName = this._readField(CYBERSOURCE_FIELDS.holder);
        const expMonth = this._readField(CYBERSOURCE_FIELDS.month);
        const expYear = this._readField(CYBERSOURCE_FIELDS.year);
        const cvv = this._readField(CYBERSOURCE_FIELDS.cvv);

        const validationError = this._validateCardDetails(cardNumber, holderName, expMonth, expYear, cvv);
        if (validationError) {
            this._displayErrorDialog(_t("Payment error"), validationError);
            return false;
        }

        try {
            const payload = {
                reference: processingValues.reference,
                customer_input: {
                    card_num: cardNumber,
                    exp_month: expMonth,
                    exp_year: expYear,
                    cvv,
                    name: holderName,
                },
                values: {
                    amount: processingValues.amount,
                    currency: processingValues.currency_id,
                    partner: processingValues.partner_id,
                },
            };
            const response = await jsonrpc("/payment/cybersource/process", payload);
            if (response?.success) {
                window.location = "/payment/status";
                return true;
            }
            this._displayErrorDialog(
                _t("Payment declined"),
                response?.message || _t("CyberSource declined the transaction."),
            );
            return false;
        } catch (error) {
            console.error("CyberSource payment error", error); // eslint-disable-line no-console
            this._displayErrorDialog(
                _t("Server Error"),
                _t("We were unable to contact CyberSource. Please try again."),
            );
            return false;
        }
    },

    _readField(id) {
        const element = document.getElementById(id);
        return element ? element.value.trim() : "";
    },

    _validateCardDetails(cardNumber, holderName, expMonth, expYear, cvv) {
        if (!holderName) {
            return _t("Please enter the card holder name.");
        }
        if (!cardNumber) {
            return _t("Please enter a valid card number.");
        }
        if (!expMonth || !expYear) {
            return _t("Please provide the card expiry date.");
        }
        const month = Number.parseInt(expMonth, 10);
        const year = Number.parseInt(expYear, 10);
        if (!Number.isInteger(month) || month < 1 || month > 12) {
            return _t("The expiry month must be between 1 and 12.");
        }
        const now = new Date();
        const currentYear = now.getFullYear();
        const currentMonth = now.getMonth() + 1;
        if (!Number.isInteger(year) || year < currentYear || year > currentYear + 20) {
            return _t("The expiry year is not valid.");
        }
        if (year === currentYear && month < currentMonth) {
            return _t("The card has expired.");
        }
        if (!cvv) {
            return _t("Please provide the card security code (CVV).");
        }
        return null;
    },
});

