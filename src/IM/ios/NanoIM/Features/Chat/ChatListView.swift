import SwiftUI

struct ChatListView: View {
    @Bindable var store: ChatStore
    let open: (String) -> Void
    @State private var search = ""
    @State private var category = "all"
    @State private var newChat = false
    @State private var distill = false
    var filtered: [Conversation] {
        store.conversations.filter { (category == "all" || $0.category == category) && (search.isEmpty || $0.title.localizedCaseInsensitiveContains(search) || ($0.last_message_preview ?? "").localizedCaseInsensitiveContains(search)) }
            .sorted { a, b in a.is_pinned != b.is_pinned ? a.is_pinned : (a.last_message_at ?? a.created_at) > (b.last_message_at ?? b.created_at) }
    }
    var body: some View {
        List {
            NanoSearchField(text: $search, prompt: L("搜索聊天", "Search conversations"))
                .listRowSeparator(.hidden).listRowInsets(EdgeInsets(top: 6, leading: 20, bottom: 8, trailing: 20))
            if !store.connectionText.isEmpty { Text(store.connectionText).font(.caption).foregroundStyle(.secondary) }
            if let error = store.listError { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await store.loadConversations() } } }
            Group {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        categoryButton("all", L("全部", "All")); categoryButton("people", L("真人", "People"))
                        categoryButton("agent", "Agent"); categoryButton("group", L("群聊", "Groups")); categoryButton("network", L("协作网", "Network"))
                    }.padding(.vertical, 2)
                }
            }.listRowInsets(EdgeInsets(top: 0, leading: 20, bottom: 10, trailing: 20)).listRowSeparator(.hidden)
            ForEach(filtered) { chat in
                Button { open(chat.id) } label: {
                    HStack(spacing: 12) {
                        AvatarView(name: chat.title, kind: chat.type == "group" ? "group" : chat.category == "agent" ? "agent" : "person")
                        VStack(alignment: .leading, spacing: 6) {
                            HStack(spacing: 6) {
                                Text(chat.title).font(.body.weight(.semibold)).foregroundStyle(NanoTheme.ink).lineLimit(1)
                                if chat.is_pinned { Image(systemName: "pin.fill").font(.caption2).foregroundStyle(NanoTheme.muted) }
                                if chat.is_muted { Image(systemName: "bell.slash").font(.caption2).foregroundStyle(NanoTheme.muted) }
                                Spacer(minLength: 4)
                                NanoTimestamp(value: chat.last_message_at ?? chat.created_at)
                            }
                            HStack(spacing: 8) {
                                Text(chat.last_message_preview ?? L("开始聊天", "Start a conversation"))
                                    .font(.subheadline).foregroundStyle(NanoTheme.muted).lineLimit(1)
                                Spacer(minLength: 0)
                                if chat.unread_count > 0 { Text(chat.unread_count > 99 ? "99+" : "\(chat.unread_count)").font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 3).foregroundStyle(.white).background(NanoTheme.accent, in: Capsule()) }
                            }
                        }
                    }.padding(.vertical, 8)
                }.buttonStyle(.plain).listRowInsets(EdgeInsets(top: 3, leading: 20, bottom: 3, trailing: 20)).contextMenu {
                    Button(chat.is_pinned ? L("取消置顶", "Unpin") : L("置顶", "Pin")) { patch(chat, "is_pinned", !chat.is_pinned) }
                    Button(chat.is_muted ? L("取消静音", "Unmute") : L("静音", "Mute")) { patch(chat, "is_muted", !chat.is_muted) }
                }
            }
            if filtered.isEmpty, store.listError == nil { ContentUnavailableView(L("暂无聊天", "No conversations"), systemImage: "bubble.left.and.bubble.right", description: Text(L("使用右上角 + 创建聊天。", "Use + to start a conversation."))) }
        }.nanoList().nanoRootTitle(L("聊天", "Chats"))
            .refreshable { await store.loadConversations() }
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Menu {
                Button(L("新建聊天", "New conversation"), systemImage: "plus") { newChat = true }
                Button(L("整理会话知识", "Distill conversations"), systemImage: "sparkles") { distill = true }
            } label: { Image(systemName: "plus") }.accessibilityLabel(L("新建与整理", "Create or distill")) } }
            .sheet(isPresented: $newChat) { NewChatView(client: store.client, userID: store.user.id) { chat in newChat = false; Task { await store.loadConversations() }; open(chat.id) } }
            .sheet(isPresented: $distill) { DistillView(store: store) { id, text in store.drafts[id] = text; distill = false; open(id) } }
    }
    private func categoryButton(_ value: String, _ title: String) -> some View {
        Button { category = value } label: {
            Text(title).font(.subheadline.weight(category == value ? .semibold : .regular))
                .foregroundStyle(category == value ? NanoTheme.accent : NanoTheme.muted)
                .padding(.horizontal, 13).padding(.vertical, 9)
                .background(category == value ? NanoTheme.softAccent : Color.clear, in: Capsule())
        }.buttonStyle(.plain).accessibilityAddTraits(category == value ? .isSelected : [])
    }
    private func patch(_ chat: Conversation, _ key: String, _ value: Bool) {
        Task { do { let _: Conversation = try await store.client.send("/im/v1/conversations/\(chat.id.pathComponent)", method: "PATCH", body: [key: value]); await store.loadConversations() } catch { store.listError = error.localizedDescription } }
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
    @State private var title = ""
    @State private var search = ""
    @State private var error: String?
    @State private var busy = false
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Toggle(L("创建群聊", "Create group"), isOn: $group).onChange(of: group) { _, value in if !value { selection = Set(selection.prefix(1)) } }
                    if group { TextField(L("群名称", "Group name"), text: $title) }
                }
                if let error { Section { ErrorNotice(message: error) } }
                Section(L("联系人", "Contacts")) {
                    ForEach(contacts.filter { $0.user_id != userID && (search.isEmpty || $0.display_name.localizedCaseInsensitiveContains(search)) }) { contact in
                        Button { if selection.contains(contact.id) { selection.remove(contact.id) } else if group { selection.insert(contact.id) } else { selection = [contact.id] } } label: {
                            HStack { AvatarView(name: contact.display_name, online: contact.status == "online"); VStack(alignment: .leading) {
                                Text(contact.display_name).foregroundStyle(.primary)
                                Text([contact.kind == "agent" ? "Agent" : L("真人", "Person"), contact.owner_display_name, contact.node_name].compactMap { $0 }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                            }; Spacer(); Image(systemName: selection.contains(contact.id) ? "checkmark.circle.fill" : "circle") }
                        }
                    }
                }
            }.navigationTitle(L("新建聊天", "New conversation"))
                .searchable(text: $search, prompt: L("搜索联系人", "Search contacts"))
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) { Button(L("创建", "Create")) { Task { await create() } }.disabled(busy || selection.isEmpty || (group && title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)) }
                }.task { do { contacts = try await client.contacts() } catch { self.error = error.localizedDescription } }
        }
    }
    private func create() async {
        busy = true; error = nil; defer { busy = false }
        let selected = contacts.filter { selection.contains($0.id) }
        do { let chat = try await client.createConversation(title: group ? title : selected.first?.display_name ?? "", type: group ? "group" : "direct", participants: selected.map(\.actor), userID: userID); completed(chat) }
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
                Section { Text(L("选择同一设备上的已空闲会话。生成的内容会进入草稿，确认后再发送。", "Select idle conversations on one device. The generated prompt remains a draft for review.")) }
                Section(L("来源会话", "Source conversations")) { ForEach(candidates) { item in
                    Toggle(item.title, isOn: Binding(get: { selected.contains(item.id) }, set: { if $0 { selected.insert(item.id) } else { selected.remove(item.id) } }))
                } }
                Section {
                    Picker(L("执行 Agent", "Execution agent"), selection: $execution) {
                        Text(L("请选择", "Select")).tag("")
                        ForEach(executionCandidates, id: \.self) { agent in Text(agent).tag(agent) }
                    }
                    Picker(L("目标范围", "Target scope"), selection: $scope) { Text("Agent").tag("agent"); Text(L("全局", "Global")).tag("global") }
                }
                if let error { ErrorNotice(message: error) }
                Button(L("生成待发草稿", "Generate draft")) { Task { await create() } }.disabled(busy || selected.isEmpty || execution.isEmpty)
            }.navigationTitle(L("整理知识", "Distill knowledge"))
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { dismiss() } } }
        }
    }
    private var executionCandidates: [String] {
        let node = candidates.first { selected.contains($0.id) }?.source_node_id
        return Array(Set(candidates.filter { $0.source_node_id == node }.compactMap(\.source_agent_id))).sorted()
    }
    private func create() async {
        let sources = candidates.filter { selected.contains($0.id) }
        guard Set(sources.compactMap(\.source_node_id)).count == 1 else { error = L("来源必须属于同一设备。", "Sources must belong to one device."); return }
        struct Source: Encodable, Sendable { let conversation_id: String; let source_agent_id: String }
        struct Body: Encodable, Sendable { let sources: [Source]; let execution_agent_id: String; let target_scope: String }
        struct Result: Decodable, Sendable { let conversation: Conversation; let prompt: String }
        busy = true; defer { busy = false }
        do {
            let response: Result = try await store.client.send("/im/v1/conversations/distill-prompt", body: Body(sources: sources.map { Source(conversation_id: $0.id, source_agent_id: $0.source_agent_id!) }, execution_agent_id: execution, target_scope: scope))
            completed(response.conversation.id, response.prompt)
        } catch { self.error = error.localizedDescription }
    }
}
