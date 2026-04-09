/** @odoo-module **/
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

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
        const partner = this.state.card?.partner || {};
        if (partner.id) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "res.partner",
                res_id: partner.id,
                views: [[false, "form"]],
                target: "current",
            });
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_name: this.state.card?.identity?.display_name || this.state.card?.thread_name || "",
                default_email: this.state.card?.identity?.booking_email || "",
            },
        });
    }
}
