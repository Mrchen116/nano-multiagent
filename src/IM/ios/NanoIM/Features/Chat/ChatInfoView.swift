import SwiftUI

struct ChatInfoView: View {
    @Bindable var store: ChatStore
    let conversationID: String
    let openChat: (String) -> Void
    let openInbox: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var chat: Conversation?
    @State private var title = ""
    @State private var contacts: [Contact] = []
    @State private var selected: Set<String> = []
    @State private var addingMembers = false
    @State private var memberSearch = ""
    @State private var error: String?
    @State private var personal: NativePersonalAgentState.Binding?
    @State private var busy = false
    @State private var confirmDelete = false
    @State private var confirmExitGroup = false
    @State private var remove: ActorRef?
    @State private var editingName = false
    @State private var showingMembers = false
    private var dirtyTitle: Bool { chat != nil && title != chat?.title }
    private var availableContacts: [Contact] {
        contacts.filter { item in
            !(chat?.participants.contains { ($0.user_id ?? $0.id) == item.user_id || ($0.type == "agent" && $0.id == item.agent_id) } ?? false)
            && (memberSearch.isEmpty || (item.display_name + " " + (item.agent_id ?? "") + " " + (item.node_name ?? "")).localizedCaseInsensitiveContains(memberSearch))
        }.sorted { $0.display_name.localizedStandardCompare($1.display_name) == .orderedAscending }
    }
    private func canManageMembers(_ chat: Conversation) -> Bool {
        chat.type == "group" && chat.creator_id == store.user.id && chat.can_write != false && chat.is_observer != true
    }
    var body: some View {
        ScrollView {
            if let chat {
                VStack(alignment: .leading, spacing: 24) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(chat.title).font(.largeTitle.bold()).foregroundStyle(NanoTheme.ink)
                        HStack(spacing: 5) {
                            if chat.type == "group" {
                                Image(systemName: chat.visibility == "public" ? "globe" : "lock")
                                Text(chat.visibility == "public" ? L("公开群", "Public group") : L("私密群", "Private group"))
                                Text("·")
                            }
                            Text(L("\(chat.participants.count) 位成员", "\(chat.participants.count) members"))
                        }.font(.subheadline).foregroundStyle(.secondary)
                        if chat.dissolved_at != nil { Text(L("群聊已解散，可查看历史消息", "Group dissolved. Message history is available.")).font(.callout) }
                        else if chat.is_observer == true { Text(L("助手协作会话，只读", "Assistant collaboration, read only")).font(.callout) }
                    }
                    membersPreview(chat)
                    if let personal, personal.conversation_id == chat.id {
                        NavigationLink { PersonalAgentManagementView(client: store.client, agentID: personal.agent_id) } label: {
                            CrewdenDestination(title: L("个人助手设置", "Personal assistant settings"), symbol: "slider.horizontal.3")
                        }
                    }
                    if chat.type == "group" {
                        NavigationLink { GroupTasksView(client: store.client, conversationID: conversationID) { id, text in
                            store.setDraft(id, [store.drafts[id] ?? "", text].filter { !$0.isEmpty }.joined(separator: "\n\n"))
                            openChat(id)
                        } } label: {
                            CrewdenDestination(title: L("群任务", "Group tasks"), symbol: "checklist")
                                .padding(.horizontal, 16)
                                .background(Color("GroupAvatar").opacity(0.68), in: RoundedRectangle(cornerRadius: 14))
                        }
                    }
                    if chat.is_observer != true {
                        VStack(spacing: 0) {
                            Toggle(isOn: Binding(get: { chat.is_pinned }, set: { mutate(["is_pinned": .bool($0)]) })) {
                                Label(L("置顶聊天", "Pin chat"), systemImage: "pin")
                            }.padding(.vertical, 11)
                            Divider()
                            Toggle(isOn: Binding(get: { chat.is_muted }, set: { mutate(["is_muted": .bool($0)]) })) {
                                Label(L("消息免打扰", "Mute notifications"), systemImage: "bell.slash")
                            }.padding(.vertical, 11)
                        }.disabled(chat.can_write == false || busy).tint(NanoTheme.accent)
                    }
                    if let error { ErrorNotice(message: error) }
                }.padding(.horizontal, 22).padding(.vertical, 16)
            } else if let error {
                ErrorNotice(message: error)
                Button(L("重试", "Retry")) { Task { await load() } }
            } else { ProgressView() }
        }.background(NanoTheme.surface).foregroundStyle(NanoTheme.ink).buttonStyle(.plain)
        .navigationTitle(L("聊天详情", "Conversation details")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .toolbar {
            if let chat, chat.is_observer != true, chat.can_write != false {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button(L("修改名称", "Rename"), systemImage: "pencil") { title = chat.title; editingName = true }
                        if chat.can_change_visibility == true && chat.type == "group" {
                            Picker(L("可见范围", "Visibility"), selection: Binding(get: { chat.visibility ?? "private" }, set: { mutate(["visibility": .string($0)]) })) {
                                Text(L("公开群", "Public group")).tag("public")
                                Text(L("私密群", "Private group")).tag("private")
                            }
                        }
                        if canManageMembers(chat) {
                            Button(L("管理成员", "Manage members"), systemImage: "person.2") { showingMembers = true }
                            Button(L("解散群聊", "Dissolve group"), role: .destructive) { confirmDelete = true }
                        } else if chat.type == "group" && chat.is_member == true && chat.creator_id != store.user.id {
                            Button(L("退出群聊", "Leave group"), role: .destructive) { confirmExitGroup = true }
                        }
                    } label: { Image(systemName: "ellipsis") }.disabled(busy).accessibilityLabel(L("更多聊天选项", "More chat options"))
                }
            }
        }
        .sheet(isPresented: $editingName, onDismiss: { title = chat?.title ?? "" }) {
            NavigationStack {
                Form {
                    TextField(L("名称", "Name"), text: $title)
                    if let error { ErrorNotice(message: error) }
                }.navigationTitle(L("修改名称", "Rename")).navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { editingName = false }.disabled(busy) }
                    ToolbarItem(placement: .confirmationAction) {
                        Button(L("保存", "Save")) { mutate(["title": .string(title)]) }
                            .disabled(busy || !dirtyTitle || title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
            }.presentationDetents([.medium, .large]).interactiveDismissDisabled(dirtyTitle || busy)
        }
        .sheet(isPresented: $showingMembers) {
            if let chat {
                NavigationStack {
                    List {
                        if let error { ErrorNotice(message: error) }
                        ForEach(chat.participants, id: \.id) { actor in
                            HStack(spacing: 12) {
                                portrait(actor, size: 40)
                                Text(actor.display_name ?? actor.id)
                                Spacer()
                                if canManageMembers(chat), let userID = actor.user_id, userID != store.user.id {
                                    Button(L("移除", "Remove"), role: .destructive) { remove = actor }.disabled(busy)
                                }
                            }
                        }
                    }.navigationTitle(L("群成员", "Members")).navigationBarTitleDisplayMode(.inline)
                    .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("完成", "Done")) { showingMembers = false } } }
                    .confirmationDialog(L("移除此成员？", "Remove this member?"), isPresented: Binding(get: { remove != nil }, set: { if !$0 { remove = nil } }), presenting: remove) { actor in
                        Button(L("移除", "Remove"), role: .destructive) { Task { await removeMember(actor) } }
                    }
                }
            }
        }
            .task { await load(); contacts = (try? await store.client.contacts()) ?? [] }
            .sheet(isPresented: $addingMembers, onDismiss: { selected = []; memberSearch = "" }) {
                NavigationStack {
                    List {
                        if let error { ErrorNotice(message: error) }
                        ForEach(availableContacts) { contact in
                            Button { if selected.contains(contact.id) { selected.remove(contact.id) } else { selected.insert(contact.id) } } label: {
                                HStack(spacing: 12) {
                                    AvatarView(name: contact.display_name, online: contact.status == "online", kind: contact.kind == "agent" ? "agent" : "person", agentID: contact.agent_id, role: contact.role, variant: contact.avatar_variant)
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(contact.display_name).foregroundStyle(NanoTheme.ink)
                                        Text([contact.kind == "agent" ? "Agent" : L("真人", "Person"), contact.agent_id, contact.owner_display_name, contact.node_name].compactMap { $0 }.joined(separator: " · ")).font(.caption).foregroundStyle(NanoTheme.muted)
                                    }
                                    Spacer(); Image(systemName: selected.contains(contact.id) ? "checkmark.circle.fill" : "circle")
                                }.contentShape(Rectangle())
                            }.buttonStyle(.plain)
                        }
                        if availableContacts.isEmpty { Text(memberSearch.isEmpty ? L("没有可添加的成员", "No members to add") : L("没有匹配的成员", "No matching members")).foregroundStyle(.secondary) }
                    }.nanoList().navigationTitle(L("添加成员", "Add members"))
                        .searchable(text: $memberSearch, prompt: L("搜索名称、ID 或设备", "Search name, ID, or device"))
                        .toolbar {
                            ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { addingMembers = false }.disabled(busy) }
                            ToolbarItem(placement: .confirmationAction) { Button(L("添加", "Add") + (selected.isEmpty ? "" : " (\(selected.count))")) { Task { await addMember() } }.disabled(selected.isEmpty || busy) }
                        }.interactiveDismissDisabled(busy)
                }
            }
            .confirmationDialog(L("退出此群聊？", "Leave this group?"), isPresented: $confirmExitGroup, titleVisibility: .visible) {
                Button(L("退出群聊", "Leave group"), role: .destructive) { Task { await leaveGroup() } }
            }
            .confirmationDialog(L("解散此群聊？", "Dissolve this group?"), isPresented: $confirmDelete, titleVisibility: .visible) {
                Button(L("解散群聊", "Dissolve group"), role: .destructive) { Task { await deleteGroup() } }
            } message: { Text(L("未完成任务会关闭，已完成结果与聊天历史保留，只读查看。", "Unfinished tasks close. Completed results and conversation history remain read-only.")) }
    }
    private func portrait(_ actor: ActorRef, size: CGFloat) -> some View {
        AvatarView(name: actor.display_name ?? actor.id, kind: actor.type == "agent" ? "agent" : "person",
                   size: size, agentID: actor.id, role: actor.role, variant: actor.avatar_variant)
    }

    private func membersPreview(_ chat: Conversation) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if chat.participants.count > 7 {
                Button { showingMembers = true } label: {
                    HStack { Text(L("查看全部成员", "View all members")); Image(systemName: "chevron.right") }
                        .font(.subheadline.weight(.medium))
                }
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 60), spacing: 8)], alignment: .leading, spacing: 14) {
                ForEach(chat.participants.prefix(7), id: \.id) { actor in
                    VStack(spacing: 7) {
                        portrait(actor, size: 46)
                        Text(actor.display_name ?? actor.id).font(.caption).lineLimit(1)
                    }.accessibilityElement(children: .combine)
                }
                if canManageMembers(chat) {
                    Button { addingMembers = true } label: {
                        VStack(spacing: 7) {
                            Image(systemName: "plus").font(.title3.weight(.medium))
                                .frame(width: 46, height: 46)
                                .overlay { Circle().strokeBorder(NanoTheme.border, style: StrokeStyle(lineWidth: 1.5, dash: [4, 3])) }
                            Text(L("邀请", "Invite")).font(.caption)
                        }.foregroundStyle(NanoTheme.accent)
                    }.disabled(busy).accessibilityLabel(L("添加成员", "Add members"))
                }
            }
        }
    }

    private func load() async {
        let unsavedTitle = dirtyTitle ? title : nil
        do { let value: Conversation = try await store.client.get("/im/v1/conversations/\(conversationID.pathComponent)"); chat = value; title = unsavedTitle ?? value.title; error = nil
            if value.peerAgent?.role == "personal" {
                let state: NativePersonalAgentState = try await store.client.get("/im/v1/personal-agent")
                personal = state.binding?.conversation_id == value.id ? state.binding : nil
            } else { personal = nil }
        }
        catch { self.error = error.localizedDescription }
    }
    private func mutate(_ patch: [String: JSONValue]) {
        Task { busy = true; defer { busy = false }
            do {
                if let name = patch["title"]?.stringValue, chat?.peerAgent?.role == "personal" {
                    let state: NativePersonalAgentState = try await store.client.get("/im/v1/personal-agent")
                    if state.binding?.conversation_id == conversationID {
                        let _: NativePersonalAgentState = try await store.client.send("/im/v1/personal-agent", method: "PATCH", body: ["display_name": name])
                        editingName = false
                        title = chat?.title ?? ""
                        await load()
                        await store.loadConversations()
                        return
                    }
                }
                let value: Conversation = try await store.client.send("/im/v1/conversations/\(conversationID.pathComponent)", method: "PATCH", body: patch)
                chat = value; if patch["title"] != nil { title = value.title; editingName = false }; error = nil; await store.loadConversations()
            }
            catch { self.error = error.localizedDescription }
        }
    }
    private func addMember() async {
        let members = contacts.filter { selected.contains($0.id) }
        guard !members.isEmpty else { return }
        struct Body: Encodable, Sendable { let participants: [ActorRef] }
        busy = true; defer { busy = false }
        do { let _: Conversation = try await store.client.send("/im/v1/conversations/\(conversationID.pathComponent)/participants", body: Body(participants: members.map(\.actor))); selected = []; addingMembers = false; await load() }
        catch { self.error = error.localizedDescription }
    }
    private func removeMember(_ actor: ActorRef) async {
        guard let userID = actor.user_id else { return }
        busy = true; defer { busy = false }
        do { let _: EmptyResponse = try await store.client.delete("/im/v1/conversations/\(conversationID.pathComponent)/participants/\(userID.pathComponent)"); remove = nil; await load() }
        catch { self.error = error.localizedDescription }
    }
    private func leaveGroup() async {
        busy = true; defer { busy = false }
        do {
            let _: EmptyResponse = try await store.client.delete("/im/v1/conversations/\(conversationID.pathComponent)/participants/\(store.user.id.pathComponent)")
            await store.loadConversations()
            openInbox()
        } catch { self.error = error.localizedDescription }
    }
    private func deleteGroup() async {
        do { let _: EmptyResponse = try await store.client.delete("/im/v1/conversations/\(conversationID.pathComponent)"); await store.loadConversations(); dismiss() }
        catch { self.error = error.localizedDescription }
    }
}
