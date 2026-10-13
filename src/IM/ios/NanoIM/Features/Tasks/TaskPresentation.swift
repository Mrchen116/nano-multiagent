import SwiftUI

func taskStatusIcon(_ status: String) -> String {
    switch status {
    case "doing": return "circle.lefthalf.filled"
    case "in_review": return "questionmark.circle"
    case "done": return "checkmark.circle.fill"
    case "paused": return "pause.circle"
    case "closed": return "nosign"
    default: return "circle"
    }
}

struct TaskStatusBadge: View {
    let status: String
    var body: some View {
        Label(taskStatus(status), systemImage: taskStatusIcon(status))
            .font(.subheadline.weight(.medium))
            .foregroundStyle(status == "closed" ? NanoTheme.muted : NanoTheme.accent)
            .padding(.horizontal, 10).padding(.vertical, 6)
            .background(status == "closed" ? NanoTheme.canvas : NanoTheme.softAccent, in: Capsule())
    }
}

struct TaskActorLabel: View {
    let actor: ActorRef?
    var size: CGFloat = 24
    var showKind = false
    var body: some View {
        HStack(spacing: 8) {
            if let actor, actor.type == "user" {
                AvatarView(name: actor.taskName, size: size)
            } else {
                Image(systemName: actor == nil ? "person" : "cpu")
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
        }.font(.subheadline).fixedSize(horizontal: false, vertical: true)
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
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 6) {
                    ForEach(taskStatuses, id: \.self) { value in
                        Button {
                            status = value; dismiss()
                        } label: {
                            HStack(spacing: 12) {
                                Image(systemName: taskStatusIcon(value)).foregroundStyle(NanoTheme.accent)
                                Text(taskStatus(value)).foregroundStyle(NanoTheme.ink)
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
        }.presentationDetents([.height(540), .large]).presentationDragIndicator(.visible)
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
