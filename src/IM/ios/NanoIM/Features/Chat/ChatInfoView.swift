import SwiftUI

struct ChatInfoView: View {
    @Bindable var store: ChatStore
    let conversationID: String
    let openChat: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var chat: Conversation?
    @State private var title = ""
    @State private var contacts: [Contact] = []
    @State private var selected = ""
    @State private var error: String?
    @State private var busy = false
    @State private var confirmDelete = false
    @State private var remove: ActorRef?
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
                        HStack { Text(actor.display_name ?? actor.id); Spacer(); Text(actor.type).font(.caption).foregroundStyle(.secondary)
                            if chat.type == "group", chat.creator_id == store.user.id, actor.user_id != store.user.id {
                                Button(role: .destructive) { remove = actor } label: { Image(systemName: "minus.circle") }.accessibilityLabel(L("移除", "Remove"))
                            }
                        }
                    }
                    if chat.type == "group", chat.creator_id == store.user.id {
                        Picker(L("添加成员", "Add member"), selection: $selected) {
                            Text(L("请选择", "Select")).tag("")
                            ForEach(contacts.filter { item in !chat.participants.contains { $0.user_id == item.user_id || ($0.id == item.agent_id && $0.type == "agent") } }) { item in Text(item.display_name).tag(item.id) }
                        }
                        Button(L("添加", "Add")) { Task { await addMember() } }.disabled(selected.isEmpty || busy)
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
        }.navigationTitle(L("聊天详情", "Conversation details")).toolbar(.hidden, for: .tabBar)
            .task { await load(); contacts = (try? await store.client.contacts()) ?? [] }
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
            do { let value: Conversation = try await store.client.send("/im/v1/conversations/\(conversationID.pathComponent)", method: "PATCH", body: patch); chat = value; title = value.title; error = nil; await store.loadConversations() }
            catch { self.error = error.localizedDescription }
        }
    }
    private func addMember() async {
        guard let contact = contacts.first(where: { $0.id == selected }) else { return }
        struct Body: Encodable, Sendable { let participants: [ActorRef] }
        busy = true; defer { busy = false }
        do { let _: Conversation = try await store.client.send("/im/v1/conversations/\(conversationID.pathComponent)/participants", body: Body(participants: [contact.actor])); selected = ""; await load() }
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
