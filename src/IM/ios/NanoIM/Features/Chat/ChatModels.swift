import Foundation

struct ChatCardPreview: Codable, Sendable, Hashable {
    var title: String?
}

/// Only task notices have the server-generated actor prefix and task link.
struct ChatPreviewNotice: Codable, Sendable, Hashable {
    let kind: String?
    let graph_id: String?
    let change_kinds: [String]?

    func summary(content: String?) -> String? {
        guard kind == "task_graph" else { return nil }
        let changes = change_kinds ?? []
        let action: String
        if changes.contains("created") { action = L("新建任务", "Task created") }
        else if changes.contains("deleted") { action = L("任务已删除", "Task deleted") }
        else if changes.contains("assignment") { action = L("任务分配更新", "Task assignment updated") }
        else if changes.contains("status") { action = L("任务状态更新", "Task status updated") }
        else { action = L("任务更新", "Task updated") }
        // The server caps previews at 120 characters. Require a link to this graph
        // before using its label, as the truncated content alone is ambiguous.
        guard let graph_id, !graph_id.isEmpty, let content, let start = content.range(of: "：["),
              let end = content.range(of: "](/tasks/" + graph_id, range: start.upperBound..<content.endIndex) else { return action }
        let title = MarkdownContent.copy(String(content[start.upperBound..<end.lowerBound]))
        return title.isEmpty ? action : action + " · " + title
    }
}

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
    var last_message_sender_name: String?
    var last_message_card: ChatCardPreview?
    var last_message_system_notice: ChatPreviewNotice?
    var last_message_at: String?
    var created_at: String
    var run_state: String?
    var source_agent_id: String?
    var source_node_id: String?
    var external_source: String?
    var external_chat_id: String?
    var visibility: String?
    var dissolved_at: String?
    var is_member: Bool?
    var can_write: Bool?
    var write_blocked_reason: String? = nil
    var is_observer: Bool?
    var can_change_visibility: Bool?
    var execution_cleanup_revision: Int?
    var category: String {
        if type == "direct" { if direct_kind == "agent-agent" { return "network" }; return ["user-user", "user"].contains(direct_kind ?? "") ? "people" : "agent" }
        return !participants.isEmpty && participants.allSatisfy { $0.type == "agent" } ? "network" : "group"
    }
    var peerAgent: ActorRef? { type == "direct" ? participants.first { $0.type == "agent" } : nil }

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
struct MessageReceipt: Codable, Sendable, Identifiable {
    enum Status: String, Codable, Sendable { case sent, received, read }
    var recipient: ActorRef?
    var recipient_id: String
    var display_name: String
    var status: Status
    var id: String { recipient_id }
}

struct ChatReply: Codable, Sendable, Equatable {
    let message_id: String
    let sender: ActorRef
    let content: String
    let attachments: [ChatAttachment]

    func preview(participants: [ActorRef]) -> String {
        let text = content.trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty { return ChatText.display(String(text.prefix(180)), participants: participants) }
        let names = attachments.map { file in
            file.file_name ?? (file.content_type?.hasPrefix("image/") == true ? L("图片", "Image") : L("文件", "File"))
        }
        return names.isEmpty ? L("消息", "Message") : names.joined(separator: " · ")
    }
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
    var reply_to: ChatReply?
    var work_record_deleted: Bool?
    var availableReply: ChatReply? {
        guard ["agent", "user"].contains(sender_type), ["completed", "sent", "pending"].contains(delivery_status) else { return nil }
        return ChatReply(message_id: id, sender: sender, content: String(content.trimmingCharacters(in: .whitespacesAndNewlines).prefix(180)), attachments: attachments)
    }
    var permission_requests: [ChatPermission]?
    var token_usage: JSONValue?
    var elapsed_ms: Double?
    var kernel_message_id: String?
    var system_notice: JSONValue?
    var interactive: MessageInteractive?
    var interaction_reply: JSONValue?
    var pa_agent_id: String?
    var receipts_requested: Bool?
    var receipts: [MessageReceipt]?
    var delegation: JSONValue?
    var task_cards: [TaskCardRef]? = nil
    var thread_root_message_id: String?
    var thread: ThreadSummary?
    var canStartThread: Bool {
        thread_root_message_id == nil && ["agent", "user"].contains(sender_type) && ["completed", "sent", "pending"].contains(delivery_status)
    }
}
struct ThreadParticipant: Codable, Sendable { var actor: ActorRef?; var id: String; var display_name: String }
struct ThreadSummary: Codable, Sendable { var reply_count: Int; var latest_preview: String?; var latest_at: String?; var participants: [ThreadParticipant]? }
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
struct ThreadPage: Codable, Sendable { var following: Bool; var items: [TimelineItem] }
struct MessagePage: Codable, Sendable {
    var items: [TimelineItem]
    var next_before_message_id: String?
    var execution_cleanup_revision: Int?
}
struct SyncSnapshot: Decodable, Sendable {
    var items: [Conversation]
    var max_event_id: Int
    var execution_cleanup_revisions: [String: Int]?
}
struct ChatCommandSet: Codable, Sendable, Identifiable {
    var agent_id: String; var display_name: String; var status: String
    var skills: [Skill]; var commands: [Command]
    var id: String { agent_id }
    struct Skill: Codable, Sendable, Identifiable { var skill_key: String; var name: String; var description: String; var id: String { skill_key } }
    struct Command: Codable, Sendable, Identifiable { var name: String; var description: String; var id: String { name } }
}
struct PendingSend: Codable, Sendable {
    var key = UUID().uuidString
    let content: String
    let attachments: [ChatAttachment]
    var requestBody: Data?
    var reply: ChatReply?
}

enum ChatTimelinePresentation {
    /// Group nearby messages, retaining a time marker when the local date changes.
    static func timestampMessageIDs(in items: [TimelineItem], calendar: Calendar = .current) -> Set<String> {
        var dates = NanoDateParser()
        var result = Set<String>()
        var previous: Date?
        for item in items {
            guard let message = item.message, message.system_notice == nil,
                  let date = dates.date(from: message.created_at) else { continue }
            if let previous {
                if !calendar.isDate(date, inSameDayAs: previous) || date.timeIntervalSince(previous) >= 300 { result.insert(message.id) }
            } else {
                result.insert(message.id)
            }
            previous = date
        }
        return result
    }
}

/// Merge authoritative pages by stable identity; replay never appends a delta twice.
enum TimelineMerge {
    static func merge(current: [TimelineItem], page: [TimelineItem], older: Bool, discarded: Set<String>) -> [TimelineItem] {
        let byID = Dictionary((current + page).map { ($0.id, $0) }, uniquingKeysWith: { first, last in
            var merged = last
            if merged.message?.task_cards == nil, let existing = first.message?.task_cards {
                merged.message?.task_cards = existing
            }
            return merged
        })
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
