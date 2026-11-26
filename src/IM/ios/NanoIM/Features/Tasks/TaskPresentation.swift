import SwiftUI

struct TaskWaitView: View {
    let wait: TaskWait?
    let health: TaskWaitHealth?
    var compact = false
    private var hasTimer: Bool { wait?.schedule_id != nil }
    private var state: String { health?.state ?? (hasTimer ? "unknown" : "none") }

    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 4 : 8) {
            if !compact {
                Text(wait?.asked_user_id != nil
                     ? L("待回复问题", "Awaiting your reply")
                     : L("当前等待原因与复查安排", "Waiting reason and follow-up"))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.orange)
            }
            Text(wait?.reason ?? L("等待原因暂不可用", "Waiting reason unavailable"))
                .lineLimit(compact ? 2 : nil)
                .fixedSize(horizontal: false, vertical: true)
            if hasTimer {
                if state == "invalid" {
                    Text(L("安排需要处理：负责人需重新核对并安排跟进。", "Schedule needs attention. The assignee must check and arrange follow-up."))
                        .foregroundStyle(.orange)
                    Text(L("下次检查 · 暂无有效安排", "Next check · No valid schedule"))
                } else {
                    if state != "valid" && (!compact || health != nil) {
                        Text(L("暂无法核实安排，请稍后重试。", "Schedule could not be verified. Check again later."))
                            .foregroundStyle(.orange)
                    }
                    if let nextCheck = wait?.next_check_at, !nextCheck.isEmpty {
                        HStack(spacing: 4) {
                            Text(state == "valid" ? L("下次复查：", "Next check: ") : L("已保存安排：", "Saved check: "))
                                .foregroundStyle(NanoTheme.muted)
                            NanoDateTime(value: nextCheck)
                        }
                    }
                }
                if !compact {
                    Text(L("安排时间不是执行回执；以实际检查结果为准。", "A scheduled time is not an execution receipt. Check the actual outcome."))
                        .font(.footnote).foregroundStyle(NanoTheme.muted)
                }
            }
        }
        .font(compact ? .caption : .subheadline)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(compact ? 0 : 12)
        .background(compact ? Color.clear : Color.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct TaskRuntimeState: Decodable { let state: String }

struct TaskAgentRuntimeView: View {
    let client: IMClient
    let agentID: String
    let graphID: String
    let nodeID: String
    @State private var state = "unknown"
    var body: some View {
        Text(L("负责人执行状态", "Assignee execution") + " · " + (state == "offline" ? L("节点离线", "Node offline") : state == "unknown" ? L("暂无法核实", "Could not be verified") : agentWorkStatus(state)))
            .font(.footnote).foregroundStyle(NanoTheme.muted)
            .task(id: "\(graphID)/\(nodeID)/\(agentID)") {
                state = "unknown"
                while !Task.isCancelled {
                    do {
                        let observed: TaskRuntimeState = try await client.get("/im/v1/task-graphs/\(graphID.pathComponent)/runtime?node_id=\(nodeID.pathComponent)")
                        guard !Task.isCancelled else { return }
                        state = ["running", "idle", "offline"].contains(observed.state) ? observed.state : "unknown"
                    } catch { state = "unknown" }
                    try? await Task.sleep(for: .seconds(3))
                }
            }
    }
}

func taskStatusIcon(_ status: String) -> String {
    switch status {
    case "proposed": return "sparkles"
    case "todo": return "circle"
    case "doing": return "circle.lefthalf.filled"
    case "waiting": return "clock"
    case "in_review": return "eye.circle"
    case "done": return "checkmark.circle.fill"
    case "paused": return "pause.circle"
    case "backlog": return "tray"
    case "closed": return "nosign"
    default: return "circle.dashed"
    }
}

struct TaskStatusPalette {
    let background: Color
    let foreground: Color
    let border: Color
    let dashed: Bool

    static func forStatus(_ status: String) -> TaskStatusPalette {
        switch status {
        case "proposed":
            return .init(background: Color("Butter"), foreground: Color(red: 0.37, green: 0.28, blue: 0.06), border: Color(red: 0.92, green: 0.83, blue: 0.47), dashed: false)
        case "todo":
            return .init(background: NanoTheme.softAccent, foreground: NanoTheme.accent, border: NanoTheme.accent.opacity(0.28), dashed: false)
        case "doing":
            return .init(background: Color.green.opacity(0.13), foreground: Color(red: 0.14, green: 0.42, blue: 0.27), border: Color.green.opacity(0.30), dashed: false)
        case "waiting":
            return .init(background: Color.orange.opacity(0.14), foreground: Color(red: 0.60, green: 0.38, blue: 0.09), border: Color.orange.opacity(0.32), dashed: false)
        case "in_review":
            return .init(background: Color.blue.opacity(0.12), foreground: Color(red: 0.11, green: 0.36, blue: 0.55), border: Color.blue.opacity(0.28), dashed: false)
        case "backlog":
            return .init(background: NanoTheme.canvas, foreground: Color(red: 0.36, green: 0.33, blue: 0.27), border: NanoTheme.muted.opacity(0.45), dashed: true)
        case "paused":
            return .init(background: Color.secondary.opacity(0.12), foreground: Color.secondary, border: Color.secondary.opacity(0.25), dashed: false)
        case "done":
            return .init(background: Color.green.opacity(0.08), foreground: Color(red: 0.24, green: 0.39, blue: 0.29), border: Color.green.opacity(0.22), dashed: false)
        case "closed":
            return .init(background: NanoTheme.canvas, foreground: NanoTheme.muted, border: NanoTheme.border, dashed: false)
        default:
            return .init(background: NanoTheme.canvas, foreground: NanoTheme.muted, border: NanoTheme.muted.opacity(0.4), dashed: true)
        }
    }
}

/// Strictly displays one of the 9 canonical status words (or unknown fallback); wait reasons and assignees stay outside.
struct TaskStatusBadge: View {
    let status: String
    var body: some View {
        let palette = TaskStatusPalette.forStatus(status)
        Text(taskStatus(status))
            .font(.caption.weight(.bold))
            .foregroundStyle(palette.foreground)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(palette.background, in: RoundedRectangle(cornerRadius: 6))
            .overlay {
                RoundedRectangle(cornerRadius: 6)
                    .strokeBorder(palette.border, style: StrokeStyle(lineWidth: 1, dash: palette.dashed ? [4, 3] : []))
            }
            .fixedSize()
    }
}

struct TaskCrumbPill: View {
    let text: String
    var highlight = false
    var action: (() -> Void)? = nil

    var body: some View {
        if let action {
            Button(action: action) { pill }.buttonStyle(.plain)
        } else {
            pill
        }
    }

    private var pill: some View {
        Text(text)
            .font(.caption2.weight(.semibold))
            .foregroundStyle(highlight ? NanoTheme.accent : NanoTheme.muted)
            .lineLimit(1)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(highlight ? NanoTheme.softAccent : NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 6))
    }
}

struct TaskActorLabel: View {
    let actor: ActorRef?
    var size: CGFloat = 24
    var showKind = false
    var compact = false
    var body: some View {
        HStack(spacing: compact ? 5 : 8) {
            if let actor {
                AvatarView(id: .actor(actor), size: size)
            } else {
                Image(systemName: "person")
                    .font(.system(size: size * 0.5, weight: .medium))
                    .foregroundStyle(NanoTheme.accent).frame(width: size, height: size)
                    .background(NanoTheme.softAccent, in: RoundedRectangle(cornerRadius: size * 0.3))
                    .accessibilityHidden(true)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(actor?.taskName ?? L("未分配", "Unassigned")).foregroundStyle(NanoTheme.ink)
                if showKind, let actor {
                    Text(actor.type == "agent" ? "Agent" : L("真人", "Person"))
                        .font(.caption).foregroundStyle(NanoTheme.muted)
                }
            }
            if !showKind, actor?.type == "agent" { Text("Agent").font(.caption).foregroundStyle(NanoTheme.muted) }
        }.font(compact ? .caption : .subheadline).fixedSize(horizontal: false, vertical: true)
    }
}

struct TaskPropertyRow<Content: View>: View {
    let title: String
    @ViewBuilder var content: () -> Content
    var body: some View {
        HStack(alignment: .center, spacing: 16) {
            Text(title).font(.subheadline).foregroundStyle(NanoTheme.muted)
            Spacer(minLength: 8)
            content()
            Image(systemName: "chevron.down").font(.caption).foregroundStyle(NanoTheme.muted)
        }.padding(.vertical, 12).frame(minHeight: 48).contentShape(Rectangle())
    }
}

struct TaskActorPicker: View {
    let actors: [ActorRef]
    let selectedKey: String?
    var allowUnassigned = true
    var context = ""
    let select: (ActorRef?) -> Void
    @State private var query = ""
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if !context.isEmpty { Text(context).font(.subheadline).foregroundStyle(NanoTheme.muted) }
                    NanoSearchField(text: $query, prompt: L("搜索成员", "Search people or agents"))
                    if allowUnassigned && (query.isEmpty || L("未分配", "Unassigned").localizedCaseInsensitiveContains(query)) { row(nil) }
                    let matches = actors.filter { $0.is_stale != true && (query.isEmpty || $0.taskName.localizedCaseInsensitiveContains(query)) }
                    ForEach(matches, id: \.taskKey) { row($0) }
                    if matches.isEmpty && !query.isEmpty { Text(L("没有找到对应成员", "No matching members")).font(.subheadline).foregroundStyle(NanoTheme.muted).frame(maxWidth: .infinity).padding(.vertical, 24) }
                    if allowUnassigned {
                        Divider()
                        Text(L("仅限会话成员。分配不会自动开始工作。", "Conversation members only. Assignment does not start work."))
                            .font(.footnote).foregroundStyle(NanoTheme.muted).padding(.top, 4)
                    }
                }.padding(24)
            }.background(NanoTheme.surface).scrollDismissesKeyboard(.interactively)
                .navigationTitle(L("选择负责人", "Choose assignee")).navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("关闭", "Close"), systemImage: "xmark") { dismiss() }.labelStyle(.iconOnly) } }
        }.presentationDetents([.medium, .large]).presentationDragIndicator(.visible)
    }
    private func row(_ actor: ActorRef?) -> some View {
        Button {
            select(actor); dismiss()
        } label: {
            HStack(spacing: 12) {
                TaskActorLabel(actor: actor, size: 36, showKind: true)
                Spacer(minLength: 8)
                if actor?.taskKey == selectedKey { Image(systemName: "checkmark").foregroundStyle(NanoTheme.accent) }
            }.padding(12).frame(minHeight: 56).frame(maxWidth: .infinity, alignment: .leading)
                .background(actor?.taskKey == selectedKey ? NanoTheme.softAccent : NanoTheme.surface, in: RoundedRectangle(cornerRadius: 12))
                .contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityAddTraits(actor?.taskKey == selectedKey ? .isSelected : [])
    }
}

struct TaskStatusPicker: View {
    @Binding var status: String
    var originalStatus: String?
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 6) {
                    ForEach(taskEditableStatuses(originalStatus), id: \.self) { value in
                        Button {
                            status = value; dismiss()
                        } label: {
                            HStack(spacing: 12) {
                                TaskStatusBadge(status: value)
                                Spacer()
                                if status == value { Image(systemName: "checkmark").foregroundStyle(NanoTheme.accent) }
                            }.padding(14).frame(minHeight: 50)
                                .background(status == value ? NanoTheme.softAccent : NanoTheme.surface, in: RoundedRectangle(cornerRadius: 12))
                        }.buttonStyle(.plain).accessibilityAddTraits(status == value ? .isSelected : [])
                    }
                    Text(L("选择后返回编辑，保存时才会生效。", "Your selection takes effect when you save."))
                        .font(.footnote).foregroundStyle(NanoTheme.muted).padding(.top, 14)
                }.padding(24)
            }.background(NanoTheme.surface).navigationTitle(L("任务状态", "Task status")).navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("关闭", "Close"), systemImage: "xmark") { dismiss() }.labelStyle(.iconOnly) } }
        }.presentationDetents([.medium, .large]).presentationDragIndicator(.visible)
    }
}

/// Explains the 9 canonical task statuses, lifecycle flow, and page zones.
struct TaskStatusHelpSheet: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text(L("彩色状态框固定只有以下 9 个状态词；等待原因、复查时间与负责人独立显示在状态框旁边。",
                           "Status badges strictly use these 9 canonical words; wait reasons, check times, and assignees appear alongside."))
                        .font(.footnote).foregroundStyle(NanoTheme.muted)

                    VStack(alignment: .leading, spacing: 12) {
                        Text(L("1. 状态流转主线（从想法到完成）", "1. Primary lifecycle (from proposal to done)"))
                            .font(.subheadline.bold())
                        flowRow("proposed", arrow: L("批准 →", "Approve →"), note: L("助手提议 · 未批不执行", "Proposed · never auto-runs"))
                        flowRow("todo", arrow: L("动手 →", "Start →"), note: L("已定要做 · 排队待开工", "Queued and ready"))
                        flowRow("doing", arrow: L("交成果 →", "Submit →"), note: L("你或助手正在推进", "Actively advancing"))
                        flowRow("in_review", arrow: L("确认 →", "Confirm →"), note: L("等你扫一眼验收", "Awaiting confirmation"))
                        flowRow("done", arrow: nil, note: L("彻底搞定", "Completed"))
                    }
                    .padding(14)
                    .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 14))

                    VStack(alignment: .leading, spacing: 10) {
                        Text(L("2. 旁路留存与中途等待", "2. Stashing, waiting, and pausing"))
                            .font(.subheadline.bold())
                        branchRow("backlog", text: L("暂不排期、收进「先存着」免催促，随时可点「提上日程」回待办。", "Saved without reminders; tap Schedule anytime to move to To do."))
                        branchRow("waiting", text: L("卡在外部条件（如跨天定时复查或等你回话拍板）。", "Waiting on a scheduled check or a person's reply."))
                        branchRow("paused", text: L("推进中途被人工暂缓（如 /stop），等待明确恢复。", "Explicitly paused mid-work until resumed."))
                        branchRow("closed", text: L("决定不做，或探索后归档保留负结果的分支。", "Declined or archived exploration branch."))
                    }
                    .padding(14)
                    .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 14))

                    VStack(alignment: .leading, spacing: 10) {
                        Text(L("3. 页面分区说明", "3. Focus desk zones"))
                            .font(.subheadline.bold())
                        zoneRow(title: L("① 顶部候选池（待你拍板 ⇄ 先存着）", "① Top pool (Needs decision ⇄ Stashed)"),
                                badges: ["proposed", "in_review", "backlog", "paused"],
                                detail: L("等拿主意的事项与暂不急做的点子并列一键切换。", "Switch between items needing your call and stashed ideas."))
                        zoneRow(title: L("② 进行中（当前行动主区）", "② Active (Current actions)"),
                                badges: ["doing", "todo", "waiting"],
                                detail: L("已在日程上的具体步骤；长线目标当下正在推进的阶段也会自动出现在这里。", "Active leaf steps, including the current stage of multi-step goals."))
                        zoneRow(title: L("③ 底部折叠（已完结）", "③ Completed history"),
                                badges: ["done", "closed"],
                                detail: L("已完成或关闭的历史事项收在底部，平时不占视线。", "Completed and closed items stay folded at the bottom."))
                    }
                    .padding(14)
                    .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 14))
                }
                .padding(20)
            }
            .background(NanoTheme.surface)
            .navigationTitle(L("状态与分区说明", "Statuses & zones"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(L("关闭", "Close")) { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }

    private func flowRow(_ status: String, arrow: String?, note: String) -> some View {
        HStack(spacing: 10) {
            TaskStatusBadge(status: status)
            Text(note).font(.caption).foregroundStyle(NanoTheme.muted)
            Spacer()
            if let arrow {
                Text(arrow).font(.caption2.weight(.semibold)).foregroundStyle(NanoTheme.accent)
            }
        }
    }

    private func branchRow(_ status: String, text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            TaskStatusBadge(status: status)
            Text(text).font(.caption).foregroundStyle(NanoTheme.muted).fixedSize(horizontal: false, vertical: true)
        }
    }

    private func zoneRow(title: String, badges: [String], detail: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.caption.bold()).foregroundStyle(NanoTheme.ink)
            HStack(spacing: 6) {
                ForEach(badges, id: \.self) { TaskStatusBadge(status: $0) }
            }
            Text(detail).font(.caption).foregroundStyle(NanoTheme.muted)
        }
    }
}

struct TaskConflictView: View {
    let conflict: TaskConflict
    let confirm: (TaskDraft) -> Void
    @State private var choices: [TaskEditField: Bool] = [:]
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Label(L("这项任务有新的修改", "This task has new changes"), systemImage: "arrow.triangle.branch")
                    .font(.subheadline).foregroundStyle(NanoTheme.accent)
                Text(conflict.fields.isEmpty ? L("更新已合并，等待确认", "Updates merged, ready to confirm") : L("确认本次保存的内容", "Choose what to save"))
                    .font(.title2.bold())
                Text(L("你的编辑已保留。确认后才会保存。", "Your edits are retained. Nothing is saved until you confirm."))
                    .foregroundStyle(NanoTheme.muted)
                ForEach(conflict.fields) { field in
                    VStack(alignment: .leading, spacing: 10) {
                        Text(field.label).font(.subheadline.weight(.semibold)).foregroundStyle(NanoTheme.muted)
                        choice(field, mine: true)
                        choice(field, mine: false)
                    }
                }
                if !conflict.retained.isEmpty {
                    summary(L("保留你的修改", "Keeping your changes"), fields: conflict.retained, draft: conflict.mine)
                }
                if !conflict.adopted.isEmpty {
                    summary(L("同时采用最新内容", "Including the latest changes"), fields: conflict.adopted, draft: conflict.latest)
                }
            }.padding(24)
        }.background(NanoTheme.surface).navigationTitle(L("确认更新", "Review changes")).navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .bottom) {
                Button { if let draft = conflict.resolved(keepingMine: choices) { confirm(draft) } } label: {
                    Text(L("确认并保存", "Confirm and save")).font(.headline).frame(maxWidth: .infinity).padding(.vertical, 10)
                }.buttonStyle(.borderedProminent).disabled(conflict.resolved(keepingMine: choices) == nil).padding(20).background(NanoTheme.surface)
            }
    }
    private func choice(_ field: TaskEditField, mine: Bool) -> some View {
        Button { choices[field] = mine } label: {
            VStack(alignment: .leading, spacing: 10) {
                Label(mine ? L("我的修改", "My changes") : L("最新内容", "Latest content"), systemImage: choices[field] == mine ? "checkmark.circle.fill" : "circle")
                    .font(.subheadline.weight(.semibold)).foregroundStyle(NanoTheme.accent)
                Text(field.display(in: mine ? conflict.mine : conflict.latest)).foregroundStyle(NanoTheme.ink).textSelection(.enabled)
            }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
                .background(choices[field] == mine ? NanoTheme.softAccent : NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 12))
                .contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityAddTraits(choices[field] == mine ? .isSelected : [])
    }
    private func summary(_ title: String, fields: [TaskEditField], draft: TaskDraft) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Divider()
            Text(title).font(.headline)
            ForEach(fields) { field in
                VStack(alignment: .leading, spacing: 4) {
                    Text(field.label).font(.caption).foregroundStyle(NanoTheme.muted)
                    Text(field.display(in: draft)).textSelection(.enabled)
                }
            }
        }
    }
}

struct TaskSubtaskLabel: View {
    let counts: TaskCounts?
    var body: some View {
        HStack(spacing: 5) {
            if let counts, counts.total > 0 {
                Text(L("子脉络 \(counts.done)/\(counts.total)", "Subtasks \(counts.done)/\(counts.total)"))
            } else {
                Text(L("进入子脉络", "Open sub-scope"))
            }
            Image(systemName: "chevron.right").font(.caption2)
        }.font(.caption.weight(.semibold)).foregroundStyle(NanoTheme.accent).padding(.vertical, 4)
            .accessibilityLabel(counts.map { $0.total > 0 ? $0.summary : L("查看子任务", "View subtasks") } ?? L("查看子任务", "View subtasks"))
    }
}
