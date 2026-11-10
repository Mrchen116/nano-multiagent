import Foundation
import Observation
import os

/// Projection of the local chat store plus the user's intents.
///
/// The database is the durable truth; the arrays below are what the UI renders. Every write
/// the user or the network produces goes through `ChatRepository` first and is re-projected
/// from it, so a cold start can paint from disk before any request completes.
@MainActor @Observable
final class ChatStore {
    let client: IMClient
    let user: AuthUser
    var conversations: [Conversation] = []
    var inspectedConversation: Conversation?
    var timelines: [String: [TimelineItem]] = [:]
    private var receivedTimelineResults: Set<String> = []
    var before: [String: String] = [:]
    /// Conversations with a known incomplete local window: older history needs the network.
    var olderNeedsNetwork: Set<String> = []
    var drafts: [String: String] = [:]
    var attachments: [String: [ChatAttachment]] = [:]
    var uploadDrafts: [String: [AttachmentUpload]] = [:]
    var pending: [String: PendingSend] = [:] { didSet { pendingRevision = UUID() } }
    var interactionPending: [String: PendingSend] = [:] { didSet { pendingRevision = UUID() } }
    @ObservationIgnored private var pendingRevision = UUID()
    @ObservationIgnored private var unpersistedCleanups: [String: ChatAttemptPersistence.CleanupKind] = [:]
    @ObservationIgnored private var cleanupBlocked = false
    let interactionDrafts: InteractionDraftCoordinator
    private(set) var interactionEpoch = UUID()
    var interactionSending: Set<String> = []
    private var interactionConversations: [String: String] = [:]
    var sending: Set<String> = []
    var errors: [String: String] = [:]
    struct ComposeRequest: Identifiable {
        let id = UUID()
        let target: String
        let text: String
    }
    var composeRequest: ComposeRequest?
    var selectedID: String? {
        didSet {
            if let oldValue, oldValue != selectedID { interactionDrafts.leave(oldValue) }
        }
    }
    /// Content phase: whether anything can be shown. Independent of the connection.
    var listPhase: ChatListPhase = .loadingFirst
    /// Connection phase: how the correction is going.
    var connection: ConnectionState = .starting
    /// Unconfirmed sends waiting for the first successful sync to resolve their conversation.
    var pendingCount = 0
    var lastFullAt: String?
    var storage: ChatStorageState = .opening
    var listError: String?
    var banner: ChatBanner?
    var checkingAccess: Set<String> = []
    private var cursor: Int?
    private var epoch = UUID()
    private var projectionRevision = UUID()
    /// An authoritative discard retires reads, not unrelated frozen send ownership.
    private var discardReadRevision = UUID()
    /// Freeze the partition and snapshot generation before IO, never after a response arrives.
    private struct ReadRequest {
        let epoch: UUID
        let revision: UUID
        let discardRevision: UUID
        let repository: ChatRepository?
        let context: ChatWriteContext?
    }

    private func readRequest() async throws -> ReadRequest {
        guard !cleanupBlocked else {
            throw ChatRepositoryError.databaseUnavailable(L("本机内容仍需清理，请重试。", "Local cleanup is still pending; retry storage."))
        }
        let token = epoch, revision = projectionRevision, discardRevision = discardReadRevision, repository = repository
        let context = try await repository?.writeContext()
        guard token == epoch, revision == projectionRevision, discardRevision == discardReadRevision else { throw CancellationError() }
        return ReadRequest(epoch: token, revision: revision, discardRevision: discardRevision, repository: repository, context: context)
    }

    private func isCurrent(_ request: ReadRequest) async -> Bool {
        guard !Task.isCancelled, request.epoch == epoch, request.revision == projectionRevision,
              request.discardRevision == discardReadRevision, request.repository === repository else { return false }
        if let repository = request.repository {
            guard let context = try? await repository.writeContext(), context == request.context else { return false }
        }
        return !Task.isCancelled && request.epoch == epoch && request.revision == projectionRevision && request.discardRevision == discardReadRevision
    }
    private var sendEpoch = UUID()
    private var ownerRevision: Int?
    private var stream: UserStream
    private var discarded: Set<String> = []
    private(set) var revokedChats: Set<String> = []
    private var dirtyChats: Set<String> = []
    private var executionCleanupRevisions: [String: Int] = [:]
    /// Permanent facts survive list churn/degraded storage, but never an owner reset.
    private var knownDeletedActorIDs: Set<String> = []
    private var readingPositions: [String: String] = [:]
    private var pendingReadingPositions: [String: String] = [:]
    var restoreReadingPositions: [String: String] = [:]
    private var needsList = false
    private var refreshTask: Task<Void, Never>?
    private var accessRecovery: Task<Void, Never>?
    @ObservationIgnored private var attemptRestore: Task<Void, Never>?
    @ObservationIgnored private var draftFlush: Task<Void, Never>?
    @ObservationIgnored private var draftWriteTail: Task<Void, Never>?
    @ObservationIgnored private var queuedDrafts: [String: String] = [:]
    @ObservationIgnored private var dirtyDraftIDs: Set<String> = []
    private var notificationFloor = 0
    private var storageController: ChatStorageController?
    /// First-paint read interval (design D2). `log stream`/Instruments read it in the field.
    private static let signposter = OSSignposter(subsystem: "com.nanoim.app", category: "ChatStore")

    var repository: ChatRepository? {
        if case .ready(let repository) = storage { return repository }
        return nil
    }
    /// Non-empty exactly when the connection is not `.online`.
    var connectionText: String { ChatConnectionText.describe(connection, lastFullAt: lastFullAt) }
    var storageDegradedReason: String? {
        if case .degraded(let reason) = storage { return reason }
        return nil
    }

    func timelinePhase(_ id: String) -> ChatTimelinePhase {
        if (timelines[id] ?? []).contains(where: { $0.message != nil }) { return .loaded }
        if receivedTimelineResults.contains(id) { return .empty }
        if errors[id] != nil { return .needsConnection }
        switch connection {
        case .offline, .unavailable: return .needsConnection
        default: return .loadingFirst
        }
    }

    init(client: IMClient, user: AuthUser, controller: ChatStorageController? = nil) {
        self.client = client; self.user = user; self.stream = UserStream(client: client)
        self.interactionDrafts = InteractionDraftCoordinator(client: client, userID: user.id)
        self.storageController = controller
        if let controller { controller.attach(self) } else { scheduleAttemptRestore() }
    }

    /// Storage state transitions come from the controller only.
    func bind(storage next: ChatStorageState, seed: ChatBootstrapSeed? = nil) {
        let previous = repository
        storage = next
        if previous !== repository { projectionRevision = UUID() }
        guard case .ready = next else {
            if case .degraded = next { scheduleAttemptRestore() }
            return
        }
        cleanupBlocked = false
        if let seed { applySeed(seed) }
        else { Task { await loadSeed() } }
    }

    /// `.degraded` retry point: user tap, next foreground, or the next `run()`, whichever
    /// comes first. It never silently becomes "pure network forever".
    func retryStorage() async {
        if let storageController {
            await storageController.retryOpen()
            await flushDrafts()
            return
        }
        do {
            let revision = try await sessionRevision()
            for (id, kind) in unpersistedCleanups.sorted(by: { $0.key < $1.key }) {
                try await client.session.removeConversationAttempts(id, kind: kind, userID: user.id, revision: revision)
                unpersistedCleanups[id] = nil
            }
            cleanupBlocked = false
            scheduleAttemptRestore()
            await attemptRestore?.value
        } catch { listError = error.localizedDescription }
    }

    func blockForCleanup() {
        cleanupBlocked = true
        resetProjection()
    }

    /// Read only the current partition generation; a slow seed cannot undo a newer snapshot.
    func loadSeed() async {
        guard let repository else { return }
        let signpostID = Self.signposter.makeSignpostID()
        let interval = Self.signposter.beginInterval("bootstrapSeed", id: signpostID)
        defer { Self.signposter.endInterval("bootstrapSeed", interval) }
        guard let request = try? await readRequest(),
              let seed = try? await repository.bootstrapSeed(), await isCurrent(request) else { return }
        applySeed(seed)
        if let revoked = try? await repository.revokedConversations(), await isCurrent(request) {
            revokedChats.formUnion(revoked)
        }
    }

    /// The controller loads this before RootTabs exists, so its very first frame has rows.
    /// This applies value types only; no synchronous file/SQLite work happens on MainActor.
    private func applySeed(_ seed: ChatBootstrapSeed) {
        conversations = normalizingDeletedActors(seed.conversations)
        for chat in seed.conversations { observeExecutionCleanup(chat.id, revision: chat.execution_cleanup_revision ?? 0) }
        for (id, body) in seed.drafts where !dirtyDraftIDs.contains(id) && (drafts[id] == nil || drafts[id]?.isEmpty == true) { drafts[id] = body }
        pendingCount = seed.pendingCount
        lastFullAt = seed.connection.lastFullAt
        if cursor == nil, seed.connection.maxEventID > 0 { cursor = seed.connection.maxEventID }
        if listPhase == .loadingFirst, !conversations.isEmpty { listPhase = .loaded }
        if connection == .starting, !conversations.isEmpty { connection = .localOnly }
    }

    private func scheduleAttemptRestore() {
        attemptRestore?.cancel()
        attemptRestore = Task { [weak self] in
            guard let self else { return }
            await self.readRestoredAttempts()
        }
    }

    /// Allows an entry point/test to await the constructor's single asynchronous restore.
    func restoreAttempts() async {
        if let attemptRestore { await attemptRestore.value }
        else { await readRestoredAttempts() }
    }

    /// Degraded storage still restores frozen requests, off MainActor and through the same
    /// policy/handoff boundary as SQLite. This is never an implicit resend.
    private func readRestoredAttempts() async {
        guard !cleanupBlocked, unpersistedCleanups.isEmpty else { return }
        let token = epoch, revision = projectionRevision, pendingVersion = pendingRevision
        do {
            let owner = try await sessionRevision()
            let attempts = try await client.session.loadSendAttempts(userID: user.id, revision: owner)
            guard !Task.isCancelled, token == epoch, revision == projectionRevision,
                  pendingVersion == pendingRevision, repository == nil else { return }
            for attempt in attempts {
                if let source = attempt.sourceMessageID {
                    if interactionPending[source] == nil { adopt(attempt) }
                } else if pending[attempt.conversationID] == nil { adopt(attempt) }
            }
            pendingCount = attempts.count
        } catch {
            guard token == epoch, revision == projectionRevision, !(error is CancellationError) else { return }
            listError = error.localizedDescription
        }
    }

    /// A restored attempt becomes a projection row only; nothing is submitted from here.
    private func adopt(_ attempt: SendAttempt) {
        if let source = attempt.sourceMessageID {
            interactionPending[source] = attempt.draft; interactionConversations[source] = attempt.conversationID
        } else {
            pending[attempt.conversationID] = attempt.draft
            if repository == nil, drafts[attempt.conversationID] == nil {
                drafts[attempt.conversationID] = attempt.draft.content
            }
            if attachments[attempt.conversationID] == nil { attachments[attempt.conversationID] = attempt.draft.attachments }
        }
    }

    /// Rebuild the pending projection from the store: the count shown at launch and the rows
    /// that can be reconciled are the same durable source.
    /// The read seam pins continuation interleavings in tests; production always reads the
    /// repository. Local mutations after that snapshot invalidate it even without a new sync.
    func reloadPending(read: @Sendable (ChatRepository) async throws -> [SendAttempt] = { try await $0.pendingAttempts() }) async {
        let pendingVersion = pendingRevision
        guard let request = try? await readRequest(), let repository = request.repository else { return }
        do {
            let attempts = try await read(repository)
            guard await isCurrent(request), pendingVersion == pendingRevision else { return }
            pending = [:]; interactionPending = [:]; interactionConversations = [:]
            for attempt in attempts { adopt(attempt) }
            pendingCount = attempts.count
        } catch {
            guard await isCurrent(request), !(error is CancellationError) else { return }
            // Preserve unresolved memory while its handoff cannot be imported; an empty DB
            // result is not permission to discard a frozen request that is still on disk.
            listError = error.localizedDescription
        }
    }

    /// Check the target using the signed-in viewer before changing either local draft.
    func checkComposeTarget(_ target: String) async throws {
        let destination: Conversation = try await client.get("/im/v1/conversations/\(target.pathComponent)")
        guard destination.can_write == true, destination.dissolved_at == nil, destination.external_source == nil else {
            throw APIError(status: 403, detail: L("目标聊天不可用，或你没有发送权限。", "This conversation is unavailable or you do not have permission to write."))
        }
    }
    func hasComposeConflict(_ target: String, text: String) -> Bool {
        let draft = drafts[target] ?? ""
        return (!draft.isEmpty && draft != text) || !(attachments[target] ?? []).isEmpty || !(uploadDrafts[target] ?? []).isEmpty
    }
    func adoptCompose(_ target: String, text: String) {
        setDraft(target, text); attachments[target] = []; uploadDrafts[target] = []
        composeRequest = ComposeRequest(target: target, text: text)
    }

    /// Composer edits land in memory only; the flush points below persist the newest text.
    func setDraft(_ id: String, _ text: String) {
        drafts[id] = text
        // One serial writer keeps "last text wins": a fire-and-forget task per keystroke could
        // commit an older snapshot after a newer one.
        queuedDrafts[id] = text
        dirtyDraftIDs.insert(id)
        guard draftFlush == nil else { return }
        let token = epoch
        draftFlush = Task { [weak self] in
            try? await Task.sleep(for: .seconds(1))
            guard let self, !Task.isCancelled, token == self.epoch else { return }
            await self.flushDrafts()
        }
    }

    /// Flush points share one waiting chain: a newer snapshot cannot commit before an older
    /// flush finishes. The writer seam controls interleavings without replacing real storage.
    func flushDrafts(write: @escaping @Sendable (ChatRepository, String, String) async throws -> Void = {
        try await $0.setDraft($1, body: $2)
    }) async {
        draftFlush?.cancel(); draftFlush = nil
        guard !queuedDrafts.isEmpty else { await draftWriteTail?.value; return }
        guard let repository else { return } // Keep edits queued while storage is unavailable.
        let writes = queuedDrafts
        queuedDrafts = [:]
        let previous = draftWriteTail
        // Network stop/backgrounding must not invalidate a draft flush. Only losing the
        // account owner cancels this chain; resetProjection rotates sendEpoch.
        let owner = sendEpoch
        let task = Task { [weak self] in
            await previous?.value
            guard let self, owner == self.sendEpoch, !Task.isCancelled else { return }
            var failure: String?
            for (id, body) in writes.sorted(by: { $0.key < $1.key }) {
                guard owner == self.sendEpoch, !Task.isCancelled else { return }
                guard self.drafts[id] != nil, !self.revokedChats.contains(id) else { continue }
                // A still-queued edit has not joined the chain yet. An already consumed newer
                // flush is ordered after this task, so it will safely win without this guard.
                guard self.queuedDrafts[id] == nil else { continue }
                do {
                    guard self.repository === repository else { throw ChatRepositoryError.databaseUnavailable("storage changed before draft flush") }
                    try await write(repository, id, body)
                    if self.drafts[id] == body, self.queuedDrafts[id] == nil { self.dirtyDraftIDs.remove(id) }
                } catch {
                    guard owner == self.sendEpoch else { return }
                    if self.drafts[id] == body, self.queuedDrafts[id] == nil { self.queuedDrafts[id] = body }
                    failure = error.localizedDescription
                }
            }
            if let failure, owner == self.sendEpoch, self.repository === repository {
                self.listError = failure
                if let controller = self.storageController { controller.reportStorageFailure(failure) }
                else { self.storage = .degraded(reason: failure) }
            }
        }
        draftWriteTail = task
        await task.value
    }

    func stop() {
        epoch = UUID(); refreshTask?.cancel(); refreshTask = nil
        accessRecovery?.cancel(); accessRecovery = nil
        Task { await stream.stop() }
    }

    /// Reset every projection to its initial value; durable rows are the controller's business.
    func resetProjection() {
        sendEpoch = UUID(); interactionEpoch = UUID(); projectionRevision = UUID()
        attemptRestore?.cancel(); attemptRestore = nil
        draftFlush?.cancel(); draftFlush = nil
        draftWriteTail?.cancel(); draftWriteTail = nil
        queuedDrafts = [:]; dirtyDraftIDs = []
        stop()
        timelines = [:]; drafts = [:]; attachments = [:]; uploadDrafts = [:]; pending = [:]; conversations = []
        inspectedConversation = nil; before = [:]; olderNeedsNetwork = []; receivedTimelineResults = []
        interactionPending = [:]; interactionConversations = [:]; interactionSending = []; sending = []
        discarded = []; revokedChats = []; checkingAccess = []; selectedID = nil; interactionDrafts.clear(); composeRequest = nil; banner = nil
        listPhase = .loadingFirst; connection = .starting; pendingCount = 0; lastFullAt = nil; listError = nil
        cursor = nil; needsList = false; dirtyChats = []
        executionCleanupRevisions = [:]; knownDeletedActorIDs = []; readingPositions = [:]; pendingReadingPositions = [:]; restoreReadingPositions = [:]
    }

    func run() async {
        // Foreground is one of the three retry points for an unopenable partition.
        if case .degraded = storage { await retryStorage() }
        let token = epoch
        var attempt = 0
        defer { Task { await stream.stop() } }
        await loadSeed()
        await reloadPending()
        while !Task.isCancelled && token == epoch {
            do {
                connection = listPhase == .loaded ? .syncing : .starting
                let currentUser = try await client.session.updateUser()
                guard token == epoch, !Task.isCancelled else { return }
                guard currentUser.accountEnabled else { return }
                let request = try await readRequest()
                let sync: SyncSnapshot = try await client.get("/im/v1/sync")
                guard await isCurrent(request) else { continue }
                try await applySnapshot(sync, request: request)
                guard token == epoch, !Task.isCancelled else { return }
                // Content correction completed. An unrelated lookup or WebSocket ticket must
                // not keep a successfully synchronized list labeled "Connecting" forever.
                connection = .online; attempt = 0
                await recoverPending()
                await interactionDrafts.foreground(activeConversation: selectedID)
                if let selectedID, interactionDrafts.failure(selectedID) != nil { _ = await flushDrafts(selectedID) }
                guard token == epoch, !Task.isCancelled else { return }
                notificationFloor = sync.max_event_id
                if cursor == nil { cursor = sync.max_event_id }
                // Persisted snapshots contain every delta, so invalidation/re-read avoids
                // replaying text already included in a concurrently loaded history page.
                if let selectedID { await loadChat(selectedID) }
                let events = try await stream.connect(after: cursor ?? sync.max_event_id)
                guard token == epoch, !Task.isCancelled else { return }
                for try await event in events {
                    guard token == epoch, !Task.isCancelled else { return }
                    if event.op == "membership_changed" {
                        if let id = event.data?["conversation_id"].stringValue {
                            await verifyAccess(id)
                        } else {
                            needsList = true; scheduleRefresh()
                        }
                        continue
                    }
                    if event.op == "resync_required" { cursor = nil; break }
                    if event.op == "event" { await consume(event) }
                }
            } catch {
                guard token == epoch, !Task.isCancelled else { return }
                if error is CancellationError || (error as? ChatRepositoryError) == .staleWrite { continue }
                let failure = ChatFailure.from(error)
                if listPhase == .loadingFirst { listPhase = .failed }
                switch failure {
                case .unauthorized, .deactivated:
                    connection = failure.connection ?? .unauthorized
                    return
                case .forbidden:
                    // Conversation-scoped failures are handled where the conversation is known.
                    connection = .offline(attempt: attempt, nextRetryAt: nil)
                case .offline:
                    connection = .offline(attempt: attempt, nextRetryAt: Date().addingTimeInterval(max((error as? APIError)?.retryAfter ?? 0, min(30, pow(2, Double(attempt))))))
                case .unavailable(let status):
                    connection = .unavailable(status: status)
                }
                let delay = max((error as? APIError)?.retryAfter ?? 0, min(30, pow(2, Double(attempt))))
                attempt += 1
                try? await Task.sleep(for: .seconds(delay))
            }
        }
    }

    /// Writes the authoritative snapshot, then projects it. Only a successful full sync may
    /// conclude that a conversation disappeared with it.
    private func applySnapshot(_ sync: SyncSnapshot, request: ReadRequest) async throws {
        guard await isCurrent(request) else { throw CancellationError() }
        guard let repository = request.repository, let context = request.context else {
            projectionRevision = UUID()
            for (id, revision) in sync.execution_cleanup_revisions ?? [:] { observeExecutionCleanup(id, revision: revision) }
            await reconcileNetwork(sync.items)
            return
        }
        let privateDraftIDs = await privateDraftConversationIDs()
        guard await isCurrent(request) else { throw CancellationError() }
        do {
            let result = try await repository.applySnapshot(sync.items, maxEventID: sync.max_event_id,
                                                            snapshotSeq: context.snapshotSeq + 1,
                                                            executionCleanupRevisions: sync.execution_cleanup_revisions ?? [:],
                                                            privateDraftIDs: privateDraftIDs, write: context)
            guard request.epoch == epoch, request.discardRevision == discardReadRevision, self.repository === repository else { throw CancellationError() }
            guard result.conversations.allSatisfy({ ($0.execution_cleanup_revision ?? 0) >= (executionCleanupRevisions[$0.id] ?? 0) }) else { throw CancellationError() }
            projectionRevision = UUID()
            for chat in result.conversations { observeExecutionCleanup(chat.id, revision: chat.execution_cleanup_revision ?? 0) }
            for (id, revision) in sync.execution_cleanup_revisions ?? [:] { observeExecutionCleanup(id, revision: revision) }
            conversations = normalizingDeletedActors(result.conversations)
            revokedChats.subtract(Set(result.conversations.map(\.id)))
            pendingCount = result.pendingCount
            lastFullAt = (try? await repository.connectionSeed())?.lastFullAt ?? lastFullAt
            for id in result.revoked {
                clearConversationState(id)
                revokedChats.insert(id)
                errors[id] = L("你已无法访问此聊天。", "You no longer have access to this conversation.")
            }
            // The SQLite transaction may have already recorded the revocation on a previous
            // launch. Clean up a still-present card ledger even for a known tombstone.
            let revokedDraftIDs = privateDraftIDs.subtracting(sync.items.map(\.id)).union(result.revoked)
            for id in revokedDraftIDs { interactionDrafts.remove(id) }
            for id in revokedDraftIDs {
                await eraseDraftLedger(id)
                guard request.epoch == epoch else { throw CancellationError() }
            }
            for chat in result.conversations where chat.can_write == false || chat.dissolved_at != nil {
                await discardConversationAttempts(chat.id)
            }
            guard request.epoch == epoch, request.discardRevision == discardReadRevision, self.repository === repository else { throw CancellationError() }
            if let selectedID, !result.conversations.contains(where: { $0.id == selectedID }) {
                await inspectConversation(selectedID)
            } else { inspectedConversation = nil }
            revokedChats.formUnion(checkingAccess.subtracting(Set(result.conversations.map(\.id))))
            revokedChats.formUnion(result.revoked)
            checkingAccess = []
            listPhase = result.conversations.isEmpty && pendingCount == 0 ? .empty : (result.conversations.isEmpty ? .loadingFirst : .loaded)
            listError = nil
        } catch {
            guard request.epoch == epoch, request.discardRevision == discardReadRevision,
                  request.repository === self.repository, (error as? ChatRepositoryError) != .staleWrite,
                  !(error is CancellationError) else { throw CancellationError() }
            if let cleanup = error as? ChatCleanupFailure { handleCleanupFailure(cleanup) }
            let failure = ChatFailure.from(error)
            if listPhase == .loadingFirst { listPhase = .failed }
            connection = failure.connection ?? connection
            listError = error.localizedDescription
            throw error
        }
    }

    /// Pure-network fallback used while the partition cannot be opened (design D3 degraded).
    private func reconcileNetwork(_ values: [Conversation]) async {
        let values = normalizingDeletedActors(values)
        let token = epoch, discardRevision = discardReadRevision
        let privateDraftIDs = await privateDraftConversationIDs()
        guard token == epoch, discardRevision == discardReadRevision else { return }
        for chat in values { observeExecutionCleanup(chat.id, revision: chat.execution_cleanup_revision ?? 0) }
        if let id = selectedID, !values.contains(where: { $0.id == id }) { await inspectConversation(id) }
        else { inspectedConversation = nil }
        var allowed = Set(values.map(\.id))
        if let inspectedConversation { allowed.insert(inspectedConversation.id) }
        revokedChats.formUnion(checkingAccess.subtracting(allowed))
        revokedChats.subtract(allowed)
        for id in Set(timelines.keys).union(uploadDrafts.keys).union(checkingAccess).union(pending.keys).union(interactionConversations.values).union(privateDraftIDs) where !allowed.contains(id) {
            // A degraded partition still has old JSON/handoff qualification to revoke.
            await revokeConversation(id, reason: .snapshotAbsent)
            errors[id] = L("你已无法访问此聊天。", "You no longer have access to this conversation.")
        }
        for chat in values where chat.can_write == false || chat.dissolved_at != nil {
            await discardConversationAttempts(chat.id)
        }
        guard token == epoch, discardRevision == discardReadRevision else { return }
        checkingAccess = []
        conversations = values
        listPhase = values.isEmpty ? .empty : .loaded
        listError = nil
    }

    func loadConversations() async {
        guard let request = try? await readRequest() else { return }
        do {
            let page: ItemsPage<Conversation> = try await client.get("/im/v1/conversations")
            guard await isCurrent(request) else { return }
            try await applyConversationList(page.items, request: request)
        } catch {
            guard await isCurrent(request), !(error is CancellationError) else { return }
            let failure = ChatFailure.from(error)
            if listPhase == .loadingFirst { listPhase = .failed }
            connection = failure.connection ?? connection
            listError = error.localizedDescription
            if failure != .unauthorized { for id in checkingAccess { errors[id] = error.localizedDescription } }
        }
    }

    /// A conversation page is not authority for absence: it may add rows, never revoke them.
    /// Without a partition there is nothing durable to keep, so the page uses the same
    /// pure-network reconcile a degraded launch uses (it inspects the open conversation and
    /// drops rows the server no longer lists).
    private func applyConversationList(_ items: [Conversation], request: ReadRequest) async throws {
        guard let repository = request.repository, let context = request.context else {
            await reconcileNetwork(items)
            return
        }
        let values: [Conversation]
        do { values = try await repository.applyConversationList(items, write: context) }
        catch {
            guard request.epoch == epoch, request.repository === self.repository else { throw CancellationError() }
            if let cleanup = error as? ChatCleanupFailure { handleCleanupFailure(cleanup) }
            throw error
        }
        guard await isCurrent(request) else { return }
        guard values.allSatisfy({ ($0.execution_cleanup_revision ?? 0) >= (executionCleanupRevisions[$0.id] ?? 0) }) else { throw CancellationError() }
        for chat in values { observeExecutionCleanup(chat.id, revision: chat.execution_cleanup_revision ?? 0) }
        conversations = normalizingDeletedActors(values)
        listPhase = values.isEmpty && pendingCount == 0 ? .empty : (values.isEmpty ? .loadingFirst : .loaded)
        listError = nil
    }

    func inspectConversation(_ id: String) async {
        guard let request = try? await readRequest() else { return }
        do {
            let loaded: Conversation = try await client.get("/im/v1/conversations/\(id.pathComponent)")
            guard await isCurrent(request) else { return }
            let value = try await persistConversation(loaded, request: request)
            guard await isCurrent(request) else { return }
            inspectedConversation = value; revokedChats.remove(id); checkingAccess.remove(id)
        } catch {
            guard await isCurrent(request) else { return }
            inspectedConversation = nil
            if [403, 404].contains((error as? APIError)?.status ?? 0) {
                await revokeConversation(id, reason: .detailForbidden)
                revokedChats.insert(id)
                conversations.removeAll { $0.id == id }
                errors[id] = L("此聊天已不可访问。", "This conversation is no longer accessible.")
            } else {
                connection = ChatFailure.from(error).connection ?? connection
                errors[id] = error.localizedDescription
            }
        }
    }

    @discardableResult
    private func persistConversation(_ value: Conversation, request: ReadRequest) async throws -> Conversation {
        var projection = value
        if let repository = request.repository, let context = request.context {
            do { projection = try await repository.applyConversation(value, members: value.participants, write: context) }
            catch {
                guard request.epoch == epoch, request.repository === self.repository else { throw CancellationError() }
                if let cleanup = error as? ChatCleanupFailure { handleCleanupFailure(cleanup) }
                throw error
            }
        }
        guard await isCurrent(request) else { throw CancellationError() }
        guard (projection.execution_cleanup_revision ?? 0) >= (executionCleanupRevisions[projection.id] ?? 0) else { throw CancellationError() }
        observeExecutionCleanup(projection.id, revision: projection.execution_cleanup_revision ?? 0)
        projection = normalizingDeletedActors([projection])[0]
        if let index = conversations.firstIndex(where: { $0.id == projection.id }) { conversations[index] = projection }
        conversations = normalizingDeletedActors(conversations, including: [projection])
        if let inspectedConversation {
            self.inspectedConversation = normalizingDeletedActors([inspectedConversation], including: [projection])[0]
        }
        return projection
    }

    /// Actor deletion is permanent across conversations, including degraded network projections.
    private func normalizingDeletedActors(_ values: [Conversation], including extra: [Conversation] = []) -> [Conversation] {
        knownDeletedActorIDs.formUnion((conversations + [inspectedConversation].compactMap { $0 } + values + extra)
            .flatMap(\.participants).filter { $0.is_deleted == true }.map(\.id))
        func normalized(_ value: Conversation) -> Conversation {
            var value = value
            value.participants = value.participants.map { actor in
                var actor = actor
                if knownDeletedActorIDs.contains(actor.id) { actor.is_deleted = true }
                return actor
            }
            return value
        }
        // A list can learn a deletion in another chat while its stale detail remains open.
        if let inspectedConversation { self.inspectedConversation = normalized(inspectedConversation) }
        return values.map(normalized)
    }

    /// Entering a cached chat never waits for the detail request (including its timeout).
    func openConversation(_ id: String) async {
        selectedID = id
        guard !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
        await loadLocalTimeline(id)
        async let detail: Void = inspectConversation(id)
        async let messages: Void = loadChat(id)
        _ = await (detail, messages)
    }

    func loadChat(_ id: String, older: Bool = false) async {
        guard !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
        let token = epoch
        // Local first: an open conversation paints from disk before the request completes.
        await loadLocalTimeline(id)
        guard token == epoch, !Task.isCancelled else { return }
        guard let request = try? await readRequest() else { return }
        do {
            var page = try await client.messages(id, before: older ? before[id] : nil)
            guard token == epoch, !Task.isCancelled, !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
            let revision = page.execution_cleanup_revision ?? 0
            let advanced = observeExecutionCleanup(id, revision: revision)
            guard revision == (executionCleanupRevisions[id] ?? 0) else { return }
            if advanced && older {
                // Still persist the fence even when this older page is not admitted.
                if let repository = request.repository, let context = request.context {
                    _ = try await repository.applyPage(id, items: [], executionCleanupRevision: revision, write: context)
                }
                dirtyChats.insert(id); scheduleRefresh()
                return
            }
            let anchor = pendingReadingPositions[id]
            let boundary = anchor.map { Set([$0]) } ?? Set((timelines[id] ?? []).map(\.id))
            // Bridge pages must share a revision; a cleanup midway restarts from the latest page.
            while !older, !boundary.isEmpty, !page.items.contains(where: { boundary.contains($0.id) }), let next = page.next_before_message_id {
                let previous = try await client.messages(id, before: next)
                guard token == epoch, !Task.isCancelled, !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
                if observeExecutionCleanup(id, revision: previous.execution_cleanup_revision ?? 0) {
                    if let repository = request.repository, let context = request.context {
                        _ = try await repository.applyPage(id, items: [], executionCleanupRevision: previous.execution_cleanup_revision ?? 0, write: context)
                    }
                    dirtyChats.insert(id); scheduleRefresh()
                    return
                }
                guard revision == (executionCleanupRevisions[id] ?? 0), (previous.execution_cleanup_revision ?? 0) == revision else { return }
                page.items = TimelineMerge.merge(current: page.items, page: previous.items, older: true, discarded: discarded)
                page.next_before_message_id = previous.next_before_message_id
            }
            guard await isCurrent(request), revision == (executionCleanupRevisions[id] ?? 0) else { return }
            try await applyPage(id, page: page, older: older, request: request)
            guard await isCurrent(request), revision == (executionCleanupRevisions[id] ?? 0) else { return }
            if older || before[id] == nil { before[id] = page.next_before_message_id }
            if !older, let anchor {
                pendingReadingPositions[id] = nil
                if page.items.contains(where: { $0.id == anchor }) { restoreReadingPositions[id] = anchor }
            }
            errors[id] = nil
            await recoverPending(id)
        } catch {
            guard await isCurrent(request), !(error is CancellationError) else { return }
            let failure = ChatFailure.from(error)
            if [403, 404].contains((error as? APIError)?.status ?? 0) { await revokeConversation(id, reason: .detailForbidden) }
            guard token == epoch else { return }
            connection = failure.connection ?? connection
            errors[id] = error.localizedDescription
        }
    }

    /// Merge the durable window into the rendered projection. `TimelineMerge` supplies the
    /// same `(created_at, id)` order the network merge uses, so a correction cannot reorder rows.
    private func loadLocalTimeline(_ id: String) async {
        guard !revokedChats.contains(id), !checkingAccess.contains(id),
              let request = try? await readRequest(), let repository = request.repository,
              let page = try? await repository.timeline(id), await isCurrent(request),
              !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
        guard page.executionCleanupRevision >= (executionCleanupRevisions[id] ?? 0) else { return }
        observeExecutionCleanup(id, revision: page.executionCleanupRevision)
        if !page.items.isEmpty {
            timelines[id] = TimelineMerge.merge(current: timelines[id] ?? [], page: page.items, older: false, discarded: discarded)
        }
        if page.olderNeedsNetwork, before[id] == nil { olderNeedsNetwork.insert(id) } else { olderNeedsNetwork.remove(id) }
    }

    private func applyPage(_ id: String, page: MessagePage, older: Bool, request: ReadRequest,
                           recordsHistory: Bool = true) async throws {
        let revision = page.execution_cleanup_revision ?? 0
        guard revision >= (executionCleanupRevisions[id] ?? 0) else { throw ChatRepositoryError.staleWrite }
        if let repository = request.repository, let context = request.context {
            let result = try await repository.applyPage(id, items: page.items,
                                                        hasEarlierMessages: recordsHistory ? page.next_before_message_id != nil : nil,
                                                        executionCleanupRevision: revision, write: context)
            guard await isCurrent(request), result.executionCleanupRevision >= (executionCleanupRevisions[id] ?? 0) else { return }
            observeExecutionCleanup(id, revision: result.executionCleanupRevision)
            if result.olderNeedsNetwork, before[id] == nil { olderNeedsNetwork.insert(id) } else { olderNeedsNetwork.remove(id) }
            timelines[id] = TimelineMerge.merge(current: timelines[id] ?? [], page: result.items, older: true, discarded: discarded)
        } else {
            guard await isCurrent(request), revision >= (executionCleanupRevisions[id] ?? 0) else { return }
            observeExecutionCleanup(id, revision: revision)
            timelines[id] = TimelineMerge.merge(current: timelines[id] ?? [], page: page.items, older: older, discarded: discarded)
        }
        if recordsHistory { receivedTimelineResults.insert(id) }
    }

    func consume(_ event: UserEvent,
                 writeCleanup: @Sendable (ChatRepository, UserEvent, ChatWriteContext) async throws -> ChatEventResult = {
                     try await $0.applyEvent($1, write: $2)
                 }) async {
        let data = event.data ?? .null
        let chat = data["conversation_id"].stringValue
        if event.event_type == "conversation.execution_cleanup" {
            if let eventID = event.event_id { cursor = max(cursor ?? 0, eventID) }
            if let chat {
                let token = epoch, target = repository
                let advanced = observeExecutionCleanup(chat, revision: data["execution_cleanup_revision"].intValue ?? 0)
                if let target {
                    do {
                        // Another snapshot may supersede the context while this actor call is
                        // queued. Cleanup is monotonic: retry its qualification, not its authority.
                        while token == epoch, target === repository, !Task.isCancelled {
                            let context = try await target.writeContext()
                            guard token == epoch, target === repository, !Task.isCancelled else { return }
                            do { _ = try await writeCleanup(target, event, context); break }
                            catch ChatRepositoryError.staleWrite { continue }
                        }
                    } catch {
                        guard token == epoch, target === repository, !Task.isCancelled,
                              !(error is CancellationError) else { return }
                        // Only current, actual IO failures may degrade storage. An older owner
                        // cannot publish a failure into the partition that replaced it.
                        let reason = error.localizedDescription
                        if let storageController { storageController.reportStorageFailure(reason) }
                        else { storage = .degraded(reason: reason) }
                    }
                }
                guard token == epoch, !Task.isCancelled else { return }
                if advanced { dirtyChats.insert(chat); needsList = true; scheduleRefresh() }
            }
            return
        }
        if event.event_type == "conversation.membership_changed" || event.event_type == "conversation.deleted" {
            // The cursor-free frame also covers creation, rename and member addition, so the
            // event alone cannot tell "renamed" from "removed". Ask the server.
            if let chat { await verifyAccess(chat) } else { needsList = true; scheduleRefresh() }
            return
        }
        guard let eventID = event.event_id, eventID > (cursor ?? 0) else { return }
        cursor = eventID
        if event.event_type == "message.discarded", let id = data["message_id"].stringValue {
            discardReadRevision = UUID()
            if !checkingAccess.isEmpty { scheduleAccessRecovery() }
            discarded.insert(id)
            if let chat { timelines[chat]?.removeAll { $0.id == id } }
        }
        if let chat { dirtyChats.insert(chat) }
        needsList = true
        // Human writes emit message.sent; their optional creation event must not remind twice.
        let newMessage = (event.event_type == "message.sent" && data["sender_type"].stringValue == "user")
            || (event.event_type == "message.created" && (data["sender_type"].stringValue != "user" || data["pa_agent_id"].stringValue != nil))
        if newMessage, eventID > notificationFloor,
           let chat, chat != selectedID, conversations.contains(where: { $0.id == chat && !$0.is_muted }),
           data["sender_user_id"].stringValue != user.id,
           UserDefaults.standard.object(forKey: "nano.foregroundReminders") as? Bool ?? true {
            banner = ChatBanner(conversationID: chat)
        }
        await persistEvent(event)
        scheduleRefresh()
    }

    private func persistEvent(_ event: UserEvent) async {
        guard let repository else { return }
        let token = epoch
        while token == epoch, repository === self.repository, !Task.isCancelled {
            do {
                let context = try await repository.writeContext()
                guard token == epoch, repository === self.repository, !Task.isCancelled else { return }
                _ = try await repository.applyEvent(event, write: context)
                return
            } catch ChatRepositoryError.staleWrite { continue }
            catch { return }
        }
    }

    /// Targeted access check for `membership_changed` (design D11): keep the list row, hold the
    /// timeline behind the existing "checking access" placeholder, and let the detail response
    /// decide. A transport failure decides nothing — the next successful sync converges.
    private func verifyAccess(_ id: String) async {
        checkingAccess.insert(id)
        timelines[id] = nil; before[id] = nil; olderNeedsNetwork.remove(id); receivedTimelineResults.remove(id)
        if banner?.conversationID == id { banner = nil }
        guard let request = try? await readRequest() else { return }
        do {
            let loaded: Conversation = try await client.get("/im/v1/conversations/\(id.pathComponent)")
            guard await isCurrent(request) else { return }
            let value = try await persistConversation(loaded, request: request)
            guard await isCurrent(request) else { return }
            // The open view prefers inspected detail. Publish the access check here,
            // not in the shared writer: a late /read DTO must not replace that detail.
            if inspectedConversation?.id == id { inspectedConversation = value }
            checkingAccess.remove(id); revokedChats.remove(id)
            await loadLocalTimeline(id)
            if timelines[id]?.isEmpty ?? true { await loadChat(id) }
        } catch {
            guard await isCurrent(request), !(error is CancellationError) else { return }
            let failure = ChatFailure.from(error)
            switch failure {
            case .forbidden:
                await revokeConversation(id, reason: .membershipDenied)
                revokedChats.insert(id)
                conversations.removeAll { $0.id == id }
                errors[id] = L("此聊天已不可访问。", "This conversation is no longer accessible.")
            case .unauthorized, .deactivated:
                connection = failure.connection ?? connection
            default:
                connection = failure.connection ?? connection
                errors[id] = error.localizedDescription
                scheduleAccessRecovery()
            }
        }
    }

    /// The placeholder's retry must recheck authority, not reload a list that cannot decide absence.
    func retryAccess(_ id: String) async { await verifyAccess(id) }

    /// A healthy socket may never reconnect. Resolve an inconclusive membership check with
    /// bounded full-sync retries rather than leaving its placeholder there indefinitely.
    private func scheduleAccessRecovery() {
        guard accessRecovery == nil else { return }
        let token = epoch
        accessRecovery = Task { [weak self] in
            guard let self else { return }
            defer { self.accessRecovery = nil }
            for delay in [1, 2, 4] {
                do { try await Task.sleep(for: .seconds(delay)) } catch { return }
                guard token == self.epoch, !Task.isCancelled, !self.checkingAccess.isEmpty else { return }
                do {
                    let request = try await self.readRequest()
                    let sync: SyncSnapshot = try await self.client.get("/im/v1/sync")
                    guard await self.isCurrent(request) else { continue }
                    try await self.applySnapshot(sync, request: request)
                    self.connection = .online
                    if let id = self.selectedID { await self.loadLocalTimeline(id) }
                    return
                } catch {
                    guard token == self.epoch, !Task.isCancelled else { return }
                    if error is CancellationError || (error as? ChatRepositoryError) == .staleWrite { continue }
                    self.connection = ChatFailure.from(error).connection ?? self.connection
                }
            }
            // A failed bounded recovery keeps the explicit retry available. It does not
            // infer revocation, clear the cache or introduce U7's connection coordinator.
        }
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
    /// Keep the scroll anchor, while discarding all process-bearing pages from the old revision.
    func recordReadingPosition(_ messageID: String?, in conversationID: String) {
        readingPositions[conversationID] = messageID
    }

    @discardableResult
    private func observeExecutionCleanup(_ id: String, revision: Int) -> Bool {
        guard revision > (executionCleanupRevisions[id] ?? 0) else { return false }
        executionCleanupRevisions[id] = revision
        pendingReadingPositions[id] = readingPositions[id] ?? pendingReadingPositions[id]
        timelines[id] = nil
        before[id] = nil
        olderNeedsNetwork.remove(id); receivedTimelineResults.remove(id)
        return true
    }


    func markRead(_ id: String, messageID: String) async {
        guard selectedID == id, let request = try? await readRequest() else { return }
        do {
            let updated: Conversation = try await client.send("/im/v1/conversations/\(id.pathComponent)/read", body: ["last_read_message_id": messageID])
            guard await isCurrent(request) else { return }
            try await persistConversation(updated, request: request)
            // U1 records only the confirmed boundary. U3 owns monotonic read semantics.
            try? await request.repository?.markReadBoundary(id, messageID: messageID)
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
                await revokeConversation(id, reason: .detailForbidden)
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
        await attemptRestore?.value
        let chat = inspectedConversation?.id == id ? inspectedConversation : conversations.first { $0.id == id }
        guard chat?.can_write != false else { return }
        guard !sending.contains(id), !checkingAccess.contains(id), !revokedChats.contains(id) else { return }
        let token = sendEpoch
        sending.insert(id)
        defer { if token == sendEpoch { sending.remove(id) } }
        // This click owns this text/files, not edits made while the draft PUT is awaited.
        let clickedContent = drafts[id] ?? "", clickedFiles = textOnly ? [] : attachments[id] ?? []
        if !retry {
            let saved = await flushDrafts(id)
            guard token == sendEpoch, !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
            guard saved else {
                errors[id] = L("消息尚未发送，请重试。", "Message was not sent. Please try again.")
                return
            }
            guard pending[id] == nil, !(uploadDrafts[id] ?? []).contains(where: \.uploading),
                  textOnly || (uploadDrafts[id] ?? []).isEmpty else { return }
            let content = clickedContent, files = clickedFiles
            guard !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !files.isEmpty else { return }
            do {
                let revision = try await sessionRevision()
                guard token == sendEpoch else { return }
                guard !revokedChats.contains(id), !checkingAccess.contains(id) else { return }
                let draft = try client.prepareMessage(PendingSend(content: content, attachments: files), userID: user.id,
                    participants: chat?.participants ?? [])
                let attempt = SendAttempt(conversationID: id, sourceMessageID: nil, draft: draft)
                try await persistAttempt(attempt, revision: revision)
                guard token == sendEpoch else { return }
                pending[id] = draft
            } catch { errors[id] = error.localizedDescription; return }
        }
        guard let draft = pending[id] else { return }
        let attempt = SendAttempt(conversationID: id, sourceMessageID: nil, draft: draft)
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
        await attemptRestore?.value
        try requireWritable(id)
        let token = sendEpoch
        guard await flushDrafts(id) else { throw APIError(status: 0, detail: errors[id] ?? "Draft not saved") }
        guard token == sendEpoch else { throw CancellationError() }
        let source = input.source_message_id
        guard interactionPending[source] == nil, !interactionSending.contains(source) else {
            throw APIError(status: 0, detail: unconfirmedText)
        }
        interactionSending.insert(source)
        defer { if token == sendEpoch { interactionSending.remove(source) } }
        let revision = try await sessionRevision()
        guard token == sendEpoch else { throw CancellationError() }
        try requireWritable(id)
        let draft = try client.prepareMessage(PendingSend(key: key, content: "", attachments: []), userID: user.id, interaction: input)
        let attempt = SendAttempt(conversationID: id, sourceMessageID: source, draft: draft)
        try await persistAttempt(attempt, revision: revision)
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
        await attemptRestore?.value
        if repository != nil { await reloadPending() }
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
        guard !cleanupBlocked, unpersistedCleanups.isEmpty,
              !revokedChats.contains(id), !checkingAccess.contains(id), chat?.can_write != false, chat?.dissolved_at == nil else {
            throw APIError(status: 403, detail: L("此聊天不能发送消息。", "This conversation does not allow sending."))
        }
    }

    func isGroupConversation(_ id: String) -> Bool {
        let chat = inspectedConversation?.id == id ? inspectedConversation : conversations.first { $0.id == id }
        return chat?.type == "group"
    }

    @discardableResult
    func flushDrafts(_ id: String) async -> Bool {
        // Group drafts remain private until explicit submission.
        if isGroupConversation(id) { return true }
        return await interactionDrafts.flush(id)
    }

    private func isCurrent(_ attempt: SendAttempt, token: UUID) -> Bool {
        guard token == sendEpoch, !revokedChats.contains(attempt.conversationID), !checkingAccess.contains(attempt.conversationID) else { return false }
        if let source = attempt.sourceMessageID { return interactionAttempt(attempt.conversationID, sourceMessageID: source)?.key == attempt.draft.key }
        return pending[attempt.conversationID]?.key == attempt.draft.key
    }

    private func resolveAttempt(_ attempt: SendAttempt, lookup: Bool, resend: Bool) async throws -> ChatMessage? {
        let token = sendEpoch, revision = try await sessionRevision()
        let id = attempt.conversationID
        // A sparse send acknowledgement has no page revision. Pin its qualification before
        // provider IO, not when appendSent receives a potentially pre-cleanup payload.
        let cleanupRevision = try await repository?.executionCleanupRevision(id) ?? executionCleanupRevisions[id] ?? 0
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
            try await removeAttempt(attempt, revision: revision)
            guard isCurrent(attempt, token: token) else { throw CancellationError() }
            await appendSent(message, cleanupRevision: cleanupRevision)
            if let source = attempt.sourceMessageID { interactionPending[source] = nil; interactionConversations[source] = nil }
            else {
                pending[id] = nil
                if drafts[id] == attempt.draft.content {
                    setDraft(id, "")
                } else if drafts[id] == nil {
                    drafts[id] = ""
                }
                let sentIDs = Set(attempt.draft.attachments.map(\.id))
                attachments[id]?.removeAll { sentIDs.contains($0.id) }
            }
            errors[id] = nil
            return message
        } catch {
            guard isCurrent(attempt, token: token), !(error is CancellationError) else { throw CancellationError() }
            try await client.session.assertOwner(user.id, revision: revision)
            if let api = error as? APIError, (400..<500).contains(api.status), ![408, 429].contains(api.status) {
                // A rejected background leaves the original text available for a new send.
                let restoreDraft = api.code == "interaction_background_too_large" && attempt.sourceMessageID == nil
                    && drafts[id] == nil
                try await removeAttempt(attempt, revision: revision, restoreDraft: restoreDraft)
                guard isCurrent(attempt, token: token) else { throw CancellationError() }
                if let source = attempt.sourceMessageID { interactionPending[source] = nil; interactionConversations[source] = nil }
                else {
                    pending[id] = nil
                    if restoreDraft, drafts[id] == nil {
                        drafts[id] = attempt.draft.content
                    }
                }
                if [403, 404].contains(api.status) { await revokeConversation(id, reason: .detailForbidden) }
                errors[id] = api.detail
                throw api
            }
            errors[id] = unconfirmedText
            throw APIError(status: 0, detail: unconfirmedText)
        }
    }

    /// The confirmed message joins the durable window too, so the next first paint shows it.
    private func appendSent(_ message: ChatMessage, cleanupRevision: Int) async {
        guard let request = try? await readRequest() else { return }
        let item = TimelineItem(type: "message", message: message)
        try? await applyPage(message.conversation_id, page: MessagePage(items: [item], execution_cleanup_revision: cleanupRevision), older: false, request: request, recordsHistory: false)
    }

    private func persistAttempt(_ attempt: SendAttempt, revision: Int) async throws {
        let token = sendEpoch, projection = projectionRevision
        let currentRepository = repository
        if let currentRepository {
            // The pending transaction consumes composer text, so it belongs to the same
            // chain as every draft writer, not merely to the repository's SQLite queue.
            // Freeze the request before waiting; newer composer edits remain separate.
            await flushDrafts()
            let previous = draftWriteTail
            let task = Task { [weak self] in
                await previous?.value
                guard let self, token == self.sendEpoch, projection == self.projectionRevision,
                      currentRepository === self.repository else { throw CancellationError() }
                try await self.client.session.assertOwner(self.user.id, revision: revision)
                let context = try await currentRepository.writeContext()
                guard token == self.sendEpoch, projection == self.projectionRevision,
                      currentRepository === self.repository else { throw CancellationError() }
                try self.requireWritable(attempt.conversationID)
                try await currentRepository.upsertPending(attempt, write: context)
                guard token == self.sendEpoch, projection == self.projectionRevision else { throw CancellationError() }
                try self.requireWritable(attempt.conversationID)
                if attempt.sourceMessageID == nil, self.drafts[attempt.conversationID] == attempt.draft.content {
                    // Absence means this attempt owns the text. An explicitly cleared
                    // newer composer draft is the empty string and stays independent.
                    self.drafts[attempt.conversationID] = nil; self.queuedDrafts[attempt.conversationID] = nil
                    self.dirtyDraftIDs.remove(attempt.conversationID)
                }
            }
            draftWriteTail = Task { _ = try? await task.value }
            try await task.value
        } else {
            let stamp = try await client.session.reserveSendAttempt(attempt.conversationID, userID: user.id, revision: revision)
            guard token == sendEpoch, projection == projectionRevision else { throw CancellationError() }
            try requireWritable(attempt.conversationID)
            // A cleanup between this UI check and the file write invalidates the captured
            // stamp under the shared lock. It cannot relabel this old request as a new one.
            try await client.session.saveSendAttempt(attempt, stamp: stamp, userID: user.id, revision: revision)
            guard token == sendEpoch, projection == projectionRevision else { throw CancellationError() }
            try requireWritable(attempt.conversationID)
        }
    }

    private func removeAttempt(_ attempt: SendAttempt, revision: Int, restoreDraft: Bool = false) async throws {
        if let repository {
            try await client.session.assertOwner(user.id, revision: revision)
            let context = try await repository.writeContext()
            try await repository.removePending(attempt, restoreDraft: restoreDraft, write: context)
        } else {
            try await client.session.removeSendAttempt(attempt, userID: user.id, revision: revision)
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
        let token = epoch
        pending[id] = nil
        for source in interactionConversations.filter({ $0.value == id }).map(\.key) {
            interactionPending[source] = nil; interactionConversations[source] = nil; interactionSending.remove(source)
        }
        await forgetInteractionDrafts(id)
        do {
            if let repository {
                let context = try await repository.writeContext()
                try await repository.deletePending(conversationID: id, write: context)
            } else {
                let revision = try await sessionRevision()
                try await client.session.removeConversationAttempts(id, userID: user.id, revision: revision)
            }
        } catch {
            guard token == epoch else { return }
            handleCleanupFailure(error, conversationID: id, kind: .discardPending)
        }
    }

    private func handleCleanupFailure(_ failure: ChatCleanupFailure) {
        for intent in failure.intents {
            handleCleanupFailure(failure, conversationID: intent.conversationID, kind: intent.kind)
        }
    }

    private func handleCleanupFailure(_ error: Error, conversationID: String, kind: ChatAttemptPersistence.CleanupKind) {
        if error is CancellationError { return }
        if let repositoryError = error as? ChatRepositoryError {
            switch repositoryError {
            case .staleWrite, .revokedConversation: return
            case .databaseUnavailable: break
            }
        }
        let reason = error.localizedDescription
        if let storageController {
            storageController.reportCleanupFailure(reason, conversationID: conversationID, kind: kind)
        } else {
            let previous = unpersistedCleanups[conversationID]
            unpersistedCleanups[conversationID] = previous == .revokeAccess ? .revokeAccess : kind
            blockForCleanup()
            storage = .degraded(reason: reason)
        }
        listError = reason
    }

    /// Removes one conversation's rendered state and books the revocation in the store, so a
    /// restart or an offline launch cannot show it again once access is known to be gone.
    private func revokeConversation(_ id: String, reason: ChatRevokeReason?) async {
        projectionRevision = UUID()
        let token = epoch
        // Stop rendering before IO. Access revocation must not first commit the weaker
        // discardPending intent: a crash in that gap would retain readable revoked history.
        clearConversationState(id)
        revokedChats.insert(id)
        conversations.removeAll { $0.id == id }
        if inspectedConversation?.id == id { inspectedConversation = nil }
        await forgetInteractionDrafts(id)
        do {
            if let reason, let repository {
                let context = try await repository.writeContext()
                guard token == epoch else { return }
                try await repository.revoke(id, reason: reason, write: context)
            } else if repository == nil, reason != nil {
                let revision = try await sessionRevision()
                guard token == epoch else { return }
                try await client.session.removeConversationAttempts(id, kind: .revokeAccess,
                                                                     userID: user.id, revision: revision)
            }
        } catch {
            guard token == epoch else { return }
            handleCleanupFailure(error, conversationID: id, kind: .revokeAccess)
        }
    }

    private func privateDraftConversationIDs() async -> Set<String> {
        let live = Set(interactionDrafts.watermarks.keys)
        guard let revision = try? await sessionRevision(),
              let stored = try? await client.session.draftLedgerConversationIDs(userID: user.id, revision: revision) else { return live }
        return live.union(stored)
    }

    private func forgetInteractionDrafts(_ id: String) async {
        interactionDrafts.remove(id)
        await eraseDraftLedger(id)
    }

    private func eraseDraftLedger(_ id: String) async {
        if let revision = try? await sessionRevision() {
            try? await client.session.removeDraftLedger(id, userID: user.id, revision: revision)
        }
    }

    private func clearConversationState(_ id: String) {
        queuedDrafts[id] = nil; dirtyDraftIDs.remove(id)
        timelines[id] = nil; before[id] = nil; drafts[id] = nil; attachments[id] = nil; uploadDrafts[id] = nil
        olderNeedsNetwork.remove(id); receivedTimelineResults.remove(id); pending[id] = nil
        for source in interactionConversations.filter({ $0.value == id }).map(\.key) {
            interactionPending[source] = nil; interactionConversations[source] = nil; interactionSending.remove(source)
        }
    }
}
