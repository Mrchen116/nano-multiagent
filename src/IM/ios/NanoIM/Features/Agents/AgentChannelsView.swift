import SwiftUI

struct AgentChannelsView: View {
    let client: IMClient; let agentID: String
    @Environment(\.scenePhase) private var scenePhase
    @State private var channels: [AgentChannel] = []
    @State private var loaded = false
    @State private var error: String?
    @State private var busy = false
    @State private var adding = false
    @State private var editing: AgentChannel?
    @State private var deleting: AgentChannel?
    private var base: String { agentPath(agentID) + "/channels" }
    var body: some View {
        List {
            if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } }
            if !loaded { ProgressView() }
            if loaded && channels.isEmpty { ContentUnavailableView(L("暂无通道", "No channels"), systemImage: "point.3.connected.trianglepath.dotted") }
            ForEach(channels) { channel in
                Section(channel.provider == "feishu" ? L("飞书", "Feishu") : channel.provider) {
                    if channel.isRemoval { removal(channel) } else { active(channel) }
                }
            }
            Section { Text(L("每个 Agent 每种 provider 仅一个通道。凭据由节点安全存储；删除通道保留聊天历史。", "One channel per provider per Agent. Credentials use node secure storage. Removing a channel preserves chat history.")).font(.caption).foregroundStyle(.secondary) }
        }
        .navigationTitle(L("外部通道", "Channels")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .toolbar { Button { adding = true } label: { Label(L("添加通道", "Add channel"), systemImage: "plus") }.disabled(channels.contains { $0.provider == "feishu" }) }
        .sheet(isPresented: $adding, onDismiss: { Task { await load() } }) { NavigationStack { AgentChannelEditor(client: client, agentID: agentID) } }
        .sheet(item: $editing, onDismiss: { Task { await load() } }) { channel in NavigationStack { AgentChannelEditor(client: client, agentID: agentID, existing: channel) } }
        .confirmationDialog(L("删除通道并停止连接？聊天历史保留。", "Delete this channel and stop its connection? Chat history is preserved."), isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }), titleVisibility: .visible) {
            if let deleting { Button(L("删除通道", "Delete channel"), role: .destructive) { Task { await remove(deleting) } } }
        }
        .refreshable { await load() }
        .task(id: scenePhase) { guard scenePhase == .active else { return }; var firstLoad = true; repeat { await load(clearError: firstLoad); firstLoad = false; try? await Task.sleep(for: .seconds(3)) } while !Task.isCancelled }
    }
    @ViewBuilder private func active(_ channel: AgentChannel) -> some View {
        LabeledContent("App ID", value: channel.config?["app_id"] ?? "—")
        LabeledContent(L("期望状态", "Desired state"), value: channel.enabled == true ? L("启用", "Enabled") : L("停用", "Disabled"))
        LabeledContent(L("配置版本 / 同步", "Revision / sync"), value: "\(channel.channel_revision ?? 0) · \(channel.sync_state ?? "unknown")")
        if let observed = channel.observed {
            LabeledContent(observed.status_stale == true ? L("最后已知连接状态", "Last known connection state") : L("实际连接状态", "Observed connection state"), value: connectionLabel(observed.connection_state))
            NanoDateTime(value: observed.status_updated_at).font(.caption).foregroundStyle(.secondary)
            if observed.status_stale == true { Text(L("节点离线或状态已过期；此状态并非当前连接确认。", "Node offline or status stale; this is not a current connection confirmation.")).font(.caption) }
            if let message = observed.status_message, !message.isEmpty { Text(message) }
            if let code = observed.status_code, !code.isEmpty { Text(code).font(.caption).textSelection(.enabled) }
            if observed.diagnostics_state == "unknown" { Text(L("权限状态暂时无法确认。可重连后重试诊断。", "Permission status is unknown. Reconnect to retry diagnostics.")) }
            ForEach(observed.checks ?? []) { check in
                DisclosureGroup(check.check_id + " · " + check.state) {
                    Text(check.effect)
                    if check.check_id == "feishu.receive_group_message" && check.state == "missing" { Text(L("未 @Bot 的普通群消息不会进入 Agent 上下文。", "Group messages without @Bot do not enter Agent context.")) }
                    Text(check.remediation)
                    Text(L("建议权限", "Recommended scopes") + ": " + check.required.recommended_scopes.joined(separator: ", "))
                    ForEach(Array(check.required.accepted_scope_sets.enumerated()), id: \.offset) { _, scopes in Text(scopes.joined(separator: " + ")).font(.caption) }
                }.textSelection(.enabled)
            }
        } else { Text(L("连接状态尚未报告", "Connection status has not been reported")) }
        if let failure = channel.apply_error { ErrorNotice(message: failure.code + ": " + failure.message) }
        HStack {
            Button(L("编辑", "Edit")) { editing = channel }
            Spacer()
            Button(channel.enabled == true ? L("停用", "Disable") : L("启用", "Enable")) { Task { await toggle(channel) } }
            Button(L("重连", "Reconnect")) { Task { await action(channel, removal: false) } }
        }.disabled(busy).buttonStyle(.borderless)
        Button(L("删除通道", "Delete channel"), role: .destructive) { deleting = channel }.disabled(busy)
        Link(L("检查飞书开放平台权限", "Check Feishu permissions"), destination: URL(string: "https://open.feishu.cn/app/\(agentSegment(channel.config?["app_id"] ?? ""))/auth")!)
    }
    @ViewBuilder private func removal(_ channel: AgentChannel) -> some View {
        Text(L("通道正在删除；等待节点实际停止连接。", "Channel removal is pending until the node actually stops its connection."))
        LabeledContent("App ID", value: channel.display_config?["app_id_suffix"] ?? "—")
        LabeledContent(L("删除状态", "Removal state"), value: channel.apply_state ?? "pending")
        LabeledContent(L("删除版本", "Removal revision"), value: String(channel.deletion_manifest_revision ?? 0))
        if let failure = channel.apply_error { ErrorNotice(message: failure.code + ": " + failure.message) }
        Button(L("重试停止与删除", "Retry stop and removal")) { Task { await action(channel, removal: true) } }.disabled(busy)
    }
    private func connectionLabel(_ state: String) -> String {
        switch state { case "connected": return L("已连接", "Connected"); case "limited": return L("连接受限", "Limited"); case "connecting": return L("连接中", "Connecting"); case "reconnecting": return L("正在重连", "Reconnecting"); case "failed": return L("连接失败", "Failed"); case "disabled": return L("已停用", "Disabled"); default: return state }
    }
    private func load(clearError: Bool = true) async {
        do { let value: [AgentChannel] = try await client.get(base); guard !Task.isCancelled else { return }; channels = value; loaded = true; if clearError || channels.isEmpty { error = nil } }
        catch { if !Task.isCancelled { self.error = agentError(error); loaded = true; if let api = error as? APIError, [401, 403, 404].contains(api.status) { channels = [] } } }
    }
    private func toggle(_ channel: AgentChannel) async {
        busy = true; error = nil; defer { busy = false }
        do {
            let body: [String: JSONValue] = ["channel_revision": .number(Double(channel.channel_revision ?? 0)), "enabled": .bool(channel.enabled != true), "config": .object((channel.config ?? [:]).mapValues(JSONValue.string)), "credentials": .object(["mode": .string("keep")])]
            let _: AgentChannel = try await client.send(base + "/" + agentSegment(channel.id), method: "PATCH", body: body)
            await load()
        } catch { self.error = agentError(error) }
    }
    private func action(_ channel: AgentChannel, removal: Bool) async {
        busy = true; error = nil; defer { busy = false }
        do {
            let path = removal ? agentPath(agentID) + "/channel-removals/" + agentSegment(channel.id) + "/actions/retry" : base + "/" + agentSegment(channel.id) + "/actions/reconnect"
            let _: AgentChannel = try await client.send(path, body: [String: String]())
            await load()
        } catch let failure as APIError where failure.status == 409 {
            error = failure.code == "channel_node_offline"
                ? L("节点离线，恢复在线后请重试通道操作。", "The node is offline. Retry the channel action after it reconnects.")
                : L("通道操作与当前状态冲突，请重读通道状态后重试。", "The channel state changed. Reload its status before retrying.")
        } catch { self.error = agentError(error) }
    }
    private func remove(_ channel: AgentChannel) async {
        busy = true; error = nil; defer { busy = false }
        do {
            let receipt: AgentChannel = try await client.delete(base + "/" + agentSegment(channel.id), query: [URLQueryItem(name: "channel_revision", value: String(channel.channel_revision ?? 0))])
            channels.removeAll { $0.id == channel.id }; channels.append(receipt); deleting = nil
        } catch { self.error = agentError(error) }
    }
}

struct AgentChannelEditor: View {
    let client: IMClient; let agentID: String; var existing: AgentChannel? = nil
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @State private var appID = ""
    @State private var secret = ""
    @State private var enabled = true
    @State private var replace = false
    @State private var busy = false
    @State private var error: String?
    @State private var conflict = false
    @State private var latest: AgentChannel?
    @State private var saved = false
    @State private var confirmCancel = false
    private var baseline: AgentChannel? { latest ?? existing }
    private var dirty: Bool { !saved && (appID != (existing?.config?["app_id"] ?? "") || enabled != (existing?.enabled ?? true) || !secret.isEmpty || (existing != nil && replace)) }
    private var needsSecret: Bool { existing == nil || replace || appID != baseline?.config?["app_id"] }
    var body: some View {
        Form {
            Section(L("飞书机器人", "Feishu bot")) {
                Text(L("在飞书开放平台创建应用、启用机器人及长连接。节点必须具备安全凭据存储。", "Create an app on Feishu Open Platform, enable its bot and long connection. The node must support secure credential storage."))
                Link(L("打开飞书开放平台", "Open Feishu Open Platform"), destination: URL(string: "https://open.feishu.cn/page/launcher?from=backend_oneclick")!)
                TextField("App ID", text: $appID).textInputAutocapitalization(.never).autocorrectionDisabled()
                Toggle(L("启用通道", "Enable channel"), isOn: $enabled)
                if existing != nil { Toggle(L("替换密钥", "Replace secret"), isOn: $replace).disabled(appID != baseline?.config?["app_id"]) }
                if needsSecret { SecureField("App Secret", text: $secret).textInputAutocapitalization(.never).autocorrectionDisabled() }
                Text(L("已保存的密钥不可读取。修改 App ID 必须提供新密钥；提交后输入的密钥立即清除。", "Saved secrets cannot be read. Changing App ID requires a new secret. Entered secrets are cleared after submission.")).font(.caption).foregroundStyle(.secondary)
            }
            Section {
                if let latest {
                    DisclosureGroup(L("最新服务器配置", "Latest server configuration")) {
                        LabeledContent("App ID", value: latest.config?["app_id"] ?? "—")
                        LabeledContent(L("启用", "Enabled"), value: latest.enabled == true ? L("是", "Yes") : L("否", "No"))
                        LabeledContent(L("版本", "Revision"), value: String(latest.channel_revision ?? 0))
                    }
                }
                if let error { ErrorNotice(message: error) }
                if conflict {
                    Button(L("重读通道版本，保留表单", "Reload channel version and keep form")) { Task { await reload() } }
                } else if saved {
                    Text(L("期望配置已保存。请返回查看实际连接与诊断。", "Desired configuration saved. Return to check the actual connection and diagnostics."))
                    Button(L("完成", "Done")) { dismiss() }
                } else {
                    Button(L("保存", "Save")) { Task { await save() } }.disabled(busy || appID.trimmingCharacters(in: .whitespaces).isEmpty || (needsSecret && secret.isEmpty))
                }
                if busy { ProgressView() }
            }
        }.navigationTitle(existing == nil ? L("添加通道", "Add channel") : L("编辑通道", "Edit channel"))
        .toolbar {
            ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { if dirty { confirmCancel = true } else { secret = ""; dismiss() } } }
            ToolbarItem(placement: .confirmationAction) { if !saved && !conflict { Button(L("保存", "Save")) { Task { await save() } }.disabled(busy || appID.trimmingCharacters(in: .whitespaces).isEmpty || (needsSecret && secret.isEmpty)) } }
        }
        .interactiveDismissDisabled(dirty || busy)
        .confirmationDialog(L("放弃未保存的通道配置？", "Discard unsaved channel settings?"), isPresented: $confirmCancel, titleVisibility: .visible) { Button(L("放弃", "Discard"), role: .destructive) { secret = ""; dismiss() } }
        .onAppear { appID = existing?.config?["app_id"] ?? ""; enabled = existing?.enabled ?? true; replace = existing == nil }
        .onDisappear { secret = "" }
        .onChange(of: scenePhase) { _, phase in if phase != .active { secret = "" } }
        .onChange(of: appID) { _, value in if value != baseline?.config?["app_id"] { replace = true } }
    }
    private func save() async {
        busy = true; error = nil; defer { busy = false; secret = "" }
        var credentials: [String: JSONValue] = ["mode": .string(needsSecret ? "replace" : "keep")]
        if needsSecret { credentials["app_secret"] = .string(secret.trimmingCharacters(in: .whitespacesAndNewlines)) }
        var body: [String: JSONValue] = ["enabled": .bool(enabled), "config": .object(["app_id": .string(appID.trimmingCharacters(in: .whitespacesAndNewlines))]), "credentials": .object(credentials)]
        let path = agentPath(agentID) + "/channels"
        do {
            if let baseline { body["channel_revision"] = .number(Double(baseline.channel_revision ?? 0)); let _: AgentChannel = try await client.send(path + "/" + agentSegment(baseline.id), method: "PATCH", body: body) }
            else { body["provider"] = .string("feishu"); let _: AgentChannel = try await client.send(path, body: body) }
            saved = true
        } catch { self.error = agentError(error); conflict = existing != nil && (error as? APIError)?.status == 409 }
    }
    private func reload() async {
        do {
            let channels: [AgentChannel] = try await client.get(agentPath(agentID) + "/channels")
            guard let current = channels.first(where: { $0.id == existing?.id }), !current.isRemoval else { error = L("通道已移除或正在删除，请返回列表。", "Channel removed or being deleted. Return to the list."); return }
            latest = current; conflict = false
            error = L("已重读版本。请核对 App ID、开关及凭据后再保存。", "Version reloaded. Review App ID, enabled state, and credentials before saving.")
        } catch { self.error = agentError(error) }
    }
}
