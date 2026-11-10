import SwiftUI

struct ChatMessageView: View {
    let client: IMClient
    let chat: ChatStore
    let message: ChatMessage
    let selfID: String
    var participants: [ActorRef] = []
    var showSenderName = false
    var readOnly = false
    let refreshed: () -> Void
    @State private var showProcess = false
    private var mine: Bool { message.sender.id == selfID }
    private var receipts: [MessageReceipt] { mine && message.sender_type == "user" ? message.receipts ?? [] : [] }
    private var intelligentUI: Bool { message.interactive?.catalog_version == "nano-iui-1" }
    private var senderName: String { message.sender.display_name ?? participants.first { ($0.user_id ?? $0.id) == message.sender.id }?.display_name ?? message.sender.id }
    var body: some View {
        if message.system_notice?["kind"].stringValue == "task_graph" {
            VStack(spacing: 4) {
                NanoTimestamp(value: message.created_at)
                Text(taskNoticeText).font(.caption).multilineTextAlignment(.center).tint(NanoTheme.accent)
            }.font(.caption).foregroundStyle(NanoTheme.muted).frame(maxWidth: .infinity).padding(.vertical, 6).textSelection(.enabled)
        } else if intelligentUI {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    AvatarView(name: senderName, kind: message.sender_type == "agent" ? "agent" : "person", size: 32)
                    senderIdentity
                }
                messageContent
                if hasMetadata { metadata }
            }.frame(maxWidth: .infinity, alignment: .leading)
        } else { bubble }
    }
    private var taskNoticeText: AttributedString {
        let text = ChatText.display(message.content, participants: participants)
        return (try? AttributedString(markdown: text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace), baseURL: client.baseURL)) ?? AttributedString(text)
    }
    private var bubble: some View {
        HStack(alignment: .top, spacing: 8) {
            if mine { Spacer(minLength: 28) }
            else if message.system_notice == nil { AvatarView(name: senderName, kind: message.sender_type == "agent" ? "agent" : "person", size: 32) }
            VStack(alignment: receipts.isEmpty ? .leading : .trailing, spacing: 6) {
                if message.system_notice == nil && ((showSenderName && !mine) || message.pa_agent_id != nil || message.delegation != nil) {
                    senderIdentity
                }
                messageContent
                if hasMetadata { metadata }
                if !receipts.isEmpty { MessageReceiptButton(receipts: receipts) }
            }
            if !mine { Spacer(minLength: 14) }
            else if message.system_notice == nil { AvatarView(name: senderName, size: 32) }
        }
    }
    private var senderIdentity: some View {
        HStack(spacing: 6) {
            Text(senderName).fixedSize(horizontal: false, vertical: true)
            if message.pa_agent_id != nil { Text(L("PA 代发", "Sent by PA")).foregroundStyle(.secondary).fixedSize() }
            else if let label = message.delegation?["label"].stringValue { Text(label).foregroundStyle(.secondary) }
        }.font(.caption).foregroundStyle(NanoTheme.muted).padding(.horizontal, 4)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(message.pa_agent_id != nil ? senderName + L("，由 PA 代发", ", sent by PA") : senderName + (message.delegation?["label"].stringValue.map { ", " + $0 } ?? ""))
    }
    private var messageContent: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let notice = message.system_notice {
                Label(notice["kind"].stringValue ?? L("系统通知", "System notice"), systemImage: "info.circle").font(.callout)
                if let name = notice["source_agent_display_name"].stringValue { Text(name).font(.caption).foregroundStyle(.secondary) }
                if let targets = notice["updated_targets"].arrayValue { Text(targets.compactMap(\.stringValue).joined(separator: ", ")).font(.caption) }
            }
            if !message.content.isEmpty { MarkdownView(text: ChatText.display(message.content, participants: participants), client: client) }
            if message.interactive != nil {
                InteractiveCardView(client: client, message: message, chat: chat,
                    readOnly: readOnly || message.interactive?.read_only == true || message.interactive?.superseded_by != nil)
                    .textSelection(.disabled)
            } else {
                ForEach(message.attachments.indices, id: \.self) { index in
                    AttachmentView(client: client, attachment: message.attachments[index])
                }
            }
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
                                NavigationLink(L("全部详情", "All details")) { JSONDetailPage(value: value) }
                            }
                            }
                        }
                    }.padding(.top, 8)
                } label: { Label(L("过程", "Process") + " (\(processItems.count))", systemImage: "list.bullet.rectangle").font(.caption) }
            }
            ForEach(message.permission_requests ?? []) { permission in
                ChatPermissionCard(client: client, conversationID: message.conversation_id, messageID: message.id, permission: permission, readOnly: readOnly, refreshed: refreshed)
            }
            }.padding(intelligentUI ? 0 : 14).background(intelligentUI ? Color.clear : mine ? NanoTheme.softAccent : NanoTheme.surface, in: RoundedRectangle(cornerRadius: 16))
                .overlay(RoundedRectangle(cornerRadius: 16).stroke(mine || intelligentUI ? Color.clear : NanoTheme.border, lineWidth: 1))
                .foregroundStyle(NanoTheme.ink).textSelection(.enabled)
    }
    private var hasMetadata: Bool {
        message.delivery_status == "running" || (message.delivery_status == "failed" && receipts.isEmpty)
            || (message.sender_type == "agent" && (message.token_usage != nil || message.elapsed_ms != nil))
    }
    private var metadata: some View {
        HStack(alignment: .top, spacing: 8) {
            if mine { Spacer(minLength: 0) }
            if message.delivery_status == "failed" { Label(mine ? L("发送失败", "Send failed") : L("失败", "Failed"), systemImage: "exclamationmark.circle").foregroundStyle(.red) }
            else if message.delivery_status == "running" { Text(L("进行中", "Running")) }
            if message.sender_type == "agent" {
                if let usage = message.token_usage { ChatUsageView(usage: usage) }
                if !mine { Spacer(minLength: 0) }
                if let ms = message.elapsed_ms { Text(String(format: "%.1fs", ms / 1000)) }
                else if message.delivery_status == "running", let start = nanoDate(message.created_at) {
                    Text(start, style: .timer).monospacedDigit().accessibilityLabel(L("本轮耗时", "Turn duration"))
                }
            }
        }.font(.caption2).foregroundStyle(.secondary).padding(.horizontal, 4)
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
                if let input = tool.input { NavigationLink(L("输入", "Input")) { JSONDetailPage(value: input) } }
                if let detail = tool.detail { NavigationLink(L("结果详情", "Result details")) { JSONDetailPage(value: detail) } }
            }
        } label: { HStack { Text((tool.emoji ?? "🔧") + " " + tool.name); Spacer(); Text(tool.status).font(.caption); if let ms = tool.duration_ms { Text(String(format: "%.1fs", ms / 1000)).font(.caption) } } }
    }
}

private struct MessageReceiptButton: View {
    let receipts: [MessageReceipt]
    @State private var showDetails = false

    private var status: MessageReceipt.Status {
        if receipts.contains(where: { $0.status == .sent }) { return .sent }
        if receipts.contains(where: { $0.status == .received }) { return .received }
        return .read
    }

    var body: some View {
        Button { showDetails = true } label: {
            ReceiptMark(status: status).frame(width: 44, height: 26).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(status.title)
        .accessibilityHint(L("轻点查看消息回执", "Tap to view message receipts"))
        .accessibilityIdentifier("message.receipt")
        .popover(isPresented: $showDetails) {
            VStack(alignment: .leading, spacing: 0) {
                Text(L("消息回执", "Message receipts"))
                    .font(.subheadline.weight(.semibold))
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .accessibilityAddTraits(.isHeader)
                Divider()
                if receipts.count > 5 {
                    ScrollView { receiptRows }.frame(height: 230)
                } else {
                    receiptRows
                }
            }
            .foregroundStyle(NanoTheme.ink)
            .frame(width: 252)
            .presentationCompactAdaptation(.popover)
        }
    }

    private var receiptRows: some View {
        VStack(spacing: 6) {
            ForEach(receipts) { receipt in
                HStack(spacing: 8) {
                    AvatarView(name: receipt.display_name, size: 24).accessibilityHidden(true)
                    Text(receipt.display_name).font(.subheadline.weight(.medium))
                    Spacer(minLength: 4)
                    HStack(spacing: 4) {
                        ReceiptMark(status: receipt.status).accessibilityHidden(true)
                        Text(receipt.status.title).font(.caption.weight(.medium))
                    }
                    .foregroundStyle(receipt.status == .read ? NanoTheme.accent : NanoTheme.muted)
                    .padding(.horizontal, 7).padding(.vertical, 4)
                    .background(receipt.status == .read ? NanoTheme.softAccent : NanoTheme.canvas, in: Capsule())
                }.accessibilityElement(children: .combine)
            }
        }.padding(12)
    }
}

private extension MessageReceipt.Status {
    var title: String {
        switch self {
        case .sent: L("待送达", "Pending")
        case .received: L("已送达", "Delivered")
        case .read: L("已读", "Read")
        }
    }
}

private struct ReceiptMark: View {
    let status: MessageReceipt.Status

    var body: some View {
        Path { path in
            path.move(to: CGPoint(x: 1, y: 5))
            path.addLine(to: CGPoint(x: 4, y: 8))
            path.addLine(to: CGPoint(x: 10, y: 2))
            if status != .sent {
                path.move(to: CGPoint(x: 7, y: 8))
                path.addLine(to: CGPoint(x: 13, y: 2))
            }
        }
        .stroke(status == .read ? NanoTheme.accent : NanoTheme.muted,
                style: StrokeStyle(lineWidth: 1.4, lineCap: .round, lineJoin: .round))
        .frame(width: 14, height: 10)
    }
}

private struct ChatUsageView: View {
    let usage: JSONValue
    var body: some View {
        DisclosureGroup {
            VStack(alignment: .leading, spacing: 8) {
                LabeledContent(L("本轮输出", "Turn output"), value: count("output"))
                LabeledContent(L("本轮总用量", "Turn total"), value: count("total"))
                LabeledContent(L("已用上下文", "Context used"), value: count("context_used") + " / " + count("context_window"))
                if let cached = usage["cache_read_tokens"].intValue, let input = usage["cache_total_input_tokens"].intValue {
                    let rate = input > 0 ? Double(cached) / Double(input) * 100 : 0
                    LabeledContent(L("缓存命中", "Cache hits"), value: "\(cached.formatted()) (\(Int(rate.rounded()))%)")
                } else {
                    LabeledContent(L("缓存命中", "Cache hits"), value: "—")
                }
                if let used = usage["context_used"].intValue, let window = usage["context_window"].intValue, window > 0 {
                    let fraction = Double(used) / Double(window)
                    ProgressView(value: min(1, fraction)).tint(fraction >= 0.9 ? .red : fraction >= 0.7 ? .orange : .teal)
                        .accessibilityLabel(L("上下文占用", "Context utilization"))
                    Text(String(format: "%.0f%%", fraction * 100))
                    if fraction >= 0.7 { Text(L("上下文接近上限，可压缩上下文或新建会话。", "Context is approaching its limit. Compact it or start a new conversation.")) }
                }
            }.padding(10).background(.teal.opacity(0.05), in: RoundedRectangle(cornerRadius: 8))
        } label: { Text(count("total") + " tokens") }
    }
    private func count(_ key: String) -> String { usage[key].intValue?.formatted() ?? L("未报告", "Unreported") }
}

struct ChatPermissionCard: View {
    let client: IMClient
    let conversationID: String
    let messageID: String
    let permission: ChatPermission
    var readOnly = false
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
            NavigationLink(L("查看操作输入", "Inspect action input")) { JSONDetailPage(value: permission.tool_input) }
            if permission.status == "resolved" { Text(L("已处理：", "Resolved: ") + (permission.decision ?? "")).foregroundStyle(.secondary) }
            else if permission.status == "submitted" || submitted { Label(L("已提交，等待确认", "Submitted, awaiting confirmation"), systemImage: "clock") }
            else if !readOnly { ForEach(permission.options) { option in
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
        guard !readOnly else { return }
        struct Body: Encodable, Sendable { let message_id: String; let decision: String; let reason: String? }
        busy = true; error = nil; defer { busy = false }
        do {
            let _: JSONValue = try await client.send("/im/v1/conversations/\(conversationID.pathComponent)/permissions/\(permission.id.pathComponent)", body: Body(message_id: messageID, decision: option.id, reason: reason.isEmpty ? nil : reason))
            submitted = true; decision = nil; refreshed()
        } catch { self.error = error.localizedDescription; if (error as? APIError)?.status == 409 { refreshed() } }
    }
}
