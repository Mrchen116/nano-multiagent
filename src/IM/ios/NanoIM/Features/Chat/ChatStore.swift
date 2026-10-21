import Foundation
import Observation

@MainActor @Observable
final class ChatStore {
    let client: IMClient
    let user: AuthUser
    var conversations: [Conversation] = []
    var inspectedConversation: Conversation?
    var timelines: [String: [TimelineItem]] = [:]
    var before: [String: String] = [:]
    var drafts: [String: String] = [:]
    var attachments: [String: [ChatAttachment]] = [:]
    var uploadDrafts: [String: [AttachmentUpload]] = [:]
    var pending: [String: PendingSend] = [:]
    var interactionPending: [String: PendingSend] = [:]
    var interactionSelections: [String: InteractionSelection] = [:]
    var interactionSending: Set<String> = []
    private var interactionConversations: [String: String] = [:]
    var sending: Set<String> = []
    var errors: [String: String] = [:]
    var selectedID: String?
    var connectionText = ""
    var listError: String?
    var listLoaded = false
    var banner: ChatBanner?
    var checkingAccess: Set<String> = []
    private var cursor: Int?
    private var epoch = UUID()
    private var sendEpoch = UUID()
    private var ownerRevision: Int?
    private var stream: UserStream
    private var discarded: Set<String> = []
    private(set) var revokedChats: Set<String> = []
    private var dirtyChats: Set<String> = []
    private var needsList = false
    private var refreshTask: Task<Void, Never>?
    private var notificationFloor = 0

    init(client: IMClient, user: AuthUser) {
        self.client = client; self.user = user; self.stream = UserStream(client: client)
        restoreAttempts()
    }
    private func restoreAttempts() {
        do {
            for attempt in try client.session.sendAttempts.load(origin: client.baseURL, userID: user.id) {
                if let source = attempt.sourceMessageID {
                    interactionPending[source] = attempt.draft; interactionConversations[source] = attempt.conversationID
                } else {
                    pending[attempt.conversationID] = attempt.draft
                    if drafts[attempt.conversationID] == nil { drafts[attempt.conversationID] = attempt.draft.content }
                    if attachments[attempt.conversationID] == nil { attachments[attempt.conversationID] = attempt.draft.attachments }
                }
            }
        } catch { listError = error.localizedDescription }
    }

    func stop() {
        epoch = UUID(); refreshTask?.cancel(); refreshTask = nil
        Task { await stream.stop() }
    }
    func clear() {
        sendEpoch = UUID()
        stop(); timelines = [:]; drafts = [:]; attachments = [:]; uploadDrafts = [:]; pending = [:]; conversations = []; inspectedConversation = nil
        interactionPending = [:]; interactionConversations = [:]; interactionSelections = [:]; interactionSending = []; sending = []
        discarded = []; revokedChats = []; checkingAccess = []; selectedID = nil; banner = nil; listLoaded = false
    }
    func run() async {
        restoreAttempts()
        let token = epoch
        var attempt = 0
        defer { Task { await stream.stop() } }
        while !Task.isCancelled && token == epoch {
            do {
                connectionText = L("正在连接…", "Connecting…")
                let currentUser = try await client.session.updateUser()
                guard token == epoch, !Task.isCancelled else { return }
                guard currentUser.accountEnabled else { clear(); return }
                let sync: SyncSnapshot = try await client.get("/im/v1/sync")
                guard token == epoch, !Task.isCancelled else { return }
                await reconcile(sync.items)
                await recoverPending()
                guard token == epoch, !Task.isCancelled else { return }
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
        // Human writes emit message.sent; their optional creation event must not remind twice.
        let newMessage = (event.event_type == "message.sent" && data["sender_type"].stringValue == "user")
            || (event.event_type == "message.created" && data["sender_type"].stringValue != "user")
        if newMessage, eventID > notificationFloor,
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
                if let id = self.selectedID, chats.contains(id), (self.conversations.contains(where: { $0.id == id }) || self.inspectedConversation?.id == id) { await self.loadChat(id) }
            }
        }
    }
    private func reconcile(_ values: [Conversation]) async {
        let token = epoch
        if let id = selectedID, !values.contains(where: { $0.id == id }) { await inspectConversation(id) }
        else { inspectedConversation = nil }
        guard token == epoch, !Task.isCancelled else { return }
        var allowed = Set(values.map(\.id))
        if let inspectedConversation { allowed.insert(inspectedConversation.id) }
        revokedChats.formUnion(checkingAccess.subtracting(allowed))
        revokedChats.subtract(allowed)
        for id in Set(timelines.keys).union(uploadDrafts.keys).union(checkingAccess).union(pending.keys).union(interactionConversations.values) where !allowed.contains(id) {
            await revokeConversation(id)
            guard token == epoch else { return }
            errors[id] = L("你已无法访问此聊天。", "You no longer have access to this conversation.")
        }
        for chat in values where chat.can_write == false || chat.dissolved_at != nil {
            await discardConversationAttempts(chat.id)
            guard token == epoch else { return }
        }
        checkingAccess = []
        conversations = values
        listLoaded = true
        listError = nil
    }
    func loadConversations() async {
        let token = epoch
        do {
            let page: ItemsPage<Conversation> = try await client.get("/im/v1/conversations")
            guard token == epoch, !Task.isCancelled else { return }; await reconcile(page.items)
        } catch { if token == epoch, !(error is CancellationError) { listError = error.localizedDescription; for id in checkingAccess { errors[id] = error.localizedDescription } } }
    }
    func inspectConversation(_ id: String) async {
        let token = epoch
        do {
            let value: Conversation = try await client.get("/im/v1/conversations/\(id.pathComponent)")
            guard token == epoch, !Task.isCancelled else { return }
            inspectedConversation = value; revokedChats.remove(id); checkingAccess.remove(id)
        } catch {
            guard token == epoch else { return }
            inspectedConversation = nil
            if [403, 404].contains((error as? APIError)?.status ?? 0) {
                await revokeConversation(id)
                guard token == epoch else { return }
                revokedChats.insert(id)
                conversations.removeAll { $0.id == id }
                errors[id] = L("此聊天已不可访问。", "This conversation is no longer accessible.")
            } else { errors[id] = error.localizedDescription }
        }
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
            await recoverPending(id)
        } catch {
            guard token == epoch, !(error is CancellationError) else { return }
            if [403,404].contains((error as? APIError)?.status ?? 0) { await revokeConversation(id) }
            guard token == epoch else { return }
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
    func addUpload(_ id: String, data: Data?, name: String, type: String, error: String? = nil) async {
        guard pending[id] == nil, !checkingAccess.contains(id), !revokedChats.contains(id), conversations.contains(where: { $0.id == id }) else { return }
        let item = AttachmentUpload(data: data, fileName: name, contentType: type, error: error, retryable: data != nil)
        uploadDrafts[id, default: []].append(item)
        if data != nil { await retryUpload(id, uploadID: item.id) }
    }
    func removeUpload(_ id: String, uploadID: UUID) {
        guard pending[id] == nil else { return }
        uploadDrafts[id]?.removeAll { $0.id == uploadID && !$0.uploading }
    }
    func retryUpload(_ id: String, uploadID: UUID) async {
        guard pending[id] == nil, !checkingAccess.contains(id), !revokedChats.contains(id),
              let index = uploadDrafts[id]?.firstIndex(where: { $0.id == uploadID }),
              let item = uploadDrafts[id]?[index], let data = item.data,
              item.retryable, !item.uploading, (item.retryAt ?? .distantPast) <= Date() else { return }
        uploadDrafts[id]?[index].uploading = true
        uploadDrafts[id]?[index].error = nil
        do {
            // The server applies its current policy; a fixed client limit would reject valid files.
            let attachment = try await client.upload(data, fileName: item.fileName, contentType: item.contentType, conversationID: id)
            // Stream suspension keeps uploads alive; clear/revoke remove this UUID before a late reply.
            guard !revokedChats.contains(id), conversations.contains(where: { $0.id == id }),
                  uploadDrafts[id]?.contains(where: { $0.id == uploadID }) == true else { return }
            uploadDrafts[id]?.removeAll { $0.id == uploadID }
            attachments[id, default: []].append(attachment)
        } catch {
            guard let current = uploadDrafts[id]?.firstIndex(where: { $0.id == uploadID }) else { return }
            let api = error as? APIError
            if [403,404].contains(api?.status ?? 0) {
                await revokeConversation(id)
                errors[id] = L("你已无法访问此聊天。", "You no longer have access to this conversation.")
                await loadConversations()
                return
            }
            let reason: String
            switch api?.status {
            case 413: reason = L("文件超过服务允许的大小。", "The file exceeds the server's size limit.")
            case 415: reason = L("不支持此文件格式。", "This file format is not supported.")
            case 507: reason = L("暂时无法上传附件。", "Attachments cannot be uploaded right now.")
            case 429: reason = L("上传过于频繁，请稍后重试。", "Uploads are temporarily rate limited. Try again later.")
            default: reason = L("上传失败，请重试。", "Upload failed. Please retry.")
            }
            uploadDrafts[id]?[current].uploading = false
            uploadDrafts[id]?[current].error = reason
            uploadDrafts[id]?[current].retryable = ![413,415].contains(api?.status ?? 0)
            let delay = max(api?.retryAfter ?? 0, api?.status == 429 ? 2 : 0)
            uploadDrafts[id]?[current].retryAt = delay > 0 ? Date().addingTimeInterval(delay) : nil
        }
    }
    func send(_ id: String, retry: Bool = false, textOnly: Bool = false) async {
        let chat = inspectedConversation?.id == id ? inspectedConversation : conversations.first { $0.id == id }
        guard chat?.can_write != false else { return }
        guard !sending.contains(id), !checkingAccess.contains(id), !revokedChats.contains(id) else { return }
        sending.insert(id)
        defer { sending.remove(id) }
        if !retry {
            guard pending[id] == nil, !(uploadDrafts[id] ?? []).contains(where: \.uploading),
                  textOnly || (uploadDrafts[id] ?? []).isEmpty else { return }
            let content = drafts[id] ?? "", files = textOnly ? [] : attachments[id] ?? []
            guard !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !files.isEmpty else { return }
            do {
                let token = sendEpoch, revision = try await sessionRevision()
                guard token == sendEpoch else { return }
                guard !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
                let draft = try client.prepareMessage(PendingSend(content: content, attachments: files), userID: user.id,
                    participants: chat?.participants ?? [], contexts: backgroundContexts(id, chat: chat))
                let attempt = SendAttempt(conversationID: id, sourceMessageID: nil, draft: draft)
                try await client.session.saveSendAttempt(attempt, userID: user.id, revision: revision)
                guard token == sendEpoch else { return }
                pending[id] = draft
            } catch { errors[id] = error.localizedDescription; return }
        }
        guard let draft = pending[id] else { return }
        let attempt = SendAttempt(conversationID: id, sourceMessageID: nil, draft: draft)
        let token = sendEpoch
        errors[id] = nil
        do {
            _ = try await resolveAttempt(attempt, lookup: retry, resend: true)
        } catch {
            if !(error is CancellationError) {
                errors[id] = error.localizedDescription
                if pending[id] != nil { await loadChat(id) }
                if token == sendEpoch, pending[id]?.key == draft.key { errors[id] = error.localizedDescription }
            }
        }
    }

    func interactionAttempt(_ id: String, sourceMessageID: String) -> PendingSend? {
        interactionConversations[sourceMessageID] == id ? interactionPending[sourceMessageID] : nil
    }

    func submitInteraction(_ id: String, input: InteractionReplyInput, key: String) async throws -> ChatMessage {
        try requireWritable(id)
        let source = input.source_message_id
        guard interactionPending[source] == nil, !interactionSending.contains(source) else {
            throw APIError(status: 0, detail: unconfirmedText)
        }
        interactionSending.insert(source)
        defer { interactionSending.remove(source) }
        let token = sendEpoch, revision = try await sessionRevision()
        guard token == sendEpoch else { throw CancellationError() }
        try requireWritable(id)
        let draft = try client.prepareMessage(PendingSend(key: key, content: "", attachments: []), userID: user.id, interaction: input)
        let attempt = SendAttempt(conversationID: id, sourceMessageID: source, draft: draft)
        try await client.session.saveSendAttempt(attempt, userID: user.id, revision: revision)
        guard token == sendEpoch else { throw CancellationError() }
        interactionPending[source] = draft; interactionConversations[source] = id
        guard let message = try await resolveAttempt(attempt, lookup: false, resend: true) else { throw APIError(status: 0, detail: unconfirmedText) }
        return message
    }

    func retryInteraction(_ id: String, sourceMessageID: String) async throws -> ChatMessage {
        try requireWritable(id)
        guard let draft = interactionAttempt(id, sourceMessageID: sourceMessageID), !interactionSending.contains(sourceMessageID) else { throw CancellationError() }
        interactionSending.insert(sourceMessageID)
        defer { interactionSending.remove(sourceMessageID) }
        let attempt = SendAttempt(conversationID: id, sourceMessageID: sourceMessageID, draft: draft)
        guard let message = try await resolveAttempt(attempt, lookup: true, resend: true) else { throw APIError(status: 0, detail: unconfirmedText) }
        return message
    }

    /// Reopening queries durable attempts without submitting any new work.
    func recoverPending(_ id: String? = nil) async {
        let ordinary = pending.filter { id == nil || $0.key == id }.map { SendAttempt(conversationID: $0.key, sourceMessageID: nil, draft: $0.value) }
        let cards = interactionPending.compactMap { source, draft -> SendAttempt? in
            guard let chat = interactionConversations[source], id == nil || id == chat else { return nil }
            return SendAttempt(conversationID: chat, sourceMessageID: source, draft: draft)
        }
        for attempt in ordinary + cards {
            guard !revokedChats.contains(attempt.conversationID), !checkingAccess.contains(attempt.conversationID) else { continue }
            if let source = attempt.sourceMessageID {
                guard !interactionSending.contains(source) else { continue }
                interactionSending.insert(source)
                _ = try? await resolveAttempt(attempt, lookup: true, resend: false)
                interactionSending.remove(source)
            } else {
                guard !sending.contains(attempt.conversationID) else { continue }
                sending.insert(attempt.conversationID)
                _ = try? await resolveAttempt(attempt, lookup: true, resend: false)
                sending.remove(attempt.conversationID)
            }
        }
    }

    private var unconfirmedText: String { L("发送结果尚未确认。重试会核对同一条消息。", "Delivery is unconfirmed. Retry checks the same message.") }

    private func requireWritable(_ id: String) throws {
        let chat = inspectedConversation?.id == id ? inspectedConversation : conversations.first { $0.id == id }
        guard !revokedChats.contains(id), !checkingAccess.contains(id), chat?.can_write != false, chat?.dissolved_at == nil else {
            throw APIError(status: 403, detail: L("此聊天不能发送消息。", "This conversation does not allow sending."))
        }
    }

    private func backgroundContexts(_ id: String, chat: Conversation?) -> [InteractionContextInput] {
        guard chat?.type == "direct" else { return [] }
        let messages = (timelines[id] ?? []).compactMap(\.message)
        let replaced = Set(messages.compactMap { $0.interactive?.supersedes_message_id })
        return messages.enumerated().compactMap { index, message -> (InteractionSelection, Int)? in
            guard let card = message.interactive, card.read_only != true, card.superseded_by == nil, !replaced.contains(message.id),
                  let selection = interactionSelections[message.id], selection.conversationID == id else { return nil }
            return (selection, index)
        }.sorted { $0.0.editedAt == $1.0.editedAt ? $0.1 > $1.1 : $0.0.editedAt > $1.0.editedAt }.prefix(3)
            .map { InteractionContextInput(source_message_id: $0.0.source_message_id, state: $0.0.state, interacted_at: $0.0.editedAt == 0 ? nil : $0.0.editedAt) }
    }

    private func isCurrent(_ attempt: SendAttempt, token: UUID) -> Bool {
        guard token == sendEpoch, !revokedChats.contains(attempt.conversationID), !checkingAccess.contains(attempt.conversationID) else { return false }
        if let source = attempt.sourceMessageID { return interactionAttempt(attempt.conversationID, sourceMessageID: source)?.key == attempt.draft.key }
        return pending[attempt.conversationID]?.key == attempt.draft.key
    }

    private func resolveAttempt(_ attempt: SendAttempt, lookup: Bool, resend: Bool) async throws -> ChatMessage? {
        let token = sendEpoch, revision = try await sessionRevision()
        let id = attempt.conversationID
        let lookupKey = attempt.sourceMessageID == nil ? attempt.draft.key : "interaction:\(user.id):\(attempt.draft.key)"
        do {
            try await client.session.assertOwner(user.id, revision: revision)
            var message: ChatMessage?
            if lookup { message = try await client.lookupMessageAttempt(id, key: lookupKey) }
            guard isCurrent(attempt, token: token) else { throw CancellationError() }
            if message == nil, resend {
                do { message = try await client.sendMessage(id, draft: attempt.draft, userID: user.id) }
                catch let conflict as APIError where conflict.status == 409 {
                    // A conflict may be a lost acknowledgement; only the sender's receipt resolves it.
                    message = try await client.lookupMessageAttempt(id, key: lookupKey)
                    if message == nil { throw conflict }
                }
            }
            try await client.session.assertOwner(user.id, revision: revision)
            guard isCurrent(attempt, token: token) else { throw CancellationError() }
            guard let message else { errors[id] = unconfirmedText; return nil }
            try await client.session.removeSendAttempt(attempt, userID: user.id, revision: revision)
            guard isCurrent(attempt, token: token) else { throw CancellationError() }
            timelines[id] = TimelineMerge.merge(current: timelines[id] ?? [], page: [TimelineItem(type: "message", message: message)], older: false, discarded: discarded)
            if let source = attempt.sourceMessageID { interactionPending[source] = nil; interactionConversations[source] = nil }
            else {
                pending[id] = nil
                if drafts[id] == attempt.draft.content {
                    drafts[id] = ""
                    let sentIDs = Set(attempt.draft.attachments.map(\.id))
                    attachments[id]?.removeAll { sentIDs.contains($0.id) }
                }
            }
            errors[id] = nil
            return message
        } catch {
            guard isCurrent(attempt, token: token), !(error is CancellationError) else { throw CancellationError() }
            try await client.session.assertOwner(user.id, revision: revision)
            if let api = error as? APIError, (400..<500).contains(api.status), ![408, 429].contains(api.status) {
                try await client.session.removeSendAttempt(attempt, userID: user.id, revision: revision)
                guard isCurrent(attempt, token: token) else { throw CancellationError() }
                if let source = attempt.sourceMessageID { interactionPending[source] = nil; interactionConversations[source] = nil }
                else { pending[id] = nil }
                if [403, 404].contains(api.status) { await revokeConversation(id) }
                errors[id] = api.detail
                throw api
            }
            errors[id] = unconfirmedText
            throw APIError(status: 0, detail: unconfirmedText)
        }
    }

    private func sessionRevision() async throws -> Int {
        let revision = await client.session.revision()
        if let ownerRevision, ownerRevision != revision { throw CancellationError() }
        try await client.session.assertOwner(user.id, revision: revision)
        ownerRevision = revision
        return revision
    }

    private func discardConversationAttempts(_ id: String) async {
        guard let revision = try? await sessionRevision() else { return }
        pending[id] = nil
        for source in interactionConversations.filter({ $0.value == id }).map(\.key) {
            interactionPending[source] = nil; interactionConversations[source] = nil; interactionSending.remove(source)
        }
        interactionSelections = interactionSelections.filter { $0.value.conversationID != id }
        try? await client.session.removeConversationAttempts(id, userID: user.id, revision: revision)
    }
    private func revokeConversation(_ id: String) async {
        let token = epoch
        await discardConversationAttempts(id)
        guard token == epoch else { return }
        timelines[id] = nil; before[id] = nil; drafts[id] = nil; attachments[id] = nil; uploadDrafts[id] = nil
        revokedChats.insert(id)
    }
}
