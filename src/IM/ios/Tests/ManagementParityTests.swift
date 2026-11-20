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

    @Test func savingUnrelatedFieldsKeepsAnExplicitApprovalOverride() throws {
        var draft = AgentDraft()
        draft.approval_mode = "cc"
        #expect(draft.payload(version: 2)["approval_mode"] == .string("cc"))
        draft.approval_mode = ""
        #expect(draft.payload(version: 2)["approval_mode"] == .null)
    }
}
