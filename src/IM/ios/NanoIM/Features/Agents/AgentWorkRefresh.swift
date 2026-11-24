import Combine
import SwiftUI

extension Notification.Name {
    static let crewdenWorkUpdated = Notification.Name("Crewden.Work.Updated")
}

/// Views listen to the signed-in client's existing stream and only read while visible.
private struct AgentWorkRefresh: ViewModifier {
    let client: IMClient
    let agentID: String
    let interval: TimeInterval
    let enabled: Bool
    let action: @MainActor () async -> Void
    @Environment(\.scenePhase) private var scenePhase
    @State private var pending: AsyncStream<Void>.Continuation?

    func body(content: Content) -> some View {
        content
            .onReceive(NotificationCenter.default.publisher(for: .crewdenWorkUpdated)) { event in
                guard let sender = event.object as? IMClient, sender === client,
                      event.userInfo?["agent_id"] as? String == agentID else { return }
                pending?.yield(())
            }
            .onReceive(Timer.publish(every: interval, on: .main, in: .common).autoconnect()) { _ in
                pending?.yield(())
            }
            .task(id: enabled && scenePhase == .active) {
                guard enabled && scenePhase == .active else { return }
                let (changes, continuation) = AsyncStream<Void>.makeStream(bufferingPolicy: .bufferingNewest(1))
                pending = continuation
                defer { continuation.finish() }
                // Subscribe before the first read. A readiness event during that read queues a correction.
                await action()
                for await _ in changes {
                    guard !Task.isCancelled else { return }
                    do { try await Task.sleep(for: .milliseconds(200)) } catch { return }
                    await action()
                }
            }
    }
}

extension View {
    func workRefresh(client: IMClient, agentID: String, every interval: TimeInterval, enabled: Bool = true,
                     action: @escaping @MainActor () async -> Void) -> some View {
        modifier(AgentWorkRefresh(client: client, agentID: agentID, interval: interval, enabled: enabled, action: action))
    }
}

func workAccessLost(_ error: Error) -> Bool {
    guard let error = error as? APIError else { return false }
    return [401, 403, 404, 409, 410].contains(error.status)
}
