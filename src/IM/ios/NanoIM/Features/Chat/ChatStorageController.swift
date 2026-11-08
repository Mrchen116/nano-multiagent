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
        await activate(ChatPartition(origin: client.baseURL, userID: user.id))
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
        guard let partition else { return }
        await activate(partition)
    }

    func purge(reason: PurgeReason) async { await move(to: nil, reason: reason) }

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
        generation += 1
        let token = generation
        if partition != next { store?.resetProjection() }
        partition = next
        publish(.opening)
        let task = Task { [weak self] in
            // Cancellation cannot stop a synchronous SQLite open. Drain it and let its
            // stale-generation branch close/purge before this transition touches disk.
            await previous?.value
            guard let self, token == self.generation else { return }
            do {
                if next == nil || (self.openedPartition != nil && self.openedPartition != next) {
                    try await self.clearOpenedPartition()
                }
                guard token == self.generation else { return }
                guard let next else {
                    self.publish(reason == .partitionChanged ? .opening : .degraded(reason: Self.describe(reason ?? .signedOut)))
                    return
                }
                let location = self.makeLocation(next)
                self.openedPartition = next
                self.openedLocation = location
                let opener = self.opener
                let signpostID = Self.signposter.makeSignpostID()
                let interval = Self.signposter.beginInterval("open", id: signpostID)
                defer { Self.signposter.endInterval("open", interval) }
                let result = await Task.detached(priority: .userInitiated) {
                    do { return Result<ChatRepository, Error>.success(try await opener(next, location)) }
                    catch { return .failure(error) }
                }.value
                switch result {
                case .success(let repository):
                    self.activeRepository = repository
                    guard token == self.generation, self.partition == next else {
                        try await self.clearOpenedPartition()
                        return
                    }
                    do {
                        let seed = try await repository.bootstrapSeed()
                        guard token == self.generation, self.partition == next else {
                            try await self.clearOpenedPartition()
                            return
                        }
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
                        try await self.clearOpenedPartition()
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

    /// Also handles `.opening` and `.degraded`: their on-disk partition can exist even when
    /// no repository has been published. Earlier opener tasks have already been drained.
    private func clearOpenedPartition() async throws {
        if let activeRepository { try await activeRepository.purge() }
        if let openedLocation { try openedLocation.removeAll() }
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
