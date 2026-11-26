import SwiftUI

struct TopicEntryButton: View {
    let summary: ThreadSummary
    let trailing: Bool
    let open: () -> Void

    var body: some View {
        Button(action: open) {
            HStack(spacing: 6) {
                HStack(spacing: -5) {
                    ForEach((summary.participants ?? []).prefix(3), id: \.id) { person in
                        AvatarView(id: .threadParticipant(person), size: 18)
                    }
                }.accessibilityHidden(true)
                Text(L("\(summary.reply_count) 条回复", "\(summary.reply_count) replies"))
                    .font(.caption.weight(.semibold)).foregroundStyle(NanoTheme.accent).fixedSize()
                if let preview = summary.latest_preview, !preview.isEmpty {
                    Text(preview).font(.caption2).foregroundStyle(NanoTheme.muted).lineLimit(1)
                } else if let latest = summary.latest_at {
                    NanoTimestamp(value: latest)
                }
                Image(systemName: "chevron.forward").font(.caption2).foregroundStyle(NanoTheme.muted)
            }.frame(maxWidth: .infinity, alignment: trailing ? .trailing : .leading)
        }.buttonStyle(.plain)
    }
}

struct ThreadView: View {
    @Bindable var store: ChatStore
    let conversation: Conversation
    let root: ChatMessage
    @State private var items: [ChatMessage] = []
    @State private var following: Bool?
    @State private var draft = ""
    @State private var quote: ChatMessage?
    @State private var sending = false
    @State private var changingFollow = false
    @State private var followsTail = true
    @State private var userScrolling = false
    @State private var error: String?
    private var writable: Bool { conversation.can_write != false }

    var body: some View {
        VStack(spacing: 0) {
            if let error { ErrorNotice(message: error).padding(10) }
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 16) {
                        row(root, proxy: proxy)
                        HStack {
                            line
                            let replyCount = items.filter { $0.system_notice == nil }.count
                            Text(L("\(replyCount) 条回复", "\(replyCount) replies")).font(.caption)
                                .foregroundStyle(NanoTheme.muted).fixedSize()
                            line
                        }
                        ForEach(items) { message in
                            row(message, proxy: proxy)
                                .onScrollVisibilityChange(threshold: 0.2) { visible in
                                    if visible, writable, message.id == items.last?.id {
                                        Task { await store.markRead(conversation.id, messageID: message.id) }
                                    }
                                }
                        }
                    }.padding()
                }
                .defaultScrollAnchor(.bottom, for: .initialOffset)
                .onScrollPhaseChange { _, phase, context in
                    userScrolling = phase == .interacting || phase == .decelerating
                    if userScrolling || phase == .idle { followsTail = nearTail(context.geometry) }
                }
                .onScrollGeometryChange(for: Bool.self) { nearTail($0) } action: { _, near in
                    if userScrolling { followsTail = near }
                }
                .onChange(of: items.last?.id) { _, id in
                    if followsTail, let id { proxy.scrollTo(id, anchor: .bottom) }
                }
            }
        }
        .transformEnvironment(\.avatarDirectory) { $0 = $0.includingHistory([root] + items) }
        .safeAreaInset(edge: .bottom, spacing: 0) { if writable { composer } }
        .background(NanoTheme.canvas)
        .navigationTitle(L("话题", "Thread"))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.hidden, for: .tabBar)
        .toolbar {
            if writable && conversation.type == "group" {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(following == true ? L("关注中", "Following") : L("关注", "Follow")) {
                        Task { await toggle() }
                    }.disabled(following == nil || changingFollow).accessibilityIdentifier("thread.follow")
                }
            }
        }
        .onAppear { store.openThreadRoot = root.id }
        .onDisappear { if store.openThreadRoot == root.id { store.openThreadRoot = nil } }
        .task(id: store.threadRevision) { await load() }
    }

    private var line: some View { Rectangle().fill(.separator).frame(height: 1) }

    private func nearTail(_ geometry: ScrollGeometry) -> Bool {
        geometry.contentSize.height + geometry.contentInsets.bottom - geometry.visibleRect.maxY < 48
    }

    private func row(_ message: ChatMessage, proxy: ScrollViewProxy) -> some View {
        ChatMessageView(client: store.client, chat: store, message: message, selfID: store.user.id,
                        participants: conversation.participants, showSenderName: conversation.type == "group",
                        readOnly: !writable, locateQuote: { id in
                            followsTail = false
                            proxy.scrollTo(id, anchor: .center)
                        }, refreshed: { store.threadRevision += 1 })
            .id(message.id)
            .contextMenu {
                if writable && message.system_notice == nil && ["sent", "completed", "pending"].contains(message.delivery_status) {
                    Button(L("回复", "Reply"), systemImage: "arrowshape.turn.up.left") { quote = message }
                }
            }
    }

    private var composer: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let quote {
                HStack {
                    VStack(alignment: .leading) {
                        Text(quote.sender.display_name ?? quote.sender.id).font(.caption.weight(.semibold))
                        Text(ChatText.display(quote.content, participants: conversation.participants))
                            .font(.caption).lineLimit(1)
                    }
                    Spacer()
                    Button(L("取消引用", "Cancel quote")) { self.quote = nil }.font(.caption)
                }
            }
            HStack(alignment: .bottom) {
                TextField(L("写在话题里", "Reply in thread"), text: $draft, axis: .vertical)
                    .lineLimit(1...5).accessibilityIdentifier("thread.draft")
                Button { Task { await send() } } label: {
                    Image(systemName: "arrow.up.circle.fill").font(.title2)
                }.disabled(sending || draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    .accessibilityLabel(L("发送", "Send")).accessibilityIdentifier("thread.send")
            }
        }
        .disabled(sending)
        .padding(12).background(.background, in: RoundedRectangle(cornerRadius: 14))
        .overlay { RoundedRectangle(cornerRadius: 14).strokeBorder(.separator) }.padding(12)
    }

    private func load() async {
        do {
            let page = try await store.client.threadMessages(conversation.id, root: root.id)
            guard !Task.isCancelled else { return }
            items = page.items.compactMap(\.message)
            following = page.following
        } catch { if !Task.isCancelled { self.error = error.localizedDescription } }
    }

    private func send() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !sending else { return }
        sending = true
        defer { sending = false }
        do {
            _ = try await store.client.sendThread(conversation.id, root: root.id,
                text: ChatText.wire(text, participants: conversation.participants), userID: store.user.id, replyTo: quote?.id)
            draft = ""
            quote = nil
            error = nil
            store.threadRevision += 1
        } catch { self.error = error.localizedDescription }
    }

    private func toggle() async {
        guard let following, !changingFollow else { return }
        changingFollow = true
        defer { changingFollow = false }
        do {
            try await store.client.setThreadFollow(conversation.id, root: root.id, following: !following)
            self.following = !following
            error = nil
            store.threadRevision += 1
        } catch { self.error = error.localizedDescription }
    }
}
