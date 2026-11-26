import SwiftUI

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
    private var filtered: [Contact] {
        contacts.filter { $0.user_id != userID && $0.matchesConversationSearch(search) }
            .sorted { $0.display_name.localizedStandardCompare($1.display_name) == .orderedAscending }
    }
    private var selectedContacts: [Contact] { contacts.filter { selection.contains($0.id) } }

    var body: some View {
        NavigationStack {
            List {
                Picker(L("聊天类型", "Conversation type"), selection: $group) {
                    Text(L("私聊", "Direct")).tag(false)
                    Text(L("群聊", "Group")).tag(true)
                }.pickerStyle(.segmented)
                    .listRowSeparator(.hidden)
                    .listRowInsets(EdgeInsets(top: 0, leading: 16, bottom: 4, trailing: 16))

                if group {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack(spacing: 8) {
                            Image(systemName: "person.2.fill").foregroundStyle(Color("GroupAvatarInk"))
                            TextField(L("群名称（可选）", "Group name (optional)"), text: $title).font(.headline)
                            Picker(L("可见范围", "Visibility"), selection: $visibility) {
                                Text(L("公开", "Public")).tag("public")
                                Text(L("私密", "Private")).tag("private")
                            }.pickerStyle(.menu).tint(NanoTheme.ink).font(.footnote)
                        }
                        if !selectedContacts.isEmpty {
                            SelectedChatContacts(contacts: selectedContacts) { selection.remove($0.id) }
                        }
                    }.padding(12)
                        .background(Color("GroupAvatar").opacity(0.50), in: RoundedRectangle(cornerRadius: 14))
                        .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 6, trailing: 16))
                        .listRowSeparator(.hidden)
                }

                if let error {
                    ErrorNotice(message: error)
                    if !loaded { Button(L("重试", "Retry")) { Task { await loadContacts() } } }
                }
                if !loaded && error == nil { ProgressView(L("正在加载联系人…", "Loading contacts…")) }
                if loaded && filtered.isEmpty && error == nil {
                    Text(search.isEmpty ? L("暂无联系人", "No contacts") : L("没有匹配的联系人", "No matching contacts")).foregroundStyle(.secondary)
                }
                let visible = filtered
                contactSection(visible.filter { $0.kind != "agent" }, title: L("同事", "People"))
                contactSection(visible.filter { $0.kind == "agent" }, title: L("助手", "Assistants"))
            }
            .listStyle(.plain).scrollContentBackground(.hidden).background(NanoTheme.surface)
            .scrollDismissesKeyboard(.interactively).disabled(busy)
            .navigationTitle(L("新建聊天", "New conversation")).navigationBarTitleDisplayMode(.inline)
            .searchable(text: $search, placement: .navigationBarDrawer(displayMode: .always), prompt: L("搜索联系人", "Search contacts"))
            .safeAreaInset(edge: .bottom, spacing: 0) {
                if search.isEmpty && !group {
                    NavigationLink { PublicGroupsView(client: client, completed: completed) } label: {
                        Label(L("发现公开群", "Discover public groups"), systemImage: "person.2.badge.plus")
                            .font(.subheadline.weight(.medium)).frame(maxWidth: .infinity, minHeight: 46)
                    }.buttonStyle(.plain).foregroundStyle(NanoTheme.accent).background(.bar).disabled(busy)
                }
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { dismiss() }.disabled(busy) }
                if group {
                    ToolbarItem(placement: .confirmationAction) {
                        Button(L("创建", "Create")) { Task { await create(with: selectedContacts) } }
                            .disabled(busy || selection.isEmpty)
                    }
                }
            }.task { await loadContacts() }.interactiveDismissDisabled(busy)
        }
    }

    @ViewBuilder private func contactSection(_ members: [Contact], title: String) -> some View {
        if !members.isEmpty {
            Section {
                ForEach(members) { contact in
                    ChatContactRow(contact: contact, selected: group ? selection.contains(contact.id) : nil) {
                        if !group { Task { await create(with: [contact]) } }
                        else if selection.contains(contact.id) { selection.remove(contact.id) }
                        else { selection.insert(contact.id) }
                    }
                }
            } header: {
                Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(NanoTheme.muted).textCase(nil)
            }
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

extension Contact {
    func matchesConversationSearch(_ query: String) -> Bool {
        query.isEmpty || [display_name, agent_id, user_id, node_name, owner_display_name].compactMap { $0 }
            .contains { $0.localizedCaseInsensitiveContains(query) }
    }
}

struct ChatContactRow: View {
    let contact: Contact
    let selected: Bool?
    let choose: () -> Void
    private var assistantRole: String {
        let role = contact.role == "personal" ? L("个人助手", "Personal assistant") : L("助手", "Assistant")
        guard let owner = contact.owner_display_name, !owner.isEmpty else { return role }
        return L("\(owner) 的\(role)", "\(role) for \(owner)")
    }
    var body: some View {
        Button(action: choose) {
            HStack(spacing: 12) {
                AvatarView(id: .contact(contact), size: 40, online: contact.status == "online")
                VStack(alignment: .leading, spacing: 3) {
                    Text(contact.display_name).font(.body.weight(.medium)).foregroundStyle(NanoTheme.ink)
                    if contact.kind == "agent" { Text(assistantRole).font(.caption).foregroundStyle(NanoTheme.muted) }
                }
                Spacer(minLength: 4)
                if let selected {
                    Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                        .font(.title3).foregroundStyle(selected ? NanoTheme.accent : NanoTheme.muted)
                }
            }.padding(.vertical, 3).contentShape(Rectangle())
        }.buttonStyle(.plain)
            .accessibilityAddTraits(selected == true ? .isSelected : [])
            .listRowSeparator(.hidden)
    }
}

struct SelectedChatContacts: View {
    let contacts: [Contact]
    let remove: (Contact) -> Void
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(contacts) { contact in
                    Button { remove(contact) } label: {
                        HStack(spacing: 5) {
                            Text(contact.display_name).font(.caption.weight(.medium))
                            Image(systemName: "xmark").font(.caption2)
                        }.padding(.horizontal, 10).padding(.vertical, 7)
                            .background(NanoTheme.surface, in: Capsule())
                    }.buttonStyle(.plain).accessibilityLabel(L("取消选择\(contact.display_name)", "Deselect \(contact.display_name)"))
                }
            }
        }
    }
}
