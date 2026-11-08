import CryptoKit
import Foundation

struct InteractionContextInput: Codable, Sendable {
    let source_message_id: String
    let state: [String: JSONValue]
    let interacted_at: Double?
}

struct SendAttempt: Codable, Sendable {
    let conversationID: String
    let sourceMessageID: String?
    let draft: PendingSend
}

/// Durable requests contain no credentials and belong to one server and account.
struct SendAttemptStore: Sendable {
    let directory: URL

    init(directory: URL? = nil) {
        self.directory = directory ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("NanoIM/SendAttempts", isDirectory: true)
    }

    func load(origin: URL, userID: String) throws -> [SendAttempt] {
        try attemptFiles(origin: origin, userID: userID).map { try attempt(at: $0) }
    }

    /// Per-file import view. Only a genuinely missing directory means no attempts; failed
    /// enumeration must abort the import transaction instead of permanently recording empty.
    func attemptFiles(origin: URL, userID: String) throws -> [URL] {
        let entries: [URL]
        do {
            entries = try FileManager.default.contentsOfDirectory(at: ownerDirectory(origin, userID), includingPropertiesForKeys: nil)
        } catch {
            if isMissing(error) { return [] }
            throw error
        }
        return entries.filter { $0.pathExtension == "json" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    private func isMissing(_ error: Error) -> Bool {
        let value = error as NSError
        if value.domain == NSPOSIXErrorDomain { return value.code == Int(POSIXErrorCode.ENOENT.rawValue) }
        // Foundation can present ENOTDIR as a high-level "no such file" error. Inspect the
        // underlying cause before accepting absence; a blocked ancestor is recoverable IO.
        if let underlying = value.userInfo[NSUnderlyingErrorKey] as? NSError { return isMissing(underlying) }
        return value.domain == NSCocoaErrorDomain
            && (value.code == NSFileReadNoSuchFileError || value.code == NSFileNoSuchFileError)
    }

    func attempt(at file: URL) throws -> SendAttempt {
        try JSONDecoder().decode(SendAttempt.self, from: Data(contentsOf: file))
    }

    /// Persist before POST; failure leaves the composer editable and sends nothing.
    func save(_ attempt: SendAttempt, origin: URL, userID: String) throws {
        guard attempt.draft.requestBody != nil else {
            throw EncodingError.invalidValue(attempt.draft, .init(codingPath: [], debugDescription: "A send attempt requires its serialized request."))
        }
        let owner = ownerDirectory(origin, userID)
        try FileManager.default.createDirectory(at: owner, withIntermediateDirectories: true)
        var options: Data.WritingOptions = [.atomic]
        #if os(iOS)
        options.insert(.completeFileProtection)
        #endif
        try JSONEncoder().encode(attempt).write(to: file(attempt, origin, userID), options: options)
        #if os(iOS)
        try FileManager.default.setAttributes([.protectionKey: FileProtectionType.complete], ofItemAtPath: owner.path)
        #endif
    }

    func remove(_ attempt: SendAttempt, origin: URL, userID: String) throws {
        try removeIfPresent(file(attempt, origin, userID))
    }

    func remove(origin: URL, userID: String, conversationID: String? = nil) throws {
        if let conversationID {
            for attempt in try load(origin: origin, userID: userID) where attempt.conversationID == conversationID {
                try remove(attempt, origin: origin, userID: userID)
            }
        } else { try removeIfPresent(ownerDirectory(origin, userID)) }
    }

    private func ownerDirectory(_ origin: URL, _ userID: String) -> URL {
        let port = origin.port ?? (origin.scheme == "https" ? 443 : 80)
        let identity = "\(origin.scheme?.lowercased() ?? "")://\(origin.host?.lowercased() ?? ""):\(port)\n\(userID)"
        return directory.appendingPathComponent(digest(identity), isDirectory: true)
    }
    private func file(_ attempt: SendAttempt, _ origin: URL, _ userID: String) -> URL {
        ownerDirectory(origin, userID).appendingPathComponent(digest("\(attempt.conversationID)\n\(attempt.sourceMessageID ?? "")\n\(attempt.draft.key)") + ".json")
    }
    private func digest(_ value: String) -> String { SHA256.hash(data: Data(value.utf8)).map { String(format: "%02x", $0) }.joined() }
    private func removeIfPresent(_ url: URL) throws {
        if FileManager.default.fileExists(atPath: url.path) { try FileManager.default.removeItem(at: url) }
    }
}
