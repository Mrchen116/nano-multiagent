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
    var personal_space_enabled: Bool?
    var accountEnabled: Bool { personal_space_enabled == true || membership_status == "active" }
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
    var role: String?
    var avatar_variant: Int?
    var id: String { user_id }
    var actor: ActorRef { ActorRef(type: kind == "agent" ? "agent" : "user", id: agent_id ?? user_id) }
}

struct ActorRef: Codable, Sendable, Hashable {
    var avatar_id: String?
    var type: String
    var id: String
    var display_name: String?
    var user_id: String?
    var is_stale: Bool?
    var is_deleted: Bool?
    var role: String?
    var avatar_variant: Int?
}

struct APIError: Error, LocalizedError, Sendable {
    var status: Int
    var detail: String
    var retryAfter: TimeInterval = 0
    var code: String? = nil
    var blocks: [CapabilityBlock] = []
    var errorDescription: String? {
        switch detail {
        case "invalid credentials": L("用户名或密码不正确。", "Incorrect username or password.")
        case "username already exists": L("这个用户名已有人使用，换一个试试。", "That username is taken. Try another.")
        case "username uses a reserved runtime identity": L("这个用户名无法使用，换一个试试。", "That username is unavailable. Try another.")
        case "password must be at least 8 characters": L("密码至少需要 8 个字符。", "Use at least 8 characters for your password.")
        case "password must be at most 72 UTF-8 bytes": L("密码太长了，请缩短后重试。", "This password is too long. Shorten it and try again.")
        default: detail
        }
    }
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
