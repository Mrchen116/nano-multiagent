import SwiftUI

/// Conversation-level recovery stays next to Send even when the failed card is offscreen.
struct DraftFailureNotice: View {
    let runtime: InteractiveRuntime
    let failure: DraftFailure
    @State private var inspectionError: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ErrorNotice(message: failure.reason == .conflict
                ? L("另一台设备更新了这张卡片，这个会话暂时不能发送", "Another device changed this card. This conversation cannot send yet.")
                : L("卡片改动尚未保存，这个会话暂时不能发送", "Card changes are not saved. This conversation cannot send yet."))
            Text(failure.reason == .conflict
                ? L("「\(failure.title)」的草稿在另一台设备上改过；本机改动尚未保存，所以现在发送不会带上它。同一会话的其他消息也要等冲突处理完。", "The draft for ‘\(failure.title)’ changed on another device. Your local edits are not saved and would not be included. All messages in this conversation must wait until the conflict is resolved.")
                : L("先保存「\(failure.title)」的改动再发送，否则这次不会带上你刚改的内容；同一会话的其他消息也要等它保存好。", "Save the changes to ‘\(failure.title)’ first, or this message would not include them. Other messages in this conversation must wait too."))
                .font(.caption)
            if failure.offline {
                Text(L("当前网络不可用，恢复后会自动放行。", "The network is unavailable. Sending is unblocked once saving succeeds after reconnecting.")).font(.caption)
            }
            if failure.reason == .conflict {
                Button(L("查看最新改动", "View latest changes")) {
                    Task {
                        do { _ = try await runtime.describeConflict(); inspectionError = nil }
                        catch { inspectionError = error.localizedDescription }
                    }
                }.disabled(runtime.inspectingConflict)
                if let columns = runtime.conflictColumns {
                    Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 8) {
                        GridRow {
                            Text(L("字段", "Field")); Text(L("另一台设备", "Other device")); Text(L("我这台", "This device"))
                        }.fontWeight(.semibold)
                        ForEach(columns) { column in
                            GridRow { Text(column.label); Text(column.remote); Text(column.local) }
                        }
                    }.font(.caption).frame(maxWidth: .infinity, alignment: .leading)
                    if columns.isEmpty { Text(L("可读取的字段值相同；采用最新草稿仍会放弃本机这次编辑。", "The readable fields match. Adopting the latest draft still discards this local edit.")).font(.caption) }
                    Button(L("改用最新草稿（会放弃本机这次改动）", "Use latest draft (discards these local edits)"), role: .destructive) {
                        Task { if !(await runtime.adoptRemote()) { inspectionError = runtime.error } }
                    }
                }
            } else {
                Button(L("重试保存", "Retry saving")) { Task { await runtime.retrySaving() } }
            }
            if let inspectionError { ErrorNotice(message: inspectionError) }
        }.font(.callout).accessibilityElement(children: .contain)
    }
}
