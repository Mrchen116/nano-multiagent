import SwiftUI

struct InteractiveCardView: View {
    @State private var runtime: InteractiveRuntime
    let readOnly: Bool
    @Environment(\.openURL) private var openURL
    init(client: IMClient, message: ChatMessage, chat: ChatStore, readOnly: Bool) {
        _runtime = State(initialValue: InteractiveRuntime(client: client, message: message, chat: chat, readOnly: readOnly))
        self.readOnly = readOnly
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if runtime.loaded {
                InteractiveNodeView(node: runtime.root, runtime: runtime)
                    .disabled(runtime.busy || runtime.hasPending)
            } else if runtime.error == nil { ProgressView(L("载入交互内容…", "Loading interaction…")) }
            if runtime.readOnly { Text(L("历史回复，仅供阅读", "Historical reply · read only")).font(.caption).foregroundStyle(.secondary) }
            if runtime.busy { ProgressView(runtime.composing ? L("正在采用…", "Preparing draft…") : L("正在发送…", "Sending…")) }
            else if runtime.submitted && !runtime.hasPending { Text(L("请求已发送，Agent 将在聊天中回复。", "Request sent. The Agent will reply in the conversation.")).font(.caption).foregroundStyle(NanoTheme.accent) }
            if let error = runtime.error {
                ErrorNotice(message: error)
                if runtime.conflict || !runtime.loaded { Button(L("读取最新", "Load latest")) { Task { await runtime.load() } } }
                else if !runtime.hasPending { Button(L("重试", "Retry")) { Task { await runtime.retryContent() } } }
            }
            if runtime.hasPending { Button(L("重试核对上次请求", "Check previous request")) { Task { await runtime.retry() } }.disabled(runtime.readOnly || runtime.busy) }
        }
        .accessibilityElement(children: .contain)
        .task { runtime.openURL = { openURL($0) }; await runtime.load() }
        .onChange(of: readOnly) { _, value in runtime.setReadOnly(value) }
        .onDisappear { runtime.leave() }
        .confirmationDialog(L("替换未发送的内容？", "Replace unsent content?"), isPresented: Binding(get: { runtime.pendingCompose != nil }, set: { if !$0 { runtime.pendingCompose = nil } }), titleVisibility: .visible) {
            Button(L("替换", "Replace"), role: .destructive) {
                if let request = runtime.pendingCompose { Task { await runtime.replaceCompose(request) } }
            }
            Button(L("取消", "Cancel"), role: .cancel) { runtime.pendingCompose = nil }
        }
    }
}
