import Foundation

struct Conversation: Codable, Identifiable, Sendable, Hashable {
    var id: String
    var title: String
    var participants: [ActorRef]
    var participant_ids: [String]
    var type: String
    var direct_kind: String?
    var owner_id: String
    var creator_id: String
    var is_pinned: Bool
    var is_muted: Bool
    var unread_count: Int
    var last_message_preview: String?
    var last_message_at: String?
    var created_at: String
    var run_state: String?
    var source_agent_id: String?
    var source_node_id: String?
    var external_source: String?
    var external_chat_id: String?
    var category: String {
        if type == "direct" { return ["user-user", "user"].contains(direct_kind ?? "") ? "people" : "agent" }
        return !participants.isEmpty && participants.allSatisfy { $0.type == "agent" } ? "network" : "group"
    }
    func avatarName(selfID: String) -> String {
        guard type != "group" else { return title }
        let peer = participants.first { category == "agent" ? $0.type == "agent" : $0.type == "user" && ($0.user_id ?? $0.id) != selfID }
        return peer?.display_name ?? peer?.id ?? title
    }
}
struct ChatAttachment: Codable, Sendable, Hashable, Identifiable {
    var url: String
    var content_type: String?
    var file_name: String?
    var id: String { url }
}
struct AttachmentUpload: Identifiable, Sendable {
    let id = UUID()
    let data: Data?
    let fileName: String
    let contentType: String
    var uploading = false
    var error: String?
    var retryAt: Date?
    var retryable = true
}
struct ChatToolCall: Codable, Sendable, Identifiable {
    var id: String
    var name: String
    var status: String
    var input: JSONValue?
    var output: String?
    var detail: JSONValue?
    var reason: String?
    var approval: String?
    var emoji: String?
    var duration_ms: Double?
    var seq: Int?
}
struct ChatThinking: Codable, Sendable { var seq: Int; var text: String }
struct ChatPermissionOption: Codable, Sendable, Identifiable {
    var id: String; var label: String; var description: String
}
struct ChatPermission: Codable, Sendable, Identifiable {
    var request_id: String
    var tool_name: String
    var tool_input: JSONValue
    var question: String
    var options: [ChatPermissionOption]
    var status: String
    var decided_by: String?
    var decision: String?
    var agent_id: String?
    var id: String { request_id }
}
struct ChatMessage: Codable, Sendable, Identifiable {
    var id: String
    var conversation_id: String
    var sender: ActorRef
    var sender_user_id: String
    var sender_type: String
    var content: String
    var attachments: [ChatAttachment]
    var delivery_status: String
    var created_at: String
    var tool_calls: [ChatToolCall]?
    var thinking: [ChatThinking]?
    var background_returns: [JSONValue]?
    var reply_process: [JSONValue]?
    var permission_requests: [ChatPermission]?
    var token_usage: JSONValue?
    var elapsed_ms: Double?
    var kernel_message_id: String?
    var system_notice: JSONValue?
}
struct TimelineItem: Codable, Sendable, Identifiable {
    var type: String
    var message: ChatMessage?
    var boundaryID: String?
    var conversation_id: String?
    var agent_id: String?
    var before_message_id: String?
    var applied_at: String?
    var id: String { message?.id ?? boundaryID ?? "" }
    enum CodingKeys: String, CodingKey { case type, message, boundaryID = "id", conversation_id, agent_id, before_message_id, applied_at }
}
struct MessagePage: Codable, Sendable {
    var items: [TimelineItem]
    var next_before_message_id: String?
}
struct SyncSnapshot: Decodable, Sendable { var items: [Conversation]; var max_event_id: Int }
struct ChatCommandSet: Codable, Sendable, Identifiable {
    var agent_id: String; var display_name: String; var status: String
    var skills: [Skill]; var commands: [Command]
    var id: String { agent_id }
    struct Skill: Codable, Sendable, Identifiable { var skill_key: String; var name: String; var description: String; var id: String { skill_key } }
    struct Command: Codable, Sendable, Identifiable { var name: String; var description: String; var id: String { name } }
}
struct PendingSend: Sendable {
    var key = UUID().uuidString
    let content: String
    let attachments: [ChatAttachment]
}

/// Merge authoritative pages by stable identity; replay never appends a delta twice.
enum TimelineMerge {
    static func merge(current: [TimelineItem], page: [TimelineItem], older: Bool, discarded: Set<String>) -> [TimelineItem] {
        let byID = Dictionary((current + page).map { ($0.id, $0) }, uniquingKeysWith: { _, last in last })
        let retained = byID.values.filter { !discarded.contains($0.id) }
        let messages = retained.filter { $0.message != nil }.sorted {
            ($0.message?.created_at ?? "", $0.id) < ($1.message?.created_at ?? "", $1.id)
        }
        // Adoption happens after the request is cached; its marker still explains that request.
        let boundaries = Dictionary(grouping: retained.filter { $0.message == nil }, by: { $0.before_message_id ?? "" })
        let messageIDs = Set(messages.map(\.id))
        let unanchored = boundaries.filter { !messageIDs.contains($0.key) }.values.flatMap { $0 }.sorted { $0.id < $1.id }
        return unanchored + messages.flatMap { message in
            (boundaries[message.id] ?? []).sorted { $0.id < $1.id } + [message]
        }
    }
}
