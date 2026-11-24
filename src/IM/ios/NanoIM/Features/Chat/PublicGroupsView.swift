import SwiftUI

struct PublicGroupsView: View {
    let client: IMClient
    let completed: (Conversation) -> Void
    @State private var groups: [Conversation] = []
    @State private var search = ""
    @State private var error: String?
    @State private var loaded = false
    private var filtered: [Conversation] {
        groups.filter { search.isEmpty || $0.title.localizedCaseInsensitiveContains(search) }
    }

    var body: some View {
        List {
            if let error {
                ErrorNotice(message: error)
                Button(L("重试", "Retry")) { Task { await load() } }
            }
            if !loaded && error == nil { ProgressView() }
            if loaded && filtered.isEmpty && error == nil {
                Text(search.isEmpty ? L("暂无公开群", "No public groups") : L("没有匹配的群聊", "No matching groups"))
                    .foregroundStyle(NanoTheme.muted)
            }
            ForEach(filtered) { chat in
                Button { completed(chat) } label: {
                    HStack(spacing: 12) {
                        AvatarView(name: chat.title, kind: "group", size: 44)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(chat.title).font(.body.weight(.semibold)).foregroundStyle(NanoTheme.ink)
                            Text(chat.participants.isEmpty
                                 ? L("公开群", "Public group") : L("\(chat.participants.count) 位成员", "\(chat.participants.count) members"))
                                .font(.caption).foregroundStyle(NanoTheme.muted)
                        }
                        Spacer()
                        if chat.is_member == true {
                            Label(L("已加入", "Joined"), systemImage: "checkmark").font(.caption.weight(.medium)).foregroundStyle(NanoTheme.muted)
                        } else {
                            Image(systemName: "chevron.right").font(.footnote).foregroundStyle(NanoTheme.muted)
                        }
                    }.contentShape(Rectangle())
                }.buttonStyle(.plain).listRowSeparator(.hidden)
            }
        }.nanoList().navigationTitle(L("发现公开群", "Discover public groups"))
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $search, placement: .navigationBarDrawer(displayMode: .always), prompt: L("搜索公开群", "Search public groups"))
            .task { await load() }.refreshable { await load() }
    }

    private func load() async {
        do {
            let page: ItemsPage<Conversation> = try await client.get("/im/v1/conversations", query: [.init(name: "scope", value: "public")])
            groups = page.items; loaded = true; error = nil
        } catch { if !Task.isCancelled { self.error = error.localizedDescription } }
    }
}
