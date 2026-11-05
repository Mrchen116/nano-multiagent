import Foundation
import Observation

/// Owns the lifecycle of exactly one local chat partition at a time.
///
/// It decides *when* a partition is opened or dropped; it holds no business SQL and never
/// chooses what to delete inside a conversation. `ChatStore` only consumes the published
/// state, so a deleted partition cannot be resurrected by a late write from the store.
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
    private weak var store: ChatStore?
    private let client: IMClient
    private let makeLocation: (ChatPartition) -> ChatStorageLocation
    private var opening: Task<Void, Never>?

    init(client: IMClient, location: ((ChatPartition) -> ChatStorageLocation)? = nil) {
        self.client = client
        self.makeLocation = location ?? { ChatStorageLocation.standard(partition: $0) }
    }

    var repository: ChatRepository? {
        if case .ready(let repository) = state { return repository }
        return nil
    }

    /// The store is created when the UI first shows the account; it receives the current
    /// state immediately so it never renders "no local cache" for a partition that is
    /// merely still opening.
    func attach(_ store: ChatStore) {
        self.store = store
        store.bind(storage: state)
    }

    /// Launch path: open the partition of the account already stored in the Keychain.
    /// Reads the credential only; no network call happens here.
    func bootstrapOnLaunch() async {
        guard let user = (try? await client.session.storedUser()) ?? nil else {
            publish(.opening)
            return
        }
        await open(ChatPartition(origin: client.baseURL, userID: user.id))
    }

    /// Called after credentials were accepted (first login, account switch) and whenever the
    /// session publishes a user whose `(origin, userID)` no longer matches the open partition.
    func activate(_ next: ChatPartition) async {
        if partition == next, repository != nil { return }
        if partition != nil { await closeAndPurge() }
        await open(next)
    }

    /// `.degraded` retry point: user tap, next foreground, or next `run()`, whichever is first.
    func retryOpen() async {
        guard let partition else { return }
        await open(partition)
    }

    /// The only purge entry point. Triggered by `Session.termination` (nil user or an
    /// unavailable account) and by partition switches — never by `ChatStore`.
    func purge(reason: PurgeReason) async {
        await closeAndPurge()
        publish(reason == .partitionChanged ? .opening : .degraded(reason: Self.describe(reason)))
    }

    private static func describe(_ reason: PurgeReason) -> String {
        switch reason {
        case .signedOut, .credentials, .partitionChanged:
            return L("已退出登录，本机聊天内容已清除。", "Signed out; local chat content was cleared.")
        case .deactivated:
            return L("账号当前不可用，本机聊天内容已清除。", "Account unavailable; local chat content was cleared.")
        }
    }

    private func open(_ next: ChatPartition) async {
        opening?.cancel()
        partition = next
        publish(.opening)
        let location = makeLocation(next)
        let task = Task.detached(priority: .userInitiated) { () -> Result<ChatRepository, Error> in
            do { return .success(try ChatRepository.open(next, location: location)) }
            catch { return .failure(error) }
        }
        opening = Task { [weak self] in
            let result = await task.value
            guard !Task.isCancelled, let self, self.partition == next else { return }
            switch result {
            case .success(let repository):
                self.publish(.ready(repository))
            case .failure(let error):
                self.publish(.degraded(reason: error.localizedDescription))
            }
        }
        await opening?.value
    }

    private func closeAndPurge() async {
        opening?.cancel()
        opening = nil
        guard let repository else {
            partition = nil
            store?.resetProjection()
            return
        }
        try? await repository.purge()
        partition = nil
        store?.resetProjection()
    }

    private func publish(_ next: ChatStorageState) {
        state = next
        store?.bind(storage: next)
    }
}
