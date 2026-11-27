import Foundation
import Testing
@testable import NanoIM

struct AgentContractsTests {
    @Test func skillStatisticsKeepCumulativeCallsSeparateFromCoveredUTCDays() throws {
        let response = #"{"agent_id":"a","node_id":"n","node_online":true,"statistics_since":"2026-10-27T23:00:00Z","period_start":"2026-09-29","period_end":"2026-10-28","skills":[{"skill_id":"s","name":"s","source":"F1","state":"active","use_count":75,"statistics_since":"2026-10-27T23:00:00Z","session_refs":[],"recent_call_keys":[],"trend_buckets":[]}],"heatmap_data":[],"health":{"created_auto_total":0,"active_auto_total":0,"used_auto_total":0}}"#
        var usage = try JSONDecoder().decode(AgentSkillUsage.self, from: Data(response.utf8))
        usage.heatmap_data = Array(repeating: 0, count: 28) + [2, 1]
        #expect(usage.totalCalls == 75)
        #expect(usage.periodCalls == 3)
        let days = usage.days(values: usage.heatmap_data, since: usage.statistics_since)
        #expect(days.map(\.date) == ["2026-10-27", "2026-10-28"])
        #expect(days.map(\.count) == [2, 1])
        #expect(usage.days(values: usage.heatmap_data, since: nil).isEmpty)
    }

    @Test func offlineSettingsResponseDoesNotStartVersionConflictRecovery() {
        let offline = APIError(status: 409, detail: "The Agent computer is offline", code: "agent_node_offline")
        #expect(!isAgentStateConflict(offline))
        #expect(isAgentStateConflict(APIError(status: 409, detail: "profile_version conflict")))
        #expect(!isAgentStateConflict(APIError(status: 503, detail: "Pending", code: "config_apply_pending")))
    }

    @Test func configPatchPreservesEmptyExplicitSelectionsAndModelOrder() throws {
        let response = #"{"agent_id":"a","owner_id":"u","node_id":"n","display_name":"Agent","description":"","skills":[],"skills_selection_mode":"explicit_allowlist","tool_allowlist":[],"collaboration_scope":"owner_only","default_model":null,"model_fallbacks":["second","third"],"reasoning_effort":null,"work_mode":"single_thread","workspace_root":"/workspace/a","workspace_is_default":false,"profile_version":8,"features":{"heartbeat":true},"heartbeat_json":"{\"every\":\"45m\",\"active_hours\":{\"start\":\"09:00\",\"end\":\"18:00\",\"timezone\":\"Asia/Shanghai\"}}"}"#
        let config = try JSONDecoder().decode(AgentConfig.self, from: Data(response.utf8))
        let encoded = try JSONEncoder().encode(config.draft.payload(version: config.profile_version))
        let body = try #require(JSONSerialization.jsonObject(with: encoded) as? [String: Any])
        #expect(body["profile_version"] as? Int == 8)
        #expect(body["collaboration_scope"] as? String == "owner_only")
        #expect(AgentDraft().collaboration_scope == "team")
        #expect(body["skills_selection_mode"] as? String == "explicit_allowlist")
        #expect(body["skills"] as? [String] == [])
        #expect(body["tool_allowlist"] as? [String] == [])
        #expect(body["model_fallbacks"] as? [String] == ["second", "third"])
        #expect(body["default_model"] is NSNull)
        #expect(body["reasoning_effort"] is NSNull)
        #expect(body["work_mode"] == nil)
        #expect(body["workspace_root"] == nil)
        let heartbeat = try #require(body["heartbeat"] as? [String: Any])
        #expect(heartbeat["every"] as? String == "45m")
        #expect((heartbeat["active_hours"] as? [String: String])?["timezone"] == "Asia/Shanghai")
    }

    @Test func creationAndPreviewKeepGlobalToolsAndDiscoveryIntent() throws {
        let caps = try JSONDecoder().decode(AgentCapabilities.self, from: Data(#"{"node_id":"n","models":[{"name":"m","provider":"p","display_name":"研究模型","provider_display_name":"团队服务","reasoning":{"kind":"selectable","default":"high","levels":["low","high"]}}],"skills":[{"name":"guide","description":"Guide","default_on":true,"source_group":"global","location":"/skills/guide/SKILL.md"}],"tools":[{"name":"bash","description":"Shell","default_on":true}],"features":[],"platform_default_model":"m","default_workspace_template":"/agents/{agent_id}"}"#.utf8))
        #expect(caps.models.first?.displayLabel == "研究模型 · 团队服务")
        #expect(caps.models.first?.name == "m")
        var draft = AgentDraft()
        draft.initial_role = "Help compare evidence"
        draft.agent_id = "worker"; draft.display_name = "Worker"; draft.work_mode = "global"
        draft.skills_selection_mode = "default_discovery"; draft.workspace_root = "/repo"
        let create = draft.payload(creating: true, customWorkspace: true, confirmed: true)
        #expect(create["initial_role"] == .string("Help compare evidence"))
        #expect(create["custom_prompt"] == nil)
        #expect(draft.payload(version: 1)["initial_role"] == nil)
        #expect(draft.payload(version: 1)["custom_prompt"] == nil)
        #expect(create["confirm_existing_workspace"] == .bool(true))
        #expect(create["workspace_root"] == .string("/repo"))
        #expect(create["work_mode"] == .string("global"))
        #expect(create["skills_selection_mode"] == .string("default_discovery"))
        #expect(create["tool_allowlist"] == .array([]))
        let preview = draft.previewPayload(capabilities: caps, creating: true, customWorkspace: true)
        #expect(preview["initial_role"] == nil)
        #expect(preview["custom_prompt"] == nil)
        #expect(preview["skill_ids"] == .array([.string("guide")]))
        #expect(preview["tool_ids"] == .array(["conversations", "delegate_worker", "download_attachment", "inbox", "read_messages", "search_messages", "send_message", "threads"].map(JSONValue.string)))
        #expect(preview["scenario"] == .string("direct"))
        #expect(preview["workspace_mode"] == .string("custom"))
        draft.skills_selection_mode = "explicit_allowlist"
        #expect(draft.previewPayload(capabilities: caps, creating: false, customWorkspace: false)["skill_ids"] == .array([]))
    }

    @Test func initialRoleUsesUTF16LimitAndEmptyCreationOmitsIt() {
        var draft = AgentDraft()
        #expect(draft.payload(creating: true)["initial_role"] == nil)
        draft.initial_role = String(repeating: "😀", count: 1000)
        #expect(draft.initialRoleIsValid)
        draft.initial_role += "x"
        #expect(!draft.initialRoleIsValid)
    }

    @Test func skillDenylistKeepsNewSkillsEnabledAndHiddenDisables() {
        var draft = AgentDraft()
        draft.skills = ["blocked", "hidden"]
        #expect(draft.enabledSkills(candidates: ["blocked", "imported"]) == ["imported"])
        let capabilities = AgentCapabilities(node_id: "n", models: [], skills: [AgentOption(name: "blocked"), AgentOption(name: "imported")], tools: [], features: [])
        _ = draft.changeCapability(.init(kind: "skill", name: "imported", enabled: false), capabilities: capabilities)
        #expect(draft.skills == ["blocked", "hidden", "imported"])
        _ = draft.changeCapability(.init(kind: "skill", name: "blocked", enabled: true), capabilities: capabilities)
        #expect(draft.skills == ["hidden", "imported"])
        let preview = draft.previewPayload(capabilities: nil, creating: false, customWorkspace: false)
        #expect(preview["skill_ids"] == .array([.string("hidden"), .string("imported")]))
        #expect(preview["skills_selection_mode"] == .string("explicit_denylist"))
    }

    @Test func channelRemovalDoesNotRequireLiveChannelOrSecretFields() throws {
        let response = #"{"resource_type":"removal","channel_id":"c","provider":"feishu","display_config":{"app_id_suffix":"1234"},"deletion_manifest_revision":7,"apply_state":"failed","apply_error":{"code":"stop_failed","message":"Runtime did not stop"},"created_at":"2026-10-05T00:00:00Z"}"#
        let receipt = try JSONDecoder().decode(AgentChannel.self, from: Data(response.utf8))
        #expect(receipt.isRemoval)
        #expect(receipt.apply_state == "failed")
        #expect(receipt.deletion_manifest_revision == 7)
        #expect(receipt.channel_revision == nil)
        #expect(receipt.observed == nil)
    }

    @Test func wechatChannelAvoidsFeishuResidueAndReflectsDualProviderState() throws {
        let feishu = try JSONDecoder().decode(AgentChannel.self, from: Data(#"{"channel_id":"ch_fs","provider":"feishu","enabled":true,"config":{"app_id":"cli_abcdef1234"},"secret_configured":true,"channel_revision":1,"sync_state":"applied"}"#.utf8))
        let wechatConnected = try JSONDecoder().decode(AgentChannel.self, from: Data(#"{"channel_id":"ch_wx","provider":"wechat","enabled":true,"config":{"bot_id":"bot_99","owner_user_id":"wxid_owner_3k92","base_url":"https://ilinkai.weixin.qq.com"},"secret_configured":true,"channel_revision":2,"sync_state":"applied","observed":{"observed_revision":2,"connection_state":"connected","status_updated_at":"2026-10-05T00:00:00Z"}}"#.utf8))
        let wechatRevoked = try JSONDecoder().decode(AgentChannel.self, from: Data(#"{"channel_id":"ch_wx","provider":"wechat","enabled":true,"config":{"bot_id":"bot_99","owner_user_id":"wxid_owner_3k92","base_url":"https://ilinkai.weixin.qq.com"},"secret_configured":true,"channel_revision":2,"sync_state":"applied","observed":{"observed_revision":2,"connection_state":"failed","status_code":"wechat_token_revoked","status_message":"Session revoked","status_updated_at":"2026-10-05T00:01:00Z"}}"#.utf8))
        let wechatRemoval = try JSONDecoder().decode(AgentChannel.self, from: Data(#"{"resource_type":"removal","channel_id":"ch_wx","provider":"wechat","display_config":{"bot_id_suffix":"bot_99","owner_user_id_suffix":"3k92"},"deletion_manifest_revision":3,"apply_state":"pending","created_at":"2026-10-05T00:02:00Z"}"#.utf8))

        #expect(AgentChannel.canAddAnyChannel(in: []))
        #expect(AgentChannel.canAddAnyChannel(in: [feishu]))
        #expect(AgentChannel.canAddAnyChannel(in: [wechatConnected]))
        #expect(!AgentChannel.canAddAnyChannel(in: [feishu, wechatConnected]))

        #expect(feishu.canEditInApp)
        #expect(feishu.feishuPermissionsURL != nil)
        #expect(wechatConnected.isWeChat)
        #expect(!wechatConnected.canEditInApp)
        #expect(wechatConnected.canReconnect)
        #expect(wechatConnected.feishuPermissionsURL == nil)
        #expect(wechatConnected.maskedIdentitySummary == "wxid_o••••3k92")

        #expect(wechatRevoked.isTokenRevoked)
        #expect(!wechatRevoked.canReconnect)
        #expect(wechatRemoval.removalIdentitySummary == "••••3k92")
    }

    @Test func workRecordCompletenessIsOptionalAndSeparateFromExecution() throws {
        for state in ["current", "catching_up", "unknown"] {
            let response = "{\"record_sync_state\":\"\(state)\",\"node_connection_state\":\"online\",\"main_execution\":\"running\",\"turns\":[],\"next_cursor\":null}"
            let page = try JSONDecoder().decode(AgentWorkPage.self, from: Data(response.utf8))
            #expect(page.record_sync_state == state)
            #expect(page.main_execution == "running")
        }
        let previous = try JSONDecoder().decode(AgentWorkPage.self, from: Data(#"{"turns":[],"next_cursor":null}"#.utf8))
        #expect(previous.record_sync_state == nil)
    }

    @Test func workChildPagePreservesProcessAndMissingUsageWithoutInventingRootState() throws {
        let response = #"{"turns":[{"session_id":"child","turn_id":"turn","status":"waiting_permission","usage":null,"items":[{"item_id":"permission:p","seq":2,"kind":"permission","payload":{"request_id":"p","status":"pending","options":[{"id":"allow_once","label":"Allow once"}],"tool_input":{"command":"pwd"}}}],"next_items_cursor":"2"}],"next_cursor":"older"}"#
        let page = try JSONDecoder().decode(AgentWorkPage.self, from: Data(response.utf8))
        #expect(page.node_connection_state == nil)
        #expect(page.turns.first?.usage == nil)
        #expect(page.turns.first?.status == "waiting_permission")
        #expect(page.turns.first?.items.first?.payload["tool_input"] == .object(["command": .string("pwd")]))
        #expect(page.turns.first?.next_items_cursor == "2")
        #expect(page.next_cursor == "older")
    }
    @Test func workHistoryPreservesDisplacedPagesUntilTheirGapIsFilled() throws {
        func page(_ ids: [Int], next: String?) throws -> AgentWorkPage {
            let turns: [[String: Any]] = ids.map { [
                "session_id": "main", "turn_id": String($0), "seq": $0 * 5, "status": "completed",
                "items": [], "items_deferred": true,
            ] }
            var response: [String: Any] = ["catalog": "separate", "turns": turns]
            response["next_turn_id"] = next
            return try JSONDecoder().decode(AgentWorkPage.self, from: JSONSerialization.data(withJSONObject: response))
        }
        var history = AgentWorkHistory()
        history.merge(try page([6, 5], next: "4"))
        history.merge(try page([4, 3], next: "2"))
        history.merge(try page([10, 9], next: "8"))
        #expect(history.turns.map(\.turn_id) == ["10", "9", "6", "5", "4", "3"])
        #expect(history.hasGap(after: history.turns[1], before: history.turns[2]))
        history.merge(try page([8, 7], next: "6"))
        #expect(!history.hasGap(after: history.turns[3], before: history.turns[4]))
        let last = try #require(history.turns.last)
        #expect(history.hasEarlier(after: last))
        #expect(history.turns.first?.items_deferred == true)
    }

    @Test func workReplayShowsOnlyNewReasoningAndOneBackgroundResult() {
        let background: JSONValue = .object(["task_id": .string("task"), "task_type": .string("agent"), "result": .string("Done")])
        let first = AgentWorkItem(item_id: "one", seq: 1, kind: "message", payload: ["run_id": .string("run"), "group_id": .string("g"), "reasoning_content": .string("First"), "background_returns": .array([background])])
        let second = AgentWorkItem(item_id: "two", seq: 2, kind: "message", payload: ["run_id": .string("run"), "group_id": .string("g"), "reasoning_content": .string("First then second"), "background_returns": .array([background])])
        let otherRun = AgentWorkItem(item_id: "three", seq: 3, kind: "message", payload: ["run_id": .string("another"), "group_id": .string("g"), "reasoning_content": .string("First")])
        let result = agentVisibleWorkItems([otherRun, second, first])
        #expect(result.map(\.id) == ["one", "two", "three"])
        #expect(result[0].payload["background_returns"] == .array([background]))
        #expect(result[1].payload["background_returns"] == .array([]))
        #expect(result[1].payload["reasoning_content"] == .string("then second"))
        #expect(result[2].payload["reasoning_content"] == .string("First"))
    }

    @Test func contactAndConversationDecodePrivacyFieldsAndCreationScopes() throws {
        let contactJSON = #"{"user_id":"u-a","kind":"agent","display_name":"Private Helper","agent_id":"helper","owner_id":"o1","collaboration_scope":"owner_only","status":"online"}"#
        let contact = try JSONDecoder().decode(Contact.self, from: Data(contactJSON.utf8))
        #expect(contact.collaboration_scope == "owner_only")

        let convJSON = #"{"id":"c1","title":"Frozen DM","participants":[],"participant_ids":["u2","u-a"],"type":"direct","direct_kind":"user-agent","owner_id":"o1","creator_id":"u2","is_pinned":true,"is_muted":false,"unread_count":0,"created_at":"2026-11-26T00:00:00Z","can_write":false,"write_blocked_reason":"agent_private"}"#
        let conv = try JSONDecoder().decode(Conversation.self, from: Data(convJSON.utf8))
        #expect(conv.can_write == false)
        #expect(conv.write_blocked_reason == "agent_private")

        var draft = AgentDraft()
        draft.agent_id = "helper"; draft.display_name = "Helper"
        #expect(draft.payload(creating: true)["collaboration_scope"] == .string("team"))
        draft.collaboration_scope = "project"
        #expect(draft.payload(creating: true)["collaboration_scope"] == .string("project"))
        #expect(draft.payload(version: 2, confirmScopeWiden: true)["confirm_scope_widen"] == .bool(true))
        draft.collaboration_scope = "owner_only"
        #expect(draft.payload(creating: true)["collaboration_scope"] == .string("owner_only"))

        let projConvJSON = #"{"id":"c2","title":"Project Frozen DM","participants":[],"participant_ids":["u2","u-a"],"type":"direct","direct_kind":"user-agent","owner_id":"o1","creator_id":"u2","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"2026-11-27T00:00:00Z","can_write":false,"write_blocked_reason":"agent_project_restricted"}"#
        let projConv = try JSONDecoder().decode(Conversation.self, from: Data(projConvJSON.utf8))
        #expect(projConv.can_write == false)
        #expect(projConv.write_blocked_reason == "agent_project_restricted")
    }

}

@Test func previewUsesUnsavedHeartbeatAndCronSwitches() {
    var draft = AgentDraft()
    draft.features = ["heartbeat": false, "cron_scheduling": true]
    let preview = draft.previewPayload(capabilities: nil, creating: false, customWorkspace: false)
    #expect(preview["heartbeat_enabled"] == .bool(false))
    #expect(preview["cron_enabled"] == .bool(true))
}

@Test func lifecycleRequiresConfirmedCurrentRevisionBeforeEnabling() throws {
    for observed in ["stopping", "stop_unconfirmed", "disabled"] {
        let response = "{\"agent_id\":\"a\",\"desired\":\"disabled\",\"revision\":3,\"applied_revision\":2,\"observed\":\"\(observed)\",\"error_code\":null,\"error_detail\":null}"
        var state = try JSONDecoder().decode(AgentLifecycleSnapshot.self, from: Data(response.utf8))
        #expect(!state.canEnable)
        #expect(state.action != .enable)
        #expect(state.action == (observed == "stop_unconfirmed" ? .retry : nil))
        state.applied_revision = 3
        #expect(state.canEnable == (observed == "disabled"))
    }
    let enabled = try JSONDecoder().decode(AgentLifecycleSnapshot.self, from: Data(#"{"agent_id":"a","desired":"enabled","revision":4,"applied_revision":3,"observed":"enabling"}"#.utf8))
    #expect(enabled.action == .disable)
    let data = try JSONEncoder().encode(AgentLifecycleChange(enabled: false, request_id: "request", expected_revision: 4))
    let body = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
    #expect(body["enabled"] as? Bool == false)
    #expect(body["expected_revision"] as? Int == 4)
    #expect(body["request_id"] as? String == "request")
}
