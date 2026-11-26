import SwiftUI

/// Discover company Agents without loading another owner's management configuration.
struct AgentsView: View {
    let client: IMClient
    let user: AuthUser
    let onOpenChat: @MainActor (String) -> Void
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.dynamicTypeSize) private var typeSize
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
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 18) {
                NanoSearchField(text: $search, prompt: L("搜索助手", "Search assistants"))
                if let error {
                    ErrorNotice(message: error)
                    Button(L("重试", "Retry")) { Task { await load() } }
                }
                if !loaded { ProgressView() }
                if let personalError {
                    ErrorNotice(message: personalError)
                    Button(L("重试读取个人助手", "Retry personal assistant")) { Task { await loadPersonal() } }
                }
                if let binding, personalMatches { personalEntry(binding) }
                if personal?.creation != nil {
                    Text(L("个人助手正在设置。", "Personal assistant setup is in progress.")).foregroundStyle(.secondary)
                }
                if !regular.isEmpty {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(L("团队助手", "Team assistants")).font(.title3.bold())
                        Text(regular.count, format: .number).font(.subheadline.monospacedDigit()).foregroundStyle(.secondary)
                    }.accessibilityAddTraits(.isHeader)
                    LazyVGrid(columns: typeSize.isAccessibilitySize ? [GridItem(.flexible())] : [GridItem(.adaptive(minimum: 136), spacing: 14)], alignment: .leading, spacing: 20) {
                        ForEach(regular) { contact in
                            NavigationLink {
                                AgentProfileView(client: client, user: user, contact: contact, onOpenChat: onOpenChat)
                            } label: { directoryEntry(contact) }
                            .buttonStyle(.plain)
                        }
                    }
                } else if loaded && !personalMatches && error == nil {
                    ContentUnavailableView(search.isEmpty ? L("还没有助手", "No assistants yet") : L("没有找到助手", "No matching assistants"),
                        systemImage: search.isEmpty ? "person.2" : "magnifyingglass",
                        description: Text(search.isEmpty ? L("连接电脑后就可以创建助手。", "Connect a computer to create an assistant.") : L("试试其他名称、ID 或设备。", "Try another name, ID, or device.")))
                }
            }.padding(.horizontal, 20).padding(.top, 6).padding(.bottom, 28)
        }
        .background(NanoTheme.surface).foregroundStyle(NanoTheme.ink)
        .navigationTitle(L("助手", "Assistants")).navigationBarTitleDisplayMode(.large)
        .toolbar { Button { creating = true } label: { Label(L("新建助手", "New assistant"), systemImage: "plus") } }
        .sheet(isPresented: $creating, onDismiss: { Task { await load() } }) { NavigationStack { AgentCreateView(client: client) } }
        .refreshable { await load() }
        .task(id: scenePhase) {
            guard scenePhase == .active else { return }
            repeat { await load(); try? await Task.sleep(for: .seconds(3)) } while !Task.isCancelled
        }
    }

    private func personalEntry(_ assistant: NativePersonalAgentState.Binding) -> some View {
        HStack(spacing: 12) {
            NavigationLink {
                PersonalAgentManagementView(client: client, agentID: assistant.agent_id)
            } label: {
                HStack(spacing: 12) {
                    AvatarView(id: .personal(assistant), size: 36)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(L("我的个人助手", "My personal assistant")).font(.caption.weight(.medium)).foregroundStyle(NanoTheme.muted)
                        Text(assistant.display_name).font(.headline).foregroundStyle(NanoTheme.ink)
                    }
                    Spacer(minLength: 2)
                }.contentShape(Rectangle())
            }
            .accessibilityIdentifier("personal-agent-settings")
            .accessibilityHint(L("打开个人助手配置", "Open personal assistant settings"))
            if let chat = assistant.conversation_id {
                Button { onOpenChat(chat) } label: {
                    Image(systemName: "bubble.left").font(.body.weight(.semibold)).frame(width: 44, height: 44)
                        .background(NanoTheme.surface, in: Circle()).foregroundStyle(NanoTheme.accent)
                }.accessibilityLabel(L("和\(assistant.display_name)聊天", "Chat with \(assistant.display_name)"))
            }
        }.buttonStyle(.plain).padding(.horizontal, 14).padding(.vertical, 9)
            .background(NanoTheme.softAccent, in: RoundedRectangle(cornerRadius: 19))
    }

    private func directoryEntry(_ contact: Contact) -> some View {
        let id = contact.agent_id ?? contact.user_id
        let owned = contact.owner_id != nil && (contact.owner_id == user.id || contact.owner_id == user.owner_id)
        return HStack(spacing: 9) {
            AvatarView(id: .contact(contact), size: 32)
                .overlay(alignment: .bottomTrailing) {
                    if let status = contact.status {
                        Circle().fill(status == "online" ? Color.green : Color.secondary)
                            .frame(width: 7, height: 7)
                            .overlay(Circle().stroke(NanoTheme.surface, lineWidth: 1.5))
                            .accessibilityLabel(settingsStatus(status))
                    }
                }
            VStack(alignment: .leading, spacing: 3) {
                Text(contact.display_name).font(.subheadline.weight(.semibold)).foregroundStyle(NanoTheme.ink)
                if let owner = contact.owner_display_name {
                    Text(owned ? L("我管理的助手", "Managed by me") : L("\(owner) 的助手", "Assistant for \(owner)"))
                        .font(.caption).foregroundStyle(NanoTheme.muted)
                }
                AgentLifecycleControls(client: client, agentID: id, canManage: false, online: contact.status == "online", compact: true)
            }
        }.frame(maxWidth: .infinity, minHeight: 48, alignment: .leading)
            .contentShape(Rectangle()).accessibilityElement(children: .combine)
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

/// Keep the profile tint keyed to the selected assistant identity.
private func assistantPaper(_ id: String, _ selected: Int?) -> Color {
    let variant = selected.flatMap { (0..<24).contains($0) ? $0 : nil } ?? PortraitPreview.defaultVariant(for: id)
    return [Color.purple, .mint, .blue, .orange, .pink, .yellow][variant % 6].opacity(0.12)
}

struct NativePersonalAgentState: Decodable, Sendable {
    var binding: Binding?
    var creation: JSONValue?
    struct Binding: Decodable, Sendable, PersonalAvatarBinding {
        var agent_id: String; var display_name: String; var status: String
        var node_id: String?; var conversation_id: String?; var avatar_variant: Int?
    }
}

struct AgentProfileView: View {
    let client: IMClient; let user: AuthUser; let contact: Contact; let onOpenChat: @MainActor (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var error: String?
    @State private var openingChat = false
    @State private var refreshedContact: Contact?
    @State private var statusError: String?
    @State private var deleted = false
    @Environment(\.scenePhase) private var scenePhase
    private var shownContact: Contact { refreshedContact ?? contact }
    private var agentID: String { shownContact.agent_id ?? shownContact.user_id }
    private var owned: Bool { shownContact.owner_id == user.id || shownContact.owner_id == user.owner_id }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                VStack(alignment: .leading, spacing: 22) {
                    HStack(alignment: .center, spacing: 14) {
                        VStack(alignment: .leading, spacing: 7) {
                            if let owner = shownContact.owner_display_name {
                                Text(owned ? L("我的助手", "My assistant") : L("\(owner) 的助手", "Assistant for \(owner)"))
                                    .font(.subheadline.weight(.medium)).foregroundStyle(.secondary)
                            }
                            Text(shownContact.display_name).font(.largeTitle.bold()).foregroundStyle(NanoTheme.ink)
                            if let status = shownContact.status {
                                HStack(spacing: 6) {
                                    Circle().fill(status == "online" ? Color.green : Color.secondary).frame(width: 8, height: 8)
                                    Text(settingsStatus(status))
                                }.font(.subheadline).foregroundStyle(.secondary)
                            }
                        }
                        Spacer(minLength: 0)
                        AvatarView(id: .contact(shownContact), size: 86)
                    }
                    Button { Task { await openChat() } } label: {
                        Label(L("发消息", "Message"), systemImage: "bubble.left.fill")
                            .font(.headline).padding(.horizontal, 14).frame(minHeight: 42)
                            .background(NanoTheme.ink, in: Capsule()).foregroundStyle(NanoTheme.surface)
                    }.buttonStyle(.plain).disabled(openingChat)
                }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
                    .background(assistantPaper(agentID, shownContact.avatar_variant), in: RoundedRectangle(cornerRadius: 22))
                if let error { ErrorNotice(message: error) }
                if let statusError { Text(statusError).font(.footnote).foregroundStyle(.secondary) }
                else if shownContact.status == "offline" { Text(L("电脑重新上线后，助手就能回复。", "The assistant can reply once its computer reconnects.")).font(.footnote).foregroundStyle(.secondary) }
                if shownContact.work_mode == "global" {
                    NavigationLink {
                        AgentWorkView(client: client, agentID: agentID, canManage: owned, onOpenChat: onOpenChat, displayName: shownContact.display_name)
                    } label: {
                        CrewdenDestination(title: L("工作记录", "Work records"), symbol: "clock.arrow.circlepath")
                    }.accessibilityLabel(L("工作记录", "Work records"))
                }
                if owned {
                    VStack(alignment: .leading, spacing: 0) {
                        Text(L("管理", "Manage")).font(.headline).padding(.bottom, 3)
                        NavigationLink {
                            AgentConfigView(client: client, agentID: agentID, personal: shownContact.role == "personal", onDeleted: shownContact.role == "personal" ? nil : { deleted = true })
                        } label: { CrewdenDestination(title: L("助手设置", "Assistant settings"), symbol: "slider.horizontal.3") }
                        Divider()
                        NavigationLink { AgentChannelsView(client: client, agentID: agentID) } label: {
                            CrewdenDestination(title: L("外部通道", "Channels"), symbol: "antenna.radiowaves.left.and.right")
                        }
                        Divider()
                        NavigationLink { AgentSkillsView(client: client, agentID: agentID, canManage: owned, global: shownContact.work_mode == "global", onOpenChat: onOpenChat) } label: {
                            CrewdenDestination(title: L("技能使用情况", "Skill usage"), symbol: "sparkles")
                        }
                    }
                }
                DisclosureGroup(L("助手资料", "Assistant details")) {
                    VStack(alignment: .leading, spacing: 12) {
                        if let computer = shownContact.node_name { LabeledContent(L("工作电脑", "Work computer"), value: computer) }
                        LabeledContent(L("助手 ID", "Assistant ID"), value: agentID).textSelection(.enabled)
                        LabeledContent(L("管理者", "Owner"), value: shownContact.owner_display_name ?? shownContact.owner_id ?? "—")
                        LabeledContent(L("工作模式", "Work mode"), value: shownContact.work_mode == "global" ? L("全局模式", "Global") : L("单会话", "Single conversation"))
                    }.font(.subheadline).padding(.top, 8)
                }
                AgentLifecycleControls(client: client, agentID: agentID, canManage: owned, online: shownContact.status == "online", groupDisableAction: true)
            }.padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 24)
        }.buttonStyle(.plain).background(NanoTheme.surface)
            .navigationTitle(L("助手详情", "Assistant profile")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
            .onAppear { if deleted { dismiss() } }
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
    @State private var resolvedApproval: String?
    private var approvalWorkspace: String {
        if customWorkspace { return draft.workspace_root.trimmingCharacters(in: .whitespacesAndNewlines) }
        guard !draft.agent_id.isEmpty else { return "" }
        return capabilities?.default_workspace_template?.replacingOccurrences(of: "{agent_id}", with: draft.agent_id) ?? ""
    }
    @State private var purpose = "general"
    @State private var selectedVariant = 0
    @State private var choosingAppearance = false
    @State private var advanced = false
    @State private var openingChat = false
    init(client: IMClient, nodeID: String? = nil) {
        self.client = client; self.nodeID = nodeID
        var initial = AgentDraft()
        initial.agent_id = "agent-" + String(UUID().uuidString.prefix(8)).lowercased()
        _draft = State(initialValue: initial); _initialDraft = State(initialValue: initial)
    }
    private var hasEdits: Bool { draft != initialDraft || customWorkspace || selectedVariant != 0 }

    @State private var customWorkspace = false
    @State private var error: String?
    @State private var busy = false
    @State private var pending = false
    @State private var created: AgentConfig?
    @State private var confirmWorkspace = false
    @State private var confirmLeave = false
    @State private var preview: AgentPrompt?
    private var canCreate: Bool { !busy && !pending && draft.initialRoleIsValid && !selectedNode.isEmpty && capabilities?.models.isEmpty == false && !draft.agent_id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !draft.display_name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && (!customWorkspace || !draft.workspace_root.isEmpty) && nodes.first(where: { $0.id == selectedNode })?.status == "online" }

    var body: some View {
        Form {
            if let created {
                Section {
                    VStack(spacing: 10) {
                        AvatarView(id: .created(created), size: 84)
                        Text(created.display_name).font(.title.bold())
                        Label(L("助手已创建", "Assistant created"), systemImage: "checkmark.circle.fill").font(.subheadline).foregroundStyle(.secondary)
                        Button(L("开始聊天", "Start chatting")) { Task { await openCreatedChat(created) } }
                            .buttonStyle(.borderedProminent).disabled(openingChat)
                    }.frame(maxWidth: .infinity).padding(.vertical, 10)
                        .listRowBackground(NanoTheme.softAccent)
                    if let error { ErrorNotice(message: error) }
                }
            } else {
                Group {
                Section {
                    HStack(spacing: 14) {
                        Button { choosingAppearance.toggle() } label: {
                            ZStack(alignment: .bottomTrailing) {
                                PortraitPreview(personal: false, variant: selectedVariant, size: 58)
                                Image(systemName: "paintpalette.fill").font(.caption2).frame(width: 22, height: 22)
                                    .foregroundStyle(NanoTheme.accent).background(NanoTheme.surface, in: Circle())
                            }
                        }.buttonStyle(.plain).accessibilityLabel(L("助手形象", "Appearance"))
                        VStack(alignment: .leading, spacing: 5) {
                            Text(L("名称", "Name")).font(.caption).foregroundStyle(NanoTheme.muted)
                            TextField(L("例如：研究助手", "For example: Research assistant"), text: $draft.display_name).font(.headline)
                        }
                    }.padding(.vertical, 4).listRowBackground(NanoTheme.softAccent)
                    if choosingAppearance { PortraitPicker(personal: false, variant: $selectedVariant) }
                    Picker(L("用途", "Purpose"), selection: $purpose) {
                        Text(L("日常协助", "Everyday help")).tag("general")
                        Text(L("研究与资料比较", "Research and comparison")).tag("research")
                        Text(L("写作与内容策划", "Writing and planning")).tag("writing")
                    }
                    VStack(alignment: .leading, spacing: 6) {
                        Text(L("初始角色约定", "Initial role agreement")).font(.caption).foregroundStyle(NanoTheme.muted)
                        TextField(L("说明目标或偏好，可稍后调整", "Describe goals or preferences; edit later"), text: $draft.initial_role, axis: .vertical).lineLimit(2...5).accessibilityLabel(L("初始角色约定", "Initial role agreement"))
                        if !draft.initialRoleIsValid { Text(L("初始角色约定超过 2,000 个 UTF-16 码元上限。", "The initial role exceeds the 2,000 UTF-16 unit limit.")).font(.caption).foregroundStyle(.red) }
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
                AgentEditorFields(draft: $draft, capabilities: capabilities, onCapabilityChange: changeCapabilities, approvalRules: resolvedApproval, customApprovalWorkspace: customWorkspace || !approvalWorkspace.isEmpty, showProfile: false, showCapabilities: false)
                Section {
                    DisclosureGroup(L("高级设置", "Advanced settings"), isExpanded: $advanced) {
                        VStack(alignment: .leading, spacing: 6) { Text(L("助手标识", "Assistant ID")).font(.caption).foregroundStyle(.secondary); TextField("Agent ID", text: $draft.agent_id).textInputAutocapitalization(.never).autocorrectionDisabled() }
                        Picker(L("工作模式", "Work mode"), selection: $draft.work_mode) { Text(L("全局模式", "Global")).tag("global"); Text(L("单会话", "Single conversation")).tag("single_thread") }
                        Text(L("工作模式和目录在创建后固定。", "Work mode and directory are fixed after creation.")).font(.caption).foregroundStyle(.secondary)
                        Toggle(L("自定义工作目录", "Custom working directory"), isOn: $customWorkspace)
                        if customWorkspace { TextField(L("电脑上的绝对路径", "Absolute path on computer"), text: $draft.workspace_root).textInputAutocapitalization(.never).autocorrectionDisabled() }
                        else { Text(L("使用电脑默认目录", "Use the computer's default directory")).font(.callout).foregroundStyle(.secondary) }
                    }
                }
                if advanced { AgentEditorFields(draft: $draft, capabilities: capabilities, onCapabilityChange: changeCapabilities, showProfile: false, showModels: false) }
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
        .task(id: [selectedNode, approvalWorkspace]) {
            resolvedApproval = nil
            guard !selectedNode.isEmpty, !approvalWorkspace.isEmpty else { return }
            do {
                try await Task.sleep(for: .milliseconds(300))
                let result: JSONValue = try await client.get("/im/v1/nodes/" + agentSegment(selectedNode) + "/approval", query: [.init(name: "workspace_root", value: approvalWorkspace)])
                try Task.checkCancellation()
                resolvedApproval = result["inherited_approval_rules"].stringValue
            } catch { }
        }
        .onChange(of: purpose) { _, value in
            let instruction = value == "research" ? L("整理资料并比较方案，说明依据和待确认事项。", "Research and compare options, explaining evidence and open questions.") : value == "writing" ? L("协助构思、写作和修改，保留事实与原意。", "Help plan, write and revise while preserving facts and intent.") : ""
            draft.description = value == "research" ? L("研究与资料比较", "Research and comparison") : value == "writing" ? L("写作与内容策划", "Writing and planning") : ""
            draft.initial_role = instruction
        }
        .onChange(of: draft.work_mode) { _, _ in
            guard let capabilities else { return }
            let active = draft.effectiveFeatures(capabilities: capabilities)
            for feature in capabilities.features where active[feature.key] == true {
                _ = draft.changeCapability(.init(kind: "feature", name: feature.key, enabled: true), capabilities: capabilities)
            }
            draft.tool_allowlist = draft.sanitizeStaticTools(personal: false, capabilities: capabilities)
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
    private func changeCapabilities(_ actions: [CapabilityAction]) {
        capabilityToast = nil
        guard let capabilities else { return }
        if let block = draft.changeCapabilities(actions, capabilities: capabilities).first {
            capabilityToast = .init(text: block.message, anchor: block.target.kind + ":" + block.target.name)
        } else {
            draft.tool_allowlist = draft.sanitizeStaticTools(personal: false, capabilities: capabilities)
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
            draft.tool_allowlist = value.tools.filter { $0.default_on == true && $0.source_group != "workspace" }.map(\.name)
            draft.skills = []; draft.skills_selection_mode = "explicit_denylist"
            draft.initializeCapabilities(value)
            if !changed { initialDraft = draft }
        } catch { if !Task.isCancelled { self.error = agentError(error) } }
    }
    private func create(confirmed: Bool) async {
        guard draft.agent_id.range(of: "^[a-z0-9_-]+$", options: .regularExpression) != nil else { error = L("Agent ID 仅允许小写字母、数字、下划线和短横线。", "Agent ID accepts lowercase letters, digits, underscores, and hyphens only."); return }
        busy = true; error = nil; defer { busy = false }
        do {
            var payload = draft.payload(creating: true, customWorkspace: customWorkspace, confirmed: confirmed, capabilities: capabilities)
            payload["avatar_variant"] = .number(Double(selectedVariant))
            created = try await client.send("/im/v1/nodes/\(agentSegment(selectedNode))/agents", body: payload)
        }
        catch {
            if let api = error as? APIError, api.code == "workspace_confirmation_required" { confirmWorkspace = true }
            else if let api = error as? APIError, api.code == "role_conflict" { self.error = L("这个工作区已有不同的角色约定。清空初始角色可保留现有约定，或选择另一个工作区。", "This workspace already has a different role agreement. Leave the initial role empty to keep it, or choose another workspace.") }
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
                    if preview { Text(L("当前草稿的稳定提示词；不包含角色约定、群聊、心跳及本轮运行时上下文。", "Stable prompt for the current draft; excludes role agreement, group, heartbeat, and current-turn runtime context.")).font(.callout).foregroundStyle(.secondary) }
                    Text(text.isEmpty ? L("文件不存在或内容为空", "The file is absent or empty") : text).font(.system(.body, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                }.padding()
            }.navigationTitle(title).toolbar { Button(L("完成", "Done")) { dismiss() } }
        }
    }
}

/// Distinguish a saved-state conflict from a node availability precondition.
func isAgentStateConflict(_ error: Error) -> Bool {
    guard let failure = error as? APIError else { return false }
    return failure.status == 409 && failure.code != "agent_node_offline"
}

func agentError(_ error: Error) -> String {
    if let error = error as? APIError {
        if error.code == "config_apply_pending" { return L("已提交，等待节点确认。请重读状态，勿重复保存。", "Submitted; waiting for the node. Reload status before saving again.") }
        if error.code == "agent_node_offline" { return L("所属电脑离线，草稿已保留，请恢复连接后重试。", "The computer is offline. Your draft is preserved; reconnect before trying again.") }
        if error.status == 409 { return L("状态冲突；草稿已保留，请重读并核对。", "State conflict; draft preserved. Reload and review.") + "\n" + error.detail }
        if error.status == 403 || error.status == 404 { return L("当前账号无法访问，或资源已移除。", "This account cannot access the resource, or it was removed.") + "\n" + error.detail }
    }
    return error.localizedDescription
}
