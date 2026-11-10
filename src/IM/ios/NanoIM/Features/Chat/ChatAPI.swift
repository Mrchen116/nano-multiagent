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
    nonisolated func prepareMessage(_ draft: PendingSend, userID: String, participants: [ActorRef] = [], interaction: InteractionReplyInput? = nil) throws -> PendingSend {
        struct Body: Encodable, Sendable {
            let sender: ActorRef; let content: String; let attachments: [ChatAttachment]; let timezone: String
            let interaction_reply: InteractionReplyInput?
        }
        var frozen = draft
        if frozen.requestBody == nil {
            frozen.requestBody = try JSONEncoder().encode(Body(sender: ActorRef(type: "user", id: userID),
                content: ChatText.wire(draft.content, participants: participants), attachments: draft.attachments,
                timezone: TimeZone.autoupdatingCurrent.identifier, interaction_reply: interaction))
        }
        return frozen
    }
    func sendMessage(_ id: String, draft: PendingSend, userID: String, participants: [ActorRef] = []) async throws -> ChatMessage {
        let frozen = try prepareMessage(draft, userID: userID, participants: participants)
        do {
            return try await request("/im/v1/conversations/\(id.pathComponent)/messages", method: "POST",
                                     body: frozen.requestBody, headers: ["Idempotency-Key": frozen.key])
        } catch let error as APIError where error.status == 422 && error.code == "interaction_background_too_large" {
            throw APIError(status: error.status, detail: L(
                "待发送的卡片背景过大，消息尚未发送。请缩减卡片内容后重试；如需清除待发背景，请在做过改动的设备上离开此聊天。正文和卡片编辑都会保留。",
                "Card background is too large; the message was not sent. Reduce card content and retry, or leave this chat on the devices where you edited cards to clear their pending backgrounds. Your message and card edits are kept."), code: error.code)
        }
    }
    /// Older servers and revoked conversations do not make leaving a chat fail visibly.
    func discardInteractionBackground(_ id: String, through: String) async throws -> Bool {
        do {
            let _: EmptyResponse = try await send("/im/v1/conversations/\(id.pathComponent)/interaction-background/discard", body: ["through": through])
            return true
        } catch let error as APIError where [404, 501].contains(error.status) { return false }
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
