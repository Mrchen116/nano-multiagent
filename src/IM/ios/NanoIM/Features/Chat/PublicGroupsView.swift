import SwiftUI

struct PublicGroupsView: View {
    let client: IMClient
    let completed: (Conversation) -> Void
    @State private var groups: [Conversation] = []
    @State private var error: String?
    var body: some View {
        List {
            if let error { ErrorNotice(message: error) }
            ForEach(groups) { chat in
                Button { completed(chat) } label: {
                    VStack(alignment: .leading) {
                        Text(chat.title)
                        Text(chat.is_member == true ? L("已加入", "Joined") : L("公开 · 查看后可加入", "Public · view and join")).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            if groups.isEmpty && error == nil { Text(L("暂无公开群", "No public groups")) }
        }.navigationTitle(L("发现公开群", "Discover public groups"))
            .task { await load() }.refreshable { await load() }
    }
    private func load() async {
        do { let page: ItemsPage<Conversation> = try await client.get("/im/v1/conversations", query: [.init(name: "scope", value: "public")]); groups = page.items; error = nil }
        catch { self.error = error.localizedDescription }
    }
}
