import SwiftUI

/// Discover company Agents without loading another owner's management configuration.
struct AgentsView: View {
    let client: IMClient
    let user: AuthUser
    let onOpenChat: @MainActor (String) -> Void
    @Environment(\.scenePhase) private var scenePhase
    @State private var contacts: [Contact] = []
    @State private var personal: NativePersonalAgentState?
    @State private var personalError: String?
    @State private var search = ""
    @State private var error: String?
    @State private var loaded = false
    @State private var creating = false
    private var filtered: [Contact] { contacts.filter { search.isEmpty || ($0.display_name + ($0.agent_id ?? "") + ($0.node_name ?? "")).localizedCaseInsensitiveContains(search) } }

    private var binding: NativePersonalAgentState.Binding? {
        personal?.creation == nil && personal?.binding?.status == "active" ? personal?.binding : nil
    }
    private var regular: [Contact] { filtered.filter { $0.agent_id != binding?.agent_id } }
    private var personalMatches: Bool {
        guard let binding else { return false }
        return filtered.contains { $0.agent_id == binding.agent_id } || search.isEmpty || (binding.display_name + binding.agent_id + L("个人助手", "Personal assistant")).localizedCaseInsensitiveContains(search)
    }
    var body: some View {
        List {
            NanoSearchField(text: $search, prompt: L("搜索名称、ID 或设备", "Search name, ID, or device"))
                .listRowSeparator(.hidden).listRowInsets(EdgeInsets(top: 6, leading: 20, bottom: 8, trailing: 20))
            if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } }
            if !loaded { ProgressView() }
            if let personalError { Section {
                ErrorNotice(message: personalError)
                Button(L("重试读取个人助手", "Retry personal assistant")) { Task { await loadPersonal() } }
            } }
            if let binding, personalMatches {
                Section(L("我的个人助手", "My personal assistant")) {
                    NavigationLink { AgentConfigView(client: client, agentID: binding.agent_id) } label: {
                        agentRow(name: binding.display_name, subtitle: L("个人助手", "Personal assistant"), status: contacts.first { $0.agent_id == binding.agent_id }?.status)
                    }.listRowInsets(EdgeInsets(top: 12, leading: 20, bottom: 12, trailing: 20))
                        .accessibilityHint(L("打开个人助手配置", "Open personal assistant settings"))
                }
            }
            if personal?.creation != nil { Text(L("个人助手正在设置，请稍后重试。", "Personal assistant setup is in progress.")).font(.callout).foregroundStyle(.secondary) }
            if !regular.isEmpty { Section(L("其他助手", "Other assistants")) {
            ForEach(regular) { contact in
                NavigationLink {
                    AgentProfileView(client: client, user: user, contact: contact, onOpenChat: onOpenChat)
                } label: {
                    agentRow(name: contact.display_name, subtitle: (contact.node_name ?? L("未知设备", "Unknown device")) + " · " + (contact.work_mode == "global" ? L("全局", "Global") : L("单会话", "Single thread")), status: contact.status)
                        .accessibilityLabel("\(contact.display_name), \(contact.status ?? "unknown"), \(contact.node_name ?? "")")
                }.listRowInsets(EdgeInsets(top: 12, leading: 20, bottom: 12, trailing: 20))
            }
            } }
            if loaded && regular.isEmpty && !personalMatches && error == nil {
                ContentUnavailableView(search.isEmpty ? L("暂无 Agent", "No Agents") : L("没有找到 Agent", "No matching Agents"), systemImage: search.isEmpty ? "person.crop.square" : "magnifyingglass", description: Text(search.isEmpty ? L("绑定设备后即可创建 Agent。", "Bind a device to create an Agent.") : L("试试其他名称、ID 或设备。", "Try another name, ID, or device.")))
            }
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
    private func agentRow(name: String, subtitle: String, status: String?) -> some View {
        HStack(spacing: 12) {
            AvatarView(name: name, online: status == "online", kind: "agent")
            VStack(alignment: .leading, spacing: 6) {
                Text(name).font(.body.weight(.semibold)).foregroundStyle(NanoTheme.ink).fixedSize(horizontal: false, vertical: true)
                Text(subtitle).font(.caption).foregroundStyle(NanoTheme.muted).fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 4)
            if let status {
                Text(status == "online" ? L("在线", "Online") : L("离线", "Offline"))
                    .font(.caption).foregroundStyle(status == "online" ? NanoTheme.accent : NanoTheme.muted)
            }
        }.accessibilityElement(children: .combine)
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
        if !Task.isCancelled { await loadPersonal() }
    }
    private func loadPersonal() async {
        do {
            let value: NativePersonalAgentState = try await client.get("/im/v1/personal-agent")
            guard !Task.isCancelled else { return }
            personal = value; personalError = nil
        } catch { if !Task.isCancelled { personalError = L("个人助手暂时无法读取，其他助手仍可使用。", "Personal assistant unavailable. Other assistants are still available.") } }
    }
}

struct NativePersonalAgentState: Decodable, Sendable {
    var binding: Binding?
    var creation: JSONValue?
    struct Binding: Decodable, Sendable {
        var agent_id: String; var display_name: String; var status: String
    }
}

struct AgentProfileView: View {
    let client: IMClient; let user: AuthUser; let contact: Contact; let onOpenChat: @MainActor (String) -> Void
    @State private var error: String?
    @State private var openingChat = false
    @State private var refreshedContact: Contact?
    @State private var statusError: String?
    @Environment(\.scenePhase) private var scenePhase
    private var shownContact: Contact { refreshedContact ?? contact }
    private var agentID: String { shownContact.agent_id ?? shownContact.user_id }
    private var owned: Bool { shownContact.owner_id == user.id || shownContact.owner_id == user.owner_id }
    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 18) {
                    HStack(spacing: 14) {
                        AvatarView(name: shownContact.display_name, online: shownContact.status == "online", kind: "agent")
                        VStack(alignment: .leading, spacing: 5) {
                            Text(shownContact.display_name).font(.title3.bold())
                            Text(agentID).font(.caption).foregroundStyle(NanoTheme.muted)
                        }
                    }
                    HStack(spacing: 7) {
                        Circle().fill(shownContact.status == "online" ? NanoTheme.accent : NanoTheme.muted).frame(width: 6, height: 6)
                        Text((shownContact.status == "online" ? L("在线", "Online") : L("离线", "Offline")) + " · " + (shownContact.node_name ?? L("未知设备", "Unknown device")))
                            .font(.subheadline).foregroundStyle(NanoTheme.muted)
                    }
                    Button { Task { await openChat() } } label: {
                        Label(L("发消息", "Message"), systemImage: "bubble.left").font(.body.weight(.semibold)).frame(maxWidth: .infinity).padding(.vertical, 5)
                    }.buttonStyle(.borderedProminent).disabled(openingChat)
                    if let error { ErrorNotice(message: error) }
                    if let statusError { Text(statusError).font(.caption).foregroundStyle(NanoTheme.muted) }
                    else if shownContact.status != "online" { Text(L("设备离线，Agent 回复需设备恢复在线。", "The device is offline. Agent replies require it to reconnect.")).font(.caption).foregroundStyle(NanoTheme.muted) }
                }.padding(.vertical, 8)
            }
            Section(L("概览", "Overview")) {
                LabeledContent(L("管理者", "Owner"), value: shownContact.owner_display_name ?? shownContact.owner_id ?? "—")
                LabeledContent(L("工作模式", "Work mode"), value: shownContact.work_mode == "global" ? L("全局模式 · 实验", "Global · Experimental") : L("单会话", "Single conversation"))
            }
            if shownContact.work_mode == "global" {
                Section { NavigationLink { AgentWorkView(client: client, agentID: agentID, canManage: owned, onOpenChat: onOpenChat) } label: { Label(L("工作轨迹", "Work"), systemImage: "point.3.connected.trianglepath.dotted") } }
            }
            if owned {
                Section(L("管理", "Manage")) {
                    NavigationLink { AgentConfigView(client: client, agentID: agentID) } label: { Label(L("配置", "Configuration"), systemImage: "slider.horizontal.3") }
                    NavigationLink { AgentChannelsView(client: client, agentID: agentID) } label: { Label(L("外部通道", "Channels"), systemImage: "antenna.radiowaves.left.and.right") }
                    NavigationLink { AgentSkillsView(client: client, agentID: agentID, canManage: owned, global: shownContact.work_mode == "global", onOpenChat: onOpenChat) } label: { Label(L("Skills 使用情况", "Skill usage"), systemImage: "sparkles") }
                }
            } else {
                Text(L("这是公开资料，配置由管理者维护。", "This is a public profile. Configuration is managed by its owner.")).font(.caption).foregroundStyle(NanoTheme.muted)
            }
        }.listStyle(.insetGrouped).contentMargins(.top, 12, for: .scrollContent).scrollContentBackground(.hidden).background(NanoTheme.canvas)
            .navigationTitle(L("Agent 详情", "Agent profile")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
            .task(id: scenePhase) {
                guard scenePhase == .active else { return }
                repeat {
                    do {
                        let contacts = try await client.contacts(kind: "agent")
                        try Task.checkCancellation()
                        if let current = contacts.first(where: { $0.user_id == contact.user_id }) { refreshedContact = current; statusError = nil }
                        else { statusError = L("此 Agent 的公开状态暂不可用。", "This Agent’s public status is unavailable.") }
                    } catch is CancellationError { return } catch { statusError = L("状态更新失败，显示最后已知信息。", "Status update failed. Showing last known information.") }
                    try? await Task.sleep(for: .seconds(3))
                } while !Task.isCancelled
            }
    }
    private func openChat() async {
        openingChat = true; defer { openingChat = false }
        do {
            let body: [String: JSONValue] = ["title": .string(shownContact.display_name), "type": .string("direct"), "participants": .array([.object(["type": .string("user"), "id": .string(user.id)]), .object(["type": .string("agent"), "id": .string(agentID)])])]
            let chat: AgentChatCreated = try await client.send("/im/v1/conversations", body: body)
            onOpenChat(chat.id)
        } catch { self.error = agentError(error) }
    }
}

struct AgentCreateView: View {
    let client: IMClient
    var nodeID: String? = nil
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @State private var capabilityToast: CapabilityToastMessage?
    @State private var nodes: [AgentNode] = []
    @State private var selectedNode = ""
    @State private var capabilities: AgentCapabilities?
    @State private var draft: AgentDraft
    @State private var initialDraft: AgentDraft
    @State private var purpose = "general"
    @State private var advanced = false
    @State private var openingChat = false
    init(client: IMClient, nodeID: String? = nil) {
        self.client = client; self.nodeID = nodeID
        var initial = AgentDraft()
        initial.agent_id = "agent-" + String(UUID().uuidString.prefix(8)).lowercased()
        _draft = State(initialValue: initial); _initialDraft = State(initialValue: initial)
    }
    private var hasEdits: Bool { draft != initialDraft || customWorkspace }

    @State private var customWorkspace = false
    @State private var error: String?
    @State private var busy = false
    @State private var pending = false
    @State private var created: AgentConfig?
    @State private var confirmWorkspace = false
    @State private var confirmLeave = false
    @State private var preview: AgentPrompt?
    private var canCreate: Bool { !busy && !pending && !selectedNode.isEmpty && capabilities?.models.isEmpty == false && !draft.agent_id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !draft.display_name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && (!customWorkspace || !draft.workspace_root.isEmpty) && nodes.first(where: { $0.id == selectedNode })?.status == "online" }

    var body: some View {
        Form {
            if let created {
                Section {
                    Label(L("助手已创建", "Assistant created"), systemImage: "checkmark.circle.fill").foregroundStyle(NanoTheme.accent)
                    Text(created.display_name).font(.headline)
                    Button(L("开始聊天", "Start chatting")) { Task { await openCreatedChat(created) } }.disabled(openingChat)
                    if let error { ErrorNotice(message: error) }
                }
            } else {
                Group {
                Section {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(L("名称", "Name")).font(.caption).foregroundStyle(NanoTheme.muted)
                        TextField(L("例如：研究助手", "For example: Research assistant"), text: $draft.display_name)
                    }
                    Picker(L("用途", "Purpose"), selection: $purpose) {
                        Text(L("日常协助", "Everyday help")).tag("general")
                        Text(L("研究与资料比较", "Research and comparison")).tag("research")
                        Text(L("写作与内容策划", "Writing and planning")).tag("writing")
                    }
                    VStack(alignment: .leading, spacing: 6) {
                        Text(L("希望它如何协助你", "How should it help you?")).font(.caption).foregroundStyle(NanoTheme.muted)
                        TextField(L("说明目标或偏好，可稍后调整", "Describe goals or preferences; edit later"), text: $draft.custom_prompt, axis: .vertical).lineLimit(2...5)
                    }
                } header: { Text(L("让它帮你做什么？", "What should it help with?")) }
                Section(L("运行位置", "Run on")) {
                    Picker(L("电脑", "Computer"), selection: $selectedNode) {
                        Text(L("选择电脑", "Select computer")).tag("")
                        ForEach(nodes) { Text($0.name + " · " + settingsStatus($0.status)).tag($0.node_id) }
                    }
                    if nodes.isEmpty { Text(L("还没有已连接的电脑。请先在“我的”绑定设备。", "No connected computers. Bind one in Me first.")).font(.callout) }
                    if !selectedNode.isEmpty {
                        NavigationLink { ModelServicesView(client: client, nodeID: selectedNode) } label: { Label(L("管理这台电脑的模型服务", "Manage this computer's models"), systemImage: "square.stack.3d.up") }
                        if capabilities?.models.isEmpty == true { Text(L("还没有可用模型，请先添加模型服务。", "No models are available. Add a model service first.")).font(.caption).foregroundStyle(.secondary) }
                    }
                    if nodes.first(where: { $0.id == selectedNode })?.status == "offline" { Text(L("电脑离线，恢复连接后可创建助手。", "This computer is offline. Reconnect it to create an assistant.")).font(.caption).foregroundStyle(.secondary) }
                }
                AgentEditorFields(draft: $draft, capabilities: capabilities, onCapabilityChange: changeCapability, showProfile: false, showCapabilities: false)
                Section {
                    DisclosureGroup(L("高级设置", "Advanced settings"), isExpanded: $advanced) {
                        VStack(alignment: .leading, spacing: 6) { Text(L("助手标识", "Assistant ID")).font(.caption).foregroundStyle(.secondary); TextField("Agent ID", text: $draft.agent_id).textInputAutocapitalization(.never).autocorrectionDisabled() }
                        Picker(L("工作模式", "Work mode"), selection: $draft.work_mode) { Text(L("单会话", "Single conversation")).tag("single_thread"); Text(L("全局模式 · 实验", "Global · Experimental")).tag("global") }
                        Text(L("工作模式和目录在创建后固定。", "Work mode and directory are fixed after creation.")).font(.caption).foregroundStyle(.secondary)
                        Toggle(L("自定义工作目录", "Custom working directory"), isOn: $customWorkspace)
                        if customWorkspace { TextField(L("电脑上的绝对路径", "Absolute path on computer"), text: $draft.workspace_root).textInputAutocapitalization(.never).autocorrectionDisabled() }
                        else { Text(L("使用电脑默认目录", "Use the computer's default directory")).font(.callout).foregroundStyle(.secondary) }
                    }
                }
                if advanced { AgentEditorFields(draft: $draft, capabilities: capabilities, onCapabilityChange: changeCapability, showProfile: false, showModels: false, showInstructions: false) }
                }.disabled(pending)
                Section {
                    if let error { ErrorNotice(message: error) }
                    if pending {
                        Text(L("创建已提交，等待电脑确认。", "Creation submitted; waiting for the computer."))
                        Button(L("重读创建结果", "Check creation result")) { Task { await reconcile() } }
                    } else {
                        Button(L("预览指令", "Preview instructions")) { Task { await loadPreview() } }.disabled(capabilities == nil)
                    }
                    if busy { ProgressView() }
                }
            }
        }
        .capabilityToast($capabilityToast)
        .disabled(busy)
        .navigationTitle(L("新建助手", "New assistant")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .navigationBarBackButtonHidden(created == nil)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button(created == nil ? L("取消", "Cancel") : L("关闭", "Close")) { if created == nil && hasEdits { confirmLeave = true } else { dismiss() } } } }
        .toolbar { if created == nil && !pending { ToolbarItem(placement: .confirmationAction) { Button(busy ? L("创建中…", "Creating…") : L("创建", "Create")) { Task { await create(confirmed: false) } }.disabled(!canCreate) } } }
        .interactiveDismissDisabled(created == nil && hasEdits)
        .confirmationDialog(L("放弃未保存的草稿？", "Discard unsaved draft?"), isPresented: $confirmLeave, titleVisibility: .visible) { Button(L("放弃", "Discard"), role: .destructive) { dismiss() } }
        .confirmationDialog(L("该目录已存在。确认使用并初始化工作文件？", "This directory exists. Use it and initialize workspace files?"), isPresented: $confirmWorkspace, titleVisibility: .visible) { Button(L("确认使用此目录", "Use this directory")) { Task { await create(confirmed: true) } } }
        .sheet(item: $preview) { value in AgentTextSheet(title: L("指令预览", "Instruction preview"), text: value.prompt, preview: true) }
        .task { do { nodes = try await client.get("/im/v1/nodes"); if selectedNode.isEmpty { selectedNode = nodeID ?? nodes.first(where: { $0.status == "online" })?.id ?? "" } } catch { self.error = agentError(error) } }
        .task(id: selectedNode) { await loadCapabilities() }
        .onChange(of: purpose) { _, value in
            let instruction = value == "research" ? L("整理资料并比较方案，说明依据和待确认事项。", "Research and compare options, explaining evidence and open questions.") : value == "writing" ? L("协助构思、写作和修改，保留事实与原意。", "Help plan, write and revise while preserving facts and intent.") : ""
            draft.description = value == "research" ? L("研究与资料比较", "Research and comparison") : value == "writing" ? L("写作与内容策划", "Writing and planning") : ""
            draft.custom_prompt = instruction
        }
    }
    private func openCreatedChat(_ agent: AgentConfig) async {
        openingChat = true; defer { openingChat = false }
        do {
            let user = await client.session.currentUser()
            guard let user else { return }
            let body: [String: JSONValue] = ["title": .string(agent.display_name), "type": .string("direct"), "participants": .array([.object(["type": .string("user"), "id": .string(user.id)]), .object(["type": .string("agent"), "id": .string(agent.agent_id)])])]
            let result: AgentChatCreated = try await client.send("/im/v1/conversations", body: body)
            dismiss()
            openURL(client.baseURL.appendingPathComponent("chat").appendingPathComponent(result.id))
        } catch { self.error = agentError(error) }
    }
    private func changeCapability(_ action: CapabilityAction) {
        capabilityToast = nil
        guard let capabilities else { return }
        if let block = draft.changeCapability(action, capabilities: capabilities).first {
            capabilityToast = .init(text: block.message, anchor: action.kind + ":" + action.name)
        }
    }
    private func loadCapabilities() async {
        let changed = hasEdits
        capabilities = nil
        guard !selectedNode.isEmpty else { return }
        do {
            let value: AgentCapabilities = try await client.get("/im/v1/nodes/\(agentSegment(selectedNode))/capabilities")
            guard !Task.isCancelled else { return }
            capabilities = value; error = nil
            draft.tool_allowlist = value.tools.filter { $0.default_on == true }.map(\.name)
            draft.skills = []; draft.skills_selection_mode = "explicit_denylist"
            draft.initializeCapabilities(value)
            if !changed { initialDraft = draft }
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
