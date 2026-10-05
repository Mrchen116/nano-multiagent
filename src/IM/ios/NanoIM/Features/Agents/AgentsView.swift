import SwiftUI

/// Discover company Agents without loading another owner's management configuration.
struct AgentsView: View {
    let client: IMClient
    let user: AuthUser
    let onOpenChat: @MainActor (String) -> Void
    @Environment(\.scenePhase) private var scenePhase
    @State private var contacts: [Contact] = []
    @State private var search = ""
    @State private var error: String?
    @State private var loaded = false
    @State private var creating = false

    var body: some View {
        List {
            NanoSearchField(text: $search, prompt: L("搜索名称、ID 或设备", "Search name, ID, or device"))
                .listRowSeparator(.hidden).listRowInsets(EdgeInsets(top: 6, leading: 20, bottom: 8, trailing: 20))
            if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } }
            if !loaded { ProgressView() }
            ForEach(contacts.filter { search.isEmpty || ($0.display_name + ($0.agent_id ?? "") + ($0.node_name ?? "")).localizedCaseInsensitiveContains(search) }) { contact in
                NavigationLink {
                    AgentProfileView(client: client, user: user, contact: contact, onOpenChat: onOpenChat)
                } label: {
                    HStack(spacing: 12) {
                        AvatarView(name: contact.display_name, online: contact.status == "online", kind: "agent")
                        VStack(alignment: .leading, spacing: 6) {
                            Text(contact.display_name).font(.body.weight(.semibold)).foregroundStyle(NanoTheme.ink).lineLimit(1)
                            Text((contact.node_name ?? L("未知设备", "Unknown device")) + " · " + (contact.work_mode == "global" ? L("全局", "Global") : L("单会话", "Single thread")))
                                .font(.caption).foregroundStyle(NanoTheme.muted).lineLimit(1)
                        }
                        Spacer(minLength: 4)
                        Text(contact.status == "online" ? L("在线", "Online") : L("离线", "Offline"))
                            .font(.caption).foregroundStyle(contact.status == "online" ? NanoTheme.accent : NanoTheme.muted)
                    }.accessibilityElement(children: .combine).accessibilityLabel("\(contact.display_name), \(contact.status ?? "unknown"), \(contact.node_name ?? "")")
                }.listRowInsets(EdgeInsets(top: 12, leading: 20, bottom: 12, trailing: 20))
            }
            if loaded && contacts.isEmpty { ContentUnavailableView(L("暂无 Agent", "No Agents"), systemImage: "person.crop.square") }
        }
        .nanoList().nanoRootTitle(L("Agent", "Agents"))
        .toolbar { Button { creating = true } label: { Label(L("新建 Agent", "New Agent"), systemImage: "plus") } }
        .sheet(isPresented: $creating, onDismiss: { Task { await load() } }) { NavigationStack { AgentCreateView(client: client) } }
        .refreshable { await load() }
        .task(id: scenePhase) {
            guard scenePhase == .active else { return }
            repeat { await load(); try? await Task.sleep(for: .seconds(3)) } while !Task.isCancelled
        }
    }
    private func load() async {
        do {
            var all: [Contact] = []; var cursor: String?
            repeat {
                var query = [URLQueryItem(name: "kind", value: "agent")]
                if let cursor { query.append(URLQueryItem(name: "cursor", value: cursor)) }
                let page: AgentContactPage = try await client.get("/im/v1/contacts", query: query)
                all += page.items; cursor = page.next_cursor
            } while cursor != nil
            guard !Task.isCancelled else { return }
            contacts = all; error = nil; loaded = true
        } catch { if !Task.isCancelled { self.error = agentError(error); loaded = true } }
    }
}

struct AgentProfileView: View {
    let client: IMClient; let user: AuthUser; let contact: Contact; let onOpenChat: @MainActor (String) -> Void
    @State private var error: String?
    @State private var openingChat = false
    private var agentID: String { contact.agent_id ?? contact.user_id }
    private var owned: Bool { contact.owner_id == user.id || contact.owner_id == user.owner_id }
    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 18) {
                    HStack(spacing: 14) {
                        AvatarView(name: contact.display_name, online: contact.status == "online", kind: "agent")
                        VStack(alignment: .leading, spacing: 5) {
                            Text(contact.display_name).font(.title3.bold())
                            Text(agentID).font(.caption).foregroundStyle(NanoTheme.muted)
                        }
                    }
                    HStack(spacing: 7) {
                        Circle().fill(contact.status == "online" ? NanoTheme.accent : NanoTheme.muted).frame(width: 6, height: 6)
                        Text((contact.status == "online" ? L("在线", "Online") : L("离线", "Offline")) + " · " + (contact.node_name ?? L("未知设备", "Unknown device")))
                            .font(.subheadline).foregroundStyle(NanoTheme.muted)
                    }
                    Button { Task { await openChat() } } label: {
                        Label(L("发消息", "Message"), systemImage: "bubble.left").font(.body.weight(.semibold)).frame(maxWidth: .infinity).padding(.vertical, 5)
                    }.buttonStyle(.borderedProminent).disabled(openingChat)
                    if let error { ErrorNotice(message: error) }
                }.padding(.vertical, 8)
            }
            Section(L("概览", "Overview")) {
                LabeledContent(L("管理者", "Owner"), value: contact.owner_display_name ?? contact.owner_id ?? "—")
                LabeledContent(L("工作模式", "Work mode"), value: contact.work_mode == "global" ? L("全局模式 · 实验", "Global · Experimental") : L("单 Thread", "Single Thread"))
            }
            if contact.work_mode == "global" {
                Section { NavigationLink { AgentWorkView(client: client, agentID: agentID, canManage: owned, onOpenChat: onOpenChat) } label: { Label(L("工作轨迹", "Work"), systemImage: "point.3.connected.trianglepath.dotted") } }
            }
            if owned {
                Section(L("管理", "Manage")) {
                    NavigationLink { AgentConfigView(client: client, agentID: agentID) } label: { Label(L("配置", "Configuration"), systemImage: "slider.horizontal.3") }
                    NavigationLink { AgentChannelsView(client: client, agentID: agentID) } label: { Label(L("外部通道", "Channels"), systemImage: "antenna.radiowaves.left.and.right") }
                    NavigationLink { AgentSkillsView(client: client, agentID: agentID, canManage: owned, global: contact.work_mode == "global", onOpenChat: onOpenChat) } label: { Label(L("Skills 使用情况", "Skill usage"), systemImage: "sparkles") }
                }
                Section { Text(L("会话管理尚未开放。聊天请从聊天入口查看；全局执行请进入工作轨迹。", "Session management is not available yet. Open Chats for conversations, or Work for global executions.")).font(.caption).foregroundStyle(NanoTheme.muted) }
            } else {
                Text(L("这是公开资料，配置由管理者维护。", "This is a public profile. Configuration is managed by its owner.")).font(.caption).foregroundStyle(NanoTheme.muted)
            }
        }.listStyle(.insetGrouped).contentMargins(.top, 12, for: .scrollContent).scrollContentBackground(.hidden).background(NanoTheme.canvas)
            .navigationTitle(L("Agent 详情", "Agent profile")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
    }
    private func openChat() async {
        openingChat = true; defer { openingChat = false }
        do {
            let body: [String: JSONValue] = ["title": .string(contact.display_name), "type": .string("direct"), "participants": .array([.object(["type": .string("user"), "id": .string(user.id)]), .object(["type": .string("agent"), "id": .string(agentID)])])]
            let chat: AgentChatCreated = try await client.send("/im/v1/conversations", body: body)
            onOpenChat(chat.id)
        } catch { self.error = agentError(error) }
    }
}

struct AgentCreateView: View {
    let client: IMClient
    var nodeID: String? = nil
    @Environment(\.dismiss) private var dismiss
    @State private var nodes: [AgentNode] = []
    @State private var selectedNode = ""
    @State private var capabilities: AgentCapabilities?
    @State private var draft = AgentDraft()
    @State private var customWorkspace = false
    @State private var error: String?
    @State private var busy = false
    @State private var pending = false
    @State private var created: AgentConfig?
    @State private var confirmWorkspace = false
    @State private var confirmLeave = false
    @State private var preview: AgentPrompt?

    var body: some View {
        Form {
            if let created {
                Section { Label(L("Agent 已创建", "Agent created"), systemImage: "checkmark.circle.fill"); Text(created.display_name); Text(created.workspace_root ?? "—").textSelection(.enabled); Button(L("完成", "Done")) { dismiss() } }
            } else {
                Section(L("设备与身份", "Device and identity")) {
                    Picker(L("设备", "Device"), selection: $selectedNode) {
                        Text(L("选择设备", "Select device")).tag("")
                        ForEach(nodes) { node in Text("\(node.name) · \(node.status)").tag(node.node_id) }
                    }.disabled(pending)
                    if nodes.isEmpty { Text(L("没有已绑定设备。请先在“我的”绑定设备。", "No bound device. Bind a device in Me first.")) }
                    TextField("Agent ID", text: $draft.agent_id).textInputAutocapitalization(.never).autocorrectionDisabled().disabled(pending)
                    Picker(L("工作模式", "Work mode"), selection: $draft.work_mode) {
                        Text(L("单 Thread", "Single Thread")).tag("single_thread")
                        Text(L("全局模式 · 实验", "Global · Experimental")).tag("global")
                    }.disabled(pending)
                    Text(L("创建后工作模式和 workspace 不可修改。", "Work mode and workspace cannot be changed after creation.")).font(.caption).foregroundStyle(.secondary)
                }
                Section("Workspace") {
                    Toggle(L("自定义路径", "Custom path"), isOn: $customWorkspace).disabled(pending)
                    if customWorkspace { TextField(L("设备上的绝对路径", "Absolute path on device"), text: $draft.workspace_root).textInputAutocapitalization(.never).autocorrectionDisabled().disabled(pending) }
                    else { Text(capabilities?.default_workspace_template?.replacingOccurrences(of: "{agent_id}", with: draft.agent_id.isEmpty ? "<agent_id>" : draft.agent_id) ?? L("等待设备报告默认路径", "Waiting for the device's default path")).textSelection(.enabled) }
                }
                AgentEditorFields(draft: $draft, capabilities: capabilities).disabled(pending)
                Section {
                    if let error { ErrorNotice(message: error) }
                    if pending {
                        Text(L("已提交，节点尚未确认。草稿已锁定，重读状态以确认创建结果。", "Submitted, awaiting node confirmation. The draft is locked; reload to check the result."))
                        Button(L("重读创建状态", "Reload creation status")) { Task { await reconcile() } }
                    } else {
                        Button(L("提示词预览", "Preview prompt")) { Task { await loadPreview() } }.disabled(capabilities == nil)
                        Button(L("创建 Agent", "Create Agent")) { Task { await create(confirmed: false) } }
                            .disabled(busy || selectedNode.isEmpty || capabilities == nil || draft.agent_id.trimmingCharacters(in: .whitespaces).isEmpty || draft.display_name.trimmingCharacters(in: .whitespaces).isEmpty || (customWorkspace && draft.workspace_root.isEmpty) || nodes.first(where: { $0.id == selectedNode })?.status != "online")
                    }
                    if busy { ProgressView() }
                }
            }
        }
        .disabled(busy)
        .navigationTitle(L("新建 Agent", "New Agent")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .navigationBarBackButtonHidden(created == nil)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { if created == nil && draft != AgentDraft() { confirmLeave = true } else { dismiss() } } } }
        .interactiveDismissDisabled(created == nil && draft != AgentDraft())
        .confirmationDialog(L("放弃未保存的草稿？", "Discard unsaved draft?"), isPresented: $confirmLeave, titleVisibility: .visible) { Button(L("放弃", "Discard"), role: .destructive) { dismiss() } }
        .confirmationDialog(L("该目录已存在。确认使用并初始化其中的 Agent 工作文件？", "This directory exists. Use it and initialize Agent workspace files?"), isPresented: $confirmWorkspace, titleVisibility: .visible) { Button(L("确认使用此目录", "Use this directory")) { Task { await create(confirmed: true) } } }
        .sheet(item: $preview) { value in AgentTextSheet(title: L("提示词预览", "Prompt preview"), text: value.prompt, preview: true) }
        .task { do { nodes = try await client.get("/im/v1/nodes"); selectedNode = nodeID ?? nodes.first(where: { $0.status == "online" })?.id ?? "" } catch { self.error = agentError(error) } }
        .task(id: selectedNode) { await loadCapabilities() }
    }
    private func loadCapabilities() async {
        capabilities = nil
        guard !selectedNode.isEmpty else { return }
        do {
            let value: AgentCapabilities = try await client.get("/im/v1/nodes/\(agentSegment(selectedNode))/capabilities")
            guard !Task.isCancelled else { return }
            capabilities = value; error = nil
            draft.tool_allowlist = value.tools.filter { $0.default_on == true }.map(\.name)
            draft.skills = value.skills.filter { $0.default_on == true }.map(\.name)
            draft.features = Dictionary(uniqueKeysWithValues: value.features.map { ($0.key, $0.default_on) })
        } catch { if !Task.isCancelled { self.error = agentError(error) } }
    }
    private func create(confirmed: Bool) async {
        guard draft.agent_id.range(of: "^[a-z0-9_-]+$", options: .regularExpression) != nil else { error = L("Agent ID 仅允许小写字母、数字、下划线和短横线。", "Agent ID accepts lowercase letters, digits, underscores, and hyphens only."); return }
        busy = true; error = nil; defer { busy = false }
        do { created = try await client.send("/im/v1/nodes/\(agentSegment(selectedNode))/agents", body: draft.payload(creating: true, customWorkspace: customWorkspace, confirmed: confirmed)) }
        catch {
            if let api = error as? APIError, api.code == "workspace_confirmation_required" { confirmWorkspace = true }
            else { self.error = agentError(error) }
            if (error as? APIError)?.code == "config_apply_pending" || !(error is APIError) { pending = true }
        }
    }
    private func reconcile() async {
        busy = true; defer { busy = false }
        do { let value: AgentConfig = try await client.get(agentPath(draft.agent_id) + "/config"); created = value; pending = false; error = nil }
        catch { self.error = agentError(error) }
    }
    private func loadPreview() async {
        busy = true; defer { busy = false }
        do { preview = try await client.send("/im/v1/nodes/\(agentSegment(selectedNode))/prompt-preview", body: draft.previewPayload(capabilities: capabilities, creating: true, customWorkspace: customWorkspace)) }
        catch { self.error = agentError(error) }
    }
}

extension AgentPrompt: Identifiable { var id: String { prompt } }
struct AgentTextSheet: View {
    let title: String; let text: String; var preview = false
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if preview { Text(L("当前草稿的稳定提示词；不包含群聊、心跳及本轮运行时上下文。", "Stable prompt for the current draft; excludes group, heartbeat, and current-turn runtime context.")).font(.callout).foregroundStyle(.secondary) }
                    Text(text.isEmpty ? L("文件不存在或内容为空", "The file is absent or empty") : text).font(.system(.body, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                }.padding()
            }.navigationTitle(title).toolbar { Button(L("完成", "Done")) { dismiss() } }
        }
    }
}

func agentError(_ error: Error) -> String {
    if let error = error as? APIError {
        if error.code == "config_apply_pending" { return L("已提交，等待节点确认。请重读状态，勿重复保存。", "Submitted; waiting for the node. Reload status before saving again.") }
        if error.status == 409 { return L("状态冲突；草稿已保留，请重读并核对。", "State conflict; draft preserved. Reload and review.") + "\n" + error.detail }
        if error.status == 403 || error.status == 404 { return L("当前账号无法访问，或资源已移除。", "This account cannot access the resource, or it was removed.") + "\n" + error.detail }
    }
    return error.localizedDescription
}
