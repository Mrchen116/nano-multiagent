import Foundation
import Security

protocol CredentialStore: Sendable {
    func load() throws -> StoredSession?
    func save(_ value: StoredSession) throws
    func remove() throws
}

struct KeychainCredentials: CredentialStore {
    let origin: URL
    private var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: "win.nanoim.session.\(origin.absoluteString)",
         kSecAttrAccount as String: "session"]
    }
    func load() throws -> StoredSession? {
        var q = query; q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var value: CFTypeRef?
        let status = SecItemCopyMatching(q as CFDictionary, &value)
        if status == errSecItemNotFound { return nil }
        try check(status)
        guard let data = value as? Data else { throw URLError(.cannotDecodeContentData) }
        return try JSONDecoder().decode(StoredSession.self, from: data)
    }
    func save(_ value: StoredSession) throws {
        let data = try JSONEncoder().encode(value)
        let attributes: [String: Any] = [kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            try check(SecItemAdd(query.merging(attributes) { _, new in new } as CFDictionary, nil))
        } else { try check(status) }
    }
    func remove() throws {
        let status = SecItemDelete(query as CFDictionary)
        if status != errSecItemNotFound { try check(status) }
    }
    private func check(_ status: OSStatus) throws {
        guard status == errSecSuccess else {
            throw APIError(status: Int(status), detail: L("无法安全保存登录状态，请重试。", "Unable to access secure sign-in storage. Please retry."))
        }
    }
}
