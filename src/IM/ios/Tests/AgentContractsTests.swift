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
        let response = #"{"agent_id":"a","owner_id":"u","node_id":"n","display_name":"Agent","description":"","skills":[],"skills_selection_mode":"explicit_allowlist","tool_allowlist":[],"group_reply_policy":"NO_REPLY","default_model":null,"model_fallbacks":["second","third"],"reasoning_effort":null,"work_mode":"single_thread","workspace_root":"/workspace/a","workspace_is_default":false,"profile_version":8,"features":{"heartbeat":true},"custom_prompt":"Keep this","heartbeat_json":"{\"every\":\"45m\",\"active_hours\":{\"start\":\"09:00\",\"end\":\"18:00\",\"timezone\":\"Asia/Shanghai\"}}"}"#
        let config = try JSONDecoder().decode(AgentConfig.self, from: Data(response.utf8))
        let encoded = try JSONEncoder().encode(config.draft.payload(version: config.profile_version))
        let body = try #require(JSONSerialization.jsonObject(with: encoded) as? [String: Any])
        #expect(body["profile_version"] as? Int == 8)
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
        draft.agent_id = "worker"; draft.display_name = "Worker"; draft.work_mode = "global"
        draft.skills_selection_mode = "default_discovery"; draft.workspace_root = "/repo"
        let create = draft.payload(creating: true, customWorkspace: true, confirmed: true)
        #expect(create["confirm_existing_workspace"] == .bool(true))
        #expect(create["workspace_root"] == .string("/repo"))
        #expect(create["work_mode"] == .string("global"))
        #expect(create["skills_selection_mode"] == .string("default_discovery"))
        #expect(create["tool_allowlist"] == .array(["conversations", "inbox", "send_message", "subagent"].map(JSONValue.string)))
        let preview = draft.previewPayload(capabilities: caps, creating: true, customWorkspace: true)
        #expect(preview["skill_ids"] == .array([.string("guide")]))
        #expect(preview["tool_ids"] == create["tool_allowlist"])
        #expect(preview["scenario"] == .string("direct"))
        #expect(preview["workspace_mode"] == .string("custom"))
        draft.skills_selection_mode = "explicit_allowlist"
        #expect(draft.previewPayload(capabilities: caps, creating: false, customWorkspace: false)["skill_ids"] == .array([]))
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
