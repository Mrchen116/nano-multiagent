import SwiftUI

protocol PersonalAvatarBinding {
    var agent_id: String { get }
    var display_name: String { get }
    var avatar_variant: Int? { get }
}

enum AvatarFace: Equatable {
    case person(String), group(String), agent(id: String, personal: Bool, variant: Int?)

    var paletteSeed: String {
        switch self {
        case let .person(name), let .group(name): name
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
        return Self(key, agent ? .agent(id:actor.id, personal:actor.role == "personal", variant:actor.avatar_variant)
                              : .person(actor.display_name.flatMap { $0.isEmpty ? nil : $0 } ?? actor.id))
    }

    static func contact(_ contact: Contact) -> Self {
        actor(ActorRef(type:contact.kind == "agent" ? "agent" : "user", id:contact.agent_id ?? contact.user_id,
                       display_name:contact.display_name, user_id:contact.user_id, role:contact.role, avatar_variant:contact.avatar_variant))
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
            faces[user.id] = .person(user.display_name.isEmpty ? user.username : user.display_name)
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

extension EnvironmentValues {
    @Entry var avatarDirectory = AvatarDirectory()
}
