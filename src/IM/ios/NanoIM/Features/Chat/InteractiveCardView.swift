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
            if runtime.busy { ProgressView(L("正在发送…", "Sending…")) }
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
    }
}
