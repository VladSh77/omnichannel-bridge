/** @odoo-module **/
import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    omniProvider: "",
    omniExternalThreadId: "",
    omniCustomerPartnerId: false,

    update(data) {
        super.update(data);
        if ("omni_provider" in data) {
            this.omniProvider = data.omni_provider || "";
        }
        if ("omni_external_thread_id" in data) {
            this.omniExternalThreadId = data.omni_external_thread_id || "";
        }
        if ("omni_customer_partner_id" in data) {
            this.omniCustomerPartnerId = data.omni_customer_partner_id || false;
        }
    },
});
