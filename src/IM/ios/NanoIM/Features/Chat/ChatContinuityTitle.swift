import SwiftUI

/// Both chat surfaces reserve the same principal slot even while silent. Feedback never
/// inserts a row or changes the content viewport; Dynamic Type scales both states equally.
private struct ChatContinuityTitle: ViewModifier {
    let title: String
    @Bindable var store: ChatStore
    let surface: ChatConnectionSurface
    @State private var showingDetails = false
    @ScaledMetric(relativeTo: .headline) private var titleHeight = 22.0
    @ScaledMetric(relativeTo: .caption2) private var auxiliaryHeight = 16.0

    func body(content: Content) -> some View {
        let presentation = store.connectionPresentation(surface)
        content.navigationTitle(title).navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    VStack(spacing: 2) {
                        Text(title).font(.headline).foregroundStyle(NanoTheme.ink)
                            .lineLimit(1).truncationMode(.tail)
                            .frame(height: titleHeight)
                            .accessibilityAddTraits(.isHeader)
                        Button {
                            showingDetails = true
                            Task { await store.retryConnectionReads(surface) }
                        } label: {
                            Text(presentation?.text ?? " ")
                                .font(.caption2).foregroundStyle(.secondary)
                                .lineLimit(1).truncationMode(.tail)
                                .frame(maxWidth: .infinity).frame(height: auxiliaryHeight)
                        }
                        .buttonStyle(.plain)
                        .opacity(presentation == nil ? 0 : 1)
                        .disabled(presentation == nil)
                        .accessibilityHidden(presentation == nil)
                        .accessibilityIdentifier("chat.connectionFeedback")
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
                                Button(L("重试更新", "Retry update")) { Task { await store.retryConnectionReads(surface) } }
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

    private var relevantFailures: [(key: ChatReadScope, value: ChatScopedReadFailure)] {
        store.continuity.readFailures.filter { $0.key.belongs(to: surface) }
            .sorted { $0.value.since < $1.value.since }
    }
}

extension View {
    func chatContinuityTitle(_ title: String, store: ChatStore, surface: ChatConnectionSurface) -> some View {
        modifier(ChatContinuityTitle(title: title, store: store, surface: surface))
    }
}
