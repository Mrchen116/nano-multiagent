import Foundation

struct AuthUser: Codable, Sendable, Equatable {
    var id: String
    var username: String
    var display_name: String
    var owner_id: String
    var locale: String
    var membership_status: String
    var is_company_admin: Bool
    var default_entry_node_id: String?
    var owned_node_ids: [String]
    var created_at: String
}

struct Contact: Codable, Identifiable, Sendable, Hashable {
    var user_id: String
    var kind: String
    var display_name: String
    var agent_id: String?
    var owner_id: String?
    var owner_display_name: String?
    var node_name: String?
    var status: String?
    var work_mode: String?
    var id: String { user_id }
    var actor: ActorRef { ActorRef(type: kind == "agent" ? "agent" : "user", id: agent_id ?? user_id) }
}

struct ActorRef: Codable, Sendable, Hashable {
    var type: String
    var id: String
    var display_name: String?
    var user_id: String?
    var is_stale: Bool?
}

struct APIError: Error, LocalizedError, Sendable {
    var status: Int
    var detail: String
    var retryAfter: TimeInterval = 0
    var code: String? = nil
    var errorDescription: String? { detail }
}

struct TokenPair: Codable, Sendable {
    let access_token: String
    let refresh_token: String
    let user: AuthUser
}

struct StoredSession: Codable, Sendable {
    let refresh_token: String
    let user: AuthUser
}
