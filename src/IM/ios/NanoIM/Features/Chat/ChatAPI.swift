import Foundation

extension IMClient {
    func messages(_ id: String, before: String? = nil) async throws -> MessagePage {
        var query = [URLQueryItem(name: "limit", value: "60")]
        if let before { query.append(.init(name: "before_message_id", value: before)) }
        return try await get("/im/v1/conversations/\(id.pathComponent)/messages", query: query)
    }
    func createConversation(title: String, type: String, participants: [ActorRef], userID: String, visibility: String = "public") async throws -> Conversation {
        struct Body: Encodable, Sendable { let title: String; let type: String; let participants: [ActorRef]; let visibility: String }
        return try await send("/im/v1/conversations", body: Body(title: title, type: type,
            participants: [ActorRef(type: "user", id: userID)] + participants.filter { !($0.type == "user" && $0.id == userID) }, visibility: visibility))
    }
    nonisolated func prepareMessage(_ draft: PendingSend, userID: String, participants: [ActorRef] = [], contexts: [InteractionContextInput] = [], interaction: InteractionReplyInput? = nil) throws -> PendingSend {
        struct Body: Encodable, Sendable {
            let sender: ActorRef; let content: String; let attachments: [ChatAttachment]; let timezone: String
            let interaction_contexts: [InteractionContextInput]?
            let interaction_reply: InteractionReplyInput?
        }
        var frozen = draft
        if frozen.requestBody == nil {
            frozen.requestBody = try JSONEncoder().encode(Body(sender: ActorRef(type: "user", id: userID),
                content: ChatText.wire(draft.content, participants: participants), attachments: draft.attachments,
                timezone: TimeZone.autoupdatingCurrent.identifier, interaction_contexts: contexts.isEmpty ? nil : contexts, interaction_reply: interaction))
        }
        return frozen
    }
    func sendMessage(_ id: String, draft: PendingSend, userID: String, participants: [ActorRef] = []) async throws -> ChatMessage {
        let frozen = try prepareMessage(draft, userID: userID, participants: participants)
        return try await request("/im/v1/conversations/\(id.pathComponent)/messages", method: "POST",
                                 body: frozen.requestBody, headers: ["Idempotency-Key": frozen.key])
    }
    func lookupMessageAttempt(_ id: String, key: String) async throws -> ChatMessage? {
        do { return try await get("/im/v1/conversations/\(id.pathComponent)/message-attempts/\(key.pathComponent)") }
        catch let error as APIError where error.status == 404 { return nil }
    }
    func upload(_ data: Data, fileName: String, contentType: String, conversationID: String) async throws -> ChatAttachment {
        try await request("/im/v1/uploads", method: "POST", body: data,
                          query: [.init(name: "file_name", value: fileName), .init(name: "conversation_id", value: conversationID)],
                          headers: ["Content-Type": contentType])
    }
}
