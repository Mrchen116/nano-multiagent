import SwiftUI
import UIKit
import Observation

struct UserAvatarRef: Equatable, Hashable, Sendable {
    let userID: String
    let version: String
}

protocol PersonalAvatarBinding {
    var agent_id: String { get }
    var display_name: String { get }
    var avatar_variant: Int? { get }
}

enum AvatarFace: Equatable {
    case person(String, avatar: UserAvatarRef? = nil), group(String), agent(id: String, personal: Bool, variant: Int?)

    var paletteSeed: String {
        switch self {
        case let .person(name, _), let .group(name): name
        case .agent: ""
        }
    }
}

struct AvatarIdentity {
    let key: String
    fileprivate let snapshot: AvatarFace

    private init(_ key: String, _ snapshot: AvatarFace) {
        self.key = key
        self.snapshot = snapshot
    }

    static func userID(_ id: String) -> Self { Self(id, .person("?")) }
    static func group(_ id: String) -> Self { Self("group:" + id, .group(id)) }

    static func actor(_ actor: ActorRef) -> Self {
        let agent = actor.type == "agent"
        let key = actor.avatar_id ?? actor.user_id ?? (agent ? "agent:" + actor.id : actor.id)
        if agent {
            return Self(key, .agent(id:actor.id, personal:actor.role == "personal", variant:actor.avatar_variant))
        }
        let name = actor.display_name.flatMap { $0.isEmpty ? nil : $0 } ?? actor.id
        let avatarRef: UserAvatarRef?
        if actor.avatar_id != nil {
            avatarRef = nil
        } else if let version = actor.avatar_version, !version.isEmpty {
            avatarRef = UserAvatarRef(userID: actor.user_id ?? actor.id, version: version)
        } else {
            avatarRef = nil
        }
        return Self(key, .person(name, avatar: avatarRef))
    }

    static func contact(_ contact: Contact) -> Self {
        actor(ActorRef(type:contact.kind == "agent" ? "agent" : "user", id:contact.agent_id ?? contact.user_id,
                       display_name:contact.display_name, user_id:contact.user_id, role:contact.role,
                       avatar_variant:contact.avatar_variant, avatar_version:contact.avatar_version))
    }

    static func member(_ member: SettingsMember) -> Self {
        let ref = member.avatar_version.flatMap { $0.isEmpty ? nil : UserAvatarRef(userID: member.id, version: $0) }
        return Self(member.id, .person(member.name, avatar: ref))
    }

    static func account(_ account: SettingsAccount) -> Self {
        let name = account.display_name.isEmpty ? account.username : account.display_name
        let uid = account.user_id.isEmpty ? account.id : account.user_id
        let ref = account.avatar_version.flatMap { $0.isEmpty ? nil : UserAvatarRef(userID: uid, version: $0) }
        return Self(uid, .person(name, avatar: ref))
    }

    static func personal(_ binding: some PersonalAvatarBinding) -> Self {
        Self("agent:" + binding.agent_id, .agent(id:binding.agent_id, personal:true, variant:binding.avatar_variant))
    }

    static func created(_ agent: AgentConfig) -> Self {
        Self("agent:" + agent.agent_id, .agent(id:agent.agent_id, personal:false, variant:agent.avatar_variant))
    }

    static func conversation(_ chat: Conversation, selfID: String) -> Self {
        if chat.type == "group" { return .group(chat.id) }
        if let peer = chat.peerAgent ?? chat.participants.first(where: { ($0.user_id ?? $0.id) != selfID }) {
            return .actor(peer)
        }
        return .userID("")
    }

    static func sender(_ message: ChatMessage) -> Self {
        Self(message.sender.avatar_id ?? message.sender_user_id, actor(message.sender).snapshot)
    }

    static func receipt(_ receipt: MessageReceipt) -> Self {
        Self(receipt.recipient_id, receipt.recipient.map { actor($0).snapshot } ?? .person(receipt.display_name))
    }

    static func threadParticipant(_ participant: ThreadParticipant) -> Self {
        Self(participant.id, participant.actor.map { actor($0).snapshot } ?? .person(participant.display_name))
    }
}

struct AvatarDirectory {
    var userID = ""
    private var faces: [String: AvatarFace] = [:]

    init(user: AuthUser? = nil, conversations: [Conversation] = [], contacts: [Contact] = []) {
        for chat in conversations {
            for actor in chat.participants { register(.actor(actor)) }
        }
        for contact in contacts { register(.contact(contact)) }
        if let user {
            userID = user.id
            let ref = user.avatar_version.flatMap { $0.isEmpty ? nil : UserAvatarRef(userID: user.id, version: $0) }
            faces[user.id] = .person(user.display_name.isEmpty ? user.username : user.display_name, avatar: ref)
        }
    }

    private mutating func register(_ identity: AvatarIdentity) {
        faces[identity.key] = identity.snapshot
        if case let .agent(id, _, _) = identity.snapshot { faces["agent:" + id] = identity.snapshot }
    }

    private struct HistoricalFace {
        let face: AvatarFace
        let timestamp: String
        let hasActor: Bool
    }
    private var history: [String: HistoricalFace] = [:]

    /// Historical labels from older servers cannot replace a known Agent portrait.
    func includingHistory(_ messages: [ChatMessage]) -> Self {
        var directory = self
        for message in messages {
            directory.record(.sender(message), at:message.created_at, hasActor:true)
            for receipt in message.receipts ?? [] {
                directory.record(.receipt(receipt), at:message.created_at, hasActor:receipt.recipient != nil)
            }
            for participant in message.thread?.participants ?? [] {
                directory.record(.threadParticipant(participant), at:message.created_at, hasActor:participant.actor != nil)
            }
        }
        return directory
    }

    private mutating func record(_ identity: AvatarIdentity, at timestamp: String, hasActor: Bool) {
        if let previous = history[identity.key] {
            if previous.hasActor && !hasActor { return }
            if previous.hasActor == hasActor && previous.timestamp > timestamp { return }
        }
        let entry = HistoricalFace(face:identity.snapshot, timestamp:timestamp, hasActor:hasActor)
        history[identity.key] = entry
        if case let .agent(id, _, _) = identity.snapshot { history["agent:" + id] = entry }
    }

    func resolve(_ identity: AvatarIdentity) -> AvatarFace {
        faces[identity.key] ?? history[identity.key]?.face ?? identity.snapshot
    }
}

/// Account-scoped, in-memory-only LRU cache for protected human avatar images (never persisted to disk).
@MainActor @Observable
final class AvatarImageStore {
    private let client: IMClient?
    private let maxEntries: Int
    private var images: [String: UIImage] = [:]
    @ObservationIgnored private var order: [String] = []
    @ObservationIgnored private var inFlight: [String: Task<Void, Never>] = [:]
    @ObservationIgnored private var failed: Set<String> = []

    init(client: IMClient? = nil, maxEntries: Int = 256) {
        self.client = client
        self.maxEntries = max(1, maxEntries)
    }

    private func cacheKey(for ref: UserAvatarRef) -> String {
        "\(ref.userID):\(ref.version)"
    }

    func image(for ref: UserAvatarRef) -> UIImage? {
        images[cacheKey(for: ref)]
    }

    var cachedCount: Int { images.count }

    func installForTesting(_ image: UIImage, for ref: UserAvatarRef) {
        store(image, forKey: cacheKey(for: ref))
    }

    private func store(_ image: UIImage, forKey key: String) {
        order.removeAll { $0 == key }
        order.append(key)
        images[key] = image
        while order.count > maxEntries {
            let oldest = order.removeFirst()
            images.removeValue(forKey: oldest)
        }
    }

    func loadIfNeeded(_ ref: UserAvatarRef) {
        guard let client, !ref.userID.isEmpty, !ref.version.isEmpty else { return }
        let key = cacheKey(for: ref)
        if images[key] != nil || inFlight[key] != nil || failed.contains(key) { return }

        let encodedID = ref.userID.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? ref.userID
        let encodedVer = ref.version.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ref.version
        let path = "/im/v1/users/\(encodedID)/avatar?v=\(encodedVer)"

        let task = Task { @MainActor [weak self] in
            defer { self?.inFlight.removeValue(forKey: key) }
            do {
                let (data, mime) = try await client.protectedResource(path)
                guard !Task.isCancelled, let self else { return }
                guard mime.lowercased().hasPrefix("image/"), let decoded = UIImage(data: data) else {
                    self.failed.insert(key)
                    return
                }
                self.failed.remove(key)
                self.store(decoded, forKey: key)
            } catch is CancellationError {
                return
            } catch {
                guard !Task.isCancelled else { return }
                self?.failed.insert(key)
            }
        }
        inFlight[key] = task
    }

    func evict(userID: String, keepingVersion: String? = nil) {
        let prefix = "\(userID):"
        let keepKey = keepingVersion.flatMap { $0.isEmpty ? nil : "\(userID):\($0)" }
        for (key, task) in inFlight where key.hasPrefix(prefix) && key != keepKey {
            task.cancel()
            inFlight.removeValue(forKey: key)
        }
        for key in Array(images.keys) where key.hasPrefix(prefix) && key != keepKey {
            images.removeValue(forKey: key)
            order.removeAll { $0 == key }
        }
        for key in Array(failed) where key.hasPrefix(prefix) {
            failed.remove(key)
        }
    }

    func resetFailures() {
        failed.removeAll()
    }

    func clear() {
        for task in inFlight.values { task.cancel() }
        inFlight.removeAll()
        images.removeAll()
        order.removeAll()
        failed.removeAll()
    }
}

extension EnvironmentValues {
    @Entry var avatarDirectory = AvatarDirectory()
    @Entry var avatarImageStore: AvatarImageStore? = nil
}
