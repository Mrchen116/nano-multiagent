import Foundation

struct AgentChannel: Codable, Identifiable, Sendable {
    static let supportedProviders = ["feishu", "wechat"]

    static func canAddAnyChannel(in channels: [AgentChannel]) -> Bool {
        let occupied = Set(channels.map(\.provider))
        return supportedProviders.contains { !occupied.contains($0) }
    }

    var channel_id: String; var provider: String
    var resource_type: String?
    var enabled: Bool?; var config: [String: String]?; var secret_configured: Bool?
    var channel_revision: Int?; var sync_state: String?; var apply_error: ApplyError?; var observed: Observed?
    var display_config: [String: String]?; var deletion_manifest_revision: Int?; var apply_state: String?; var created_at: String?
    var id: String { channel_id }
    var isRemoval: Bool { resource_type == "removal" }
    var isFeishu: Bool { provider == "feishu" }
    var isWeChat: Bool { provider == "wechat" }
    var providerTitle: String {
        switch provider {
        case "feishu": return L("飞书", "Feishu")
        case "wechat": return L("微信", "WeChat")
        default: return provider
        }
    }
    var isTokenRevoked: Bool {
        isWeChat && observed?.status_code == "wechat_token_revoked"
    }
    var canEditInApp: Bool { isFeishu }
    var canReconnect: Bool { !isTokenRevoked }
    var identityLabel: String {
        isWeChat ? L("绑定微信", "Bound WeChat") : "App ID"
    }
    var maskedIdentitySummary: String {
        let raw = (isWeChat ? config?["owner_user_id"] : config?["app_id"])?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !raw.isEmpty else { return "—" }
        guard raw.count > 8 else { return raw }
        return "\(raw.prefix(6))••••\(raw.suffix(4))"
    }
    var removalIdentitySummary: String {
        let key = isWeChat ? "owner_user_id_suffix" : "app_id_suffix"
        guard let suffix = display_config?[key], !suffix.isEmpty else { return "—" }
        return "••••\(suffix)"
    }
    var feishuPermissionsURL: URL? {
        guard isFeishu else { return nil }
        let rawAppID = (config?["app_id"] ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !rawAppID.isEmpty else {
            return URL(string: "https://open.feishu.cn/page/launcher?from=backend_oneclick")
        }
        return URL(string: "https://open.feishu.cn/app/\(agentSegment(rawAppID))/auth")
    }

    struct ApplyError: Codable, Sendable { var code: String; var message: String }
    struct Observed: Codable, Sendable {
        var observed_revision: Int; var connection_state: String; var diagnostics_state: String?; var status_code: String?
        var status_message: String?; var status_updated_at: String; var status_stale: Bool?; var checks: [Check]?
    }
    struct Check: Codable, Sendable, Identifiable {
        var check_id: String; var state: String; var required: Required; var effect: String; var remediation: String
        var id: String { check_id }
        struct Required: Codable, Sendable { var accepted_scope_sets: [[String]]; var recommended_scopes: [String] }
    }
}
