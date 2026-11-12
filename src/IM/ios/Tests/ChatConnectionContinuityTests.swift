import XCTest
import Observation
@testable import NanoIM

final class ChatConnectionContinuityTests: XCTestCase {
    private let start = Date(timeIntervalSince1970: 1_000)

    func testRetryStatesShareOneSilentPeriodUntilRealRecovery() {
        var policy = ChatConnectionContinuity()
        policy.updateTransport(.starting, now: start)
        XCTAssertNil(policy.presentation(surface: .list, now: start.addingTimeInterval(3), hasContent: true))
        policy.updateTransport(.offline(attempt: 1, nextRetryAt: nil), now: start.addingTimeInterval(3))
        policy.updateTransport(.syncing, now: start.addingTimeInterval(4))
        XCTAssertEqual(policy.presentation(surface: .list, now: start.addingTimeInterval(5), hasContent: true), .transport)
        XCTAssertNil(policy.presentation(surface: .list, now: start.addingTimeInterval(12), hasContent: false))
        policy.updateTransport(.online, now: start.addingTimeInterval(12))
        XCTAssertNil(policy.presentation(surface: .list, now: start.addingTimeInterval(12), hasContent: true))
        policy.updateTransport(.syncing, now: start.addingTimeInterval(13))
        XCTAssertNil(policy.presentation(surface: .list, now: start.addingTimeInterval(16), hasContent: true))
    }

    func testReadScopesAreIndependentAndNeverClearTransportPeriod() {
        var policy = ChatConnectionContinuity()
        policy.updateTransport(.online, now: start)
        policy.readFailed(.timeline("a"), failure: .offline, message: "timeout", now: start)
        policy.readFailed(.list, failure: .unavailable(status: 503), message: "service", now: start)
        XCTAssertNil(policy.presentation(surface: .conversation("b"), now: start.addingTimeInterval(6), hasContent: true))
        XCTAssertEqual(policy.presentation(surface: .conversation("a"), now: start.addingTimeInterval(6), hasContent: true), .read)
        policy.readSucceeded(.list)
        XCTAssertEqual(policy.presentation(surface: .conversation("a"), now: start.addingTimeInterval(6), hasContent: true), .read)
        policy.updateTransport(.offline(attempt: 0, nextRetryAt: nil), now: start)
        policy.readSucceeded(.timeline("a"))
        XCTAssertEqual(policy.presentation(surface: .conversation("a"), now: start.addingTimeInterval(6), hasContent: true), .transport)
    }

    func testRepeatedReadFailuresKeepFirstDeadlineAndTerminalClearsIt() {
        var policy = ChatConnectionContinuity()
        policy.updateTransport(.online, now: start)
        policy.readFailed(.detail("a"), failure: .offline, message: "one", now: start)
        policy.readFailed(.detail("a"), failure: .unavailable(status: 503), message: "two", now: start.addingTimeInterval(4))
        XCTAssertEqual(policy.nextDeadline(after: start), start.addingTimeInterval(5))
        XCTAssertEqual(policy.readFailures[.detail("a")]?.message, "two")
        XCTAssertNil(policy.nextDeadline(after: start.addingTimeInterval(5)))
        policy.updateTransport(.unauthorized, now: start.addingTimeInterval(6))
        XCTAssertNil(policy.presentation(surface: .conversation("a"), now: start.addingTimeInterval(10), hasContent: true))
        XCTAssertNil(policy.nextDeadline(after: start.addingTimeInterval(6)))
    }
}

extension ChatLocalFirstTests {
    func testHealthySocketReadFailureStaysScopedAndRetryClearsOnlyThatRead() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a"], messages: 1)
        store.connection = .online
        store.errors["a"] = "unsent business operation"
        await stub.failList(URLError(.timedOut))
        await stub.failMessages(URLError(.timedOut))
        await store.loadConversations()
        await store.loadChat("a")
        XCTAssertEqual(store.connection, .online)
        XCTAssertNil(store.listError)
        XCTAssertEqual(store.errors["a"], "unsent business operation")
        XCTAssertNotNil(store.continuity.readFailures[.list])
        XCTAssertNotNil(store.continuity.readFailures[.timeline("a")])
        await stub.failList(nil)
        await store.loadConversations()
        XCTAssertNil(store.continuity.readFailures[.list])
        XCTAssertNotNil(store.continuity.readFailures[.timeline("a")])
        await stub.failMessages(nil)
        await store.loadChat("a")
        XCTAssertEqual(store.connection, .online)
        XCTAssertNil(store.continuity.readFailures[.timeline("a")])
        XCTAssertEqual(store.errors["a"], "unsent business operation", "a successful read must not consume a send failure")
        store.resetProjection()
        try await store.repository?.close()
    }
}


extension ChatLocalFirstTests {
    func testSurfaceRetryRecoversAuthorityBeforeTheFailedTimeline() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a"], messages: 1)
        store.connection = .online
        await stub.failMessages(URLError(.timedOut))
        await store.loadChat("a")
        await stub.setDetail(nil, status: 503)
        await store.consume(try JSONDecoder().decode(UserEvent.self, from: Data(#"{"op":"event","event_type":"conversation.membership_changed","data":{"conversation_id":"a"}}"#.utf8)))
        XCTAssertTrue(store.checkingAccess.contains("a"))
        await stub.failMessages(nil)
        await stub.setDetail(try JSONEncoder().encode(try conversation("a")))
        await store.retryConnectionReads(.conversation("a"))
        XCTAssertFalse(store.checkingAccess.contains("a"))
        XCTAssertNil(store.continuity.readFailures[.access("a")])
        XCTAssertNil(store.continuity.readFailures[.timeline("a")])
        XCTAssertEqual(store.connection, .online)
        store.resetProjection()
        try await store.repository?.close()
    }

    func testOldReadCannotClearNewOwnersFailure() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a"], messages: 0)
        await stub.hold("/im/v1/conversations", body: Data(#"{"items":[]}"#.utf8))
        let old = Task { await store.loadConversations() }
        await stub.waitUntilHeld()
        store.resetProjection()
        await stub.failList(URLError(.timedOut))
        await store.loadConversations()
        XCTAssertNotNil(store.continuity.readFailures[.list])
        await stub.release()
        await old.value
        XCTAssertNotNil(store.continuity.readFailures[.list])
        store.resetProjection()
        try await store.repository?.close()
    }

    func testOnlineWaitsForPingWithoutWaitingForBusinessEvents() async throws {
        let (fixture, _) = try await makeStore()
        let gate = ContinuityGate()
        let socket = ControlledUserSocket(handshake: { try await gate.sleep(0) })
        let stream = UserStream(client: fixture.client, makeSocket: { _ in socket })
        let store = ChatStore(client: fixture.client, user: fixture.user, stream: stream)
        let run = Task { await store.run() }
        await gate.waitFor(0)
        XCTAssertNotEqual(store.connection, .online)
        XCTAssertEqual(socket.sent, ["resume", "protocol-ping"])
        let online = expectation(description: "confirmed stream becomes online without messages")
        withObservationTracking { _ = store.connection } onChange: { online.fulfill() }
        await gate.release(0)
        await fulfillment(of: [online], timeout: 3)
        XCTAssertEqual(store.connection, .online)
        XCTAssertTrue(store.continuity.readFailures.isEmpty)
        run.cancel(); store.stop()
        await run.value
        await stream.stop()
        fixture.resetProjection()
        try await fixture.repository?.close()
    }

    func testRepeatedPingFailureKeepsBackoffAndContinuousTransportClock() async throws {
        let (fixture, _) = try await makeStore()
        let gate = ContinuityGate()
        let now = Date(timeIntervalSince1970: 1_000)
        let timing = ChatContinuityTiming(now: { now }, sleep: { try await gate.sleep($0) })
        let socket = ControlledUserSocket(handshake: { throw URLError(.networkConnectionLost) })
        let stream = UserStream(client: fixture.client, makeSocket: { _ in socket })
        let store = ChatStore(client: fixture.client, user: fixture.user, continuityTiming: timing, stream: stream,
                              reconnectSleep: { try await gate.sleep($0) })
        let run = Task { await store.run() }
        await gate.waitFor(1)
        XCTAssertEqual(store.continuity.transportSince, now)
        XCTAssertNil(store.continuity.readFailures[.list], "WS failure is not a failed list read")
        XCTAssertNotNil(store.lastFullAt, "HTTP sync still records successful content correction")
        await gate.release(1)
        await gate.waitFor(2)
        XCTAssertEqual(store.continuity.transportSince, now)
        await gate.release(2)
        await gate.waitFor(4)
        XCTAssertEqual(store.continuity.transportSince, now)
        let delays = await gate.delays
        XCTAssertEqual(delays.filter { $0 != 5 }, [1, 2, 4], "HTTP-only recovery never resets retry attempt")
        run.cancel(); store.stop()
        await gate.releaseAll()
        await run.value
        await stream.stop()
        fixture.resetProjection()
        try await fixture.repository?.close()
    }

    func testDeadlinePublishesPersistentFeedbackWithoutPolling() async throws {
        let (fixture, _) = try await makeStore()
        let clock = ContinuityClock()
        let gate = ContinuityGate()
        let store = ChatStore(client: fixture.client, user: fixture.user,
                              continuityTiming: ChatContinuityTiming(now: { clock.now }, sleep: { try await gate.sleep($0) }))
        store.listPhase = .loaded
        store.connection = .syncing
        await gate.waitFor(5)
        XCTAssertNil(store.connectionPresentation(.list))
        let visible = expectation(description: "one deadline wake publishes persistent feedback")
        withObservationTracking { _ = store.connectionPresentation(.list) } onChange: { visible.fulfill() }
        clock.advance(5)
        await gate.release(5)
        await fulfillment(of: [visible], timeout: 3)
        XCTAssertEqual(store.connectionPresentation(.list), .transport)
        XCTAssertNil(store.continuityDeadline, "no repeated tick after feedback is visible")
        store.resetProjection(); fixture.resetProjection()
        try await fixture.repository?.close()
    }

    func testStoppedAndResetDeadlineCannotPublishIntoNewOwner() async throws {
        let (fixture, _) = try await makeStore()
        let clock = ContinuityClock()
        let gate = ContinuityGate()
        let timing = ChatContinuityTiming(now: { clock.now }, sleep: { try await gate.sleep($0) })
        let socket = ControlledUserSocket(handshake: { try await gate.sleep(0) })
        let stream = UserStream(client: fixture.client, makeSocket: { _ in socket })
        let store = ChatStore(client: fixture.client, user: fixture.user, continuityTiming: timing, stream: stream)
        store.listPhase = .loaded
        store.connection = .syncing
        await gate.waitFor(5)
        XCTAssertNotNil(store.continuityDeadline)
        store.stop()
        XCTAssertNil(store.continuityDeadline)
        let run = Task { await store.run() }
        await gate.waitFor(0)
        XCTAssertEqual(store.continuityDeadline, clock.now.addingTimeInterval(5), "new run re-registers the still relevant deadline")
        run.cancel(); store.resetProjection()
        let staleWake = expectation(description: "old timer cannot publish into reset owner")
        staleWake.isInverted = true
        withObservationTracking { _ = store.connectionPresentation(.list) } onChange: { staleWake.fulfill() }
        clock.advance(10)
        await gate.releaseAll() // Simulate a scheduler that delivers an already cancelled wake.
        await run.value
        await stream.stop()
        await fulfillment(of: [staleWake], timeout: 0.1)
        XCTAssertTrue(store.continuity.readFailures.isEmpty)
        XCTAssertNil(store.continuity.transportSince)
        XCTAssertNil(store.continuityDeadline)
        XCTAssertNil(store.connectionPresentation(.list))
        fixture.resetProjection()
        try await fixture.repository?.close()
    }
}

private final class ContinuityClock: @unchecked Sendable {
    private let lock = NSLock()
    private var date = Date(timeIntervalSince1970: 1_000)
    var now: Date { lock.withLock { date } }
    func advance(_ seconds: TimeInterval) { lock.withLock { date.addTimeInterval(seconds) } }
}

private actor ContinuityGate {
    private(set) var delays: [TimeInterval] = []
    private var sleeps: [TimeInterval: [CheckedContinuation<Void, Never>]] = [:]
    private var observers: [TimeInterval: [CheckedContinuation<Void, Never>]] = [:]
    func sleep(_ delay: TimeInterval) async throws {
        delays.append(delay)
        await withCheckedContinuation { continuation in
            sleeps[delay, default: []].append(continuation)
            observers.removeValue(forKey: delay)?.forEach { $0.resume() }
        }
        try Task.checkCancellation()
    }
    func waitFor(_ delay: TimeInterval) async {
        if sleeps[delay]?.isEmpty == false { return }
        await withCheckedContinuation { observers[delay, default: []].append($0) }
    }
    func release(_ delay: TimeInterval) { sleeps.removeValue(forKey: delay)?.forEach { $0.resume() } }
    func releaseAll() {
        let pending = sleeps; sleeps = [:]
        for values in pending.values { values.forEach { $0.resume() } }
    }
}

private final class ControlledUserSocket: UserStreamSocket, @unchecked Sendable {
    private let lock = NSLock()
    private var operations: [String] = []
    private var reader: CheckedContinuation<URLSessionWebSocketTask.Message, Error>?
    private var cancelled = false
    private let handshake: @Sendable () async throws -> Void
    init(handshake: @escaping @Sendable () async throws -> Void) { self.handshake = handshake }
    var sent: [String] { lock.withLock { operations } }
    func resume() { lock.withLock { cancelled = false } }
    func send(_ message: URLSessionWebSocketTask.Message) async throws {
        lock.withLock { operations.append("resume") }
    }
    func confirmHandshake() async throws {
        lock.withLock { operations.append("protocol-ping") }
        try await handshake()
    }
    func receive() async throws -> URLSessionWebSocketTask.Message {
        try await withCheckedThrowingContinuation { continuation in
            lock.withLock {
                if cancelled { continuation.resume(throwing: CancellationError()) }
                else { reader = continuation }
            }
        }
    }
    func cancel() {
        lock.withLock {
            cancelled = true
            reader?.resume(throwing: CancellationError()); reader = nil
        }
    }
}
