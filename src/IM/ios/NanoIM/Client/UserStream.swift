import Foundation

struct UserEvent: Decodable, Sendable {
    var op: String
    var event_type: String?
    var event_id: Int?
    var data: JSONValue?
    var reason: String?
}

/// One foreground connection. The owning feature controls resync and reconnection.
actor UserStream {
    private let client: IMClient
    private let transport = URLSession(configuration: .ephemeral, delegate: OriginRedirectDelegate(), delegateQueue: nil)
    private var socket: URLSessionWebSocketTask?
    private var ping: Task<Void, Never>?
    init(client: IMClient) { self.client = client }

    func connect(after cursor: Int) async throws -> AsyncThrowingStream<UserEvent, Error> {
        stop()
        struct Ticket: Decodable, Sendable { let ticket: String }
        let ticket: Ticket = try await client.send("/im/v1/auth/ws-ticket", body: EmptyResponse())
        var url = URLComponents(url: client.baseURL, resolvingAgainstBaseURL: false)!
        url.scheme = url.scheme == "https" ? "wss" : "ws"
        url.path = "/im/ws/user"; url.queryItems = [.init(name: "ticket", value: ticket.ticket)]
        var request = URLRequest(url: url.url!)
        request.setValue(client.baseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/")), forHTTPHeaderField: "Origin")
        let connection = transport.webSocketTask(with: request)
        socket = connection; connection.resume()
        try await connection.send(.string("{\"op\":\"resume\",\"after_event_id\":\(cursor)}"))
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
            continuation.onTermination = { _ in task.cancel(); connection.cancel(with: .goingAway, reason: nil) }
        }
    }
    func stop() { ping?.cancel(); ping = nil; socket?.cancel(with: .goingAway, reason: nil); socket = nil }
}
