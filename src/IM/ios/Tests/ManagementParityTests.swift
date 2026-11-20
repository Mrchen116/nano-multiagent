import Foundation
import Testing
@testable import NanoIM

struct ManagementParityTests {
    @Test func rebasingExclusionsRetainsConcurrentChangesAndOnlyAppliesLocalIntent() {
        let original = PersonalAgentPolicy(revision: 1, excluded_conversation_ids: ["old", "keep"])
        let latest = PersonalAgentPolicy(revision: 2, excluded_conversation_ids: ["old", "concurrent"])
        let rebased = latest.rebasing(["keep", "mine"], from: original)
        #expect(rebased == ["concurrent", "mine"])
    }

    @Test func nodeRecoveryAndCancellationReflectReportedOperation() throws {
        let data = Data(#"{"installation":"managed","current":{"version":"1"},"target":{"version":"2","sha256":"h"},"available":true,"reason":"available","install_command":"install","operation":{"id":"op","state":"failed","relay_gated":true,"cancel_requested":false}}"#.utf8)
        let update = try JSONDecoder().decode(ComputerUpdate.self, from: data)
        #expect(update.status == "recovery_required")
        #expect(!update.canStart && !update.canCancel)
    }

    @Test func editingOldAllowlistKeepsOtherGroupsAndEnablesNewSkills() {
        var draft = AgentDraft()
        draft.skills = ["keep"]; draft.skills_selection_mode = "explicit_allowlist"
        let options = ["keep", "new", "other"].map { AgentOption(name: $0) }
        let caps = AgentCapabilities(node_id: "n", models: [], skills: options, tools: [], features: [])
        let blocks = draft.changeCapabilities([.init(kind: "skill", name: "new", enabled: true)], capabilities: caps)
        #expect(blocks.isEmpty)
        #expect(draft.skills_selection_mode == "explicit_denylist")
        #expect(draft.skills == ["other"])
        #expect(draft.enabledSkills(candidates: ["keep", "new", "other", "future"]) == ["keep", "new", "future"])
    }

    @Test func cancellationUsesPersistedStageAndCannotInterruptSwitching() throws {
        func update(_ stage: String, cancelled: Bool = false) -> ComputerUpdate {
            .init(installation: "managed", reason: "available", install_command: "install",
                  current: .init(version: "1"), target: .init(version: "2", sha256: "hash", release_notes: nil),
                  available: true, operation: .init(id: "op", state: stage, cancel_requested: cancelled, relay_gated: false))
        }
        #expect(update("waiting").canCancel)
        #expect(!update("waiting", cancelled: true).canCancel)
        #expect(!update("switching").canCancel && !update("switching").canStart)
        #expect(update("failed").canStart)
    }

    @Test func savingUnrelatedFieldsKeepsAnExplicitApprovalOverride() throws {
        var draft = AgentDraft()
        draft.approval_mode = "cc"
        #expect(draft.payload(version: 2)["approval_mode"] == .string("cc"))
        draft.approval_mode = ""
        #expect(draft.payload(version: 2)["approval_mode"] == .null)
    }
}
