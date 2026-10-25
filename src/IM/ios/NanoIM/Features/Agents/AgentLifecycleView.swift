import SwiftUI

enum AgentLifecycleAction { case disable, enable, retry }

struct AgentLifecycleSnapshot: Decodable, Sendable {
    var agent_id: String
    var desired: String
    var revision: Int
    var applied_revision: Int
    var observed: String
    var error_code: String?
    var error_detail: String?

    var canEnable: Bool { desired == "disabled" && observed == "disabled" && applied_revision == revision }
    var action: AgentLifecycleAction? {
        if desired == "enabled" { return .disable }
        if observed == "stop_unconfirmed" { return .retry }
        return canEnable ? .enable : nil
    }
    var title: String {
        if observed == "stop_unconfirmed" { return L("停止未确认", "Stop unconfirmed") }
        if canEnable { return L("已停用", "Disabled") }
        if desired == "disabled" { return L("停止中", "Stopping") }
        return observed == "enabling" ? L("启用中", "Enabling") : L("已启用", "Enabled")
    }
    func explanation(online: Bool) -> String {
        if observed == "stop_unconfirmed" { return L("仍禁止新工作。请重试停止。", "New work remains blocked. Retry stopping.") }
        if canEnable { return L("重新启用只接收新工作，旧任务仍暂停。", "Enabling allows new work; old tasks remain paused.") }
        if desired == "disabled" { return online ? L("尚未确认全部停止。", "Stopping is not yet confirmed.") : L("已请求停用，等待节点确认。", "Disable requested; waiting for the node to confirm.") }
        return revision > 1 ? L("可接收新工作，旧任务仍暂停。", "Ready for new work; old tasks remain paused.") : ""
    }
}
struct AgentLifecycleChange: Encodable, Sendable {
    let enabled: Bool
    let request_id: String
    let expected_revision: Int
}

/// A page supplies either its configuration Toggle or one native action row.
struct AgentLifecycleControls: View {
    let client: IMClient
    let agentID: String
    let canManage: Bool
    let online: Bool
    var configuration = false
    var compact = false
    @Environment(\.scenePhase) private var scenePhase
    @State private var state: AgentLifecycleSnapshot?
    @State private var busy = false
    @State private var error: String?
    @State private var readFailed = false
    @State private var requestGeneration = 0
    private var path: String { agentPath(agentID) + "/lifecycle" }
    private var action: AgentLifecycleAction? { state?.action }
    private var actionLabel: String {
        if busy { return L("提交中…", "Submitting…") }
        switch action {
        case .disable: return L("停用", "Disable")
        case .enable: return L("重新启用", "Enable again")
        case .retry: return L("重试停止", "Retry stop")
        case nil: return state == nil ? L("读取状态…", "Loading state…") : L("停止中…", "Stopping…")
        }
    }
    var body: some View {
        if canManage {
            if configuration {
                Toggle(L("启用 Agent", "Enable Agent"), isOn: Binding(get: { state?.desired == "enabled" }, set: { enabled in Task { await change(enabled ? .enable : .disable) } }))
                    .disabled(busy || readFailed || action == nil || action == .retry)
                    .frame(minHeight: 44)
                if action == .retry { actionButton }
            } else { actionButton }
        }
        VStack(alignment: .leading, spacing: 4) {
            if let state {
                Text(state.title).font(.subheadline.weight(.medium))
                let explanation = state.explanation(online: online)
                if !compact && !explanation.isEmpty { Text(explanation).font(.caption).foregroundStyle(.secondary) }
                if !compact && state.observed == "stop_unconfirmed", let detail = state.error_detail { Text(detail).font(.caption).foregroundStyle(.secondary) }
            }
            if let error { Text(error).font(.caption).foregroundStyle(.red).fixedSize(horizontal: false, vertical: true) }
            if readFailed && !compact { Button(L("刷新状态", "Refresh state")) { Task { await refresh() } }.frame(minHeight: 44) }
        }.fixedSize(horizontal: false, vertical: true).accessibilityElement(children: .contain)
            .task(id: scenePhase) {
                guard scenePhase == .active else { return }
                repeat { await refresh(); try? await Task.sleep(for: .seconds(3)) } while !Task.isCancelled
            }
    }
    private var actionButton: some View {
        Button(actionLabel, role: action == .disable || action == .retry ? .destructive : nil) {
            if let action { Task { await change(action) } }
        }.disabled(busy || readFailed || action == nil).frame(minHeight: 44)
    }
    private func refresh() async {
        guard !busy else { return }
        let generation = requestGeneration
        do {
            let value: AgentLifecycleSnapshot = try await client.get(path)
            guard !Task.isCancelled, generation == requestGeneration else { return }
            state = value; readFailed = false
            if error != nil { error = nil }
        } catch {
            guard !Task.isCancelled, generation == requestGeneration else { return }
            readFailed = true; self.error = agentError(error)
        }
    }
    private func change(_ action: AgentLifecycleAction) async {
        guard canManage, !busy, !readFailed, let state, state.action == action else { return }
        busy = true; requestGeneration += 1; error = nil
        defer { busy = false }
        let requestID = UUID().uuidString
        do {
            let result: AgentLifecycleSnapshot
            if action == .retry {
                result = try await client.send(path + "/retry", body: ["request_id": requestID])
            } else {
                do {
                    result = try await client.send(path, method: "PUT", body: AgentLifecycleChange(enabled: action == .enable, request_id: requestID, expected_revision: state.revision))
                } catch let conflict as APIError where conflict.status == 409 {
                    let latest: AgentLifecycleSnapshot = try await client.get(path)
                    self.state = latest
                    guard action == .disable else { throw conflict }
                    if latest.desired == "disabled" { result = latest }
                    else { result = try await client.send(path, method: "PUT", body: AgentLifecycleChange(enabled: false, request_id: requestID, expected_revision: latest.revision)) }
                }
            }
            guard !Task.isCancelled else { return }
            self.state = result
        } catch { if !Task.isCancelled { self.error = agentError(error) } }
    }
}
