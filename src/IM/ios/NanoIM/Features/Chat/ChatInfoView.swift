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
    @State private var contactsLoaded = false
    @State private var contactsError: String?
    @State private var error: String?
    @State private var personal: NativePersonalAgentState.Binding?
    @State private var busy = false
    @State private var confirmDelete = false
    @State private var confirmExitGroup = false
    @State private var remove: ActorRef?
    @State private var editingName = false
    @State private var showingMembers = false
    @State private var rosterQuery = ""
    private var dirtyTitle: Bool { chat != nil && title != chat?.title }
    private var availableContacts: [Contact] {
        contacts.filter { item in
            !(chat?.participants.contains { ($0.user_id ?? $0.id) == item.user_id || ($0.type == "agent" && $0.id == item.agent_id) } ?? false)
            && item.matchesConversationSearch(memberSearch)
        }.sorted { $0.display_name.localizedStandardCompare($1.display_name) == .orderedAscending }
    }
    private func canManageMembers(_ chat: Conversation) -> Bool {
        chat.type == "group" && chat.creator_id == store.user.id && chat.can_write != false && chat.is_observer != true
    }
    var body: some View {
        ScrollView {
            if let chat {
                VStack(alignment: .leading, spacing: 24) {
                    if chat.type == "group" || chat.is_observer == true {
                        identityHeader(chat)
                        membersPreview(chat)
                    } else {
                        Button { showingMembers = true } label: {
                            HStack(spacing: 8) {
                                identityHeader(chat)
                                Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(NanoTheme.muted)
                            }.contentShape(Rectangle())
                        }.accessibilityHint(L("查看会话成员", "View conversation participants"))
                    }
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
        .sheet(isPresented: $showingMembers, onDismiss: { rosterQuery = "" }) {
            if let chat {
                NavigationStack {
                    List {
                        if let error { ErrorNotice(message: error) }
                        let members = chat.participants.filter { actor in
                            rosterQuery.isEmpty || (actor.display_name ?? actor.id).localizedCaseInsensitiveContains(rosterQuery)
                                || actor.id.localizedCaseInsensitiveContains(rosterQuery)
                        }
                        if members.isEmpty { Text(L("没有匹配的成员", "No matching members")).foregroundStyle(.secondary) }
                        ForEach(members, id: \.self) { actor in
                            HStack(spacing: 12) {
                                portrait(actor, size: 42)
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(actor.display_name ?? actor.id).font(.body.weight(.medium))
                                    Text(memberRole(actor, chat: chat)).font(.caption).foregroundStyle(NanoTheme.muted)
                                }
                                Spacer()
                                if canManageMembers(chat), let userID = actor.user_id, userID != store.user.id {
                                    Menu {
                                        Button(L("移除", "Remove"), systemImage: "person.crop.circle.badge.minus", role: .destructive) { remove = actor }
                                    } label: {
                                        Image(systemName: "ellipsis").frame(width: 38, height: 44)
                                    }.disabled(busy).accessibilityLabel(L("管理\(actor.display_name ?? actor.id)", "Manage \(actor.display_name ?? actor.id)"))
                                }
                            }.listRowSeparator(.hidden)
                        }
                    }.listStyle(.plain)
                        .searchable(text: $rosterQuery, placement: .navigationBarDrawer(displayMode: .always), prompt: L("搜索成员", "Search members"))
                        .navigationTitle(chat.type == "group" ? L("群成员", "Members") : L("会话成员", "Participants")).navigationBarTitleDisplayMode(.inline)
                    .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("完成", "Done")) { showingMembers = false } } }
                    .confirmationDialog(L("移除此成员？", "Remove this member?"), isPresented: Binding(get: { remove != nil }, set: { if !$0 { remove = nil } }), presenting: remove) { actor in
                        Button(L("移除", "Remove"), role: .destructive) { Task { await removeMember(actor) } }
                    }
                }
            }
        }
            .task { await load() }
            .sheet(isPresented: $addingMembers, onDismiss: { selected = []; memberSearch = ""; contactsLoaded = false; contacts = []; contactsError = nil }) {
                NavigationStack {
                    List {
                        if let error { ErrorNotice(message: error) }
                        if let contactsError {
                            ErrorNotice(message: contactsError)
                            Button(L("重试", "Retry")) { Task { await loadContacts() } }
                        } else if !contactsLoaded { ProgressView() }
                        let chosen = contacts.filter { selected.contains($0.id) }
                        if !chosen.isEmpty {
                            SelectedChatContacts(contacts: chosen) { selected.remove($0.id) }
                                .padding(.vertical, 2).listRowSeparator(.hidden)
                        }
                        ForEach(availableContacts) { contact in
                            ChatContactRow(contact: contact, selected: selected.contains(contact.id)) {
                                if selected.contains(contact.id) { selected.remove(contact.id) }
                                else { selected.insert(contact.id) }
                            }
                        }
                        if contactsLoaded && availableContacts.isEmpty { Text(memberSearch.isEmpty ? L("没有可添加的成员", "No members to add") : L("没有匹配的成员", "No matching members")).foregroundStyle(.secondary) }
                    }.disabled(busy).task { await loadContacts() }.nanoList().navigationTitle(L("添加成员", "Add members"))
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

    private func identityHeader(_ chat: Conversation) -> some View {
        let isGroup = chat.type == "group"
        let peer = chat.participants.first { ($0.user_id ?? $0.id) != store.user.id }
        return HStack(alignment: .center, spacing: 16) {
            if isGroup {
                AvatarView(name: chat.title, kind: "group", size: 64)
            } else if chat.is_observer == true {
                HStack(spacing: -15) {
                    ForEach(chat.participants.prefix(2), id: \.self) { actor in
                        portrait(actor, size: 46)
                    }
                }
            } else if let peer { portrait(peer, size: 64) }
            VStack(alignment: .leading, spacing: 6) {
                Text(chat.title).font(.system(.title2, design: .rounded, weight: .bold)).foregroundStyle(NanoTheme.ink)
                if isGroup {
                    HStack(spacing: 6) {
                        Label(chat.visibility == "public" ? L("公开群", "Public group") : L("私密群", "Private group"),
                              systemImage: chat.visibility == "public" ? "globe" : "lock")
                        if chat.creator_id == store.user.id { Text("·"); Text(L("我是群主", "You own this group")) }
                    }.font(.subheadline).foregroundStyle(NanoTheme.muted)
                } else if chat.is_observer != true, let peer {
                    let name = peer.display_name.flatMap { $0 == chat.title ? nil : $0 }
                    Text([name, memberRole(peer, chat: chat)].compactMap { $0 }.joined(separator: " · "))
                        .font(.subheadline).foregroundStyle(NanoTheme.muted)
                }
                if chat.dissolved_at != nil { Text(L("群聊已解散，可查看历史消息", "Group dissolved. Message history is available.")).font(.callout) }
                else if chat.is_observer == true { Text(L("助手协作会话，只读", "Assistant collaboration, read only")).font(.callout).foregroundStyle(NanoTheme.muted) }
            }
            Spacer(minLength: 0)
        }.padding(.vertical, 4)
    }

    private func memberRole(_ actor: ActorRef, chat: Conversation) -> String {
        let id = actor.user_id ?? actor.id
        if chat.type == "group", id == chat.creator_id { return id == store.user.id ? L("我 · 群主", "You · Group owner") : L("群主", "Group owner") }
        if id == store.user.id { return L("我", "You") }
        if actor.type == "agent" {
            if personal?.agent_id == actor.id { return L("我的个人助手", "My personal assistant") }
            return actor.role == "personal" ? L("个人助手", "Personal assistant") : L("助手", "Assistant")
        }
        return L("同事", "Person")
    }

    private func membersPreview(_ chat: Conversation) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Button { showingMembers = true } label: {
                HStack {
                    Text(L("成员", "Members")).font(.headline)
                    Spacer()
                    Text(L("\(chat.participants.count) 位成员", "\(chat.participants.count) members"))
                        .foregroundStyle(NanoTheme.muted).font(.subheadline)
                    Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(NanoTheme.muted)
                }.contentShape(Rectangle()).frame(minHeight: 36)
            }.accessibilityLabel(L("查看全部成员", "View all members"))
                .accessibilityValue(L("\(chat.participants.count) 位成员", "\(chat.participants.count) members"))
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(alignment: .top, spacing: 9) {
                    if canManageMembers(chat) {
                        Button { addingMembers = true } label: {
                            VStack(spacing: 6) {
                                Image(systemName: "plus").font(.title3.weight(.medium)).frame(width: 44, height: 44)
                                    .background(NanoTheme.softAccent, in: Circle())
                                Text(L("邀请", "Invite")).font(.caption)
                            }.frame(width: 54).foregroundStyle(NanoTheme.accent)
                        }.disabled(busy).accessibilityLabel(L("添加成员", "Add members"))
                    }
                    ForEach(chat.participants.prefix(7), id: \.self) { actor in
                        VStack(spacing: 6) {
                            portrait(actor, size: 44)
                            Text(actor.display_name ?? actor.id).font(.caption).lineLimit(1)
                        }.frame(width: 54).accessibilityElement(children: .combine)
                    }
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
    private func loadContacts() async {
        contactsError = nil
        do { contacts = try await store.client.contacts(); contactsLoaded = true }
        catch { if !Task.isCancelled { contactsError = error.localizedDescription } }
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
