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

struct AgentLifecycleChatNotice: View {
    let client: IMClient
    let agent: ActorRef
    @Environment(\.scenePhase) private var phase
    @State private var state: AgentLifecycleSnapshot?
    var body: some View {
        VStack(spacing: 0) {
            if agent.is_deleted == true {
                Text("\(agent.display_name ?? agent.id) · \(L("Agent 已删除", "Agent deleted"))")
                    .font(.caption.weight(.semibold)).frame(maxWidth: .infinity, alignment: .leading).padding(10).background(.bar)
            } else if state?.desired == "disabled" {
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(agent.display_name ?? agent.id) · \(L("不处理新消息", "Not processing new messages"))").font(.caption.weight(.semibold))
                    Text(L("消息会保留，但该 Agent 不会处理。", "Messages are kept, but this Agent will not process them.")).font(.caption)
                }.frame(maxWidth: .infinity, alignment: .leading).padding(10).background(.bar)
            }
        }.task(id: "\(agent.id)-\(phase == .active)-\(agent.is_deleted == true)") {
            guard phase == .active, agent.is_deleted != true else { return }
            repeat {
                if let current: AgentLifecycleSnapshot = try? await client.get(agentPath(agent.id) + "/lifecycle") { state = current }
                try? await Task.sleep(for: .seconds(3))
            } while !Task.isCancelled
        }
    }
}

/// A page supplies either its configuration Toggle or one native action row.
struct AgentLifecycleControls: View {
    let client: IMClient
    let agentID: String
    let canManage: Bool
    let online: Bool
    var configuration = false
    var compact = false
    var deletionName: String? = nil
    var deletionInProgress: Binding<Bool> = .constant(false)
    var onDeleted: (() -> Void)? = nil
    @Environment(\.scenePhase) private var scenePhase
    @State private var state: AgentLifecycleSnapshot?
    @State private var busy = false
    @State private var error: String?
    @State private var readFailed = false
    @State private var requestGeneration = 0
    private var deleting: Bool { deletionInProgress.wrappedValue }
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
        if canManage && !deleting {
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
        if canManage, let deletionName, state?.canEnable == true || deleting {
            AgentDeletionControl(client: client, agentID: agentID, name: deletionName, online: online, deleting: deletionInProgress, onDeleted: onDeleted)
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

private struct AgentDeletionSnapshot: Decodable, Sendable {
    struct Workspace: Decodable, Sendable { let path: String; let witness: String }
    struct Operation: Decodable, Sendable {
        let operation_id: String
        let state: String
        let error_detail: String?
    }
    let eligible: Bool
    let reason: String?
    let revision: Int
    let profile_version: Int
    let workspace: Workspace?
    let operation: Operation?
}

private struct AgentDeleteRequest: Encodable, Sendable {
    let request_id: String
    let expected_revision: Int
    let expected_profile_version: Int
    let workspace_witness: String?
}

private struct AgentDeletionControl: View {
    private struct Confirmation: Identifiable {
        let id = UUID().uuidString
        let scope: AgentDeletionSnapshot
    }

    let client: IMClient
    let agentID: String
    let name: String
    let online: Bool
    @Binding var deleting: Bool
    let onDeleted: (() -> Void)?
    @Environment(\.scenePhase) private var scenePhase
    @State private var snapshot: AgentDeletionSnapshot?
    @State private var pendingConfirmation: Confirmation?
    @State private var includeWorkspace = false
    @State private var busy = false
    @State private var readError = false
    @State private var error: String?
    @State private var generation = 0
    private var path: String { agentPath(agentID) + "/deletion" }

    var body: some View {
        // Keep the refresh task mounted before the first deletion snapshot arrives.
        VStack(alignment: .leading, spacing: 8) {
            if let operation = snapshot?.operation {
                Text(statusTitle(operation.state)).font(.subheadline.weight(.medium))
                if let detail = operation.error_detail { ErrorNotice(message: detail) }
                if operation.state == "failed" {
                    Button(L("重试清理", "Retry cleanup")) { Task { await retry(operation) } }.disabled(!online || busy)
                }
            } else if let snapshot, snapshot.eligible {
                Button(L("永久删除 Agent", "Permanently delete Agent"), role: .destructive) {
                    includeWorkspace = false
                    error = nil
                    pendingConfirmation = Confirmation(scope: snapshot)
                }.disabled(!online || busy || readError)
            } else if let reason = snapshot?.reason, !reason.isEmpty {
                Text(availabilityMessage(reason)).font(.caption).foregroundStyle(.secondary)
            }
            if let error, pendingConfirmation == nil { ErrorNotice(message: error) }
        }
        .task(id: scenePhase) {
            guard scenePhase == .active else { return }
            repeat {
                await refresh()
                if snapshot?.operation?.state == "deleted" { return }
                try? await Task.sleep(for: .seconds(3))
            } while !Task.isCancelled
        }
        .sheet(item: $pendingConfirmation) { confirmation($0) }
    }

    private func scopeCurrent(_ scope: AgentDeletionSnapshot) -> Bool {
        guard let snapshot else { return false }
        return snapshot.eligible && snapshot.revision == scope.revision
            && snapshot.profile_version == scope.profile_version
            && (!includeWorkspace || snapshot.workspace?.witness == scope.workspace?.witness)
    }

    private func availabilityMessage(_ reason: String) -> String {
        switch reason {
        case "node_offline": return L("节点重新在线后可永久删除。", "Permanent deletion is available when the device comes online.")
        case "node_upgrade_required": return L("升级节点后可永久删除。", "Update the device to enable permanent deletion.")
        case "stop_not_confirmed": return L("确认停止后可永久删除。", "Permanent deletion is available once the stop is confirmed.")
        default: return L("当前无法永久删除此 Agent。", "This Agent cannot be permanently deleted right now.")
        }
    }

    private func confirmation(_ confirmed: Confirmation) -> some View {
        NavigationStack {
            Form {
                Section {
                    Text(name).font(.headline)
                    Text(L("此操作会永久清理该 Agent 的执行会话、子会话和工作记录。聊天正文、附件和发送者身份会保留。", "This permanently removes this Agent’s execution sessions, child sessions, and work records. Chat messages, attachments, and sender identity are kept."))
                    if let workspace = confirmed.scope.workspace {
                        Toggle(L("同时删除专用工作区", "Also delete the dedicated workspace"), isOn: $includeWorkspace).disabled(busy)
                        Text(workspace.path).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                    } else { Text(L("工作区文件会保留。", "Workspace files are kept.")).font(.caption).foregroundStyle(.secondary) }
                }
                if !scopeCurrent(confirmed.scope) { ErrorNotice(message: L("删除范围已变化，请关闭后重新确认。", "The deletion scope changed. Close and review it again.")) }
                if !online { Text(L("等待设备重新在线。", "Waiting for the device to come online.")) }
                if let error { ErrorNotice(message: error) }
                Button(busy ? L("提交中…", "Submitting…") : L("确认永久删除", "Confirm permanent deletion"), role: .destructive) {
                    Task { await submit(confirmed) }
                }.disabled(!scopeCurrent(confirmed.scope) || !online || readError || busy)
            }
            .navigationTitle(L("永久删除 Agent", "Permanently delete Agent"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { pendingConfirmation = nil }.disabled(busy) } }
        }.interactiveDismissDisabled(busy)
    }

    private func statusTitle(_ state: String) -> String {
        switch state {
        case "waiting_node": L("等待节点恢复", "Waiting for the device")
        case "failed": L("清理失败", "Cleanup failed")
        case "deleted": L("已删除", "Deleted")
        default: L("正在永久删除…", "Deleting permanently…")
        }
    }

    private func apply(_ value: AgentDeletionSnapshot) {
        snapshot = value
        deleting = value.operation != nil
        if deleting { pendingConfirmation = nil }
        if value.operation?.state == "deleted" { onDeleted?() }
    }

    private func refresh() async {
        guard !busy else { return }
        let current = generation
        do {
            let value: AgentDeletionSnapshot = try await client.get(path)
            guard !Task.isCancelled, current == generation else { return }
            readError = false
            apply(value)
        } catch {
            guard !Task.isCancelled, current == generation else { return }
            readError = true
            if snapshot != nil { self.error = agentError(error) }
        }
    }

    private func submit(_ confirmed: Confirmation) async {
        let scope = confirmed.scope
        guard scopeCurrent(scope), online, !busy, !readError else { return }
        await send(path, AgentDeleteRequest(request_id: confirmed.id, expected_revision: scope.revision,
                                           expected_profile_version: scope.profile_version,
                                           workspace_witness: includeWorkspace ? scope.workspace?.witness : nil))
    }

    private func retry(_ operation: AgentDeletionSnapshot.Operation) async {
        guard online, !busy else { return }
        await send(path + "/retry", ["operation_id": operation.operation_id])
    }

    private func send<T: Encodable & Sendable>(_ endpoint: String, _ body: T) async {
        generation += 1
        busy = true
        error = nil
        defer { busy = false }
        do {
            let result: AgentDeletionSnapshot = try await client.send(endpoint, body: body)
            apply(result)
        } catch { self.error = agentError(error) }
    }
}
