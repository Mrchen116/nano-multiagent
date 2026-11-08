import Foundation
import Observation
import os

/// Owns one partition lifecycle. Transitions drain earlier opens before deleting or opening
/// another partition; no detached opener can recreate data after its sign-out completes.
@MainActor @Observable
final class ChatStorageController {
    enum PurgeReason: Sendable {
        case signedOut
        case credentials
        case deactivated
        case partitionChanged
    }

    private(set) var state: ChatStorageState = .opening
    private(set) var partition: ChatPartition?
    @ObservationIgnored private weak var store: ChatStore?
    private let client: IMClient
    private let makeLocation: (ChatPartition) -> ChatStorageLocation
    private let opener: @Sendable (ChatPartition, ChatStorageLocation) async throws -> ChatRepository
    @ObservationIgnored private var transition: Task<Void, Never>?
    @ObservationIgnored private var generation = 0
    @ObservationIgnored private var activeRepository: ChatRepository?
    @ObservationIgnored private var openedPartition: ChatPartition?
    @ObservationIgnored private var openedLocation: ChatStorageLocation?
    @ObservationIgnored private var launchSeed: ChatBootstrapSeed?
    @ObservationIgnored private var pendingCleanups: [ChatPartition: [String: ChatAttemptPersistence.CleanupKind]] = [:]
    private struct RequiredPurge {
        let id = UUID()
        let location: ChatStorageLocation
    }
    // Publication generations can be superseded; accepted cleanup authority cannot. Keep
    // that intent separate, including failures before the on-disk policy could be written.
    @ObservationIgnored private var requiredPurges: [ChatPartition: RequiredPurge] = [:]
    private static let signposter = OSSignposter(subsystem: "com.nanoim.app", category: "ChatStorage")

    init(client: IMClient,
         opener: @escaping @Sendable (ChatPartition, ChatStorageLocation) async throws -> ChatRepository = { partition, location in
             try ChatRepository.open(partition, location: location)
         },
         location: ((ChatPartition) -> ChatStorageLocation)? = nil) {
        self.client = client
        self.opener = opener
        self.makeLocation = location ?? { ChatStorageLocation.standard(partition: $0) }
    }

    var repository: ChatRepository? {
        if case .ready(let repository) = state { return repository }
        return nil
    }

    /// Attach only the account owner's stable store, never a temporary View initializer.
    /// Seed delivery is a value, not a read-and-consume event that mutates observed state.
    func attach(_ store: ChatStore) {
        guard self.store !== store else { return }
        self.store = store
        store.bind(storage: state, seed: launchSeed)
    }

    /// Read credentials and the local partition only; no network participates in bootstrap.
    func bootstrapOnLaunch() async {
        guard let user = (try? await client.session.storedUser()) ?? nil else {
            publish(.opening)
            return
        }
        let target = ChatPartition(origin: client.baseURL, userID: user.id)
        if user.accountEnabled { await activate(target) }
        else { await purge(reason: .deactivated, partition: target) }
    }

    /// Login and the session observer may call this concurrently. Same-partition callers
    /// share the in-flight transition, rather than canceling and reopening each other's DB.
    func activate(_ next: ChatPartition) async {
        if partition == next {
            if repository != nil { return }
            if let transition { await transition.value; return }
        }
        await move(to: next, reason: nil)
    }

    /// Retry preserves the failed partition's files. Failure to open is not a cleanup signal.
    func retryOpen() async {
        if let partition { await activate(partition) }
        else if !requiredPurges.isEmpty { await move(to: nil, reason: nil) }
    }

    /// A disabled stored owner can require cleanup before this controller has opened any DB.
    func purge(reason: PurgeReason, partition target: ChatPartition? = nil) async {
        if let target { requirePurge(target) }
        await move(to: nil, reason: reason)
    }

    private func requirePurge(_ target: ChatPartition) {
        requiredPurges[target] = RequiredPurge(location: openedPartition == target ? openedLocation ?? makeLocation(target) : makeLocation(target))
    }

    /// Ordinary write failures retain the owner projection/queued text, but cannot advertise
    /// a working cache. Retry closes and reopens this connection without purging requests.
    func reportStorageFailure(_ reason: String) { publish(.degraded(reason: reason)) }

    /// A cleanup whose external intent could not persist is not a successful clear. Hide the
    /// current owner and retain its files/connection for a non-destructive retry.
    func reportCleanupFailure(_ reason: String, conversationID: String, kind: ChatAttemptPersistence.CleanupKind) {
        if let partition {
            let prior = pendingCleanups[partition]?[conversationID]
            pendingCleanups[partition, default: [:]][conversationID] = prior == .revokeAccess ? .revokeAccess : kind
        }
        store?.blockForCleanup()
        publish(.degraded(reason: reason))
    }

    private static func describe(_ reason: PurgeReason) -> String {
        switch reason {
        case .signedOut, .credentials, .partitionChanged:
            return L("已退出登录，本机聊天内容已清除。", "Signed out; local chat content was cleared.")
        case .deactivated:
            return L("账号当前不可用，本机聊天内容已清除。", "Account unavailable; local chat content was cleared.")
        }
    }

    private func move(to next: ChatPartition?, reason: PurgeReason?) async {
        let previous = transition
        // Register synchronously, before publishing nil or creating a task. A newer login
        // must not erase a sign-out that has not yet begun (or whose policy IO failed).
        if let partition, partition != next { requirePurge(partition) }
        generation += 1
        let token = generation
        if partition != next { store?.resetProjection() }
        partition = next
        publish(.opening)
        let task = Task { [weak self] in
            // Cancellation cannot stop a synchronous SQLite open. Drain it before touching
            // its files; only the latest transition publishes, but all required purges survive.
            await previous?.value
            guard let self, token == self.generation else { return }
            do {
                try await self.finishRequiredPurges()
                // A normal retry closes without destroying recoverable pending requests.
                try await self.closeOpenedPartition()
                guard token == self.generation else { return }
                guard let next else {
                    self.publish(reason == .partitionChanged ? .opening : .degraded(reason: Self.describe(reason ?? .signedOut)))
                    return
                }
                let location = self.makeLocation(next)
                await self.client.session.useChatStorage(next, location: location)
                guard token == self.generation else { return }
                self.openedPartition = next
                self.openedLocation = location
                let opener = self.opener
                let pending = self.pendingCleanups[next] ?? [:]
                let signpostID = Self.signposter.makeSignpostID()
                let interval = Self.signposter.beginInterval("open", id: signpostID)
                defer { Self.signposter.endInterval("open", interval) }
                let result = await Task.detached(priority: .userInitiated) {
                    do {
                        let persistence = ChatAttemptPersistence.shared(partition: next, location: location)
                        try persistence.coordinated {
                            // A readable old policy is not evidence that the failed new
                            // cleanup was applied. Retry those known intents before any seed.
                            for (id, kind) in pending.sorted(by: { $0.key < $1.key }) {
                                _ = try persistence.recordCleanup(id, kind: kind)
                            }
                        }
                        return Result<ChatRepository, Error>.success(try await opener(next, location))
                    } catch { return .failure(error) }
                }.value
                switch result {
                case .success(let repository):
                    self.activeRepository = repository
                    guard token == self.generation, self.partition == next else {
                        try await self.closeOpenedPartition()
                        return
                    }
                    do {
                        let seed = try await repository.bootstrapSeed()
                        guard token == self.generation, self.partition == next else {
                            try await self.closeOpenedPartition()
                            return
                        }
                        guard (self.pendingCleanups[next] ?? [:]) == pending else {
                            throw ChatRepositoryError.databaseUnavailable(L("本机内容仍需清理，请重试。", "Local cleanup is still pending; retry storage."))
                        }
                        self.pendingCleanups[next] = nil
                        self.launchSeed = seed
                        self.publish(.ready(repository))
                    } catch {
                        // A failed bootstrap read must not be called a successful local paint,
                        // but its pending requests remain recoverable on a later retry.
                        try? await repository.close()
                        self.activeRepository = nil
                        throw error
                    }
                case .failure(let error):
                    guard token == self.generation else {
                        try await self.closeOpenedPartition()
                        return
                    }
                    throw error
                }
            } catch {
                guard token == self.generation else { return }
                self.publish(.degraded(reason: error.localizedDescription))
            }
        }
        transition = task
        await task.value
        if token == generation { transition = nil }
    }

    /// Cleanup is a prerequisite for every future seed, even for a same-owner activation.
    /// Remove an intent only after physical success, and never consume a newer request that
    /// arrived while the old purge was suspended on its repository/file operation.
    private func finishRequiredPurges() async throws {
        while let (target, request) = requiredPurges.first {
            if openedPartition == target, let activeRepository {
                try await activeRepository.purge()
            } else {
                try await Task.detached(priority: .userInitiated) {
                    try ChatRepository.purgeFiles(partition: target, location: request.location)
                }.value
            }
            if requiredPurges[target]?.id == request.id { requiredPurges[target] = nil }
            pendingCleanups[target] = nil
            if openedPartition == target {
                activeRepository = nil
                openedPartition = nil
                openedLocation = nil
                launchSeed = nil
            }
        }
    }

    /// A stale opener may not publish, but closing it is not authority to delete its owner.
    /// Its successor drains this close and then executes the independently retained purges.
    private func closeOpenedPartition() async throws {
        try await activeRepository?.close()
        activeRepository = nil
        openedPartition = nil
        openedLocation = nil
        launchSeed = nil
    }

    private func publish(_ next: ChatStorageState) {
        state = next
        if case .ready = next {} else { launchSeed = nil }
        store?.bind(storage: next, seed: launchSeed)
    }
}
