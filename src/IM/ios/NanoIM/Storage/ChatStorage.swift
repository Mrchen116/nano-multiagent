import CryptoKit
import Foundation

/// One locally stored chat scope: a server origin plus the account signed into it.
///
/// The identity string is byte-identical to `SendAttemptStore`'s owner directory so the
/// migration can find the legacy JSON written by previous builds; changing the derivation
/// would silently split the same account into two scopes.
struct ChatPartition: Hashable, Sendable {
    let origin: URL
    let userID: String

    var digest: String {
        let port = origin.port ?? (origin.scheme == "https" ? 443 : 80)
        let identity = "\(origin.scheme?.lowercased() ?? "")://\(origin.host?.lowercased() ?? ""):\(port)\n\(userID)"
        return SHA256.hash(data: Data(identity.utf8)).map { String(format: "%02x", $0) }.joined()
    }

    var identityDescription: String {
        "\(origin.absoluteString) · \(userID)"
    }

    /// Same directory naming as `SendAttemptStore.ownerDirectory`.
    func legacyAttemptDirectory(root: URL) -> URL {
        root.appendingPathComponent(digest, isDirectory: true)
    }
}

/// Filesystem placement for the chat database.
///
/// The content is a rebuildable copy of server-authoritative data, so the directory is
/// excluded from backups; protection matches the existing send-attempt boundary.
struct ChatStorageLocation: Sendable {
    let databaseURL: URL

    static func standard(partition: ChatPartition) -> ChatStorageLocation {
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let directory = support
            .appendingPathComponent("NanoIM/Chat", isDirectory: true)
            .appendingPathComponent(partition.digest, isDirectory: true)
        return ChatStorageLocation(databaseURL: directory.appendingPathComponent("chat.sqlite"))
    }

    static func directory(_ url: URL) -> ChatStorageLocation {
        ChatStorageLocation(databaseURL: url.appendingPathComponent("chat.sqlite"))
    }

    static var legacyAttemptRoot: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("NanoIM/SendAttempts", isDirectory: true)
    }

    /// New degraded-mode requests live beside this partition's database, not in the legacy
    /// migration source. A partition purge therefore clears them through the same boundary.
    static var handoffAttemptRoot: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("NanoIM/Chat", isDirectory: true)
    }

    var directoryURL: URL { databaseURL.deletingLastPathComponent() }

    /// Create the directory and apply the protection/backup attributes that must hold for
    /// every file inside it. Failures are reported, not swallowed: a caller that cannot
    /// protect the directory must decide whether to degrade.
    func prepare() throws {
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        #if os(iOS)
        try FileManager.default.setAttributes([.protectionKey: FileProtectionType.complete], ofItemAtPath: directoryURL.path)
        #endif
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        var directory = directoryURL
        try directory.setResourceValues(values)
    }

    func protectDatabaseFile() throws {
        #if os(iOS)
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return }
        try FileManager.default.setAttributes([.protectionKey: FileProtectionType.complete], ofItemAtPath: databaseURL.path)
        #endif
    }

    /// Move an unusable database aside so the next open starts from an empty file while
    /// leaving the legacy JSON source untouched (it is re-imported by the migration marker).
    func quarantineCorruptDatabase() -> URL? {
        let target = directoryURL.appendingPathComponent("chat.corrupt-\(UUID().uuidString).sqlite")
        for suffix in ["", "-wal", "-shm", "-journal"] {
            let source = URL(fileURLWithPath: databaseURL.path + suffix)
            guard FileManager.default.fileExists(atPath: source.path) else { continue }
            let destination = URL(fileURLWithPath: target.path + suffix)
            try? FileManager.default.removeItem(at: destination)
            try? FileManager.default.moveItem(at: source, to: destination)
        }
        return FileManager.default.fileExists(atPath: target.path) ? target : nil
    }

    func removeAll() throws {
        guard FileManager.default.fileExists(atPath: directoryURL.path) else { return }
        try FileManager.default.removeItem(at: directoryURL)
    }
}

/// A write is only valid for the partition generation and snapshot generation it was read
/// under. Late network results therefore cannot resurrect rows deleted by a newer snapshot
/// or by a partition switch.
struct ChatWriteContext: Sendable, Hashable {
    let epoch: UUID
    let snapshotSeq: Int
}

enum ChatRepositoryError: Error, Equatable {
    case staleWrite
    case revokedConversation(String)
    case databaseUnavailable(String)
}
