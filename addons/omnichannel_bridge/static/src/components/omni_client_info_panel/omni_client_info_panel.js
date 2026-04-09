/** @odoo-module **/
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

function ensureActWindowViews(action) {
    if (!action || action.type !== "ir.actions.act_window") {
        return action;
    }
    if (Array.isArray(action.views) && action.views.length) {
        return action;
    }
    const vm = (action.view_mode || "form").toString();
    const modes = vm
        .split(",")
        .map((m) => m.trim())
        .filter(Boolean)
        .map((m) => (m === "tree" ? "list" : m));
    return { ...action, views: modes.map((mode) => [false, mode]) };
}

export class OmniClientInfoPanel extends Component {
    static template = "omnichannel_bridge.OmniClientInfoPanel";
    static props = {
        thread: { type: Object },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: false,
            card: null,
        });

        onWillStart(async () => {
            await this._load(this.props.thread?.id);
        });

        onWillUpdateProps(async (nextProps) => {
            if (nextProps.thread?.id !== this.props.thread?.id) {
                await this._load(nextProps.thread?.id);
            }
        });
    }

    async _load(channelId) {
        if (!channelId) {
            this.state.card = null;
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        this.state.error = false;
        try {
            this.state.card = await this.orm.call(
                "discuss.channel",
                "omni_get_client_info_for_channel",
                [channelId],
            );
        } catch (_e) {
            this.state.error = true;
        } finally {
            this.state.loading = false;
        }
    }

    async onRefreshClick() {
        if (!this.props.thread?.id) {
            return;
        }
        this.state.loading = true;
        this.state.error = false;
        try {
            this.state.card = await this.orm.call(
                "discuss.channel",
                "omni_refresh_client_info_for_channel",
                [this.props.thread.id],
            );
        } catch (_e) {
            this.state.error = true;
        } finally {
            this.state.loading = false;
        }
    }

    async onOpenPartnerClick() {
        if (!this.props.thread?.id) {
            return;
        }
        const action = await this.orm.call(
            "discuss.channel",
            "omni_action_open_client_from_panel",
            [this.props.thread.id],
        );
        if (action) {
            await this.action.doAction(ensureActWindowViews(action));
        }
    }
}
