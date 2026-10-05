import SwiftUI

struct SettingsNodesView: View {
    let client: IMClient
    let ownerID: String
    @Environment(\.scenePhase) private var scenePhase
    @State private var nodes: [SettingsNode] = []
    @State private var loaded = false
    @State private var error: String?
    @State private var visible = false

    var body: some View {
        List {
            if let error { Section { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } } }
            if !loaded && error == nil { ProgressView(L("正在加载设备", "Loading devices")) }
            if loaded && nodes.isEmpty { ContentUnavailableView(L("尚未绑定设备", "No devices yet"), systemImage: "desktopcomputer", description: Text(L("返回“我的”，使用设备提供的链接绑定。", "Return to Me and bind with the link provided by your device."))) }
            ForEach(nodes) { node in
                NavigationLink {
                    SettingsNodeView(client: client, ownerID: ownerID, initial: node)
                } label: {
                    VStack(alignment: .leading, spacing: 5) {
                        HStack {
                            Text(node.name).font(.headline)
                            Spacer()
                            Text(settingsStatus(node.status)).font(.caption).foregroundStyle(node.status == "online" ? .green : .secondary)
                        }
                        Text(node.node_id).font(.caption.monospaced()).foregroundStyle(.secondary)
                        Text(L("\(node.agent_count) 个 Agent · 版本 \(node.version)", "\(node.agent_count) agents · Version \(node.version)")).font(.caption).foregroundStyle(.secondary)
                    }.padding(.vertical, 4)
                }
            }
        }
        .navigationTitle(L("我的设备", "My devices"))
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
            nodes = all.filter { $0.owner_id == ownerID }; loaded = true; error = nil
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
    private var canManage: Bool { accessible && node.owner_id == ownerID }
    var body: some View {
        Form {
            SettingsFeedback(error: error ?? refreshError, success: success)
            Section(L("设备状态", "Device status")) {
                LabeledContent(L("设备名称", "Device name"), value: node.node_name)
                LabeledContent(L("设备 ID", "Device ID"), value: node.node_id).textSelection(.enabled)
                LabeledContent(L("状态", "Status"), value: settingsStatus(node.status))
                LabeledContent(L("最近心跳", "Last heartbeat"), value: node.last_heartbeat_at)
                LabeledContent(L("版本", "Version"), value: node.version)
                LabeledContent("Agent", value: String(node.agent_count))
                if let message = node.last_error, !message.isEmpty { Text(message).foregroundStyle(.secondary).textSelection(.enabled) }
            }
            Section(L("设备配置", "Device settings")) {
                TextField(L("别名", "Alias"), text: $draft.alias)
                Toggle(L("启用中继", "Enable relay"), isOn: $draft.relay_enabled)
                Toggle(L("启用上报", "Enable reporting"), isOn: $draft.reporting_enabled)
            }.disabled(!canManage || busy)
            Section {
                Button(busy ? L("保存中…", "Saving…") : L("保存", "Save")) { Task { await save() } }.disabled(!canManage || busy || !dirty)
                Button(L("放弃修改", "Discard changes")) { draft = SettingsNodeUpdate(node); error = nil; success = nil }.disabled(busy || !dirty)
            }
            Section {
                NavigationLink {
                    AgentCreateView(client: client, nodeID: node.node_id)
                } label: { Label(L("在此设备创建 Agent", "Create agent on this device"), systemImage: "plus.circle") }
                    .disabled(!canManage || node.status != "online")
                if node.status != "online" { Text(L("设备恢复在线后可创建 Agent。", "Agent creation is available when the device is online.")).font(.footnote).foregroundStyle(.secondary) }
            }
        }
        .navigationTitle(node.name)
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
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
        } catch is CancellationError {} catch { self.refreshError = settingsError(error) }
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
