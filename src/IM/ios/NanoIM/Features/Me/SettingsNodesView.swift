import SwiftUI

struct SettingsNodesView: View {
    let client: IMClient
    let user: AuthUser
    let accountUpdated: @MainActor () -> Void
    @Environment(\.scenePhase) private var scenePhase
    @State private var nodes: [SettingsNode] = []
    @State private var loaded = false
    @State private var error: String?
    @State private var visible = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } }
                if !loaded && error == nil { ProgressView(L("正在加载设备", "Loading devices")) }
                if loaded && nodes.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Image(systemName: "desktopcomputer").font(.largeTitle).foregroundStyle(NanoTheme.accent)
                        Text(L("连接第一台电脑", "Connect your first computer")).font(.title2.bold())
                        Text(L("助手会在你连接的电脑上工作。", "Your assistants work on the computers you connect."))
                            .font(.subheadline).foregroundStyle(.secondary)
                    }.frame(maxWidth: .infinity, alignment: .leading)
                        .padding(18).background(NanoTheme.softAccent, in: RoundedRectangle(cornerRadius: 18))
                }
                ForEach(nodes) { node in
                    NavigationLink {
                        SettingsNodeView(client: client, ownerID: user.owner_id, initial: node)
                    } label: {
                        HStack(spacing: 14) {
                            Image(systemName: "desktopcomputer")
                                .font(.system(size: 28)).foregroundStyle(NanoTheme.ink)
                                .frame(width: 58, height: 54).background(NanoTheme.softAccent, in: RoundedRectangle(cornerRadius: 12))
                            VStack(alignment: .leading, spacing: 5) {
                                Text(node.name).font(.headline)
                                HStack(spacing: 5) {
                                    Circle().fill(node.status == "online" ? Color.green : NanoTheme.muted).frame(width: 6, height: 6)
                                    Text(settingsStatus(node.status))
                                    Text("·")
                                    Text(L("\(node.agent_count) 位助手", "\(node.agent_count) assistants"))
                                }.font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer(minLength: 4)
                            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                        }.contentShape(Rectangle())
                    }.buttonStyle(.plain)
                }
                if !nodes.isEmpty { Divider() }
                NavigationLink { ComputerInstallView(client: client) } label: {
                    Label(L("连接新电脑", "Connect a computer"), systemImage: "plus").font(.headline)
                        .frame(maxWidth: .infinity, minHeight: 48)
                        .foregroundStyle(.white).background(NanoTheme.accent, in: Capsule())
                }
                NavigationLink(L("使用绑定链接", "Use a binding link")) {
                    SettingsBindingView(client: client, user: user, onAccountUpdated: accountUpdated)
                }.font(.subheadline).frame(maxWidth: .infinity, minHeight: 44)
            }.padding(20)
        }
        .background(NanoTheme.surface)
        .navigationTitle(L("我的电脑", "My computers"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .refreshable { await load() }
        .onAppear { visible = true }
        .onDisappear { visible = false }
        .task(id: visible && scenePhase == .active) {
            guard visible && scenePhase == .active else { return }
            repeat {
                await load()
                do { try await Task.sleep(for: .seconds(5)) } catch { return }
            } while !Task.isCancelled
        }
    }
    @MainActor private func load() async {
        do {
            let all = try await client.settingsNodes()
            try Task.checkCancellation()
            nodes = all.filter { $0.owner_id == user.owner_id }; loaded = true; error = nil
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
}

struct SettingsNodeView: View {
    let client: IMClient
    let ownerID: String
    @Environment(\.scenePhase) private var scenePhase
    @State private var node: SettingsNode
    @State private var draft: SettingsNodeUpdate
    @State private var error: String?
    @State private var refreshError: String?
    @State private var success: String?
    @State private var busy = false
    @State private var visible = false
    @State private var accessible = true

    init(client: IMClient, ownerID: String, initial: SettingsNode) {
        self.client = client; self.ownerID = ownerID
        _node = State(initialValue: initial)
        _draft = State(initialValue: SettingsNodeUpdate(initial))
    }
    private var dirty: Bool { draft != SettingsNodeUpdate(node) }
    private var canManage: Bool { accessible && refreshError == nil && node.owner_id == ownerID }
    var body: some View {
        Form {
            if accessible {
                SettingsFeedback(error: error ?? refreshError, success: success)
                Section {
                    HStack(spacing: 14) {
                        Image(systemName: "desktopcomputer").font(.largeTitle).foregroundStyle(NanoTheme.accent)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(node.name).font(.title3.bold())
                            Text([settingsStatus(node.status), L("\(node.agent_count) 位助手", "\(node.agent_count) assistants")].joined(separator: " · "))
                                .font(.subheadline).foregroundStyle(.secondary)
                        }
                    }.padding(.vertical, 5)
                    if let message = node.last_error, !message.isEmpty { Text(message).foregroundStyle(.secondary).textSelection(.enabled) }
                    DisclosureGroup(L("连接详情", "Connection details")) {
                        LabeledContent(L("设备名称", "Device name"), value: node.node_name)
                        LabeledContent(L("设备 ID", "Device ID"), value: node.node_id).textSelection(.enabled)
                        LabeledContent(L("最近心跳", "Last heartbeat")) { NanoDateTime(value: node.last_heartbeat_at) }
                        LabeledContent(L("版本", "Version"), value: node.version)
                    }
                }
                Section { NavigationLink { ModelServicesView(client: client, nodeID: node.node_id) } label: { Label(L("模型服务", "Model services"), systemImage: "square.stack.3d.up") } }
                if let update = node.update {
                    ComputerUpdateSection(client: client, nodeID: node.id, update: update, canManage: canManage, refresh: refresh)
                }
                Section(L("设备配置", "Device settings")) {
                    VStack(alignment: .leading, spacing: 6) { Text(L("别名", "Alias")).font(.caption).foregroundStyle(.secondary); TextField(L("别名", "Alias"), text: $draft.alias) }
                    Toggle(L("启用中继", "Enable relay"), isOn: $draft.relay_enabled)
                    Toggle(L("启用上报", "Enable reporting"), isOn: $draft.reporting_enabled)
                }.disabled(!canManage || busy || node.update?.operation?.switching == true)
                if dirty { Section {
                    Button(L("放弃修改", "Discard changes")) { draft = SettingsNodeUpdate(node); error = nil; success = nil }.disabled(busy)
                } }
                Section {
                    NavigationLink {
                        AgentCreateView(client: client, nodeID: node.node_id)
                    } label: { Label(L("在此设备创建 Agent", "Create agent on this device"), systemImage: "plus.circle") }
                        .disabled(!canManage || node.status != "online")
                    if node.status != "online" { Text(L("设备恢复在线后可创建 Agent。", "Agent creation is available when the device is online.")).font(.footnote).foregroundStyle(.secondary) }
                }
            } else if let refreshError { ErrorNotice(message: refreshError) }
        }
        .navigationTitle(node.name)
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .nanoUnsavedChanges(dirty)
        .toolbar { ToolbarItem(placement: .confirmationAction) { Button(busy ? L("保存中…", "Saving…") : L("保存", "Save")) { Task { await save() } }.disabled(!canManage || busy || !dirty || node.update?.operation?.switching == true) } }
        .onAppear { visible = true }
        .onDisappear { visible = false }
        .task(id: visible && scenePhase == .active) {
            guard visible && scenePhase == .active else { return }
            repeat {
                await refresh()
                do { try await Task.sleep(for: .seconds(5)) } catch { return }
            } while !Task.isCancelled
        }
    }
    @MainActor private func refresh() async {
        guard !busy else { return }
        do {
            let rows = try await client.settingsNodes()
            try Task.checkCancellation()
            guard let updated = rows.first(where: { $0.node_id == node.node_id && $0.owner_id == ownerID }) else {
                accessible = false
                refreshError = L("设备已不属于当前账号，请返回列表。", "This device no longer belongs to your account. Return to the list.")
                return
            }
            // Live status refresh does not discard edits to alias or switches.
            if !dirty { draft = SettingsNodeUpdate(updated) }
            node = updated; accessible = true; refreshError = nil
        } catch is CancellationError {} catch {
            if let api = error as? APIError, [401, 403, 404].contains(api.status) { accessible = false }
            self.refreshError = settingsError(error)
        }
    }
    @MainActor private func save() async {
        guard canManage, !busy else { return }
        busy = true; error = nil; success = nil
        defer { busy = false }
        do {
            let updated = try await client.saveSettingsNode(node.node_id, update: draft)
            try Task.checkCancellation()
            node = updated; draft = SettingsNodeUpdate(updated)
            success = L("配置已保存；设备状态以实际心跳为准。", "Settings saved. Device status reflects its actual heartbeat.")
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
}
