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
    struct Binding: Decodable, Sendable {
        let binding_id, agent_id, conversation_id, display_name, status: String
    }
    let binding: Binding?
    let policy: PersonalAgentPolicy?
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
    @State private var chats: [Conversation] = []
    @State private var incidents: [PersonalIncident] = []
    @State private var blocked: [PersonalBlockedContact] = []
    @State private var selection: Set<String> = []
    @State private var query = ""
    @State private var name = ""
    @State private var error: String?
    @State private var notice: String?
    @State private var busy = false
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
                incidentSection
                blockedSection
            }
        }
        .navigationTitle(L("个人助手设置", "Personal assistant")).navigationBarTitleDisplayMode(.inline)
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
        Section(L("个人助手", "Personal assistant")) {
            TextField(L("名称", "Name"), text: $name)
            if name != binding.display_name {
                Button(L("保存名称", "Save name")) { Task { await perform {
                    let _: PersonalSettings = try await client.send(base, method: "PATCH", body: ["display_name": name.trimmingCharacters(in: .whitespacesAndNewlines)])
                } } }.disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !current || busy)
            }
            NavigationLink(L("模型、技能和运行设置", "Model, skills and runtime")) {
                AgentConfigView(client: client, agentID: agentID, personal: true)
            }
            NavigationLink(L("外部通道", "Channels")) { AgentChannelsView(client: client, agentID: agentID) }
            NavigationLink(L("技能使用情况", "Skill usage")) {
                AgentSkillsView(client: client, agentID: agentID, canManage: true, global: true, onOpenChat: openChat)
            }
        }
    }

    private func exclusions(_ binding: PersonalSettings.Binding, _ policy: PersonalAgentPolicy) -> some View {
        Section {
            DisclosureGroup(L("排除的聊天", "Excluded conversations") + " · \(selection.count)") {
                TextField(L("查找聊天", "Find a conversation"), text: $query)
                ForEach(chats.filter { $0.id != binding.conversation_id && (query.isEmpty || $0.title.localizedCaseInsensitiveContains(query)) }) { chat in
                    Toggle(chat.title, isOn: Binding(get: { selection.contains(chat.id) }, set: { excluded in
                        notice = nil
                        if excluded { selection.insert(chat.id) } else { selection.remove(chat.id) }
                    })).accessibilityIdentifier("pa-exclude-" + chat.id).disabled(!current || busy)
                }
            }.accessibilityIdentifier("pa-exclusions")
            if selection != Set(policy.excluded_conversation_ids) {
                Button(L("保存排除范围", "Save exclusions")) { Task { await savePolicy(policy) } }.disabled(!current || busy)
            }
        } header: { Text(L("聊天观察范围", "Conversation access")) }
        footer: { Text(L("选中的聊天会从助手的观察范围移除。", "Selected conversations are excluded from your assistant’s observation.")) }
    }

    private var incidentSection: some View {
        Section(L("风险事件", "Privacy incidents")) {
            if incidents.isEmpty { Text(L("暂无风险事件", "No privacy incidents")).foregroundStyle(.secondary) }
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
            if blocked.isEmpty { Text(L("暂无已限制联系人", "No blocked contacts")).foregroundStyle(.secondary) }
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
        busy = true; defer { busy = false }
        do {
            let latest: PersonalSettings = try await client.get(base)
            try Task.checkCancellation()
            guard let binding = latest.binding, binding.status == "active", binding.agent_id == agentID, let policy = latest.policy else {
                clear(); ready = true; error = L("此个人助手已无法管理。", "This personal assistant is no longer available."); return
            }
            if binding.binding_id != state?.binding?.binding_id { clear() }
            async let conversationList: ItemsPage<Conversation> = client.get("/im/v1/conversations")
            async let incidentList: ItemsPage<PersonalIncident> = client.get(base + "/incidents")
            async let blockedList: ItemsPage<PersonalBlockedContact> = client.get(base + "/blocked-contacts")
            let lists = try await (conversationList, incidentList, blockedList)
            try Task.checkCancellation()
            if let previous = state?.policy, selection != Set(previous.excluded_conversation_ids) {
                selection = policy.rebasing(selection, from: previous)
            } else { selection = Set(policy.excluded_conversation_ids) }
            if state == nil || name == state?.binding?.display_name { name = binding.display_name }
            state = latest; chats = lists.0.items; incidents = lists.1.items; blocked = lists.2.items
            current = true; ready = true; error = nil
        } catch {
            guard !Task.isCancelled else { return }
            if let api = error as? APIError, [401, 403, 404].contains(api.status) { clear() }
            current = false; self.error = agentError(error)
        }
    }

    private func clear() {
        state = nil; selection = []; chats = []; incidents = []; blocked = []; name = ""; current = false; notice = nil
    }
}
