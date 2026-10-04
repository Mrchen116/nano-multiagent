import Foundation

struct AgentChannel: Codable, Identifiable, Sendable {
    var channel_id: String; var provider: String
    var resource_type: String?
    var enabled: Bool?; var config: [String: String]?; var secret_configured: Bool?
    var channel_revision: Int?; var sync_state: String?; var apply_error: ApplyError?; var observed: Observed?
    var display_config: [String: String]?; var deletion_manifest_revision: Int?; var apply_state: String?; var created_at: String?
    var id: String { channel_id }
    var isRemoval: Bool { resource_type == "removal" }
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
