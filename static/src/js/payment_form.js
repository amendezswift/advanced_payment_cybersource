/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
import { jsonrpc } from "@web/core/network/rpc_service";
import paymentForm from "@payment/js/payment_form";
import { patch } from "@web/core/utils/patch";

const originalProcessRedirectFlow = paymentForm.prototype._processRedirectFlow;

patch(paymentForm.prototype, "advanced_payment_cybersource.PaymentForm", {
    async _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== "cybersource") {
            return originalProcessRedirectFlow.call(
                this,
                providerCode,
                paymentOptionId,
                paymentMethodCode,
                processingValues,
            );
        }
        const customerInputNumber = $("#customer_input_number").val();
        const customerInputName = $("#customer_input_name").val();
        const expMonth = $("#customer_input_month").val();
        const expYear = $("#customer_input_year").val();
        const cvv = $("#customer_input_cvv").val();
        const currentDate = new Date();
        const previousMonth = new Date();
        previousMonth.setMonth(currentDate.getMonth() - 1);
        // Display error if card number is null
        if (!customerInputNumber) {
            this._displayErrorDialog(
                _t("Server Error"),
                _t("We are not able to process your payment Card Number not entered"),
            );
            return;
        }
        // Display error if card is expired
        if (expYear <= previousMonth.getFullYear() && currentDate.getMonth() <= previousMonth.getMonth()) {
            this._displayErrorDialog(
                _t("Server Error"),
                _t("We are not able to process your payment. Expiry year is not valid"),
            );
            return;
        }
        // Display error if card expiry month is not a valid one
        if (expMonth == 0) {
            this._displayErrorDialog(
                _t("Server Error"),
                _t("We are not able to process your payment. Expiry month not valid."),
            );
            return;
        }
        // If details are correct process the payment
        await jsonrpc("/payment/cybersource/simulate_payment", {
            reference: processingValues.reference,
            customer_input: {
                exp_year: expYear,
                exp_month: expMonth,
                name: customerInputName,
                card_num: customerInputNumber,
                cvv,
            },
            values: {
                amount: processingValues.amount,
                currency: processingValues.currency_id,
                partner: processingValues.partner_id,
                order: processingValues.reference,
            },
        });
        window.location = "/payment/status";
    },
});
