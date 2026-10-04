import Foundation

extension IMClient {
    func messages(_ id: String, before: String? = nil) async throws -> MessagePage {
        var query = [URLQueryItem(name: "limit", value: "60")]
        if let before { query.append(.init(name: "before_message_id", value: before)) }
        return try await get("/im/v1/conversations/\(id.pathComponent)/messages", query: query)
    }
    func createConversation(title: String, type: String, participants: [ActorRef], userID: String) async throws -> Conversation {
        struct Body: Encodable, Sendable { let title: String; let type: String; let participants: [ActorRef] }
        return try await send("/im/v1/conversations", body: Body(title: title, type: type,
            participants: [ActorRef(type: "user", id: userID)] + participants.filter { !($0.type == "user" && $0.id == userID) }))
    }
    func sendMessage(_ id: String, draft: PendingSend, userID: String) async throws -> ChatMessage {
        struct Body: Encodable, Sendable { let sender: ActorRef; let content: String; let attachments: [ChatAttachment] }
        let body = Body(sender: ActorRef(type: "user", id: userID), content: draft.content, attachments: draft.attachments)
        return try await request("/im/v1/conversations/\(id.pathComponent)/messages", method: "POST",
                                 body: JSONEncoder().encode(body), headers: ["Idempotency-Key": draft.key])
    }
    func upload(_ data: Data, fileName: String, contentType: String, conversationID: String) async throws -> ChatAttachment {
        try await request("/im/v1/uploads", method: "POST", body: data,
                          query: [.init(name: "file_name", value: fileName), .init(name: "conversation_id", value: conversationID)],
                          headers: ["Content-Type": contentType])
    }
}
