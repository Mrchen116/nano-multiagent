import Foundation

struct MessageInteractive: Codable, Sendable {
    let format: String
    let catalog_version: String
    let source: String
    var read_only: Bool?
    var superseded_by: String?
    var supersedes_message_id: String?
}

struct InteractionReplyInput: Codable, Sendable {
    let source_message_id: String
    var action_id: String?
    var event: JSONValue?
    let state: [String: JSONValue]
}

struct InteractionSelection: Sendable {
    let conversationID: String
    let source_message_id: String
    let state: [String: JSONValue]
    let editedAt: Double
}

struct InteractionDraft: Codable, Sendable {
    var can_interact: Bool?
    var read_only: Bool?
    var superseded_by: String?
    let draft_revision: Int
    var updated_at: String?
    let state: [String: JSONValue]
    var submission_message_id: String?
}

extension IMClient {
    func interactionDraft(_ cid: String, messageID: String) async throws -> InteractionDraft {
        try await get("/im/v1/conversations/\(cid.pathComponent)/messages/\(messageID.pathComponent)/interaction-state")
    }
    func saveInteractionDraft(_ cid: String, messageID: String, revision: Int, state: [String: JSONValue]) async throws -> InteractionDraft {
        struct Body: Encodable, Sendable { let expected_draft_revision: Int; let state: [String: JSONValue] }
        return try await send("/im/v1/conversations/\(cid.pathComponent)/messages/\(messageID.pathComponent)/interaction-state", method: "PUT",
                              body: Body(expected_draft_revision: revision, state: state))
    }
}

extension JSONValue {
    var foundationObject: Any { (try? JSONSerialization.jsonObject(with: JSONEncoder().encode(self), options: [.fragmentsAllowed])) ?? NSNull() }
    init(foundationObject: Any) throws {
        self = try JSONDecoder().decode(Self.self, from: JSONSerialization.data(withJSONObject: foundationObject, options: [.fragmentsAllowed]))
    }
}
