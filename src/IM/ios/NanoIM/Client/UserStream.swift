import Foundation

struct UserEvent: Decodable, Sendable {
    var op: String
    var event_type: String?
    var event_id: Int?
    var data: JSONValue?
    var reason: String?
}

/// The socket seam exercises the actual resume/ping ordering without opening a server.
protocol UserStreamSocket: Sendable {
    func resume()
    func send(_ message: URLSessionWebSocketTask.Message) async throws
    func receive() async throws -> URLSessionWebSocketTask.Message
    func confirmHandshake() async throws
    func cancel()
}

private struct LiveUserStreamSocket: UserStreamSocket {
    let task: URLSessionWebSocketTask
    func resume() { task.resume() }
    func send(_ message: URLSessionWebSocketTask.Message) async throws { try await task.send(message) }
    func receive() async throws -> URLSessionWebSocketTask.Message { try await task.receive() }
    func confirmHandshake() async throws {
        try await awaitWebSocketPong(sendPing: { completion in task.sendPing(pongReceiveHandler: completion) },
                                     cancel: { task.cancel(with: .goingAway, reason: nil) })
    }
    func cancel() { task.cancel(with: .goingAway, reason: nil) }
}

/// Waits for pong without depending on Foundation invoking its callback after cancellation.
func awaitWebSocketPong(
    sendPing: @Sendable (@escaping @Sendable (Error?) -> Void) -> Void,
    cancel: @Sendable () -> Void
) async throws {
    let waiter = PongWaiter()
    try await withTaskCancellationHandler {
        try await withCheckedThrowingContinuation { continuation in
            waiter.install(continuation)
            sendPing { error in
                waiter.resolve(error.map { .failure($0) } ?? .success(()))
            }
        }
        try Task.checkCancellation()
    } onCancel: {
        waiter.resolve(.failure(CancellationError()))
        cancel()
    }
}

/// Cancellation and pong can race, including cancellation before continuation installation.
private final class PongWaiter: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<Void, Error>?
    private var result: Result<Void, Error>?

    func install(_ continuation: CheckedContinuation<Void, Error>) {
        let completed: Result<Void, Error>? = lock.withLock {
            if let result { return result }
            self.continuation = continuation
            return nil
        }
        if let completed { continuation.resume(with: completed) }
    }

    func resolve(_ result: Result<Void, Error>) {
        let pending: CheckedContinuation<Void, Error>? = lock.withLock {
            guard self.result == nil else { return nil }
            self.result = result
            let pending = continuation
            continuation = nil
            return pending
        }
        pending?.resume(with: result)
    }
}

struct UserStreamHandshakeTiming: Sendable {
    var timeout: Duration = .seconds(10)
    var sleep: @Sendable (Duration) async throws -> Void = { try await Task.sleep(for: $0) }
}

/// One foreground connection. The owning feature controls resync and reconnection.
actor UserStream {
    private let client: IMClient
    private let transport = URLSession(configuration: .ephemeral, delegate: OriginRedirectDelegate(), delegateQueue: nil)
    private var socket: (any UserStreamSocket)?
    private let makeSocket: (@Sendable (URLRequest) -> any UserStreamSocket)?
    private var generation = UUID()
    private var ping: Task<Void, Never>?
    private var reader: Task<Void, Never>?
    private var readiness: Task<Void, Error>?
    private let handshakeTiming: UserStreamHandshakeTiming
    init(client: IMClient, makeSocket: (@Sendable (URLRequest) -> any UserStreamSocket)? = nil,
         handshakeTiming: UserStreamHandshakeTiming = .init()) {
        self.client = client; self.makeSocket = makeSocket; self.handshakeTiming = handshakeTiming
    }

    func connect(after cursor: Int) async throws -> AsyncThrowingStream<UserEvent, Error> {
        stop()
        let owner = generation
        struct Ticket: Decodable, Sendable { let ticket: String }
        let ticket: Ticket = try await client.send("/im/v1/auth/ws-ticket", body: EmptyResponse())
        guard owner == generation else { throw CancellationError() }
        try Task.checkCancellation()
        var url = URLComponents(url: client.baseURL, resolvingAgainstBaseURL: false)!
        url.scheme = url.scheme == "https" ? "wss" : "ws"
        url.path = "/im/ws/user"; url.queryItems = [.init(name: "ticket", value: ticket.ticket)]
        var request = URLRequest(url: url.url!)
        request.setValue(client.baseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/")), forHTTPHeaderField: "Origin")
        let connection = makeSocket?(request) ?? LiveUserStreamSocket(task: transport.webSocketTask(with: request))
        socket = connection; connection.resume()
        let (events, continuation) = AsyncThrowingStream<UserEvent, Error>.makeStream()
        var receiveTask: Task<Void, Never>?
        do {
            try await withTaskCancellationHandler {
                try await connection.send(.string("{\"op\":\"resume\",\"after_event_id\":\(cursor)}"))
                try Task.checkCancellation()
                guard owner == generation else { throw CancellationError() }
                // Keep one receive pump active while confirming pong. Early events are buffered,
                // but the caller cannot mark the transport online until confirmation succeeds.
                let task = Task {
                    do {
                        while !Task.isCancelled {
                            let message = try await connection.receive()
                            let data: Data
                            switch message {
                            case .data(let value): data = value
                            case .string(let value): data = Data(value.utf8)
                            @unknown default: continue
                            }
                            continuation.yield(try JSONDecoder().decode(UserEvent.self, from: data))
                        }
                        continuation.finish()
                    } catch {
                        continuation.finish(throwing: error)
                    }
                }
                receiveTask = task; reader = task
                continuation.onTermination = { _ in task.cancel(); connection.cancel() }
                let timing = handshakeTiming
                let confirmation = Task {
                    try await withThrowingTaskGroup(of: Void.self) { group in
                        defer { group.cancelAll() }
                        group.addTask { try await connection.confirmHandshake(); try Task.checkCancellation() }
                        group.addTask {
                            try await timing.sleep(timing.timeout)
                            try Task.checkCancellation()
                            throw URLError(.timedOut)
                        }
                        _ = try await group.next()
                    }
                }
                readiness = confirmation
                try await withTaskCancellationHandler {
                    try await confirmation.value
                } onCancel: { confirmation.cancel(); connection.cancel() }
                try Task.checkCancellation()
                guard owner == generation else { throw CancellationError() }
                readiness = nil
            } onCancel: { connection.cancel() }
        } catch {
            receiveTask?.cancel()
            continuation.finish(throwing: error)
            connection.cancel()
            if owner == generation { socket = nil; reader = nil; readiness = nil }
            throw error
        }
        ping = Task {
            while !Task.isCancelled {
                do { try await Task.sleep(for: .seconds(20)); try await connection.send(.string("{\"op\":\"ping\"}")) }
                catch { return }
            }
        }
        return events
    }
    func stop() {
        generation = UUID()
        readiness?.cancel(); readiness = nil
        reader?.cancel(); reader = nil
        ping?.cancel(); ping = nil
        socket?.cancel(); socket = nil
    }
}
