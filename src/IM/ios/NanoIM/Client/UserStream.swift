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
        try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                task.sendPing { error in
                    if let error { continuation.resume(throwing: error) }
                    else { continuation.resume() }
                }
            }
            try Task.checkCancellation()
        } onCancel: { task.cancel(with: .goingAway, reason: nil) }
    }
    func cancel() { task.cancel(with: .goingAway, reason: nil) }
}

/// One foreground connection. The owning feature controls resync and reconnection.
actor UserStream {
    private let client: IMClient
    private let transport = URLSession(configuration: .ephemeral, delegate: OriginRedirectDelegate(), delegateQueue: nil)
    private var socket: (any UserStreamSocket)?
    private let makeSocket: (@Sendable (URLRequest) -> any UserStreamSocket)?
    private var generation = UUID()
    private var ping: Task<Void, Never>?
    init(client: IMClient, makeSocket: (@Sendable (URLRequest) -> any UserStreamSocket)? = nil) {
        self.client = client; self.makeSocket = makeSocket
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
        do {
            try await withTaskCancellationHandler {
                try await connection.send(.string("{\"op\":\"resume\",\"after_event_id\":\(cursor)}"))
                // resume/send can queue work before the handshake. A protocol ping confirms
                // transport usability even when there is no business event to receive.
                try await connection.confirmHandshake()
                try Task.checkCancellation()
                guard owner == generation else { throw CancellationError() }
            } onCancel: { connection.cancel() }
        } catch {
            connection.cancel()
            if owner == generation { socket = nil }
            throw error
        }
        ping = Task {
            while !Task.isCancelled {
                do { try await Task.sleep(for: .seconds(20)); try await connection.send(.string("{\"op\":\"ping\"}")) }
                catch { return }
            }
        }
        return AsyncThrowingStream { continuation in
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
                } catch { continuation.finish(throwing: error) }
            }
            continuation.onTermination = { _ in task.cancel(); connection.cancel() }
        }
    }
    func stop() { generation = UUID(); ping?.cancel(); ping = nil; socket?.cancel(); socket = nil }
}
