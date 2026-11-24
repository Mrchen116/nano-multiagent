import SwiftUI

struct ChatMessageLocation: Equatable {
    let id = UUID()
    let conversationID: String
    let messageID: String

    static func from(_ url: URL, origin: URL) -> Self? {
        guard ServerOrigin.same(origin, url) else { return nil }
        let path = url.pathComponents
        guard path.count == 3, path[1] == "chat",
              let target = URLComponents(url: url, resolvingAgainstBaseURL: false)?
                .queryItems?.first(where: { $0.name == "message_id" })?.value,
              !target.isEmpty else { return nil }
        return Self(conversationID: path[2], messageID: target)
    }
}

private struct MessageSearchPage: Decodable, Sendable {
    struct Hit: Decodable, Identifiable, Sendable {
        let message_id: String
        let conversation_id: String
        let conversation_name: String
        let sender_name: String?
        let snippet: String
        let created_at: String
        var id: String { message_id }
    }
    let messages: [Hit]
    let next_cursor: String?
}

struct ChatMessageSearch: View {
    let store: ChatStore
    let query: String
    let category: String
    let open: (String) -> Void
    @State private var hits: [MessageSearchPage.Hit] = []
    @State private var next: String?
    @State private var loading = true
    @State private var failure: String?
    @State private var generation = UUID()
    @State private var pageRequest: Task<Void, Never>?

    private var key: [String] { [query, category] }
    var body: some View {
        Section(L("历史消息", "Message history")) {
            ForEach(hits.filter { !store.revokedChats.contains($0.conversation_id) && !store.checkingAccess.contains($0.conversation_id) }) { hit in
                Button {
                    store.messageLocation = ChatMessageLocation(conversationID: hit.conversation_id, messageID: hit.id)
                    open(hit.conversation_id)
                } label: {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(highlighted(hit.snippet)).font(.body).foregroundStyle(NanoTheme.ink).lineLimit(3)
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Text([hit.sender_name, hit.conversation_name].compactMap { $0 }.joined(separator: " · "))
                                .font(.caption).foregroundStyle(NanoTheme.muted)
                            Spacer(minLength: 4)
                            NanoTimestamp(value: hit.created_at)
                        }
                    }.padding(.vertical, 4).contentShape(Rectangle())
                }.buttonStyle(.plain)
            }
            if loading { ProgressView().accessibilityLabel(L("正在搜索历史消息", "Searching message history")) }
            if let failure { ErrorNotice(message: failure) }
            if !loading {
                if next != nil || failure != nil {
                    Button(failure == nil ? L("更多结果", "More results") : L("重试搜索", "Retry search")) {
                        pageRequest = Task { await load(cursor: next, token: generation) }
                    }
                } else if hits.isEmpty { Text(L("没有找到历史消息", "No matching messages")).foregroundStyle(.secondary) }
            }
        }.task(id: key) {
            pageRequest?.cancel()
            let token = UUID()
            generation = token
            hits = []; next = nil; failure = nil; loading = true
            do { try await Task.sleep(for: .milliseconds(250)) } catch { return }
            await load(cursor: nil, token: token)
        }.onDisappear { pageRequest?.cancel() }
    }

    private func highlighted(_ snippet: String) -> AttributedString {
        var text = AttributedString(snippet)
        if !query.isEmpty, let range = text.range(of: query, options: [.caseInsensitive, .diacriticInsensitive]) {
            text[range].inlinePresentationIntent = .stronglyEmphasized
            text[range].backgroundColor = Color("Butter")
        }
        return text
    }

    private func load(cursor: String?, token: UUID) async {
        guard token == generation else { return }
        loading = true
        failure = nil
        let kind = ["people": "direct-user", "agent": "direct-agent", "network": "agent-network"][category] ?? category
        var params = [URLQueryItem(name: "q", value: query), URLQueryItem(name: "kind", value: kind)]
        if let cursor { params.append(URLQueryItem(name: "cursor", value: cursor)) }
        do {
            let page: MessageSearchPage = try await store.client.get("/im/v1/messages/search", query: params)
            guard !Task.isCancelled, token == generation else { return }
            let existing = Set(hits.map(\.id))
            hits += page.messages.filter { !existing.contains($0.id) }
            next = page.next_cursor
        } catch {
            guard !Task.isCancelled, token == generation else { return }
            failure = error.localizedDescription
        }
        loading = false
    }
}

struct ChatReplyLabel: View {
    let reply: ChatReply
    let participants: [ActorRef]
    var body: some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 2).fill(NanoTheme.accent).frame(width: 3)
            VStack(alignment: .leading, spacing: 2) {
                Text(reply.sender.display_name ?? reply.sender.id).font(.caption.weight(.semibold))
                Text(reply.preview(participants: participants)).font(.footnote).foregroundStyle(.secondary).lineLimit(2)
            }
        }.fixedSize(horizontal: false, vertical: true)
            .accessibilityElement(children: .combine)
    }
}
