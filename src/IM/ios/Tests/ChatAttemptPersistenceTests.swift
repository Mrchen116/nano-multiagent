import Foundation
import XCTest
@testable import NanoIM

/// Pure temporary-file contracts. No repository, SQLite, transport or installed App data.
final class ChatAttemptPersistenceTests: XCTestCase {
    private var root: URL!
    private let partition = ChatPartition(origin: URL(string: "https://im.example.test")!, userID: "user")
    private var location: ChatStorageLocation {
        .directory(root.appendingPathComponent("partition", isDirectory: true))
    }
    private var persistence: ChatAttemptPersistence {
        .shared(partition: partition, location: location)
    }

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory
            .appendingPathComponent("ChatAttemptPersistenceTests-" + UUID().uuidString, isDirectory: true)
            .standardizedFileURL.resolvingSymlinksInPath()
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        guard let root else { return }
        // Only this fixture's freshly-created child of the temporary directory is removable.
        guard root.deletingLastPathComponent().standardizedFileURL
                == FileManager.default.temporaryDirectory.standardizedFileURL.resolvingSymlinksInPath(),
              root.lastPathComponent.hasPrefix("ChatAttemptPersistenceTests-") else {
            XCTFail("Refusing to remove a path outside this temporary fixture.")
            return
        }
        if FileManager.default.fileExists(atPath: root.path) { try FileManager.default.removeItem(at: root) }
    }

    func testMissingPolicyIsEmptyAndStampExplicitlyEncodesNulls() throws {
        XCTAssertEqual(try persistence.policy(), ChatAttemptPersistence.Policy())
        let stamp = try persistence.stamp(for: "a")
        XCTAssertNil(stamp.purgeGeneration)
        XCTAssertNil(stamp.conversationGeneration)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(stamp)) as? [String: Any])
        XCTAssertTrue(json["purgeGeneration"] is NSNull)
        XCTAssertTrue(json["conversationGeneration"] is NSNull)
        XCTAssertFalse(FileManager.default.fileExists(atPath: persistence.policyURL.path), "A read does not create policy.")
    }

    func testStandardAndCustomPolicyAreOutsideThePurgeBoundary() throws {
        let standardDirectory = root.appendingPathComponent("NanoIM/Chat", isDirectory: true)
            .appendingPathComponent(partition.digest, isDirectory: true)
        let standardLocation = ChatStorageLocation.directory(standardDirectory)
        let standard = ChatAttemptPersistence.shared(partition: partition, location: standardLocation)
        let expected = root.appendingPathComponent("NanoIM/ChatImportPolicy", isDirectory: true)
            .appendingPathComponent(partition.digest + ".json")
        XCTAssertEqual(standard.policyURL, expected)
        XCTAssertEqual(persistence.policyURL, root.appendingPathComponent("ChatImportPolicy", isDirectory: true)
            .appendingPathComponent(partition.digest + ".json"))

        let current = try standard.recordPurge()
        try standard.save(attempt(), stamp: standard.stamp(for: "a"))
        try standardLocation.removeAll()
        XCTAssertEqual(try standard.policy(), current, "Deleting Chat/<digest> cannot reset the import fence.")
        XCTAssertTrue(try standard.loadHandoffs().isEmpty)
    }

    func testSharedNormalizesDatabasePathAndReusesTheSameInstance() throws {
        let alias = ChatStorageLocation(databaseURL: location.directoryURL
            .appendingPathComponent("unused/../chat.sqlite"))
        let first = persistence
        let second = ChatAttemptPersistence.shared(partition: partition, location: alias)
        XCTAssertTrue(first === second)
        let result = try first.coordinated {
            let policy = try second.recordCleanup("a", kind: .discardPending)
            return try second.coordinated { try first.policy() == policy }
        }
        XCTAssertTrue(result, "Nested policy operations use a recursive partition lock.")
    }

    func testCoordinatedSerializesWriterAndCleanupAcrossOwners() throws {
        let first = persistence
        let second = ChatAttemptPersistence.shared(partition: partition, location: location)
        let request = attempt()
        let entered = DispatchSemaphore(value: 0)
        let allowSave = DispatchSemaphore(value: 0)
        let cleanupAttempted = DispatchSemaphore(value: 0)
        let group = DispatchGroup()
        let trace = Trace()
        let queue = DispatchQueue(label: "ChatAttemptPersistenceTests.serial", attributes: .concurrent)
        group.enter()
        queue.async {
            defer { group.leave() }
            do {
                try first.coordinated {
                    trace.append("writer-enter")
                    let stamp = try first.stamp(for: request.conversationID)
                    entered.signal()
                    guard allowSave.wait(timeout: .now() + 5) == .success else {
                        throw TestFailure.timeout
                    }
                    try first.save(request, stamp: stamp)
                    trace.append("writer-save")
                }
            } catch { trace.fail(error) }
        }
        defer { allowSave.signal() }
        XCTAssertEqual(entered.wait(timeout: .now() + 5), .success)
        group.enter()
        queue.async {
            defer { group.leave() }
            cleanupAttempted.signal()
            do {
                try second.coordinated {
                    trace.append("cleanup-enter")
                    try second.recordPurge()
                    trace.append("cleanup-save")
                }
            } catch { trace.fail(error) }
        }
        XCTAssertEqual(cleanupAttempted.wait(timeout: .now() + 5), .success)
        XCTAssertEqual(trace.events, ["writer-enter"])
        allowSave.signal()
        XCTAssertEqual(group.wait(timeout: .now() + 5), .success)
        XCTAssertEqual(trace.events, ["writer-enter", "writer-save", "cleanup-enter", "cleanup-save"])
        XCTAssertTrue(trace.errors.isEmpty, trace.errors.joined(separator: ", "))
        XCTAssertTrue(try first.loadHandoffs().isEmpty, "The saved file is now an ineligible old-generation request.")
    }

    func testOldStampsAreRejectedAfterPurgeAndConversationCleanup() throws {
        let initial = try persistence.stamp(for: "a")
        try persistence.recordCleanup("a", kind: .discardPending)
        assertStale { try persistence.save(self.attempt(), stamp: initial) }
        let afterCleanup = try persistence.stamp(for: "a")
        XCTAssertNotEqual(afterCleanup, initial)
        try persistence.recordPurge()
        assertStale { try persistence.save(self.attempt(), stamp: afterCleanup) }
        XCTAssertTrue(try persistence.loadHandoffs().isEmpty)
    }

    func testCleanupOnlyInvalidatesItsConversationAndNewRequestsRemainEligible() throws {
        let a = attempt(conversation: "a", key: "old-a")
        let b = attempt(conversation: "b", key: "old-b")
        try persistence.save(a, stamp: persistence.stamp(for: "a"))
        try persistence.save(b, stamp: persistence.stamp(for: "b"))
        try persistence.recordCleanup("a", kind: .revokeAccess)
        let newA = attempt(conversation: "a", key: "new-a")
        try persistence.save(newA, stamp: persistence.stamp(for: "a"))
        XCTAssertEqual(Set(try persistence.loadHandoffs().map { $0.attempt.draft.key }), ["old-b", "new-a"])
    }

    func testResidualOldFileAfterCommittedPurgeIsRejectedOnReopen() throws {
        let request = attempt(key: "old")
        let oldStamp = try persistence.stamp(for: "a")
        try persistence.save(request, stamp: oldStamp)
        let oldFile = try XCTUnwrap(persistence.loadHandoffs().first?.fileURL)
        let oldBytes = try Data(contentsOf: oldFile)
        let committed = try persistence.recordPurge()
        // Crash point: policy/DB cleanup may be committed while this file still exists.
        XCTAssertEqual(try Data(contentsOf: oldFile), oldBytes)
        let reopened = ChatAttemptPersistence.shared(partition: partition, location: location)
        XCTAssertEqual(try reopened.policy(), committed)
        XCTAssertTrue(try reopened.loadHandoffs().isEmpty)
        XCTAssertFalse(FileManager.default.fileExists(atPath: oldFile.path))
        assertStale { try reopened.save(request, stamp: oldStamp) }

        let fresh = attempt(key: "new")
        let currentStamp = try reopened.stamp(for: "a")
        try reopened.save(fresh, stamp: currentStamp)
        let restored = try XCTUnwrap(reopened.loadHandoffs().first)
        XCTAssertEqual(restored.attempt.draft.key, "new")
        XCTAssertEqual(restored.stamp, currentStamp)
    }

    func testStaleFileDeletionFailureIsReportedAndRemainsIneligibleOnRetry() throws {
        try persistence.save(attempt(), stamp: persistence.stamp(for: "a"))
        let file = try XCTUnwrap(persistence.loadHandoffs().first?.fileURL)
        let original = try Data(contentsOf: file)
        try persistence.recordPurge()
        let directory = persistence.location.directoryURL
        let attributes = try FileManager.default.attributesOfItem(atPath: directory.path)
        let originalPermissions = try XCTUnwrap(attributes[.posixPermissions])
        try FileManager.default.setAttributes([.posixPermissions: 0o500], ofItemAtPath: directory.path)
        defer { try? FileManager.default.setAttributes([.posixPermissions: originalPermissions], ofItemAtPath: directory.path) }
        var failure: Error?
        do { _ = try persistence.loadHandoffs() }
        catch { failure = error }
        guard failure != nil else {
            throw XCTSkip("This filesystem/identity permits deletion from a non-writable directory.")
        }
        XCTAssertEqual(try Data(contentsOf: file), original)
        XCTAssertThrowsError(try persistence.loadHandoffs(), "A retry cannot import an ineligible residual file.")
        try FileManager.default.setAttributes([.posixPermissions: originalPermissions], ofItemAtPath: directory.path)
        XCTAssertTrue(try persistence.loadHandoffs().isEmpty)
        XCTAssertFalse(FileManager.default.fileExists(atPath: file.path))
        try persistence.save(attempt(key: "fresh"), stamp: persistence.stamp(for: "a"))
        XCTAssertEqual(try persistence.loadHandoffs().first?.attempt.draft.key, "fresh")
    }

    func testExistingOldEnvelopeCannotBeRestampedOrOverwritten() throws {
        let request = attempt()
        try persistence.save(request, stamp: persistence.stamp(for: "a"))
        let file = try XCTUnwrap(persistence.loadHandoffs().first?.fileURL)
        let original = try Data(contentsOf: file)
        try persistence.recordPurge()
        let newStamp = try persistence.stamp(for: "a")
        assertStale { try persistence.save(request, stamp: newStamp) }
        XCTAssertEqual(try Data(contentsOf: file), original)
    }

    func testTypedCleanupPersistsAcrossReadsAndOnlyExplicitIdempotenceReusesGeneration() throws {
        let first = try persistence.recordCleanup("a", kind: .discardPending)
        let firstCleanup = try XCTUnwrap(first.conversationCleanups["a"])
        let reopened = ChatAttemptPersistence.shared(partition: partition, location: location)
        XCTAssertEqual(try reopened.policy(), first)
        XCTAssertEqual(firstCleanup.kind, .discardPending)
        XCTAssertEqual(try reopened.recordCleanup("a", kind: .discardPending, forceNewGeneration: false), first)
        let rotated = try reopened.recordCleanup("a", kind: .discardPending)
        XCTAssertNotEqual(rotated.conversationCleanups["a"]?.generation, firstCleanup.generation)
        let upgraded = try reopened.recordCleanup("a", kind: .revokeAccess, forceNewGeneration: false)
        XCTAssertEqual(upgraded.conversationCleanups["a"]?.kind, .revokeAccess)
        XCTAssertNotEqual(upgraded.conversationCleanups["a"]?.generation, rotated.conversationCleanups["a"]?.generation)
        XCTAssertEqual(try reopened.policy(), upgraded)
        let firstPurge = try reopened.recordPurge()
        let secondPurge = try reopened.recordPurge()
        XCTAssertNotEqual(firstPurge.purgeGeneration, secondPurge.purgeGeneration)
        XCTAssertEqual(secondPurge.conversationCleanups, upgraded.conversationCleanups)
    }

    func testMalformedOrFuturePolicyIsFailClosedForReadsAndWrites() throws {
        try persistence.recordPurge()
        for invalid in [Data("{".utf8), Data(#"{"version":99,"conversationCleanups":{}}"#.utf8)] {
            try invalid.write(to: persistence.policyURL, options: .atomic)
            XCTAssertThrowsError(try persistence.policy())
            XCTAssertThrowsError(try persistence.stamp(for: "a"))
            XCTAssertThrowsError(try persistence.recordPurge())
            XCTAssertThrowsError(try persistence.recordCleanup("a", kind: .revokeAccess))
            XCTAssertThrowsError(try persistence.loadHandoffs())
            XCTAssertThrowsError(try persistence.save(attempt(), stamp: .init(purgeGeneration: nil, conversationGeneration: nil)))
            XCTAssertEqual(try Data(contentsOf: persistence.policyURL), invalid, "No invalid policy is replaced with empty state.")
        }
        XCTAssertThrowsError(try persistence.policy()) {
            XCTAssertEqual($0 as? ChatAttemptPersistence.PersistenceError, .unsupportedVersion(99))
        }
        let unknownKind: [String: Any] = [
            "version": 1,
            "conversationCleanups": ["a": ["generation": UUID().uuidString, "kind": "futureCleanup"]]
        ]
        let invalidKind = try JSONSerialization.data(withJSONObject: unknownKind)
        try invalidKind.write(to: persistence.policyURL, options: .atomic)
        XCTAssertThrowsError(try persistence.policy())
        XCTAssertThrowsError(try persistence.recordPurge())
        XCTAssertEqual(try Data(contentsOf: persistence.policyURL), invalidKind)
    }

    func testPolicyAndHandoffWriteFailuresPropagateWithoutReplacingData() throws {
        let parent = persistence.policyURL.deletingLastPathComponent()
        let sentinel = Data("not a directory".utf8)
        try sentinel.write(to: parent)
        XCTAssertThrowsError(try persistence.recordPurge())
        XCTAssertEqual(try Data(contentsOf: parent), sentinel)
        // A non-directory in the policy path is an IO error, never an empty policy.
        XCTAssertThrowsError(try persistence.policy())

        let otherLocation = ChatStorageLocation.directory(root.appendingPathComponent("other/partition"))
        let other = ChatAttemptPersistence.shared(partition: partition, location: otherLocation)
        try FileManager.default.createDirectory(at: root.appendingPathComponent("other"), withIntermediateDirectories: true)
        try sentinel.write(to: otherLocation.directoryURL)
        let stamp = try other.stamp(for: "a")
        XCTAssertThrowsError(try other.save(attempt(), stamp: stamp))
        XCTAssertEqual(try Data(contentsOf: otherLocation.directoryURL), sentinel)
    }

    func testUnknownOrMalformedHandoffCannotLoadOrBeOverwritten() throws {
        let request = attempt()
        let stamp = try persistence.stamp(for: "a")
        try persistence.save(request, stamp: stamp)
        let file = try XCTUnwrap(persistence.loadHandoffs().first?.fileURL)
        let original = try Data(contentsOf: file)
        var json = try XCTUnwrap(JSONSerialization.jsonObject(with: original) as? [String: Any])
        json["version"] = 22
        let future = try JSONSerialization.data(withJSONObject: json)
        try future.write(to: file, options: .atomic)
        XCTAssertThrowsError(try persistence.loadHandoffs()) {
            XCTAssertEqual($0 as? ChatAttemptPersistence.PersistenceError, .unsupportedVersion(22))
        }
        XCTAssertThrowsError(try persistence.save(request, stamp: stamp))
        XCTAssertEqual(try Data(contentsOf: file), future)

        json["version"] = 1
        json["stamp"] = ["purgeGeneration": NSNull()]
        let missingGeneration = try JSONSerialization.data(withJSONObject: json)
        try missingGeneration.write(to: file, options: .atomic)
        XCTAssertThrowsError(try persistence.loadHandoffs(), "An absent generation key cannot acquire nil eligibility.")
        XCTAssertEqual(try Data(contentsOf: file), missingGeneration)
        try Data("not JSON".utf8).write(to: file, options: .atomic)
        XCTAssertThrowsError(try persistence.loadHandoffs())
    }

    func testFallbackPreservesFrozenBodyAndImmutableInteractionIdentityExactly() throws {
        let body = Data(" {\n  \"content\": \"原始 请求\", \"interaction_contexts\": [], \"z\": null\n}\n".utf8)
        let image = ChatAttachment(url: "/im/v1/uploads/1", content_type: "image/png", file_name: "a.png")
        let request = SendAttempt(conversationID: "a", sourceMessageID: "source",
                                  draft: PendingSend(key: "fixed-key", content: "原始 请求", attachments: [image], requestBody: body))
        let stamp = try persistence.stamp(for: "a")
        try persistence.save(request, stamp: stamp)
        try persistence.save(request, stamp: stamp)
        let restored = try XCTUnwrap(persistence.loadHandoffs().first)
        XCTAssertEqual(restored.attempt.conversationID, request.conversationID)
        XCTAssertEqual(restored.attempt.sourceMessageID, request.sourceMessageID)
        XCTAssertEqual(restored.attempt.draft.key, request.draft.key)
        XCTAssertEqual(restored.attempt.draft.attachments, [image])
        XCTAssertEqual(restored.attempt.draft.requestBody, body)
        XCTAssertEqual(restored.stamp, stamp)
        XCTAssertTrue(restored.fileURL.lastPathComponent.hasPrefix("handoff-"))
        let changed = SendAttempt(conversationID: "a", sourceMessageID: "source",
                                  draft: PendingSend(key: "fixed-key", content: "changed", attachments: [], requestBody: Data("{}".utf8)))
        XCTAssertThrowsError(try persistence.save(changed, stamp: stamp))
        XCTAssertEqual(try persistence.loadHandoffs().first?.attempt.draft.requestBody, body)
        let missing = SendAttempt(conversationID: "a", sourceMessageID: nil,
                                  draft: PendingSend(content: "editable", attachments: [], requestBody: nil))
        XCTAssertThrowsError(try persistence.save(missing, stamp: stamp))
    }

    func testRemovingHandoffsNeverTouchesLegacyJSONOrUnrelatedFiles() throws {
        let legacyRoot = root.appendingPathComponent("NanoIM/SendAttempts", isDirectory: true)
        let legacy = SendAttemptStore(directory: legacyRoot)
        let a = attempt(conversation: "a")
        let b = attempt(conversation: "b")
        try legacy.save(a, origin: partition.origin, userID: partition.userID)
        let legacyFile = try XCTUnwrap(legacy.attemptFiles(origin: partition.origin, userID: partition.userID).first)
        let original = try Data(contentsOf: legacyFile)
        try persistence.save(a, stamp: persistence.stamp(for: "a"))
        try persistence.save(b, stamp: persistence.stamp(for: "b"))
        let bareJSON = location.directoryURL.appendingPathComponent("old-format.json")
        let unrelated = location.directoryURL.appendingPathComponent("handoff-note.txt")
        try original.write(to: bareJSON)
        try Data("unrelated".utf8).write(to: unrelated)

        try persistence.recordCleanup("a", kind: .discardPending)
        try persistence.removeHandoffs(conversationID: "a")
        XCTAssertEqual(try persistence.loadHandoffs().map { $0.attempt.conversationID }, ["b"])
        try persistence.removeHandoff(b)
        try persistence.removeHandoff(b) // Missing is idempotent.
        try persistence.save(b, stamp: persistence.stamp(for: "b"))
        try persistence.recordPurge()
        try persistence.removeHandoffs()
        XCTAssertTrue(try persistence.loadHandoffs().isEmpty)
        XCTAssertEqual(try Data(contentsOf: legacyFile), original)
        XCTAssertEqual(try Data(contentsOf: bareJSON), original)
        XCTAssertEqual(try Data(contentsOf: unrelated), Data("unrelated".utf8))
        XCTAssertEqual(legacy.attemptFiles(origin: partition.origin, userID: partition.userID), [legacyFile])
    }

    func testFilesAndDirectoriesAreExcludedFromBackupAndProtected() throws {
        try persistence.recordPurge()
        try persistence.save(attempt(), stamp: persistence.stamp(for: "a"))
        let handoff = try XCTUnwrap(persistence.loadHandoffs().first?.fileURL)
        for url in [persistence.policyURL, persistence.policyURL.deletingLastPathComponent(), handoff, location.directoryURL] {
            XCTAssertEqual(try url.resourceValues(forKeys: [.isExcludedFromBackupKey]).isExcludedFromBackup, true)
            #if os(iOS)
            let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
            XCTAssertEqual(attributes[.protectionKey] as? FileProtectionType, .complete)
            #endif
        }
    }

    private func attempt(conversation: String = "a", key: String = "key") -> SendAttempt {
        SendAttempt(conversationID: conversation, sourceMessageID: nil,
                    draft: PendingSend(key: key, content: "frozen", attachments: [], requestBody: Data("{\"content\":\"frozen\"}".utf8)))
    }

    private func assertStale(_ operation: () throws -> Void, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertThrowsError(try operation(), file: file, line: line) {
            XCTAssertEqual($0 as? ChatRepositoryError, .staleWrite, file: file, line: line)
        }
    }

    private enum TestFailure: Error { case timeout }

    private final class Trace: @unchecked Sendable {
        private let lock = NSLock()
        private var storedEvents: [String] = []
        private var storedErrors: [String] = []
        var events: [String] {
            lock.lock()
            defer { lock.unlock() }
            return storedEvents
        }
        var errors: [String] {
            lock.lock()
            defer { lock.unlock() }
            return storedErrors
        }
        func append(_ event: String) {
            lock.lock()
            defer { lock.unlock() }
            storedEvents.append(event)
        }
        func fail(_ error: Error) {
            lock.lock()
            defer { lock.unlock() }
            storedErrors.append(String(describing: error))
        }
    }
}
