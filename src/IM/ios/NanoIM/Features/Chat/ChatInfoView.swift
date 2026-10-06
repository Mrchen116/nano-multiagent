import SwiftUI

struct ChatInfoView: View {
    @Bindable var store: ChatStore
    let conversationID: String
    let openChat: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var chat: Conversation?
    @State private var title = ""
    @State private var contacts: [Contact] = []
    @State private var selected: Set<String> = []
    @State private var addingMembers = false
    @State private var memberSearch = ""
    @State private var error: String?
    @State private var busy = false
    @State private var confirmDelete = false
    @State private var remove: ActorRef?
    @State private var confirmLeave = false
    private var dirtyTitle: Bool { chat != nil && title != chat?.title }
    private var availableContacts: [Contact] {
        contacts.filter { item in
            !(chat?.participants.contains { ($0.user_id ?? $0.id) == item.user_id || ($0.type == "agent" && $0.id == item.agent_id) } ?? false)
            && (memberSearch.isEmpty || (item.display_name + " " + (item.agent_id ?? "") + " " + (item.node_name ?? "")).localizedCaseInsensitiveContains(memberSearch))
        }.sorted { $0.display_name.localizedStandardCompare($1.display_name) == .orderedAscending }
    }
    var body: some View {
        Form {
            if let chat {
                Section(L("聊天设置", "Conversation settings")) {
                    TextField(L("名称", "Name"), text: $title)
                    Button(L("保存名称", "Save name")) { mutate(["title": .string(title)]) }.disabled(title.isEmpty || title == chat.title || busy)
                    Toggle(L("置顶", "Pinned"), isOn: Binding(get: { chat.is_pinned }, set: { mutate(["is_pinned": .bool($0)]) })).disabled(busy)
                    Toggle(L("静音", "Muted"), isOn: Binding(get: { chat.is_muted }, set: { mutate(["is_muted": .bool($0)]) })).disabled(busy)
                }
                Section(L("成员", "Members")) {
                    ForEach(chat.participants, id: \.id) { actor in
                        HStack(spacing: 12) { AvatarView(name: actor.display_name ?? actor.id, kind: actor.type == "agent" ? "agent" : "person", size: 36); Text(actor.display_name ?? actor.id); Spacer(); Text(actor.type == "agent" ? "Agent" : L("真人", "Person")).font(.caption).foregroundStyle(.secondary)
                            if chat.type == "group", chat.creator_id == store.user.id, actor.user_id != store.user.id {
                                Button(role: .destructive) { remove = actor } label: { Image(systemName: "minus.circle") }.accessibilityLabel(L("移除", "Remove"))
                            }
                        }
                    }
                    if chat.type == "group", chat.creator_id == store.user.id {
                        Button { addingMembers = true } label: { Label(L("添加成员", "Add members"), systemImage: "person.badge.plus") }.disabled(busy)
                    }
                }
                if chat.type == "group" {
                    NavigationLink(L("群任务", "Group tasks")) { GroupTasksView(client: store.client, conversationID: conversationID) { id, text in
                        store.drafts[id] = [store.drafts[id] ?? "", text].filter { !$0.isEmpty }.joined(separator: "\n\n")
                        openChat(id)
                    } }
                    if chat.creator_id == store.user.id { Section { Button(L("解散群聊", "Dissolve group"), role: .destructive) { confirmDelete = true } } }
                }
            } else { ProgressView() }
            if let error { ErrorNotice(message: error) }
        }.navigationTitle(L("聊天详情", "Conversation details")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
            .navigationBarBackButtonHidden(dirtyTitle)
            .toolbar { if dirtyTitle { ToolbarItem(placement: .navigation) { Button(L("返回", "Back")) { confirmLeave = true } } } }
            .confirmationDialog(L("放弃未保存的名称？", "Discard the unsaved name?"), isPresented: $confirmLeave, titleVisibility: .visible) { Button(L("放弃并返回", "Discard and go back"), role: .destructive) { dismiss() } }
            .task { await load(); contacts = (try? await store.client.contacts()) ?? [] }
            .sheet(isPresented: $addingMembers, onDismiss: { selected = []; memberSearch = "" }) {
                NavigationStack {
                    List {
                        if let error { ErrorNotice(message: error) }
                        ForEach(availableContacts) { contact in
                            Button { if selected.contains(contact.id) { selected.remove(contact.id) } else { selected.insert(contact.id) } } label: {
                                HStack(spacing: 12) {
                                    AvatarView(name: contact.display_name, online: contact.status == "online", kind: contact.kind == "agent" ? "agent" : "person")
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
            .confirmationDialog(L("解散此群聊？", "Dissolve this group?"), isPresented: $confirmDelete, titleVisibility: .visible) {
                Button(L("解散群聊", "Dissolve group"), role: .destructive) { Task { await deleteGroup() } }
            } message: { Text(L("所有成员都会失去此群聊入口。", "This removes the group for all members.")) }
            .confirmationDialog(L("移除此成员？", "Remove this member?"), isPresented: Binding(get: { remove != nil }, set: { if !$0 { remove = nil } }), titleVisibility: .visible) {
                Button(L("移除", "Remove"), role: .destructive) { if let actor = remove { Task { await removeMember(actor) } } }
            }
    }
    private func load() async {
        do { let value: Conversation = try await store.client.get("/im/v1/conversations/\(conversationID.pathComponent)"); chat = value; title = value.title; error = nil }
        catch { self.error = error.localizedDescription }
    }
    private func mutate(_ patch: [String: JSONValue]) {
        Task { busy = true; defer { busy = false }
            do { let value: Conversation = try await store.client.send("/im/v1/conversations/\(conversationID.pathComponent)", method: "PATCH", body: patch); chat = value; if patch["title"] != nil { title = value.title }; error = nil; await store.loadConversations() }
            catch { self.error = error.localizedDescription }
        }
    }
    private func addMember() async {
        let members = contacts.filter { selected.contains($0.id) }
        guard !members.isEmpty else { return }
        struct Body: Encodable, Sendable { let participants: [ActorRef] }
        busy = true; defer { busy = false }
        do { let _: Conversation = try await store.client.send("/im/v1/conversations/\(conversationID.pathComponent)/participants", body: Body(participants: members.map(\.actor))); selected = []; addingMembers = false; let unsavedTitle = dirtyTitle ? title : nil; await load(); if let unsavedTitle { title = unsavedTitle } }
        catch { self.error = error.localizedDescription }
    }
    private func removeMember(_ actor: ActorRef) async {
        guard let userID = actor.user_id else { return }
        busy = true; defer { busy = false }
        do { let _: EmptyResponse = try await store.client.delete("/im/v1/conversations/\(conversationID.pathComponent)/participants/\(userID.pathComponent)"); remove = nil; await load() }
        catch { self.error = error.localizedDescription }
    }
    private func deleteGroup() async {
        do { let _: EmptyResponse = try await store.client.delete("/im/v1/conversations/\(conversationID.pathComponent)"); await store.loadConversations(); dismiss() }
        catch { self.error = error.localizedDescription }
    }
}
