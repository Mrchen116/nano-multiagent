import SwiftUI

struct ChatMessageView: View {
    let client: IMClient
    let message: ChatMessage
    let selfID: String
    let refreshed: () -> Void
    @State private var showProcess = false
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(message.sender.display_name ?? message.sender.id).font(.caption.bold()).foregroundStyle(.secondary)
                Spacer()
                Text(status).font(.caption2).foregroundStyle(message.delivery_status == "failed" ? .red : .secondary)
            }
            if let notice = message.system_notice {
                Label(notice["kind"].stringValue ?? L("系统通知", "System notice"), systemImage: "info.circle").font(.callout)
                if let name = notice["source_agent_display_name"].stringValue { Text(name).font(.caption).foregroundStyle(.secondary) }
                if let targets = notice["updated_targets"].arrayValue { Text(targets.compactMap(\.stringValue).joined(separator: ", ")).font(.caption) }
            }
            if !message.content.isEmpty { MarkdownView(text: message.content, client: client) }
            ForEach(message.attachments) { AttachmentView(client: client, attachment: $0) }
            if hasProcess {
                DisclosureGroup(isExpanded: $showProcess) {
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(processItems) { item in
                            switch item.content {
                            case .thinking(let text): DisclosureGroup(L("思考", "Thinking")) { Text(text).font(.callout).textSelection(.enabled) }
                            case .tool(let tool): toolView(tool)
                            case .other(let label, let value): DisclosureGroup(label) {
                                if let text = value["text"].stringValue ?? value["result"].stringValue { MarkdownView(text: text, client: client) }
                                if let error = value["error"].stringValue { ErrorNotice(message: error) }
                                NavigationLink(L("全部详情", "All details")) { JSONDetailView(value: value) }
                            }
                            }
                        }
                    }.padding(.top, 8)
                } label: { Label(L("过程", "Process") + " (\(processItems.count))", systemImage: "list.bullet.rectangle").font(.caption) }
            }
            ForEach(message.permission_requests ?? []) { permission in
                ChatPermissionCard(client: client, conversationID: message.conversation_id, messageID: message.id, permission: permission, refreshed: refreshed)
            }
            if message.token_usage != nil || message.elapsed_ms != nil {
                HStack {
                    if let usage = message.token_usage {
                        Text("↑ \(usage["output"].intValue ?? 0) · \(usage["context_used"].intValue ?? 0)/\(usage["context_window"].intValue ?? 0)")
                        if let cached = usage["cache_read_tokens"].intValue, let total = usage["cache_total_input_tokens"].intValue, total > 0 { Text(L("缓存 ", "Cache ") + "\(cached * 100 / total)%") }
                    }
                    Spacer()
                    if let ms = message.elapsed_ms { Text(String(format: "%.1fs", ms / 1000)) }
                }.font(.caption2).foregroundStyle(.secondary)
            }
        }.padding(14).background(message.sender.id == selfID ? Color.teal.opacity(0.10) : Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16))
            .textSelection(.enabled)
    }
    private var status: String {
        switch message.delivery_status { case "running": return L("进行中", "Running"); case "failed": return L("失败", "Failed"); case "completed": return L("已完成", "Completed"); default: return L("已发送", "Sent") }
    }
    private var hasProcess: Bool { !(message.tool_calls ?? []).isEmpty || !(message.thinking ?? []).isEmpty || !(message.background_returns ?? []).isEmpty || !(message.reply_process ?? []).isEmpty }
    private struct ProcessItem: Identifiable {
        enum Content { case thinking(String), tool(ChatToolCall), other(String, JSONValue) }
        let id: String; let seq: Int; let content: Content
    }
    private var processItems: [ProcessItem] {
        var items = (message.thinking ?? []).map { ProcessItem(id: "thinking-\($0.seq)", seq: $0.seq, content: .thinking($0.text)) }
        items += (message.tool_calls ?? []).enumerated().map { ProcessItem(id: "tool-\($0.element.id)", seq: $0.element.seq ?? $0.offset, content: .tool($0.element)) }
        items += (message.background_returns ?? []).enumerated().map { ProcessItem(id: "background-\($0.offset)", seq: $0.element["seq"].intValue ?? 0, content: .other(L("后台任务返回", "Background task result"), $0.element)) }
        items += (message.reply_process ?? []).enumerated().map { ProcessItem(id: "reply-\($0.offset)", seq: $0.element["seq"].intValue ?? 0, content: .other($0.element["kind"].stringValue ?? L("回复过程", "Reply process"), $0.element)) }
        return items.sorted { $0.seq < $1.seq }
    }
    private func toolView(_ tool: ChatToolCall) -> some View {
        DisclosureGroup {
            VStack(alignment: .leading, spacing: 6) {
                if let approval = tool.approval { Label(approval == "user_allow" ? L("已授权", "Authorized") : L("已拒绝", "Denied"), systemImage: "hand.raised") }
                if let reason = tool.reason { Text(reason).font(.caption).foregroundStyle(.secondary) }
                if let output = tool.output { Text(output).font(.callout).textSelection(.enabled) }
                if let input = tool.input { NavigationLink(L("输入", "Input")) { JSONDetailView(value: input) } }
                if let detail = tool.detail { NavigationLink(L("结果详情", "Result details")) { JSONDetailView(value: detail) } }
            }
        } label: { HStack { Text((tool.emoji ?? "🔧") + " " + tool.name); Spacer(); Text(tool.status).font(.caption); if let ms = tool.duration_ms { Text(String(format: "%.1fs", ms / 1000)).font(.caption) } } }
    }
}

struct ChatPermissionCard: View {
    let client: IMClient
    let conversationID: String
    let messageID: String
    let permission: ChatPermission
    let refreshed: () -> Void
    @State private var decision: ChatPermissionOption?
    @State private var reason = ""
    @State private var busy = false
    @State private var submitted = false
    @State private var error: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(permission.tool_name, systemImage: "hand.raised.fill").font(.headline)
            Text(permission.question)
            NavigationLink(L("查看操作输入", "Inspect action input")) { JSONDetailView(value: permission.tool_input) }
            if permission.status == "resolved" { Text(L("已处理：", "Resolved: ") + (permission.decision ?? "")).foregroundStyle(.secondary) }
            else if permission.status == "submitted" || submitted { Label(L("已提交，等待确认", "Submitted, awaiting confirmation"), systemImage: "clock") }
            else { ForEach(permission.options) { option in
                Button { decision = option } label: { VStack(alignment: .leading) { Text(option.label); if !option.description.isEmpty { Text(option.description).font(.caption).foregroundStyle(.secondary) } } }.disabled(busy)
            } }
            if let error { ErrorNotice(message: error) }
        }.padding(12).background(.orange.opacity(0.10), in: RoundedRectangle(cornerRadius: 12))
            .sheet(item: $decision) { option in
                NavigationStack { Form {
                    Section { Text(option.label).font(.headline); Text(option.description) }
                    TextField(L("补充说明（可选）", "Reason (optional)"), text: $reason, axis: .vertical).lineLimit(3...6)
                    Button(L("提交决定", "Submit decision")) { Task { await submit(option) } }.disabled(busy)
                    if let error { ErrorNotice(message: error) }
                }.navigationTitle(L("审批", "Permission")).toolbar { ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { decision = nil } } } } }
    }
    private func submit(_ option: ChatPermissionOption) async {
        struct Body: Encodable, Sendable { let message_id: String; let decision: String; let reason: String? }
        busy = true; error = nil; defer { busy = false }
        do {
            let _: JSONValue = try await client.send("/im/v1/conversations/\(conversationID.pathComponent)/permissions/\(permission.id.pathComponent)", body: Body(message_id: messageID, decision: option.id, reason: reason.isEmpty ? nil : reason))
            submitted = true; decision = nil; refreshed()
        } catch { self.error = error.localizedDescription; if (error as? APIError)?.status == 409 { refreshed() } }
    }
}
