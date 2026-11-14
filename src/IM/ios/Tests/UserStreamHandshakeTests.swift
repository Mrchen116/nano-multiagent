import XCTest
@testable import NanoIM

extension ChatLocalFirstTests {
    func testHandshakeStartsReceivePumpWithoutWaitingForBusinessEvents() async throws {
        let (fixture, _) = try await makeStore()
        let socket = ReadDrivenHandshakeSocket(autoPong: true)
        let stream = UserStream(client: fixture.client, makeSocket: { _ in socket })
        let completed = expectation(description: "receive-driven pong completes without a business frame")
        let connect = Task {
            do { _ = try await stream.connect(after: 42) }
            catch { XCTFail("Unexpected connection error: \(error)") }
            completed.fulfill()
        }
        await fulfillment(of: [completed], timeout: 3)
        XCTAssertTrue(socket.receiveRegistered)
        XCTAssertEqual(socket.resumeFrame, #"{"op":"resume","after_event_id":42}"#)
        connect.cancel(); await stream.stop(); await connect.value
        fixture.resetProjection(); try await fixture.repository?.close()
    }

    func testEarlyBusinessEventIsBufferedUntilPongConfirmsReadiness() async throws {
        let (fixture, _) = try await makeStore()
        let ping = expectation(description: "ping awaiting pong")
        let read = expectation(description: "receive pump registered")
        let socket = ReadDrivenHandshakeSocket(autoPong: false, onPing: { ping.fulfill() }, onReceive: { read.fulfill() })
        socket.enqueue(.string(#"{"op":"event","event_id":17}"#))
        let stream = UserStream(client: fixture.client, makeSocket: { _ in socket })
        var connected = false
        let received = expectation(description: "buffered event survives readiness")
        let connect = Task {
            do {
                let events = try await stream.connect(after: 16)
                connected = true
                var iterator = events.makeAsyncIterator()
                let event = try await iterator.next()
                XCTAssertEqual(event?.event_id, 17)
            } catch { XCTFail("Unexpected connection error: \(error)") }
            received.fulfill()
        }
        await fulfillment(of: [ping, read], timeout: 3)
        XCTAssertFalse(connected, "Receiving data alone must not publish online readiness")
        socket.deliverPong()
        await fulfillment(of: [received], timeout: 3)
        connect.cancel(); await stream.stop(); await connect.value
        fixture.resetProjection(); try await fixture.repository?.close()
    }

    func testMissingPongTimesOutAndCancelsReaderWithoutFoundationCallback() async throws {
        let (fixture, _) = try await makeStore()
        let ping = expectation(description: "ping registered")
        let timer = expectation(description: "deadline registered")
        let deadline = ControlledHandshakeDeadline(onEntered: { timer.fulfill() })
        let socket = ReadDrivenHandshakeSocket(autoPong: false, onPing: { ping.fulfill() })
        let timing = UserStreamHandshakeTiming(sleep: { delay in
            XCTAssertEqual(delay, .seconds(10))
            try await deadline.sleep()
        })
        let stream = UserStream(client: fixture.client, makeSocket: { _ in socket }, handshakeTiming: timing)
        let completed = expectation(description: "timeout returns even though cancel omits pong callback")
        let connect = Task {
            do { _ = try await stream.connect(after: 0); XCTFail("Missing pong must not succeed") }
            catch { XCTAssertEqual((error as? URLError)?.code, .timedOut) }
            completed.fulfill()
        }
        await fulfillment(of: [ping, timer], timeout: 3)
        deadline.fire()
        await fulfillment(of: [completed], timeout: 3)
        XCTAssertTrue(socket.isCancelled)
        socket.deliverPong() // A late callback must not resume the checked continuation twice.
        socket.deliverPong(URLError(.networkConnectionLost))
        connect.cancel(); await stream.stop(); await connect.value
        fixture.resetProjection(); try await fixture.repository?.close()
    }

    func testCancellingPendingPongDoesNotWaitForSocketCallbackOrTimeout() async throws {
        try await assertPendingPongEndsOnCancellation(stopOnly: false)
    }

    func testStoppingPendingPongDoesNotWaitForSocketCallbackOrTimeout() async throws {
        try await assertPendingPongEndsOnCancellation(stopOnly: true)
    }

    private func assertPendingPongEndsOnCancellation(stopOnly: Bool) async throws {
        let (fixture, _) = try await makeStore()
        let ping = expectation(description: "ping registered")
        let socket = ReadDrivenHandshakeSocket(autoPong: false, onPing: { ping.fulfill() })
        let stream = UserStream(client: fixture.client, makeSocket: { _ in socket })
        let completed = expectation(description: "cancellation completes without a pong callback")
        let connect = Task {
            do { _ = try await stream.connect(after: 0); XCTFail("Cancelled handshake must not succeed") }
            catch { XCTAssertTrue(error is CancellationError) }
            completed.fulfill()
        }
        await fulfillment(of: [ping], timeout: 3)
        if stopOnly { await stream.stop() } else { connect.cancel() }
        await fulfillment(of: [completed], timeout: 3)
        XCTAssertTrue(socket.isCancelled)
        socket.deliverPong()
        connect.cancel(); await stream.stop(); await connect.value
        fixture.resetProjection(); try await fixture.repository?.close()
    }
}

/// Models a transport whose pong cannot be delivered before receive registration.
/// Cancel deliberately never invokes the pong callback, matching the missing-callback risk.
private final class ReadDrivenHandshakeSocket: UserStreamSocket, @unchecked Sendable {
    private let lock = NSLock()
    private let autoPong: Bool
    private let onPing: @Sendable () -> Void
    private let onReceive: @Sendable () -> Void
    private var pong: (@Sendable (Error?) -> Void)?
    private var receiver: CheckedContinuation<URLSessionWebSocketTask.Message, Error>?
    private var queued: URLSessionWebSocketTask.Message?
    private var registered = false
    private var cancelled = false
    private var frame: String?
    private var didAutoPong = false

    init(autoPong: Bool, onPing: @escaping @Sendable () -> Void = {}, onReceive: @escaping @Sendable () -> Void = {}) {
        self.autoPong = autoPong; self.onPing = onPing; self.onReceive = onReceive
    }
    var receiveRegistered: Bool { lock.withLock { registered } }
    var isCancelled: Bool { lock.withLock { cancelled } }
    var resumeFrame: String? { lock.withLock { frame } }
    func resume() {}
    func send(_ message: URLSessionWebSocketTask.Message) async throws {
        if case .string(let value) = message { lock.withLock { frame = value } }
    }
    func confirmHandshake() async throws {
        try await awaitWebSocketPong(sendPing: { callback in
            self.lock.withLock { self.pong = callback }
            self.onPing()
            self.deliverAutomaticPongIfReady()
        }, cancel: { self.cancel() })
    }
    func receive() async throws -> URLSessionWebSocketTask.Message {
        try await withCheckedThrowingContinuation { continuation in
            let first = lock.withLock {
                let first = !registered
                registered = true
                if cancelled { continuation.resume(throwing: CancellationError()) }
                else if let queued { self.queued = nil; continuation.resume(returning: queued) }
                else { receiver = continuation }
                return first
            }
            if first { onReceive() }
            deliverAutomaticPongIfReady()
        }
    }
    func enqueue(_ message: URLSessionWebSocketTask.Message) {
        let pending = lock.withLock {
            let pending = receiver; receiver = nil
            if pending == nil { queued = message }
            return pending
        }
        pending?.resume(returning: message)
    }
    func deliverPong(_ error: Error? = nil) {
        let callback = lock.withLock { pong }
        callback?(error)
    }
    private func deliverAutomaticPongIfReady() {
        let callback: (@Sendable (Error?) -> Void)? = lock.withLock {
            guard autoPong, registered, !didAutoPong, let pong else { return nil }
            didAutoPong = true
            return pong
        }
        callback?(nil)
    }
    func cancel() {
        let pending = lock.withLock {
            cancelled = true
            let pending = receiver; receiver = nil
            return pending
        }
        pending?.resume(throwing: CancellationError())
    }
}

/// Manual, cancellation-aware deadline; tests never wait ten wall-clock seconds.
private final class ControlledHandshakeDeadline: @unchecked Sendable {
    private let lock = NSLock()
    private let onEntered: @Sendable () -> Void
    private var callback: (@Sendable (Error?) -> Void)?
    private var cancelled = false
    init(onEntered: @escaping @Sendable () -> Void) { self.onEntered = onEntered }
    func sleep() async throws {
        try await awaitWebSocketPong(sendPing: { callback in
            let cancelled = self.lock.withLock { self.callback = callback; return self.cancelled }
            self.onEntered()
            if cancelled { callback(CancellationError()) }
        }, cancel: {
            let callback = self.lock.withLock { self.cancelled = true; return self.callback }
            callback?(CancellationError())
        })
    }
    func fire() {
        let pending: (@Sendable (Error?) -> Void)? = lock.withLock { self.callback }
        pending?(nil)
    }
}
