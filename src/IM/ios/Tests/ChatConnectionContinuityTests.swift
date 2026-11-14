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
    func testMalformedCorrectionFinishesLoadingWithoutReplacingBusinessErrors() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a"], messages: 0)
        store.connection = .online
        store.errors["a"] = "unsent business operation"
        store.listError = "failed pin operation"
        await stub.setMessages(Data("{}".utf8))
        await stub.setList(Data("{}".utf8))
        await store.loadChat("a")
        await store.loadConversations()
        XCTAssertEqual(store.timelinePhase("a"), .failed, "A malformed successful response is a completed failed read, not an endless spinner or network diagnosis")
        XCTAssertEqual(store.continuity.readFailures[.timeline("a")]?.isTemporary, false)
        XCTAssertNotNil(store.continuity.readFailures[.timeline("a")])
        XCTAssertNotNil(store.continuity.readFailures[.list])
        XCTAssertEqual(store.connection, .online)
        XCTAssertEqual(store.errors["a"], "unsent business operation")
        XCTAssertEqual(store.listError, "failed pin operation")
        let chat = try conversation("a")
        await stub.setList(try JSONSerialization.data(withJSONObject: ["items": [JSONSerialization.jsonObject(with: JSONEncoder().encode(chat))]]))
        await stub.setMessages(Data(#"{"items":[]}"#.utf8))
        await store.loadConversations()
        await store.loadChat("a")
        XCTAssertNil(store.continuity.readFailures[.list])
        XCTAssertNil(store.continuity.readFailures[.timeline("a")])
        XCTAssertEqual(store.timelinePhase("a"), .empty)
        XCTAssertEqual(store.errors["a"], "unsent business operation")
        XCTAssertEqual(store.listError, "failed pin operation")
        store.resetProjection()
        try await store.repository?.close()
    }

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
    func testSurfaceRetryLoadsTheFailedEarlierPageAfterAHealthyLatestRead() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a"], messages: 0)
        store.connection = .online
        let latest = TimelineItem(type: "message", message: try message(2, conversation: "a"))
        let earlier = TimelineItem(type: "message", message: try message(1, conversation: "a"))
        await stub.setMessages(try JSONEncoder().encode(MessagePage(items: [latest], next_before_message_id: latest.id)))
        await store.loadChat("a")
        await stub.setMessages(Data("{}".utf8), before: latest.id)
        await store.loadChat("a", older: true)
        await store.loadChat("a")
        XCTAssertEqual(store.continuity.readFailures.count, 1)
        await stub.setMessages(try JSONEncoder().encode(MessagePage(items: [earlier], next_before_message_id: nil)), before: latest.id)
        await store.retryConnectionReads(.conversation("a"))
        XCTAssertEqual(store.timelines["a"]?.map(\.id), [earlier.id, latest.id])
        XCTAssertTrue(store.continuity.readFailures.isEmpty)
        store.resetProjection()
        try await store.repository?.close()
    }

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

    func testSelectedReadAndSocketReadinessDoNotWaitForEachOther() async throws {
        let (fixture, stub) = try await makeStore()
        let chat = try conversation("a")
        let row = TimelineItem(type: "message", message: try message(1, conversation: chat.id))
        let page = try JSONEncoder().encode(MessagePage(items: [row], next_before_message_id: nil))
        let sync = try JSONSerialization.data(withJSONObject: [
            "items": [JSONSerialization.jsonObject(with: JSONEncoder().encode(chat))],
            "max_event_id": 0
        ])
        await stub.setSync(sync)
        for handshakeSucceeds in [true, false] {
            let ping = ContinuityGate()
            let retry = ContinuityGate()
            let socket = ControlledUserSocket(handshake: {
                try await ping.sleep(0)
                if !handshakeSucceeds { throw URLError(.networkConnectionLost) }
            })
            let stream = UserStream(client: fixture.client, makeSocket: { _ in socket })
            let store = ChatStore(client: fixture.client, user: fixture.user, stream: stream,
                                  reconnectSleep: { try await retry.sleep($0) })
            store.selectedID = chat.id
            await stub.hold("/im/v1/conversations/a/messages", body: page)
            let run = Task { await store.run() }
            await stub.waitUntilHeld()
            let ready = expectation(description: "socket handshake starts while selected read is held")
            let observePing = Task { await ping.waitFor(0); ready.fulfill() }
            await fulfillment(of: [ready], timeout: 3)
            let changed = expectation(description: "transport status publishes the handshake result")
            withObservationTracking { _ = store.connection } onChange: { changed.fulfill() }
            await ping.release(0)
            await fulfillment(of: [changed], timeout: 3)
            XCTAssertEqual(store.connection == .online, handshakeSucceeds)
            XCTAssertNil(store.timelines[chat.id])
            let loaded = expectation(description: "selected chat renders after releasing its HTTP response")
            withObservationTracking { _ = store.timelines } onChange: { loaded.fulfill() }
            await stub.release()
            await fulfillment(of: [loaded], timeout: 3)
            XCTAssertEqual(store.timelines[chat.id]?.map(\.id), [row.id])
            XCTAssertEqual(store.connection == .online, handshakeSucceeds)
            run.cancel(); store.stop()
            await retry.releaseAll()
            await run.value
            observePing.cancel()
            await stream.stop()
        }
        fixture.resetProjection()
        try await fixture.repository?.close()
    }

    func testNetworkOnlyVisitorDetailCanWaitWithoutBlockingTheSocket() async throws {
        let (fixture, stub) = try await makeStore()
        let chat = try conversation("visitor")
        let ping = ContinuityGate()
        let socket = ControlledUserSocket(handshake: { try await ping.sleep(0) })
        let stream = UserStream(client: fixture.client, makeSocket: { _ in socket })
        let store = ChatStore(client: fixture.client, user: fixture.user, stream: stream)
        store.selectedID = chat.id
        await stub.hold("/im/v1/conversations/visitor", body: try JSONEncoder().encode(chat))
        let run = Task { await store.run() }
        await stub.waitUntilHeld()
        XCTAssertTrue(store.checkingAccess.contains(chat.id))
        let ready = expectation(description: "socket starts while the visitor's detail is held")
        let observePing = Task { await ping.waitFor(0); ready.fulfill() }
        await fulfillment(of: [ready], timeout: 3)
        let connectionChanged = expectation(description: "pong confirms live transport")
        withObservationTracking { _ = store.connection } onChange: { connectionChanged.fulfill() }
        await ping.release(0)
        await fulfillment(of: [connectionChanged], timeout: 3)
        XCTAssertTrue(store.connection.isOnline)
        XCTAssertTrue(store.checkingAccess.contains(chat.id))
        let checked = expectation(description: "the detail response resolves visitor access")
        withObservationTracking { _ = store.checkingAccess } onChange: { checked.fulfill() }
        await stub.release()
        await fulfillment(of: [checked], timeout: 3)
        XCTAssertFalse(store.checkingAccess.contains(chat.id))
        XCTAssertFalse(store.revokedChats.contains(chat.id))
        run.cancel(); store.stop()
        await run.value
        observePing.cancel()
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
