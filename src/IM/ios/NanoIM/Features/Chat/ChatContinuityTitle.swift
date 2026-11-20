import SwiftUI

/// Both chat surfaces reserve the same principal slot even while silent. Feedback never
/// inserts a row or changes the content viewport; Dynamic Type scales both states equally.
private struct ChatContinuityTitle: ViewModifier {
    let title: String
    @Bindable var store: ChatStore
    let surface: ChatConnectionSurface
    let titleAction: (() -> Void)?
    let loadEarlier: (() async -> Void)?
    @State private var showingDetails = false
    @ScaledMetric(relativeTo: .headline) private var titleHeight = 22.0
    @ScaledMetric(relativeTo: .caption2) private var auxiliaryHeight = 16.0

    func body(content: Content) -> some View {
        let presentation = store.connectionPresentation(surface)
        content.navigationTitle(title).navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    HStack(spacing: 8) {
                        if let chat = headerChat, chat.type != "group" {
                            let avatar = AvatarView(name: chat.avatarName(selfID: store.user.id),
                                kind: chat.peerAgent == nil ? "person" : "agent", size: 32,
                                agentID: chat.peerAgent?.id, role: chat.peerAgent?.role, variant: chat.peerAgent?.avatar_variant)
                            if let titleAction {
                                Button(action: titleAction) { avatar }.buttonStyle(.plain)
                                    .accessibilityLabel(L("查看当前活动", "Show current activity"))
                            } else { avatar }
                        }
                        VStack(spacing: 1) {
                            if let titleAction {
                                Button(action: titleAction) { titleLabel }.buttonStyle(.plain)
                                    .accessibilityHint(L("查看当前活动", "Show current activity"))
                            } else if let chat = headerChat, chat.type == "group" {
                                let count = chat.participants.count
                                HStack(spacing: 4) {
                                    titleLabel
                                    Text("(\(count))")
                                        .font(.subheadline).foregroundStyle(.secondary).fixedSize()
                                }
                                .accessibilityElement(children: .ignore)
                                .accessibilityLabel(L("\(title)，\(count) 位成员", "\(title), \(count) members"))
                                .accessibilityAddTraits(.isHeader)
                            } else { titleLabel }
                            if let presentation {
                                Button {
                                    showingDetails = true
                                    Task { await store.retryConnectionReads(surface, loadEarlier: loadEarlier) }
                                } label: {
                                    Text(presentation.text)
                                        .font(.caption2).foregroundStyle(.secondary)
                                        .lineLimit(1).truncationMode(.tail)
                                        .frame(height: auxiliaryHeight)
                                }
                                .buttonStyle(.plain)
                                .accessibilityIdentifier("chat.connectionFeedback")
                            }
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: max(44, titleHeight + auxiliaryHeight + 2))
                }
            }
            .sheet(isPresented: $showingDetails) {
                NavigationStack {
                    Form {
                        Section { Text(title).font(.headline).textSelection(.enabled) }
                        Section {
                            if let current = store.connectionPresentation(surface) {
                                Text(current.text)
                            } else { Text(L("连接反馈已恢复。", "Connection feedback has cleared.")) }
                            if let stamp = ChatConnectionText.absoluteTimestamp(store.lastFullAt) {
                                Text(L("上次更新 \(stamp)", "Last updated \(stamp)"))
                            } else { Text(L("尚无成功更新记录", "No successful update recorded yet")) }
                            ForEach(relevantFailures, id: \.key) { failure in
                                Text(failure.value.message).font(.callout).textSelection(.enabled)
                            }
                            if !relevantFailures.isEmpty {
                                Button(L("重试更新", "Retry update")) { Task { await store.retryConnectionReads(surface, loadEarlier: loadEarlier) } }
                            }
                        }
                    }
                    .navigationTitle(L("连接与更新", "Connection and updates"))
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar { ToolbarItem(placement: .confirmationAction) {
                        Button(L("完成", "Done")) { showingDetails = false }
                    } }
                }
            }
    }

    private var headerChat: Conversation? {
        guard case .conversation(let id) = surface, !store.revokedChats.contains(id), !store.checkingAccess.contains(id) else { return nil }
        return store.conversations.first { $0.id == id } ?? (store.inspectedConversation?.id == id ? store.inspectedConversation : nil)
    }

    private var titleLabel: some View {
        Text(title).font(.headline).foregroundStyle(NanoTheme.ink)
            .lineLimit(1).truncationMode(.tail)
            .frame(height: titleHeight)
            .accessibilityAddTraits(.isHeader)
    }

    private var relevantFailures: [(key: ChatReadScope, value: ChatScopedReadFailure)] {
        store.continuity.readFailures.filter { $0.key.belongs(to: surface) }
            .sorted { $0.value.since < $1.value.since }
    }
}

extension View {
    func chatContinuityTitle(_ title: String, store: ChatStore, surface: ChatConnectionSurface,
                             titleAction: (() -> Void)? = nil, loadEarlier: (() async -> Void)? = nil) -> some View {
        modifier(ChatContinuityTitle(title: title, store: store, surface: surface, titleAction: titleAction, loadEarlier: loadEarlier))
    }
}
