/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { OmniClientInfoPanel } from "./components/omni_client_info_panel/omni_client_info_panel";

const threadActionsRegistry = registry.category("mail.thread/actions");

threadActionsRegistry.add("omni-client-info", {
    component: OmniClientInfoPanel,
    condition(component) {
        const thread = component.thread;
        // Always expose the action in Discuss channels; panel decides if data is available.
        return thread?.model === "discuss.channel";
    },
    componentProps(_action, component) {
        return { thread: component.thread };
    },
    panelOuterClass: "o-omni-ClientInfoPanel",
    icon: "fa fa-fw fa-id-card-o",
    iconLarge: "fa-lg fa-id-card-o",
    name: _t("Картка клієнта"),
    nameActive: _t("Закрити"),
    sequence: 31,
    toggle: true,
});
