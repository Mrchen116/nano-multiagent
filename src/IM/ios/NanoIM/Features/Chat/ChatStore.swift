import Foundation
import Observation

@MainActor @Observable
final class ChatStore {
    let client: IMClient
    let user: AuthUser
    var conversations: [Conversation] = []
    var timelines: [String: [TimelineItem]] = [:]
    var before: [String: String] = [:]
    var drafts: [String: String] = [:]
    var attachments: [String: [ChatAttachment]] = [:]
    var pending: [String: PendingSend] = [:]
    var sending: Set<String> = []
    var errors: [String: String] = [:]
    var selectedID: String?
    var connectionText = ""
    var listError: String?
    var banner: ChatBanner?
    var checkingAccess: Set<String> = []
    private var cursor: Int?
    private var epoch = UUID()
    private var stream: UserStream
    private var discarded: Set<String> = []
    private var revokedChats: Set<String> = []
    private var dirtyChats: Set<String> = []
    private var needsList = false
    private var refreshTask: Task<Void, Never>?
    private var notificationFloor = 0

    init(client: IMClient, user: AuthUser) { self.client = client; self.user = user; self.stream = UserStream(client: client) }

    func stop() {
        epoch = UUID(); refreshTask?.cancel(); refreshTask = nil
        Task { await stream.stop() }
    }
    func clear() {
        stop(); timelines = [:]; drafts = [:]; attachments = [:]; pending = [:]; conversations = []
        discarded = []; revokedChats = []; checkingAccess = []; selectedID = nil; banner = nil
    }
    func run() async {
        let token = epoch
        var attempt = 0
        defer { Task { await stream.stop() } }
        while !Task.isCancelled && token == epoch {
            do {
                connectionText = L("正在连接…", "Connecting…")
                let currentUser = try await client.session.updateUser()
                guard token == epoch, !Task.isCancelled else { return }
                guard currentUser.membership_status == "active" else { clear(); return }
                let sync: SyncSnapshot = try await client.get("/im/v1/sync")
                guard token == epoch, !Task.isCancelled else { return }
                reconcile(sync.items)
                notificationFloor = sync.max_event_id
                if cursor == nil { cursor = sync.max_event_id }
                // Persisted snapshots contain every delta, so invalidation/re-read avoids
                // replaying text already included in a concurrently loaded history page.
                if let selectedID { await loadChat(selectedID) }
                let events = try await stream.connect(after: cursor ?? sync.max_event_id)
                guard token == epoch, !Task.isCancelled else { return }
                connectionText = ""; attempt = 0
                for try await event in events {
                    guard token == epoch, !Task.isCancelled else { return }
                    if event.op == "membership_changed" {
                        clear(); _ = try? await client.session.updateUser(); return
                    }
                    if event.op == "resync_required" { cursor = nil; break }
                    if event.op == "event" { consume(event) }
                }
            } catch {
                guard token == epoch, !Task.isCancelled else { return }
                connectionText = L("连接中断，正在重连", "Disconnected. Reconnecting")
                if (error as? APIError)?.status == 401 { return }
                let delay = max((error as? APIError)?.retryAfter ?? 0, min(30, pow(2, Double(attempt))))
                attempt += 1
                try? await Task.sleep(for: .seconds(delay))
            }
        }
    }
    func consume(_ event: UserEvent) {
        let data = event.data ?? .null
        let chat = data["conversation_id"].stringValue
        if event.event_type == "conversation.membership_changed" || event.event_type == "conversation.deleted" {
            // The cursor-free frame also covers creation, rename and member addition.
            // Hide private history until the membership-filtered list confirms access.
            if let chat {
                checkingAccess.insert(chat); timelines[chat] = nil; before[chat] = nil
                if banner?.conversationID == chat { banner = nil }
                dirtyChats.insert(chat)
            }
            needsList = true; scheduleRefresh()
            return
        }
        guard let eventID = event.event_id, eventID > (cursor ?? 0) else { return }
        cursor = eventID
        if event.event_type == "message.discarded", let id = data["message_id"].stringValue {
            discarded.insert(id)
            if let chat { timelines[chat]?.removeAll { $0.id == id } }
        }
        if let chat { dirtyChats.insert(chat) }
        needsList = true
        if event.event_type == "message.created", eventID > notificationFloor,
           let chat, chat != selectedID, conversations.contains(where: { $0.id == chat && !$0.is_muted }),
           data["sender_user_id"].stringValue != user.id,
           UserDefaults.standard.object(forKey: "nano.foregroundReminders") as? Bool ?? true {
            banner = ChatBanner(conversationID: chat)
        }
        scheduleRefresh()
    }
    private func scheduleRefresh() {
        guard refreshTask == nil else { return }
        let token = epoch
        refreshTask = Task { [weak self] in
            guard let self else { return }
            defer { self.refreshTask = nil }
            while !Task.isCancelled, token == self.epoch, self.needsList || !self.dirtyChats.isEmpty {
                try? await Task.sleep(for: .milliseconds(250))
                guard !Task.isCancelled, token == self.epoch else { return }
                let chats = self.dirtyChats; self.dirtyChats = []
                let list = self.needsList; self.needsList = false
                if list { await self.loadConversations() }
                if let id = self.selectedID, chats.contains(id), self.conversations.contains(where: { $0.id == id }) { await self.loadChat(id) }
            }
        }
    }
    private func reconcile(_ values: [Conversation]) {
        let allowed = Set(values.map(\.id))
        revokedChats.formUnion(checkingAccess.subtracting(allowed))
        revokedChats.subtract(allowed)
        for id in Set(timelines.keys).union(checkingAccess) where !allowed.contains(id) {
            timelines[id] = nil; before[id] = nil; drafts[id] = nil; attachments[id] = nil; pending[id] = nil
            errors[id] = L("你已无法访问此聊天。", "You no longer have access to this conversation.")
        }
        checkingAccess = []
        conversations = values
        listError = nil
    }
    func loadConversations() async {
        let token = epoch
        do {
            let page: ItemsPage<Conversation> = try await client.get("/im/v1/conversations")
            guard token == epoch, !Task.isCancelled else { return }; reconcile(page.items)
        } catch { if token == epoch, !(error is CancellationError) { listError = error.localizedDescription; for id in checkingAccess { errors[id] = error.localizedDescription } } }
    }
    func loadChat(_ id: String, older: Bool = false) async {
        guard !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
        let token = epoch
        do {
            var page = try await client.messages(id, before: older ? before[id] : nil)
            let existing = Set((timelines[id] ?? []).map(\.id))
            // Walk back to the cached boundary when a disconnect exceeded one page.
            while !older, !existing.isEmpty, !page.items.contains(where: { existing.contains($0.id) }), let next = page.next_before_message_id {
                guard token == epoch, !Task.isCancelled, !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
                let previous = try await client.messages(id, before: next)
                page.items = TimelineMerge.merge(current: page.items, page: previous.items, older: true, discarded: discarded)
                page.next_before_message_id = previous.next_before_message_id
            }
            guard token == epoch, !Task.isCancelled, !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
            timelines[id] = TimelineMerge.merge(current: timelines[id] ?? [], page: page.items, older: older, discarded: discarded)
            if older || before[id] == nil { before[id] = page.next_before_message_id }
            errors[id] = nil
        } catch {
            guard token == epoch, !(error is CancellationError) else { return }
            if [403,404].contains((error as? APIError)?.status ?? 0) { timelines[id] = nil; attachments[id] = nil; drafts[id] = nil }
            errors[id] = error.localizedDescription
        }
    }
    func markRead(_ id: String, messageID: String) async {
        guard selectedID == id else { return }
        do {
            let updated: Conversation = try await client.send("/im/v1/conversations/\(id.pathComponent)/read", body: ["last_read_message_id": messageID])
            if let i = conversations.firstIndex(where: { $0.id == id }) { conversations[i] = updated }
        } catch { /* Reading stays usable; the next visible message retries the boundary. */ }
    }
    func send(_ id: String, retry: Bool = false) async {
        guard !sending.contains(id), !checkingAccess.contains(id), !revokedChats.contains(id) else { return }
        if !retry {
            guard pending[id] == nil else { return }
            let content = drafts[id] ?? "", files = attachments[id] ?? []
            guard !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !files.isEmpty else { return }
            pending[id] = PendingSend(content: content, attachments: files)
        }
        guard let draft = pending[id] else { return }
        let token = epoch
        sending.insert(id); errors[id] = nil
        defer { sending.remove(id) }
        do {
            let message = try await client.sendMessage(id, draft: draft, userID: user.id, participants: conversations.first { $0.id == id }?.participants ?? [])
            guard token == epoch, !revokedChats.contains(id) else { return }
            timelines[id] = TimelineMerge.merge(current: timelines[id] ?? [], page: [TimelineItem(type: "message", message: message)], older: false, discarded: discarded)
            pending[id] = nil
            if drafts[id] == draft.content { drafts[id] = "" }
            attachments[id] = []
            await loadConversations()
        } catch {
            guard token == epoch, !(error is CancellationError) else { return }
            if let api = error as? APIError, (400..<500).contains(api.status), ![408,429].contains(api.status) {
                pending[id] = nil; errors[id] = api.detail
            } else {
                errors[id] = L("发送结果尚未确认。重试会核对同一条消息。", "Delivery is unconfirmed. Retry checks the same message.")
                await loadChat(id)
                // Refreshing history is useful evidence, but identical text is not a receipt.
                errors[id] = L("发送结果尚未确认。重试会核对同一条消息。", "Delivery is unconfirmed. Retry checks the same message.")
            }
        }
    }
}
