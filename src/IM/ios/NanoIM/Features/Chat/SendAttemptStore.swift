import CryptoKit
import Foundation

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
        let owner = ownerDirectory(origin, userID)
        guard FileManager.default.fileExists(atPath: owner.path) else { return [] }
        return try FileManager.default.contentsOfDirectory(at: owner, includingPropertiesForKeys: nil)
            .filter { $0.pathExtension == "json" }
            .map { try JSONDecoder().decode(SendAttempt.self, from: Data(contentsOf: $0)) }
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
            for name in ["draft-watermarks", "draft-discard-intents"] {
                var values = try loadDraftMap(name, origin: origin, userID: userID)
                if values.removeValue(forKey: conversationID) != nil { try saveDraftMap(values, name: name, origin: origin, userID: userID) }
            }
            for attempt in try load(origin: origin, userID: userID) where attempt.conversationID == conversationID {
                try remove(attempt, origin: origin, userID: userID)
            }
        } else { try removeIfPresent(ownerDirectory(origin, userID)) }
    }

    /// Watermarks share the attempt owner's protected lifetime, but are not send attempts.
    func loadDraftWatermarks(origin: URL, userID: String) throws -> [String: String] {
        try loadDraftMap("draft-watermarks", origin: origin, userID: userID)
    }

    @discardableResult
    func noteDraftSaved(_ conversationID: String, updatedAt: String, origin: URL, userID: String) throws -> [String: String] {
        var values = try loadDraftWatermarks(origin: origin, userID: userID)
        values[conversationID] = max(values[conversationID] ?? "", updatedAt)
        values = Dictionary(uniqueKeysWithValues: values.sorted {
            $0.value == $1.value ? $0.key < $1.key : $0.value > $1.value
        }.prefix(128).map { ($0.key, $0.value) })
        try saveDraftMap(values, name: "draft-watermarks", origin: origin, userID: userID)
        return values
    }

    /// A saved draft is not a leave intent; only explicit departures may be retried on launch.
    func loadDraftDiscards(origin: URL, userID: String) throws -> [String: String] {
        try loadDraftMap("draft-discard-intents", origin: origin, userID: userID)
    }
    func updateDraftDiscard(_ conversationID: String, through: String, confirmed: Bool, origin: URL, userID: String) throws {
        var values = try loadDraftDiscards(origin: origin, userID: userID)
        if confirmed {
            // An older response must never acknowledge a newer departure's cleanup.
            if let pending = values[conversationID], pending <= through { values[conversationID] = nil }
        } else {
            values[conversationID] = max(values[conversationID] ?? "", through)
            values = Dictionary(uniqueKeysWithValues: values.sorted {
                $0.value == $1.value ? $0.key < $1.key : $0.value > $1.value
            }.prefix(128).map { ($0.key, $0.value) })
        }
        try saveDraftMap(values, name: "draft-discard-intents", origin: origin, userID: userID)
    }
    private func loadDraftMap(_ name: String, origin: URL, userID: String) throws -> [String: String] {
        let url = ownerDirectory(origin, userID).appendingPathComponent(name)
        guard FileManager.default.fileExists(atPath: url.path) else { return [:] }
        return try JSONDecoder().decode([String: String].self, from: Data(contentsOf: url))
    }
    private func saveDraftMap(_ values: [String: String], name: String, origin: URL, userID: String) throws {
        let owner = ownerDirectory(origin, userID)
        try FileManager.default.createDirectory(at: owner, withIntermediateDirectories: true)
        var options: Data.WritingOptions = [.atomic]
        #if os(iOS)
        options.insert(.completeFileProtection)
        #endif
        try JSONEncoder().encode(values).write(to: owner.appendingPathComponent(name), options: options)
        #if os(iOS)
        try FileManager.default.setAttributes([.protectionKey: FileProtectionType.complete], ofItemAtPath: owner.path)
        #endif
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
