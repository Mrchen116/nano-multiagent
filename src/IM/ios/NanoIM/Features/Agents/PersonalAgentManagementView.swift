import SwiftUI

struct PersonalAgentPolicy: Decodable, Sendable, Equatable {
    let revision: Int
    let excluded_conversation_ids: [String]

    func rebasing(_ selection: Set<String>, from previous: Self) -> Set<String> {
        let old = Set(previous.excluded_conversation_ids)
        return Set(excluded_conversation_ids).subtracting(old.subtracting(selection)).union(selection.subtracting(old))
    }
}

private struct PersonalSettings: Decodable, Sendable {
    struct Binding: Decodable, Sendable, PersonalAvatarBinding {
        let binding_id, agent_id, conversation_id, display_name, status: String
        let avatar_variant: Int?
    }
    let binding: Binding?
    let policy: PersonalAgentPolicy?
}

private struct PersonalSavedRuntimeSettings: Decodable, Sendable {
    struct NodeState: Decodable, Sendable {
        let state: String?
    }
    let config: AgentConfig
    let node: NodeState?
    let pending_operation: JSONValue?

    var proactiveEnabled: Bool {
        if let explicit = config.features["proactive_planning"] { return explicit }
        if config.features["task_graph"] == false || !config.tool_allowlist.contains("task_graph") {
            return false
        }
        return true
    }

    var statusText: String {
        if pending_operation != nil {
            return L("待电脑确认", "Pending confirmation")
        }
        let base = proactiveEnabled ? L("已开启", "On") : L("已关闭", "Off")
        if node?.state == "offline" {
            return base + L(" · 离线只读", " · Offline")
        }
        return base
    }
}

private struct PersonalIncident: Identifiable, Decodable, Sendable {
    let id, actor_name, conversation_id, source_message_id, reason, status: String
    let count: Int
}

private struct PersonalBlockedContact: Identifiable, Decodable, Sendable {
    let actor_id, actor_name, reason: String
    let evidence: [Evidence]
    var id: String { actor_id }
    struct Evidence: Identifiable, Decodable, Sendable {
        let id, reason, conversation_id: String
        let message_id: String?
        let original: Bool
    }
}

/// Owner-only policy, source evidence and contact restrictions for the current PA binding.
struct PersonalAgentManagementView: View {
    let client: IMClient
    let agentID: String
    @Environment(\.openURL) private var openURL
    @Environment(\.scenePhase) private var scenePhase
    @State private var state: PersonalSettings?
    @State private var savedRuntime: PersonalSavedRuntimeSettings?
    @State private var chats: [Conversation] = []
    @State private var incidents: [PersonalIncident] = []
    @State private var blocked: [PersonalBlockedContact] = []
    @State private var selection: Set<String> = []
    @State private var query = ""
    @State private var name = ""
    @State private var error: String?
    @State private var notice: String?
    @State private var busy = false
    @State private var readGeneration = UUID()
    @State private var current = false
    @State private var ready = false
    private let base = "/im/v1/personal-agent"

    private var dirty: Bool {
        guard let state, let policy = state.policy else { return false }
        return selection != Set(policy.excluded_conversation_ids) || name != state.binding?.display_name
    }

    var body: some View {
        Form {
            if let error { Section { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await refresh() } } } }
            if let notice { Text(notice).font(.callout).foregroundStyle(.secondary).accessibilityAddTraits(.updatesFrequently) }
            if !ready && error == nil { ProgressView() }
            if let binding = state?.binding, let policy = state?.policy {
                profile(binding)
                exclusions(binding, policy)
                if !incidents.isEmpty { incidentSection }
                if !blocked.isEmpty { blockedSection }
                if incidents.isEmpty && blocked.isEmpty {
                    Label(L("暂无风险事件或受限联系人", "No privacy incidents or blocked contacts"), systemImage: "checkmark.shield")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                runtimeSettings
            }
        }
        .scrollContentBackground(.hidden).background(NanoTheme.canvas)
        .scrollDismissesKeyboard(.interactively)
        .navigationTitle(L("个人助手设置", "Personal assistant")).navigationBarTitleDisplayMode(.inline)
        .toolbar(.hidden, for: .tabBar)
        .nanoUnsavedChanges(dirty)
        .refreshable { await refresh() }
        .task(id: scenePhase) {
            guard scenePhase == .active else { current = false; return }
            repeat {
                await refresh()
                do { try await Task.sleep(for: .seconds(5)) } catch { return }
            } while !Task.isCancelled
        }
    }

    private func profile(_ binding: PersonalSettings.Binding) -> some View {
        Section {
            HStack(spacing: 14) {
                AvatarView(id: .personal(binding), size: 62)
                VStack(alignment: .leading, spacing: 5) {
                    Label(L("助手名称", "Assistant name"), systemImage: "pencil").font(.caption).foregroundStyle(.secondary)
                    TextField(L("名称", "Name"), text: $name).font(.title3.bold()).submitLabel(.done)
                }
                Button { openChat(binding.conversation_id) } label: {
                    Image(systemName: "bubble.left.fill").frame(width: 44, height: 44)
                        .foregroundStyle(NanoTheme.accent).background(NanoTheme.surface, in: Circle())
                }.buttonStyle(.plain).accessibilityLabel(L("打开聊天", "Open chat")).disabled(dirty || busy)
            }.listRowBackground(NanoTheme.softAccent).padding(.vertical, 3)
            if name != binding.display_name {
                Button(L("保存名称", "Save name")) { Task { await perform {
                    let _: PersonalSettings = try await client.send(base, method: "PATCH", body: ["display_name": name.trimmingCharacters(in: .whitespacesAndNewlines)])
                } } }.disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !current || busy)
            }
        }
    }

    private var runtimeSettings: some View {
        Section {
            NavigationLink {
                AgentConfigView(client: client, agentID: agentID, personal: true)
            } label: {
                HStack(spacing: 12) {
                    Label {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(L("主动筹划", "Proactive planning")).foregroundStyle(NanoTheme.ink)
                            Text(L("进入运行设置调整开关与任务图依赖", "Open runtime settings to toggle and save"))
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    } icon: {
                        Image(systemName: "wand.and.stars")
                    }
                    Spacer(minLength: 8)
                    Text(savedRuntime?.statusText ?? L("查看", "Inspect"))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            .accessibilityIdentifier("pa-proactive-planning-row")

            NavigationLink {
                AgentConfigView(client: client, agentID: agentID, personal: true)
            } label: { Label(L("模型、技能和运行设置", "Model, skills and runtime"), systemImage: "slider.horizontal.3") }
            NavigationLink { AgentChannelsView(client: client, agentID: agentID) } label: {
                Label(L("外部通道", "Channels"), systemImage: "antenna.radiowaves.left.and.right")
            }
            NavigationLink {
                AgentSkillsView(client: client, agentID: agentID, canManage: true, global: true, onOpenChat: openChat)
            } label: { Label(L("技能使用情况", "Skill usage"), systemImage: "sparkles") }
        } header: {
            Text(L("工作设置", "Work settings"))
        }
    }

    private func exclusions(_ binding: PersonalSettings.Binding, _ policy: PersonalAgentPolicy) -> some View {
        Section {
            DisclosureGroup {
                TextField(L("查找聊天", "Find a conversation"), text: $query)
                ForEach(chats.filter { $0.id != binding.conversation_id && (query.isEmpty || $0.title.localizedCaseInsensitiveContains(query)) }) { chat in
                    Toggle(chat.title, isOn: Binding(get: { selection.contains(chat.id) }, set: { excluded in
                        notice = nil
                        if excluded { selection.insert(chat.id) } else { selection.remove(chat.id) }
                    })).accessibilityIdentifier("pa-exclude-" + chat.id).disabled(!current || busy)
                }
            } label: { Text(L("排除的聊天", "Excluded conversations") + " · \(selection.count)") }
            if selection != Set(policy.excluded_conversation_ids) {
                Button(L("保存排除范围", "Save exclusions")) { Task { await savePolicy(policy) } }.disabled(!current || busy)
            }
        } header: { Text(L("聊天观察范围", "Conversation access")) }
        footer: { Text(L("选中的聊天会从助手的观察范围移除。", "Selected conversations are excluded from your assistant’s observation.")) }
    }

    private var incidentSection: some View {
        Section(L("风险事件", "Privacy incidents")) {
            ForEach(incidents) { item in
                DisclosureGroup {
                    Text(item.reason).font(.callout)
                    source(item.conversation_id, item.source_message_id)
                    if item.status == "open" {
                        ForEach(["dismiss", "misunderstanding", "block"], id: \.self) { action in
                            Button(actionLabel(action), role: action == "block" ? .destructive : nil) {
                                Task { await perform {
                                    let _: PersonalIncident = try await client.send(base + "/incidents/" + agentSegment(item.id), body: ["action": action])
                                } }
                            }.disabled(!current || busy)
                        }
                    }
                } label: {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(item.actor_name)
                        Text("\(item.count) · " + actionLabel(item.status)).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    private var blockedSection: some View {
        Section(L("已限制的联系人", "Blocked contacts")) {
            ForEach(blocked) { contact in
                DisclosureGroup(contact.actor_name) {
                    Text(contact.reason)
                    ForEach(contact.evidence) { record in
                        Text(record.reason).font(.callout)
                        if let id = record.message_id { source(record.conversation_id, id, original: record.original) }
                    }
                    Button(L("解除联系限制", "Unblock contact")) { Task { await perform {
                        let _: JSONValue = try await client.delete(base + "/blocked-contacts/" + agentSegment(contact.id))
                    } } }.disabled(!current || busy)
                }
            }
        }
    }

    private func openChat(_ id: String) {
        openURL(client.baseURL.appending(path: "chat").appending(component: id))
    }

    private func actionLabel(_ value: String) -> String {
        switch value {
        case "dismiss": L("标记已阅", "Mark reviewed")
        case "misunderstanding": L("标记为误会", "Mark as misunderstanding")
        case "block": L("限制该联系人", "Block this contact")
        case "open": L("待处理", "Open")
        case "closed": L("已标记为误会", "Marked as misunderstanding")
        case "blocked": L("已限制", "Blocked")
        case "dismissed": L("已阅", "Reviewed")
        default: value
        }
    }

    private func source(_ chatID: String, _ messageID: String, original: Bool = true) -> some View {
        Button(original ? L("查看原消息", "View original message") : L("查看通知", "View notice")) {
            let chat = client.baseURL.appending(path: "chat").appending(component: chatID)
            openURL(chat.appending(queryItems: [.init(name: "message_id", value: messageID)]))
        }
    }

    private func savePolicy(_ policy: PersonalAgentPolicy) async {
        let body: [String: JSONValue] = ["expected_revision": .number(Double(policy.revision)),
                                        "excluded_conversation_ids": .array(selection.sorted().map(JSONValue.string))]
        await perform {
            let _: PersonalAgentPolicy = try await client.send(base + "/policy", method: "PATCH", body: body)
        }
    }

    private func perform(_ operation: () async throws -> Void) async {
        guard current, !busy else { return }
        readGeneration = UUID()
        busy = true; notice = nil
        var failure: String?
        do { try await operation() }
        catch { failure = agentError(error) }
        busy = false
        await refresh()
        if let failure { notice = failure }
        else if current { notice = L("已保存", "Saved") }
    }

    private func refresh() async {
        guard !busy else { return }
        let generation = UUID()
        readGeneration = generation
        do {
            let latest: PersonalSettings = try await client.get(base)
            try Task.checkCancellation()
            guard readGeneration == generation else { return }
            guard let binding = latest.binding, ["active", "unavailable"].contains(binding.status), binding.agent_id == agentID, let policy = latest.policy else {
                clear(); ready = true; error = L("此个人助手已无法管理。", "This personal assistant is no longer available."); return
            }
            if binding.binding_id != state?.binding?.binding_id { clear() }
            async let conversationList: ItemsPage<Conversation> = client.get("/im/v1/conversations")
            async let incidentList: ItemsPage<PersonalIncident> = client.get(base + "/incidents")
            async let blockedList: ItemsPage<PersonalBlockedContact> = client.get(base + "/blocked-contacts")
            async let runtimeSnapshot: PersonalSavedRuntimeSettings? = try? client.get(agentPath(agentID) + "/settings", query: [.init(name: "view", value: "saved")])
            let lists = try await (conversationList, incidentList, blockedList)
            let savedSettings = await runtimeSnapshot
            try Task.checkCancellation()
            guard readGeneration == generation else { return }
            if let previous = state?.policy, selection != Set(previous.excluded_conversation_ids) {
                selection = policy.rebasing(selection, from: previous)
            } else { selection = Set(policy.excluded_conversation_ids) }
            if state == nil || name == state?.binding?.display_name { name = binding.display_name }
            state = latest; savedRuntime = savedSettings; chats = lists.0.items; incidents = lists.1.items; blocked = lists.2.items
            let nodeOnline = binding.status == "active" && savedSettings?.node?.state != "offline"
            current = nodeOnline; ready = true; error = nil
        } catch {
            guard !Task.isCancelled, readGeneration == generation else { return }
            if let api = error as? APIError, [401, 403, 404].contains(api.status) { clear() }
            current = false; self.error = agentError(error)
        }
    }

    private func clear() {
        state = nil; savedRuntime = nil; selection = []; chats = []; incidents = []; blocked = []; name = ""; current = false; notice = nil
    }
}
