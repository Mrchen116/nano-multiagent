import Foundation
import Testing
@testable import NanoIM

struct AgentContractsTests {
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
        let caps = try JSONDecoder().decode(AgentCapabilities.self, from: Data(#"{"node_id":"n","models":[{"name":"m","provider":"p","reasoning":{"kind":"selectable","default":"high","levels":["low","high"]}}],"skills":[{"name":"guide","description":"Guide","default_on":true,"source_group":"global","location":"/skills/guide/SKILL.md"}],"tools":[{"name":"bash","description":"Shell","default_on":true}],"features":[],"platform_default_model":"m","default_workspace_template":"/agents/{agent_id}"}"#.utf8))
        var draft = AgentDraft()
        draft.agent_id = "worker"; draft.display_name = "Worker"; draft.work_mode = "global"
        draft.skills_selection_mode = "default_discovery"; draft.workspace_root = "/repo"
        let create = draft.payload(creating: true, customWorkspace: true, confirmed: true)
        #expect(create["confirm_existing_workspace"] == .bool(true))
        #expect(create["workspace_root"] == .string("/repo"))
        #expect(create["work_mode"] == .string("global"))
        #expect(create["skills_selection_mode"] == .string("default_discovery"))
        #expect(create["tool_allowlist"] == .array(["agent", "conversations", "inbox", "send_message"].map(JSONValue.string)))
        let preview = draft.previewPayload(capabilities: caps, creating: true, customWorkspace: true)
        #expect(preview["skill_ids"] == .array([.string("guide")]))
        #expect(preview["tool_ids"] == create["tool_allowlist"])
        #expect(preview["scenario"] == .string("direct"))
        #expect(preview["workspace_mode"] == .string("custom"))
        draft.skills_selection_mode = "explicit_allowlist"
        #expect(draft.previewPayload(capabilities: caps, creating: false, customWorkspace: false)["skill_ids"] == .array([]))
    }

    @Test func enablingFeatureAddsOnlyItsRequiredToolAndDisablingPreservesTool() {
        var draft = AgentDraft()
        let feature = AgentFeature(key: "memory_curation", label_i18n: "feature.memory_curation.label", help_i18n: "feature.memory_curation.help", default_on: true, available: false, requires_tool: "memory")
        draft.setFeature(feature, enabled: true)
        #expect(draft.payload()["tool_allowlist"] == .array([.string("memory")]))
        draft.setFeature(feature, enabled: false)
        #expect(draft.payload()["features"] == .object(["memory_curation": .bool(false)]))
        #expect(draft.payload()["tool_allowlist"] == .array([.string("memory")]))
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
