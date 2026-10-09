import Foundation

struct SettingsAccount: Codable, Sendable, Equatable {
    let id: String
    let user_id: String
    let username: String
    var display_name: String
    let owner_id: String
    let owned_node_ids: [String]
    var default_entry_node_id: String?
    var locale: String
    let created_at: String
}

struct SettingsAccountUpdate: Encodable, Sendable {
    let display_name: String
    let default_entry_node_id: String?
    let locale: String

    // Preserve the Web account-update shape when explicitly clearing the default device.
    func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(display_name, forKey: .display_name)
        try values.encode(default_entry_node_id, forKey: .default_entry_node_id)
        try values.encode(locale, forKey: .locale)
    }
    private enum CodingKeys: String, CodingKey { case display_name, default_entry_node_id, locale }
}

struct SettingsNode: Codable, Sendable, Identifiable, Equatable {
    let node_id: String
    let owner_id: String
    let node_name: String
    let status: String
    let last_heartbeat_at: String
    let agent_count: Int
    let version: String
    var relay_enabled: Bool
    var reporting_enabled: Bool
    var alias: String?
    let last_error: String?
    var id: String { node_id }
    var name: String { alias?.isEmpty == false ? alias! : node_name }
}

struct SettingsNodeUpdate: Encodable, Sendable, Equatable {
    var alias: String
    var relay_enabled: Bool
    var reporting_enabled: Bool
    init(_ node: SettingsNode) {
        alias = node.alias ?? ""
        relay_enabled = node.relay_enabled
        reporting_enabled = node.reporting_enabled
    }
}

struct SettingsPolicy: Codable, Sendable, Equatable {
    var default_model: String
    var max_turn_per_run: Int
    var max_attachment_size_mb: Int
    var retention_days: Int
    var audit_level: String
    var rate_limit_per_min: Int
    var valid: Bool {
        !default_model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        max_turn_per_run > 0 && max_attachment_size_mb > 0 && retention_days > 0 && rate_limit_per_min > 0
    }
}

struct SettingsCapacity: Codable, Sendable {
    struct Usage: Codable, Sendable {
        let used_bytes: Int64
        let reserved_bytes: Int64
        let limit_bytes: Int64
        let full: Bool
        let owner_id: String?
        let username: String?
        let display_name: String?
    }
    let service: Usage
    let owners: [Usage]
}

struct SettingsMember: Codable, Sendable, Identifiable {
    let id: String
    let username: String
    let display_name: String
    var membership_status: String
    let is_company_admin: Bool
    let node_count: Int
    let agent_count: Int
    var name: String { display_name.isEmpty ? username : display_name }
}

struct SettingsMemberPage: Codable, Sendable {
    let members: [SettingsMember]
    let next_cursor: String?
}

struct SettingsBinding: Codable, Sendable {
    let node_id: String
    let node_name: String
    let agents: [String]
    let state: String
}

struct SettingsBindingState: Codable, Sendable { let state: String }
struct SettingsBindingRequest: Encodable, Sendable { let browser_token: String }
struct SettingsActionBody: Encodable, Sendable {}

/// Extract only a binding secret for this server; never navigate to the pasted URL.
enum SettingsBindingLink {
    enum Invalid: Error { case invalidLink }
    static func token(from text: String, server: URL) throws -> String {
        guard let url = URLComponents(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              let expected = URLComponents(url: server, resolvingAgainstBaseURL: false),
              url.scheme?.lowercased() == expected.scheme?.lowercased(),
              url.host?.lowercased() == expected.host?.lowercased(),
              effectivePort(url) == effectivePort(expected),
              url.user == nil, url.password == nil,
              url.path == "/bind/confirm", url.query == nil,
              let fragment = url.fragment else { throw Invalid.invalidLink }
        var fragmentQuery = URLComponents()
        fragmentQuery.query = fragment
        let tokens = (fragmentQuery.queryItems ?? []).filter { $0.name == "token" }
        guard tokens.count == 1, let token = tokens.first?.value,
              !token.isEmpty, token.count <= 128 else { throw Invalid.invalidLink }
        return token
    }
    private static func effectivePort(_ url: URLComponents) -> Int? {
        url.port ?? (url.scheme?.lowercased() == "https" ? 443 : url.scheme?.lowercased() == "http" ? 80 : nil)
    }
}

extension IMClient {
    func settingsAccount() async throws -> SettingsAccount { try await get("/im/v1/me") }
    func settingsNodes() async throws -> [SettingsNode] { try await get("/im/v1/nodes") }
    func saveSettingsAccount(_ account: SettingsAccountUpdate) async throws -> SettingsAccount {
        try await send("/im/v1/me", method: "PATCH", body: account)
    }
    func saveSettingsNode(_ id: String, update: SettingsNodeUpdate) async throws -> SettingsNode {
        try await send("/im/v1/nodes/\(settingsPathComponent(id))/config", method: "PATCH", body: update)
    }
    func settingsPolicies() async throws -> SettingsPolicy { try await get("/im/v1/policies") }
    func saveSettingsPolicies(_ policy: SettingsPolicy) async throws -> SettingsPolicy {
        try await send("/im/v1/policies", method: "PATCH", body: policy)
    }
    func settingsCapacity() async throws -> SettingsCapacity { try await get("/im/v1/attachments/capacity") }
    func settingsMembers(cursor: String = "") async throws -> SettingsMemberPage {
        try await get("/im/v1/company/members", query: [URLQueryItem(name: "cursor", value: cursor)])
    }
    func changeSettingsMember(_ id: String, approve: Bool) async throws -> AuthUser {
        try await send("/im/v1/company/members/\(settingsPathComponent(id))/\(approve ? "approve" : "suspend")", body: SettingsActionBody())
    }
    func inspectSettingsBinding(token: String) async throws -> SettingsBinding {
        try await send("/im/v1/device-binding/inspect", body: SettingsBindingRequest(browser_token: token))
    }
    func acceptSettingsBinding(token: String) async throws -> SettingsBinding {
        try await send("/im/v1/device-binding/accept", body: SettingsBindingRequest(browser_token: token))
    }
    func declineSettingsBinding(token: String) async throws -> SettingsBindingState {
        try await send("/im/v1/device-binding/decline", body: SettingsBindingRequest(browser_token: token))
    }
}

private func settingsPathComponent(_ value: String) -> String {
    value.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? value
}
