import CryptoKit
import Foundation

/// Serializes a partition's import policy, handoff files and caller-owned SQL work.
///
/// Callers validate their SQL write context inside `coordinated`, before recording policy,
/// and keep the SQL transaction in that same closure. The recursive lock lets those callers
/// use the smaller file methods without opening a gap between validation and persistence.
final class ChatAttemptPersistence: @unchecked Sendable {
    enum CleanupKind: String, Codable, Sendable {
        case discardPending
        case revokeAccess
    }

    struct Cleanup: Codable, Sendable, Equatable {
        let generation: UUID
        let kind: CleanupKind
    }

    struct Policy: Codable, Sendable, Equatable {
        var version = 1
        var purgeGeneration: UUID?
        var conversationCleanups: [String: Cleanup] = [:]
    }

    /// A request keeps its creation stamp, including explicit null generations, forever.
    struct Stamp: Codable, Sendable, Equatable {
        let purgeGeneration: UUID?
        let conversationGeneration: UUID?

        private enum CodingKeys: String, CodingKey {
            case purgeGeneration, conversationGeneration
        }

        init(purgeGeneration: UUID?, conversationGeneration: UUID?) {
            self.purgeGeneration = purgeGeneration
            self.conversationGeneration = conversationGeneration
        }

        init(from decoder: Decoder) throws {
            let values = try decoder.container(keyedBy: CodingKeys.self)
            // Missing is malformed, not the same as an explicitly captured nil generation.
            purgeGeneration = try values.decode(UUID?.self, forKey: .purgeGeneration)
            conversationGeneration = try values.decode(UUID?.self, forKey: .conversationGeneration)
        }

        func encode(to encoder: Encoder) throws {
            var values = encoder.container(keyedBy: CodingKeys.self)
            try values.encode(purgeGeneration, forKey: .purgeGeneration)
            try values.encode(conversationGeneration, forKey: .conversationGeneration)
        }
    }

    struct Handoff: Sendable {
        let attempt: SendAttempt
        let stamp: Stamp
        let fileURL: URL
    }

    enum PersistenceError: Error, Equatable {
        case unsupportedVersion(Int)
        case invalidHandoff(String)
    }

    nonisolated let partition: ChatPartition
    nonisolated let location: ChatStorageLocation
    nonisolated let policyURL: URL

    private let lock = NSRecursiveLock()
    private static let registryLock = NSLock()
    // A strong registry also keeps the lock stable while openers and fallback owners rotate.
    nonisolated(unsafe) private static var registry: [String: ChatAttemptPersistence] = [:]

    /// Reuses one coordination boundary for every normalized database path in this process.
    static func shared(partition: ChatPartition, location: ChatStorageLocation) -> ChatAttemptPersistence {
        let databaseURL = location.databaseURL.standardizedFileURL.resolvingSymlinksInPath()
        registryLock.lock()
        defer { registryLock.unlock() }
        if let existing = registry[databaseURL.path] { return existing }
        let persistence = ChatAttemptPersistence(partition: partition,
                                                 location: ChatStorageLocation(databaseURL: databaseURL))
        registry[databaseURL.path] = persistence
        return persistence
    }

    private init(partition: ChatPartition, location: ChatStorageLocation) {
        self.partition = partition
        self.location = location
        let directory = location.directoryURL
        let parent = directory.deletingLastPathComponent()
        // Standard placement is NanoIM/Chat/<digest>; custom test locations keep policy
        // beside (never inside) the directory that `ChatStorageLocation.removeAll` purges.
        let policyParent: URL
        if directory.lastPathComponent == partition.digest,
           parent.lastPathComponent == "Chat",
           parent.deletingLastPathComponent().lastPathComponent == "NanoIM" {
            policyParent = parent.deletingLastPathComponent()
        } else {
            policyParent = parent
        }
        policyURL = policyParent.appendingPathComponent("ChatImportPolicy", isDirectory: true)
            .appendingPathComponent(partition.digest + ".json")
    }

    func coordinated<T>(_ body: () throws -> T) rethrows -> T {
        lock.lock()
        defer { lock.unlock() }
        return try body()
    }

    /// Reads every time: policy survives database deletion and must never fall back to empty
    /// on unreadable, malformed or future-version data.
    func policy() throws -> Policy {
        try coordinated {
            guard let data = try dataIfPresent(at: policyURL) else { return Policy() }
            try validateVersion(data)
            return try JSONDecoder().decode(Policy.self, from: data)
        }
    }

    func stamp(for conversationID: String) throws -> Stamp {
        try coordinated { stamp(for: conversationID, policy: try policy()) }
    }

    @discardableResult
    func recordCleanup(_ conversationID: String, kind: CleanupKind,
                       forceNewGeneration: Bool = true) throws -> Policy {
        try coordinated {
            var current = try policy()
            if !forceNewGeneration, current.conversationCleanups[conversationID]?.kind == kind {
                return current
            }
            current.conversationCleanups[conversationID] = Cleanup(generation: UUID(), kind: kind)
            try write(current, to: policyURL)
            return current
        }
    }

    @discardableResult
    func recordPurge() throws -> Policy {
        try coordinated {
            var current = try policy()
            current.purgeGeneration = UUID()
            try write(current, to: policyURL)
            return current
        }
    }

    /// A stale writer cannot relabel its request, even if an older file still occupies its
    /// identity. Frozen request bytes likewise cannot be replaced under the same identity.
    func save(_ attempt: SendAttempt, stamp creationStamp: Stamp) throws {
        try coordinated {
            guard creationStamp == (try stamp(for: attempt.conversationID)) else {
                throw ChatRepositoryError.staleWrite
            }
            guard attempt.draft.requestBody != nil else {
                throw PersistenceError.invalidHandoff("A handoff requires its frozen request body.")
            }
            let file = handoffURL(for: attempt)
            if let data = try dataIfPresent(at: file) {
                let existing = try envelope(from: data, at: file)
                guard existing.stamp == creationStamp else { throw ChatRepositoryError.staleWrite }
                guard sameIdentity(existing.attempt, attempt),
                      existing.attempt.draft.requestBody == attempt.draft.requestBody else {
                    throw PersistenceError.invalidHandoff("An existing handoff has a different frozen request.")
                }
            }
            try write(Envelope(version: 1, attempt: attempt, stamp: creationStamp), to: file)
        }
    }

    /// Returns only eligible handoffs. An ineligible file is deleted, and deletion failures
    /// are propagated so callers can report/retry physical cleanup without importing it.
    func loadHandoffs() throws -> [Handoff] {
        try coordinated {
            let current = try policy()
            var result: [Handoff] = []
            for file in try handoffFiles() {
                let value = try envelope(from: Data(contentsOf: file), at: file)
                guard value.stamp == stamp(for: value.attempt.conversationID, policy: current) else {
                    try removeIfPresent(file)
                    continue
                }
                result.append(Handoff(attempt: value.attempt, stamp: value.stamp, fileURL: file))
            }
            return result
        }
    }

    func removeHandoff(_ attempt: SendAttempt) throws {
        try coordinated { try removeIfPresent(handoffURL(for: attempt)) }
    }

    /// Only this new namespace is ever removed; legacy bare JSON and SQLite are untouched.
    func removeHandoffs(conversationID: String? = nil) throws {
        try coordinated {
            for file in try handoffFiles() {
                if let conversationID {
                    let value = try envelope(from: Data(contentsOf: file), at: file)
                    guard value.attempt.conversationID == conversationID else { continue }
                }
                try removeIfPresent(file)
            }
        }
    }

    private struct Envelope: Codable {
        let version: Int
        let attempt: SendAttempt
        let stamp: Stamp
    }

    private struct Version: Decodable { let version: Int }

    private func validateVersion(_ data: Data) throws {
        let version = try JSONDecoder().decode(Version.self, from: data).version
        guard version == 1 else { throw PersistenceError.unsupportedVersion(version) }
    }

    private func envelope(from data: Data, at file: URL) throws -> Envelope {
        try validateVersion(data)
        let value = try JSONDecoder().decode(Envelope.self, from: data)
        guard value.attempt.draft.requestBody != nil,
              handoffURL(for: value.attempt) == file else {
            throw PersistenceError.invalidHandoff("A handoff's request body or immutable file identity is invalid.")
        }
        return value
    }

    private func stamp(for conversationID: String, policy: Policy) -> Stamp {
        Stamp(purgeGeneration: policy.purgeGeneration,
              conversationGeneration: policy.conversationCleanups[conversationID]?.generation)
    }

    private func handoffURL(for attempt: SendAttempt) -> URL {
        let identity = "\(attempt.conversationID)\n\(attempt.sourceMessageID ?? "")\n\(attempt.draft.key)"
        let hash = SHA256.hash(data: Data(identity.utf8)).map { String(format: "%02x", $0) }.joined()
        return location.directoryURL.appendingPathComponent("handoff-\(hash).json")
    }

    private func sameIdentity(_ lhs: SendAttempt, _ rhs: SendAttempt) -> Bool {
        lhs.conversationID == rhs.conversationID && lhs.sourceMessageID == rhs.sourceMessageID
            && lhs.draft.key == rhs.draft.key
    }

    private func handoffFiles() throws -> [URL] {
        do {
            return try FileManager.default.contentsOfDirectory(at: location.directoryURL, includingPropertiesForKeys: nil)
                .filter { $0.lastPathComponent.hasPrefix("handoff-") && $0.pathExtension == "json" }
                .sorted { $0.lastPathComponent < $1.lastPathComponent }
        } catch {
            if isMissing(error) { return [] }
            throw error
        }
    }

    private func dataIfPresent(at file: URL) throws -> Data? {
        do { return try Data(contentsOf: file) }
        catch {
            if isMissing(error) { return nil }
            throw error
        }
    }

    private func isMissing(_ error: Error) -> Bool {
        let error = error as NSError
        if error.domain == NSPOSIXErrorDomain {
            return error.code == Int(POSIXErrorCode.ENOENT.rawValue)
        }
        // Cocoa can map ENOTDIR to the same high-level code as ENOENT. A file blocking
        // an ancestor is an IO failure, not permission to treat policy as absent.
        if let underlying = error.userInfo[NSUnderlyingErrorKey] as? NSError {
            return isMissing(underlying)
        }
        return error.domain == NSCocoaErrorDomain
            && (error.code == NSFileReadNoSuchFileError || error.code == NSFileNoSuchFileError)
    }

    private func removeIfPresent(_ file: URL) throws {
        do { try FileManager.default.removeItem(at: file) }
        catch { if !isMissing(error) { throw error } }
    }

    private func write<T: Encodable>(_ value: T, to file: URL) throws {
        let directory = file.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        #if os(iOS)
        try FileManager.default.setAttributes([.protectionKey: FileProtectionType.complete], ofItemAtPath: directory.path)
        #endif
        try excludeFromBackup(directory)
        var options: Data.WritingOptions = [.atomic]
        #if os(iOS)
        options.insert(.completeFileProtection)
        #endif
        try JSONEncoder().encode(value).write(to: file, options: options)
        try excludeFromBackup(file)
    }

    private func excludeFromBackup(_ url: URL) throws {
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        var target = url
        try target.setResourceValues(values)
    }
}
