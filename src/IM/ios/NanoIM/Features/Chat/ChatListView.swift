import SwiftUI

struct ChatListView: View {
    @Bindable var store: ChatStore
    let open: (String) -> Void
    @State private var search = ""
    @State private var personal: NativePersonalAgentState?
    @State private var setupAssistant = false
    private var personalID: String? {
        if let personal { return personal.creation == nil ? personal.binding?.conversation_id : nil }
        return store.conversations.first {
            $0.type == "direct" && $0.peerAgent?.role == "personal" && $0.participants.contains { $0.type == "user" && $0.id == store.user.id }
        }?.id
    }
    @State private var category = "all"
    @State private var newChat = false
    @State private var distill = false
    private func preview(_ chat: Conversation) -> String? {
        let content: String?
        if let card = chat.last_message_card {
            let label = L("互动卡片", "Interactive card")
            content = card.title.map { "\(label) · \($0)" } ?? label
        } else {
            content = chat.last_message_preview
        }
        guard chat.type == "group", let sender = chat.last_message_sender_name, let content, !content.isEmpty else { return content }
        return "\(sender): \(content)"
    }
    var filtered: [Conversation] {
        store.conversations.filter { (category == "all" || $0.category == category) && (search.isEmpty || $0.title.localizedCaseInsensitiveContains(search) || (preview($0) ?? "").localizedCaseInsensitiveContains(search)) }
            .sorted { a, b in a.is_pinned != b.is_pinned ? a.is_pinned : (a.last_message_at ?? a.created_at) > (b.last_message_at ?? b.created_at) }
    }
    var body: some View {
        List {
            NanoSearchField(text: $search, prompt: L("搜索聊天", "Search conversations"))
                .listRowSeparator(.hidden).listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 8, trailing: 16))
            if let reason = store.storageDegradedReason {
                VStack(alignment: .leading, spacing: 6) {
                    Text(L("本次没有本地缓存", "No local cache this time")).font(.callout.weight(.semibold))
                    Text(reason).font(.caption).foregroundStyle(.secondary)
                    Button(L("重试", "Retry")) { Task { await store.retryStorage() } }
                }.listRowSeparator(.hidden)
            }
            if store.pendingCount > 0 {
                VStack(alignment: .leading, spacing: 6) {
                    Text(L("\(store.pendingCount) 条未确认的发送", "\(store.pendingCount) unconfirmed sends")).font(.callout.weight(.semibold))
                    Text(L("连接后会核对：仍在的会话可在其中查看，已无权访问的会被清除。",
                           "Checked once connected: sends in conversations you can still access stay visible, the rest are cleared."))
                        .font(.caption).foregroundStyle(.secondary)
                }.listRowSeparator(.hidden)
            }
            if store.listPhase == .failed || (store.listPhase == .loadingFirst && store.listError != nil) {
                loadFailure
            } else if store.listPhase == .loadingFirst {
                // A5: the count above is the whole story before the first successful sync; a
                // placeholder conversation row would be a row that cannot be opened.
                if store.pendingCount > 0 {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(L("本地还没有可显示的会话", "No conversations saved locally yet")).font(.callout)
                        Text(L("正在从服务器读取上次的会话列表…", "Reading your conversation list from the server…")).font(.caption).foregroundStyle(.secondary)
                    }.listRowSeparator(.hidden)
                } else { ProgressView(L("正在加载聊天…", "Loading conversations…")) }
            }
            if let error = store.listError, store.listPhase == .loaded || store.listPhase == .empty {
                ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await store.retryListError() } }
            }
            if showPersonalRow {
                if let chat = store.conversations.first(where: { $0.id == personalID }) {
                    conversationRow(chat, pinnedPA: true)
                } else if let binding = personal?.binding, let id = personalID {
                    Button { open(id) } label: {
                        HStack {
                            AssistantPortrait(personal: true, seed: binding.agent_id, selected: binding.avatar_variant, size: 38)
                            Text(binding.display_name).font(.headline)
                            Image(systemName: "pin").font(.caption2)
                        }
                    }.buttonStyle(.plain)
                } else if personal != nil {
                    Button { setupAssistant = true } label: {
                        HStack(spacing: 10) {
                            AssistantPortrait(personal: true, seed: store.user.id, selected: nil, size: 38)
                            Text(personal?.creation == nil ? L("创建个人助手", "Create personal assistant") : L("继续设置个人助手", "Continue assistant setup")).font(.subheadline.weight(.semibold))
                            Spacer()
                            Image(systemName: "chevron.right").font(.caption)
                        }.contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityIdentifier("assistant.setup.entry")
                }
            }
            Group {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        categoryButton("all", L("全部", "All")); categoryButton("people", L("同事", "People"))
                        categoryButton("agent", L("助手", "Assistants")); categoryButton("group", L("群聊", "Groups")); categoryButton("network", L("AI 协作", "Network"))
                    }.padding(.vertical, 2)
                }
            }.listRowInsets(EdgeInsets(top: 0, leading: 12, bottom: 2, trailing: 12)).listRowSeparator(.hidden)
            ForEach(filtered.filter { !showPersonalRow || $0.id != personalID }) { chat in
                conversationRow(chat, pinnedPA: false)
            }
            if !search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                ChatMessageSearch(store: store, query: search, category: category, open: open)
            } else if filtered.isEmpty, [.empty, .loaded].contains(store.listPhase), personalID == nil || !showPersonalRow {
                VStack(spacing: 10) {
                    Text(category == "all" ? L("还没有聊天", "No conversations yet") : L("这里还没有会话", "No conversations here yet"))
                        .font(.headline)
                    Button(L("发起聊天", "Start a chat")) { newChat = true }.buttonStyle(.bordered)
                }.frame(maxWidth: .infinity).padding(.vertical, 20).listRowSeparator(.hidden)
            }
        }.nanoList().chatContinuityTitle(L("聊天", "Chats"), store: store, surface: .list)
            .task { await readPersonal() }
            .sheet(isPresented: $setupAssistant, onDismiss: { Task { await readPersonal() } }) {
                NavigationStack {
                    PersonalAssistantSetup(client: store.client, user: store.user) { id in
                        setupAssistant = false
                        open(id)
                        Task { await store.loadConversations() }
                    }
                    .toolbar { ToolbarItem(placement: .cancellationAction) {
                        Button(L("稍后", "Later")) { setupAssistant = false }
                    } }
                }
            }
            .refreshable { await store.loadConversations(); await readPersonal() }
            .toolbar { ToolbarItemGroup(placement: .topBarTrailing) {
                Menu { Button(L("整理会话知识", "Distill conversations"), systemImage: "sparkles") { distill = true } } label: { Image(systemName: "ellipsis") }.accessibilityLabel(L("更多聊天操作", "More conversation actions"))
                Button { newChat = true } label: { Image(systemName: "plus") }.accessibilityLabel(L("新建聊天", "New conversation"))
            } }
            .sheet(isPresented: $newChat) { NewChatView(client: store.client, userID: store.user.id) { chat in newChat = false; Task { await store.loadConversations() }; open(chat.id) } }
            .sheet(isPresented: $distill) { DistillView(store: store) { id, text in store.setDraft(id, text); distill = false; open(id) } }
    }
    private var showPersonalRow: Bool { search.isEmpty && (category == "all" || category == "agent") }
    private func readPersonal() async {
        do {
            let state: NativePersonalAgentState = try await store.client.get("/im/v1/personal-agent")
            try Task.checkCancellation()
            personal = state
        } catch let error as APIError where error.status == 403 { personal = nil }
        catch { }
    }
    private func conversationRow(_ chat: Conversation, pinnedPA: Bool) -> some View {
        Button { open(chat.id) } label: {
            HStack(spacing: 12) {
                AvatarView(name: chat.avatarName(selfID: store.user.id), kind: chat.type == "group" ? "group" : chat.category == "agent" ? "agent" : "person", size: 38, agentID: chat.peerAgent?.id, role: pinnedPA ? "personal" : chat.peerAgent?.role, variant: chat.peerAgent?.avatar_variant ?? (pinnedPA ? personal?.binding?.avatar_variant : nil))
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        Text(chat.title).font(.body.weight(.semibold)).foregroundStyle(NanoTheme.ink).lineLimit(1)
                        if chat.is_pinned || pinnedPA { Image(systemName: "pin.fill").font(.caption2).foregroundStyle(NanoTheme.muted) }
                        if chat.is_muted { Image(systemName: "bell.slash").font(.caption2).foregroundStyle(NanoTheme.muted) }
                        if chat.run_state == "running" { Label(L("进行中", "Running"), systemImage: "ellipsis.circle").font(.caption2).foregroundStyle(NanoTheme.accent) }
                        Spacer(minLength: 4)
                        if let time = chat.last_message_at { NanoTimestamp(value: time) }
                    }
                    HStack(spacing: 8) {
                        Text(preview(chat) ?? L("开始聊天", "Start a conversation"))
                            .font(.subheadline).foregroundStyle(NanoTheme.muted).lineLimit(1)
                        Spacer(minLength: 0)
                        if chat.unread_count > 0 { Text(chat.unread_count > 99 ? "99+" : "\(chat.unread_count)").font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 3).foregroundStyle(.white).background(NanoTheme.accent, in: Capsule()) }
                    }
                }
            }.padding(.vertical, 5).contentShape(Rectangle())
        }.buttonStyle(.plain).listRowInsets(EdgeInsets(top: 3, leading: 16, bottom: 3, trailing: 16)).contextMenu {
            if chat.can_write != false {
            Button(chat.is_pinned ? L("取消置顶", "Unpin") : L("置顶", "Pin")) { patch(chat, "is_pinned", !chat.is_pinned) }
            Button(chat.is_muted ? L("取消静音", "Unmute") : L("静音", "Mute")) { patch(chat, "is_muted", !chat.is_muted) }
            }
        }
        .swipeActions(edge: .leading, allowsFullSwipe: false) { if chat.can_write != false { Button { patch(chat, "is_pinned", !chat.is_pinned) } label: { Label(chat.is_pinned ? L("取消置顶", "Unpin") : L("置顶", "Pin"), systemImage: "pin") }.tint(NanoTheme.accent) } }
        .swipeActions(edge: .trailing, allowsFullSwipe: false) { if chat.can_write != false { Button { patch(chat, "is_muted", !chat.is_muted) } label: { Label(chat.is_muted ? L("取消静音", "Unmute") : L("静音", "Mute"), systemImage: "bell.slash") }.tint(.gray) } }
    }
    /// A3. A first load with nothing to show must not claim "no conversations" — it may be the
    /// network or the service, and the two say different things.
    private var loadFailure: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(L("无法加载聊天", "Could not load chats"), systemImage: "cloud").font(.callout.weight(.semibold))
            Text(store.readFailureBody(.list)).font(.caption).foregroundStyle(.secondary)
            Button(L("重试", "Retry")) { Task { await store.loadConversations() } }
        }.listRowSeparator(.hidden)
    }
    private func categoryButton(_ value: String, _ title: String) -> some View {
        Button { category = value } label: {
            Text(title).font(.subheadline.weight(category == value ? .semibold : .regular))
                .foregroundStyle(category == value ? NanoTheme.accent : NanoTheme.muted)
                .padding(.horizontal, 10).padding(.vertical, 6)
                .background(category == value ? NanoTheme.softAccent : Color.clear, in: Capsule())
        }.buttonStyle(.plain).accessibilityAddTraits(category == value ? .isSelected : [])
    }
    private func patch(_ chat: Conversation, _ key: String, _ value: Bool) {
        Task { await store.updateConversationPreference(chat.id, key: key, value: value) }
    }
}

struct NewChatView: View {
    let client: IMClient
    let userID: String
    let completed: (Conversation) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var contacts: [Contact] = []
    @State private var selection: Set<String> = []
    @State private var group = false
    @State private var visibility = "public"
    @State private var title = ""
    @State private var search = ""
    @State private var error: String?
    @State private var busy = false
    @State private var loaded = false
    private var filtered: [Contact] { contacts.filter { $0.user_id != userID && (search.isEmpty || ($0.display_name + " " + ($0.agent_id ?? "") + " " + $0.user_id + " " + ($0.node_name ?? "")).localizedCaseInsensitiveContains(search)) } }
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker(L("聊天类型", "Conversation type"), selection: $group) {
                        Text(L("私聊", "Direct")).tag(false)
                        Text(L("群聊", "Group")).tag(true)
                    }.pickerStyle(.segmented)
                }
                if group {
                    Section(L("群设置", "Group settings")) {
                        TextField(L("群名称（可选）", "Group name (optional)"), text: $title)
                        Picker(L("可见范围", "Visibility"), selection: $visibility) { Text(L("公开", "Public")).tag("public"); Text(L("私密", "Private")).tag("private") }.pickerStyle(.segmented)
                    }
                }
                Section {
                    NavigationLink(L("发现公开群", "Discover public groups")) { PublicGroupsView(client: client, completed: completed) }
                }
                if let error { Section {
                    ErrorNotice(message: error)
                    if !loaded { Button(L("重试", "Retry")) { Task { await loadContacts() } } }
                } }
                Section(L("联系人", "Contacts")) {
                    if !loaded && error == nil { ProgressView(L("正在加载联系人…", "Loading contacts…")) }
                    if loaded && filtered.isEmpty && error == nil { Text(search.isEmpty ? L("暂无联系人", "No contacts") : L("没有匹配的联系人", "No matching contacts")).foregroundStyle(.secondary) }
                    ForEach(filtered) { contact in
                        Button {
                            if !group { Task { await create(with: [contact]) } }
                            else if selection.contains(contact.id) { selection.remove(contact.id) }
                            else { selection.insert(contact.id) }
                        } label: {
                            HStack { AvatarView(name: contact.display_name, online: contact.status == "online", kind: contact.kind == "agent" ? "agent" : "person", agentID: contact.agent_id, role: contact.role, variant: contact.avatar_variant); VStack(alignment: .leading) {
                                Text(contact.display_name).foregroundStyle(NanoTheme.ink)
                                if contact.kind == "agent" { Text(contact.owner_display_name.map { L("\($0) 的助手", "Assistant for \($0)") } ?? L("助手", "Assistant")).font(.caption).foregroundStyle(.secondary) }
                            }; Spacer()
                                if group { Image(systemName: selection.contains(contact.id) ? "checkmark.circle.fill" : "circle").foregroundStyle(NanoTheme.accent) }
                            }.contentShape(Rectangle())
                        }.buttonStyle(.plain)
                    }
                }
            }.nanoList().disabled(busy).navigationTitle(L("新建聊天", "New conversation")).navigationBarTitleDisplayMode(.inline)
                .searchable(text: $search, prompt: L("搜索联系人", "Search contacts"))
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { dismiss() }.disabled(busy) }
                    if group {
                        ToolbarItem(placement: .confirmationAction) {
                            Button(L("创建", "Create")) { Task { await create(with: contacts.filter { selection.contains($0.id) }) } }
                                .disabled(busy || selection.isEmpty)
                        }
                    }
                }.task { await loadContacts() }
                .interactiveDismissDisabled(busy)
        }
    }
    private func loadContacts() async {
        error = nil
        do { contacts = try await client.contacts(); loaded = true }
        catch { if !Task.isCancelled { self.error = error.localizedDescription } }
    }
    private func create(with selected: [Contact]) async {
        guard !busy, !selected.isEmpty else { return }
        busy = true; error = nil; defer { busy = false }
        let groupTitle = title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? selected.map(\.display_name).joined(separator: "、") : title
        do { let chat = try await client.createConversation(title: group ? groupTitle : selected.first?.display_name ?? "", type: group ? "group" : "direct", participants: selected.map(\.actor), userID: userID, visibility: visibility); completed(chat) }
        catch { self.error = error.localizedDescription }
    }
}

struct DistillView: View {
    @Bindable var store: ChatStore
    let completed: (String, String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var selected: Set<String> = []
    @State private var execution = ""
    @State private var scope = "agent"
    @State private var error: String?
    @State private var busy = false
    private var candidates: [Conversation] { store.conversations.filter { $0.category == "agent" && $0.source_agent_id != nil && $0.source_node_id != nil && $0.run_state != "running" } }
    var body: some View {
        NavigationStack {
            Form {
                if candidates.isEmpty {
                    ContentUnavailableView(L("还没有可整理的对话", "No conversations to distill yet"), systemImage: "text.bubble",
                        description: Text(L("和助手完成一轮对话后，就可以在这里把它整理成笔记草稿。", "Finish a conversation with an assistant to turn it into a draft note here.")))
                } else {
                    Section {
                        ForEach(candidates) { item in
                            Toggle(item.title, isOn: Binding(get: { selected.contains(item.id) }, set: {
                                if $0 { selected.insert(item.id) } else { selected.remove(item.id) }
                                if !executionCandidates.contains(execution) { execution = executionCandidates.count == 1 ? executionCandidates[0] : "" }
                            }))
                            .disabled(selectedNode != nil && selectedNode != item.source_node_id)
                        }
                    } header: { Text(L("从哪些对话整理？", "Choose conversations")) } footer: { Text(L("一次可以整理同一台电脑上的多段对话。", "Choose conversations from one computer at a time.")) }
                    if !selected.isEmpty {
                        Section {
                            Picker(L("交给谁整理", "Choose an assistant"), selection: $execution) {
                                Text(L("请选择", "Select")).tag("")
                                ForEach(executionCandidates, id: \.self) { id in
                                    Text(candidates.first { $0.source_agent_id == id }?.peerAgent?.display_name ?? candidates.first { $0.source_agent_id == id }?.title ?? id).tag(id)
                                }
                            }.pickerStyle(.navigationLink)
                            Picker(L("保存范围", "Scope"), selection: $scope) { Text(L("此助手", "This assistant")).tag("agent"); Text(L("全局", "Global")).tag("global") }.pickerStyle(.navigationLink)
                        }
                        if let error { ErrorNotice(message: error) }
                        Button(L("生成待发草稿", "Generate draft")) { Task { await create() } }.disabled(busy || execution.isEmpty)
                    }
                }
            }.navigationTitle(L("整理知识", "Distill knowledge"))
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { dismiss() } } }
        }
    }
    private var selectedNode: String? { candidates.first { selected.contains($0.id) }?.source_node_id }
    private var executionCandidates: [String] {
        return Array(Set(candidates.filter { $0.source_node_id == selectedNode }.compactMap(\.source_agent_id))).sorted()
    }
    private func create() async {
        let sources = candidates.filter { selected.contains($0.id) }
        guard Set(sources.compactMap(\.source_node_id)).count == 1 else { error = L("来源必须属于同一设备。", "Sources must belong to one device."); return }
        struct Source: Encodable, Sendable { let conversation_id: String; let source_agent_id: String }
        struct Body: Encodable, Sendable { let sources: [Source]; let execution_agent_id: String; let target_scope: String }
        struct Result: Decodable, Sendable { let conversation: Conversation; let prompt: String }
        busy = true; error = nil; defer { busy = false }
        do {
            let nodes: [AgentNode] = try await store.client.get("/im/v1/nodes")
            if let node = nodes.first(where: { $0.id == sources.first?.source_node_id }), node.status == "offline" {
                error = L("来源设备离线，请在设备恢复在线后重试。", "The source device is offline. Reconnect it before trying again.")
                return
            }
            let response: Result = try await store.client.send("/im/v1/conversations/distill-prompt", body: Body(sources: sources.map { Source(conversation_id: $0.id, source_agent_id: $0.source_agent_id!) }, execution_agent_id: execution, target_scope: scope))
            await store.loadConversations()
            completed(response.conversation.id, response.prompt)
        } catch let failure as APIError where ["source session binding is unavailable", "source session file is unavailable"].contains(failure.detail) {
            error = L("来源会话暂无可整理的执行记录。请选择已有 Agent 回复的会话，或先在该会话完成一轮对话。", "No execution history is available for this source. Select a conversation with an Agent reply, or complete a turn there first.")
        } catch { self.error = error.localizedDescription }
    }
}
