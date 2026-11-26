import SwiftUI

struct TaskDetailLoader: View {
    let client: IMClient
    let graphID: String
    let nodeID: String
    let onReference: (String, String) -> Void
    var onOpenGraph: ((String, String?) -> Void)? = nil
    @State private var graph: TaskGraph?
    @State private var error: String?

    var body: some View {
        Group {
            if let graph {
                TaskNodeView(client: client, graph: graph, nodeID: nodeID, onReference: onReference, onOpenGraph: onOpenGraph)
            } else if let error {
                ContentUnavailableView(L("任务不可用", "Task unavailable"), systemImage: "exclamationmark.circle", description: Text(error))
            } else {
                ProgressView()
            }
        }
        .task {
            do { graph = try await client.taskGraph(graphID) }
            catch { self.error = error.localizedDescription }
        }
    }
}

/// Mobile-first vertical stage spine for multi-stage goals and nested exploration scopes.
struct TaskGraphView: View {
    let client: IMClient
    let graphID: String
    var scopeID: String? = nil
    var initialNodeID: String? = nil
    let onReference: (String, String) -> Void

    @State private var graph: TaskGraph?
    @State private var selected: TaskNode?
    @State private var error: String?
    @State private var creating = false
    @State private var showingHelp = false
    @State private var visible = true
    @State private var browsingScopeID: String?
    @State private var completedStagesExpanded = false
    @State private var busyNodeIDs: Set<String> = []
    @Environment(\.openTaskOverview) private var openOverview
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var phase

    var body: some View {
        Group {
            if let graph, let root = graph.rootNode,
               let scope = graph.nodes.first(where: { $0.id == (browsingScopeID ?? scopeID ?? graph.root_node_id) }) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        breadcrumbBar(scope: scope, graph: graph)
                        northStarBanner(root: root, scope: scope, graph: graph)
                        if let error { ErrorNotice(message: error) }
                        verticalStageSpine(scope: scope, graph: graph)
                    }
                    .padding(14)
                    .padding(.bottom, 28)
                }
                .background(NanoTheme.canvas)
            } else if graph != nil {
                ContentUnavailableView(L("任务不可用", "Task unavailable"), systemImage: "exclamationmark.circle",
                                       description: Text(L("该层级已被删除或无法访问。", "This scope was deleted or is inaccessible.")))
            } else if let error {
                ContentUnavailableView {
                    Label(L("任务不可用", "Task unavailable"), systemImage: "exclamationmark.circle")
                } description: {
                    Text(error)
                } actions: {
                    Button(L("重试", "Retry")) { Task { await load() } }
                }
            } else {
                ProgressView()
            }
        }
        .navigationTitle(graph?.rootNode?.title ?? L("目标脉络", "Goal map"))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.hidden, for: .tabBar)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button { showingHelp = true } label: { Image(systemName: "questionmark.circle") }
                    .accessibilityLabel(L("状态说明", "Status guide"))
                if graph?.conversation.can_write == true {
                    Button { creating = true } label: { Image(systemName: "plus") }
                        .accessibilityLabel(L("添加子任务", "Add subtask"))
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .nanoTaskGraphChanged)) { note in
            guard (note.object as? IMClient) === client || note.object == nil else { return }
            Task { await load() }
        }
        .task(id: "\(phase == .active)-\(visible)") {
            guard phase == .active, visible else { return }
            while !Task.isCancelled {
                await load()
                try? await Task.sleep(for: .seconds(3))
            }
        }
        .onAppear { visible = true }
        .onDisappear { visible = false }
        .sheet(isPresented: $showingHelp) { TaskStatusHelpSheet() }
        .sheet(isPresented: $creating) {
            if let graph {
                NavigationStack {
                    TaskEditorView(client: client, graph: graph, node: nil,
                                   parentID: browsingScopeID ?? scopeID ?? graph.root_node_id) {
                        creating = false
                        Task { await load() }
                    }
                }
            }
        }
        .sheet(item: $selected, onDismiss: { Task { await load() } }) { node in
            if let graph {
                NavigationStack {
                    TaskNodeView(client: client, graph: graph, nodeID: node.id, onReference: { chatID, text in
                        selected = nil
                        onReference(chatID, text)
                    }, onOpenGraph: { _, targetScope in
                        selected = nil
                        if let targetScope { browsingScopeID = targetScope }
                    })
                }
            }
        }
    }

    private func breadcrumbBar(scope: TaskNode, graph: TaskGraph) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                Button(L("任务焦点台", "Focus desk")) {
                    if let openOverview { openOverview() } else { dismiss() }
                }
                .foregroundStyle(NanoTheme.accent)

                ForEach(ancestorPath(scope, graph: graph)) { item in
                    Image(systemName: "chevron.right").font(.caption2).foregroundStyle(NanoTheme.muted)
                    if item.id != scope.id {
                        Button(item.title) { browsingScopeID = item.id }
                            .foregroundStyle(NanoTheme.accent)
                    } else {
                        Text(item.title).fontWeight(.semibold).foregroundStyle(NanoTheme.ink)
                    }
                }
            }
            .font(.caption)
        }
    }

    private func northStarBanner(root: TaskNode, scope: TaskNode, graph: TaskGraph) -> some View {
        let counts = scope.direct_counts
        let goalDescription = !root.description.isEmpty ? root.description : scope.description
        return VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                TaskStatusBadge(status: root.status)
                Text(L("长线目标", "Long-term goal"))
                    .font(.caption.weight(.bold))
                    .foregroundStyle(NanoTheme.accent)
                Spacer()
                Button(L("详情", "Details")) { selected = scope }
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(NanoTheme.accent)
            }

            Text(root.title)
                .font(.headline)
                .foregroundStyle(NanoTheme.ink)
                .fixedSize(horizontal: false, vertical: true)

            if scope.id != root.id {
                Text(L("当前子脉络：", "Current sub-scope: ") + scope.title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(NanoTheme.accent)
            }

            if !goalDescription.isEmpty {
                Text(goalDescription)
                    .font(.caption)
                    .foregroundStyle(NanoTheme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let counts, counts.total > 0 {
                ProgressView(value: Double(counts.done), total: Double(max(1, counts.total)))
                    .tint(NanoTheme.accent)
                Text(counts.summary)
                    .font(.caption2)
                    .foregroundStyle(NanoTheme.muted)
            }

            HStack(spacing: 10) {
                Button { onReference(graph.conversation.id, "") } label: {
                    Label(L("回聊天讨论", "Discuss in chat"), systemImage: "bubble.left")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(NanoTheme.accent)
                        .padding(.horizontal, 11)
                        .padding(.vertical, 6)
                        .background(NanoTheme.softAccent, in: Capsule())
                }
                .buttonStyle(.plain)

                if graph.conversation.can_write {
                    Button { creating = true } label: {
                        Label(L("+ 子任务", "+ Subtask"), systemImage: "plus")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(NanoTheme.ink)
                            .padding(.horizontal, 11)
                            .padding(.vertical, 6)
                            .background(NanoTheme.canvas, in: Capsule())
                    }
                    .buttonStyle(.plain)
                }
                Spacer()
                Text(graph.conversation.title)
                    .font(.caption2)
                    .foregroundStyle(NanoTheme.muted)
                    .lineLimit(1)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 15))
        .overlay { RoundedRectangle(cornerRadius: 15).stroke(NanoTheme.accent.opacity(0.28), lineWidth: 1) }
    }

    @ViewBuilder
    private func verticalStageSpine(scope: TaskNode, graph: TaskGraph) -> some View {
        let layers = graph.stageLayers(scopeID: scope.id)
        if layers.isEmpty {
            singleScopeCard(scope: scope, graph: graph)
        } else if scope.mode == "explore" {
            VStack(alignment: .leading, spacing: 8) {
                Label(L("探索选型脉络 · 保留对比分支与负结果", "Exploration candidates · preserves archived directions"),
                      systemImage: "arrow.triangle.branch")
                    .font(.caption)
                    .foregroundStyle(NanoTheme.muted)
                let children = graph.directChildren(of: scope.id)
                VStack(spacing: 0) {
                    ForEach(Array(children.enumerated()), id: \.element.id) { index, node in
                        spineRow(isLast: index == children.count - 1, status: node.status) {
                            stageNodeCard(node: node, stageIndex: nil, scope: scope, graph: graph)
                        }
                    }
                }
            }
        } else {
            let leadingDoneCount = leadingCompletedStageCount(layers)
            VStack(alignment: .leading, spacing: 0) {
                if leadingDoneCount > 0 {
                    let foldRows = layers.prefix(leadingDoneCount)
                    spineRow(isLast: false, status: "done") {
                        VStack(alignment: .leading, spacing: 8) {
                            Button {
                                withAnimation(.easeInOut(duration: 0.18)) {
                                    completedStagesExpanded.toggle()
                                }
                            } label: {
                                HStack {
                                    TaskStatusBadge(status: "done")
                                    Text(L("前序 \(leadingDoneCount) 个已完成阶段", "Earlier \(leadingDoneCount) completed stages"))
                                        .font(.caption.weight(.bold))
                                        .foregroundStyle(NanoTheme.ink)
                                    Spacer()
                                    Text(completedStagesExpanded ? L("收起 ▴", "Hide ▴") : L("展开查看 ›", "Expand ›"))
                                        .font(.caption.weight(.semibold))
                                        .foregroundStyle(NanoTheme.accent)
                                }
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)

                            if completedStagesExpanded {
                                Divider()
                                ForEach(Array(foldRows.enumerated()), id: \.offset) { idx, stageNodes in
                                    ForEach(stageNodes) { node in
                                        stageNodeCard(node: node, stageIndex: idx + 1, scope: scope, graph: graph, nested: true)
                                    }
                                }
                            } else {
                                let titles = foldRows.flatMap { $0.map(\.title) }.joined(separator: " → ")
                                Text(titles)
                                    .font(.caption)
                                    .foregroundStyle(NanoTheme.muted)
                                    .lineLimit(2)
                            }
                        }
                        .padding(12)
                        .background(NanoTheme.surface.opacity(0.88), in: RoundedRectangle(cornerRadius: 13))
                        .overlay { RoundedRectangle(cornerRadius: 13).stroke(NanoTheme.border, lineWidth: 1) }
                    }
                }

                let remaining = Array(layers.enumerated().dropFirst(leadingDoneCount))
                ForEach(Array(remaining.enumerated()), id: \.element.offset) { remIndex, pair in
                    let stageNumber = pair.offset + 1
                    let stageNodes = pair.element
                    let primaryStatus = stageNodes.first?.status ?? "todo"
                    spineRow(isLast: remIndex == remaining.count - 1, status: primaryStatus) {
                        VStack(spacing: 8) {
                            ForEach(stageNodes) { node in
                                stageNodeCard(node: node, stageIndex: stageNumber, scope: scope, graph: graph)
                            }
                        }
                    }
                }
            }
        }
    }

    private func leadingCompletedStageCount(_ layers: [[TaskNode]]) -> Int {
        guard layers.count > 1 else { return 0 }
        var count = 0
        for layer in layers.dropLast() {
            if layer.allSatisfy({ ["done", "closed"].contains($0.status) }) {
                count += 1
            } else {
                break
            }
        }
        return count
    }

    private func spineRow<Content: View>(isLast: Bool, status: String, @ViewBuilder content: () -> Content) -> some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(spacing: 0) {
                Circle()
                    .fill(dotColor(for: status))
                    .frame(width: 11, height: 11)
                    .overlay {
                        Circle().stroke(NanoTheme.surface, lineWidth: 2)
                    }
                    .padding(.top, 14)
                if !isLast {
                    Rectangle()
                        .fill(NanoTheme.border)
                        .frame(width: 2)
                        .frame(maxHeight: .infinity)
                }
            }
            .frame(width: 14)

            content()
                .padding(.bottom, isLast ? 0 : 12)
        }
    }

    private func dotColor(for status: String) -> Color {
        switch status {
        case "done": return .green
        case "proposed": return Color(red: 0.87, green: 0.66, blue: 0.16)
        case "doing", "in_review": return NanoTheme.accent
        case "waiting": return .orange
        default: return NanoTheme.muted.opacity(0.65)
        }
    }

    private func stageNodeCard(node: TaskNode, stageIndex: Int?, scope: TaskNode, graph: TaskGraph, nested: Bool = false) -> some View {
        let childCount = graph.directChildren(of: node.id).count
        let hasSubscope = childCount > 0 || node.mode != "none"
        let prereqBlocked = node.isPrereqBlocked(in: graph)
        let isSelectedCandidate = scope.selected_candidate_id == node.id
        let isBusy = busyNodeIDs.contains(node.id)
        let isSprout = node.status == "proposed"

        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                TaskStatusBadge(status: node.status)
                if let stageIndex {
                    Text(stageLabel(stageIndex: stageIndex, status: node.status, prereqBlocked: prereqBlocked))
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(node.status == "doing" ? NanoTheme.accent : NanoTheme.muted)
                } else if isSelectedCandidate {
                    Label(L("已选定方案", "Selected"), systemImage: "checkmark.circle.fill")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(.green)
                } else if scope.mode == "explore" && node.status == "closed" {
                    Text(L("未采用", "Archived")).font(.caption2).foregroundStyle(NanoTheme.muted)
                }
                Spacer()
                Button { selected = node } label: {
                    Text(L("详情/编辑 ›", "Details ›"))
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(NanoTheme.accent)
                }
                .buttonStyle(.plain)
            }

            Button { selected = node } label: {
                VStack(alignment: .leading, spacing: 5) {
                    Text(node.title)
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(NanoTheme.ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if !node.description.isEmpty {
                        Text(node.description).font(.caption).foregroundStyle(NanoTheme.muted).lineLimit(2)
                    }
                    if let derivedID = node.derived_from_id,
                       let source = graph.nodes.first(where: { $0.id == derivedID }) {
                        Text(L("衍生自：", "Derived from: ") + source.title)
                            .font(.caption2).foregroundStyle(NanoTheme.muted)
                    }
                    if node.status == "waiting" {
                        TaskWaitView(wait: node.wait, health: node.wait_health, compact: true)
                    }
                    TaskActorLabel(actor: node.assignee, size: 20, compact: true)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if hasSubscope {
                Button { browsingScopeID = node.id } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.turn.down.right")
                        Text(childCount > 0 ? L("进入子脉络 (\(childCount)) ›", "Open sub-scope (\(childCount)) ›") : L("进入子脉络 ›", "Open sub-scope ›"))
                    }
                    .font(.caption.weight(.bold))
                    .foregroundStyle(NanoTheme.accent)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(NanoTheme.softAccent, in: Capsule())
                }
                .buttonStyle(.plain)
            }

            if graph.conversation.can_write && node.can_edit != false {
                if node.status == "proposed" {
                    HStack(spacing: 8) {
                        Button {
                            Task { await approveNode(node, in: graph) }
                        } label: {
                            Text(prereqBlocked ? L("批准立项", "Approve to queue") : L("批准开工", "Approve & start"))
                                .font(.caption.weight(.bold))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(NanoTheme.accent, in: Capsule())
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)

                        Button {
                            Task { await setNodeStatus(node, status: "backlog", in: graph) }
                        } label: {
                            Text(L("先存着", "Stash"))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(NanoTheme.ink)
                                .padding(.horizontal, 11)
                                .padding(.vertical, 6)
                                .background(NanoTheme.canvas, in: Capsule())
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)

                        Button {
                            Task { await setNodeStatus(node, status: "closed", in: graph) }
                        } label: {
                            Text(L("关闭", "Close"))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(NanoTheme.muted)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 6)
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)
                    }
                } else if node.status == "backlog" {
                    Button {
                        Task { await setNodeStatus(node, status: "todo", in: graph) }
                    } label: {
                        Text(L("↑ 提上日程", "↑ Schedule"))
                            .font(.caption.weight(.bold))
                            .foregroundStyle(NanoTheme.accent)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(NanoTheme.softAccent, in: Capsule())
                    }
                    .buttonStyle(.plain)
                    .disabled(isBusy)
                }
            }
        }
        .padding(nested ? 10 : 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(nested ? NanoTheme.canvas : NanoTheme.surface, in: RoundedRectangle(cornerRadius: 13))
        .overlay {
            if !nested {
                RoundedRectangle(cornerRadius: 13)
                    .strokeBorder(
                        isSprout ? Color(red: 0.87, green: 0.66, blue: 0.16) : (node.status == "doing" ? NanoTheme.accent : NanoTheme.border),
                        style: StrokeStyle(lineWidth: node.status == "doing" || isSprout ? 1.4 : 1, dash: isSprout ? [5, 3] : [])
                    )
            }
        }
    }

    private func stageLabel(stageIndex: Int, status: String, prereqBlocked: Bool) -> String {
        if status == "doing" { return L("阶段 \(stageIndex) · 当前前沿", "Stage \(stageIndex) · Frontier") }
        if status == "proposed" { return L("阶段 \(stageIndex) · 候选下一步", "Stage \(stageIndex) · Candidate") }
        if status == "todo" && prereqBlocked { return L("阶段 \(stageIndex) · 等前置完成", "Stage \(stageIndex) · Queued") }
        return L("阶段 \(stageIndex)", "Stage \(stageIndex)")
    }

    private func singleScopeCard(scope: TaskNode, graph: TaskGraph) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            stageNodeCard(node: scope, stageIndex: nil, scope: scope, graph: graph)
            if graph.conversation.can_write {
                Button { creating = true } label: {
                    Label(L("拆分为多阶段子任务", "Break into stage subtasks"), systemImage: "plus.circle")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(NanoTheme.accent)
                }
            }
        }
    }

    private func ancestorPath(_ node: TaskNode, graph: TaskGraph) -> [TaskNode] {
        var path = [node]
        while let parentID = path.first?.container_id, let parent = graph.nodes.first(where: { $0.id == parentID }) {
            path.insert(parent, at: 0)
        }
        return path
    }

    private func approveNode(_ node: TaskNode, in graph: TaskGraph) async {
        busyNodeIDs.insert(node.id)
        defer { busyNodeIDs.remove(node.id) }
        do {
            try await client.approveTask(graphID: graph.graph_id, revision: graph.revision, nodeID: node.id)
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func setNodeStatus(_ node: TaskNode, status: String, in graph: TaskGraph) async {
        busyNodeIDs.insert(node.id)
        defer { busyNodeIDs.remove(node.id) }
        do {
            try await client.applyTask(graph, operations: [TaskOperations.setStatus(nodeID: node.id, status: status)], key: UUID().uuidString)
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func load() async {
        guard selected == nil, !creating else { return }
        do {
            let value = try await client.taskGraph(graphID)
            try Task.checkCancellation()
            guard selected == nil, !creating else { return }
            guard value.schema_version == 2 else {
                graph = nil
                error = L("暂不支持此任务图版本。", "Unsupported task graph version.")
                return
            }
            let first = graph == nil
            graph = value
            error = nil
            if first, let initialNodeID {
                selected = value.nodes.first { $0.id == initialNodeID }
            }
        } catch is CancellationError {
        } catch {
            guard selected == nil, !creating else { return }
            self.error = error.localizedDescription
            if [403, 404].contains((error as? APIError)?.status ?? 0) {
                graph = nil
                selected = nil
            }
        }
    }
}

private func referenceText(_ node: TaskNode, graph: TaskGraph, base: URL) -> String {
    var url = URLComponents(url: base, resolvingAgainstBaseURL: false)!
    url.path = "/tasks/\(graph.graph_id)"
    url.queryItems = [.init(name: "node", value: node.id)]
    return "[\(node.title)](\(url.url!.absoluteString))"
}

/// Stage-adaptive detail sheet for any task card or graph node.
struct TaskNodeView: View {
    let client: IMClient
    let graph: TaskGraph
    let nodeID: String
    let onReference: (String, String) -> Void
    var onOpenGraph: ((String, String?) -> Void)? = nil

    @Environment(\.dismiss) private var dismiss
    @State private var updatedGraph: TaskGraph?
    @State private var editing = false
    @State private var confirmDelete = false
    @State private var claimReason = ""
    @State private var claiming = false
    @State private var busy = false
    @State private var error: String?

    private var currentGraph: TaskGraph { updatedGraph ?? graph }

    var body: some View {
        if let node = currentGraph.nodes.first(where: { $0.id == nodeID }) {
            let graph = currentGraph
            let root = graph.rootNode
            let prereqBlocked = node.isPrereqBlocked(in: graph)
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if let error {
                        ErrorNotice(message: error)
                        Button(L("读取最新内容", "Read latest content")) { Task { await refresh() } }
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        if let root, root.id != node.id {
                            TaskCrumbPill(text: L("所属目标：", "Goal: ") + root.title, highlight: true) {
                                if let onOpenGraph {
                                    onOpenGraph(graph.graph_id, node.container_id ?? root.id)
                                }
                            }
                        } else {
                            Button { onReference(graph.conversation.id, "") } label: {
                                HStack(spacing: 5) {
                                    Label(graph.conversation.title, systemImage: "bubble.left.and.bubble.right")
                                    Image(systemName: "arrow.up.right").font(.caption2)
                                }
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(NanoTheme.accent)
                            }
                            .buttonStyle(.plain)
                        }

                        Text(node.title)
                            .font(.title3.bold())
                            .foregroundStyle(NanoTheme.ink)
                            .textSelection(.enabled)

                        HStack(spacing: 12) {
                            TaskStatusBadge(status: node.status)
                            TaskActorLabel(actor: node.assignee)
                        }

                        if !graph.conversation.can_write {
                            Label(graph.conversation.dissolved_at != nil
                                  ? L("已解散群 · 历史只读", "Dissolved group · read-only history")
                                  : L("加入所属群后可修改", "Join the owning group to edit"),
                                  systemImage: "lock")
                                .font(.caption).foregroundStyle(NanoTheme.muted)
                        }
                    }

                    if node.assignee?.type == "agent", let agentID = node.assignee?.id {
                        TaskAgentRuntimeView(client: client, agentID: agentID, graphID: graph.graph_id, nodeID: node.id)
                    }

                    if node.status == "proposed" {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(L("提议事项 · 你点批准前不会自动执行", "Proposed item · Nothing runs until you approve"))
                                .font(.caption.weight(.bold))
                                .foregroundStyle(Color(red: 0.37, green: 0.28, blue: 0.06))
                            if node.can_edit == true {
                                HStack(spacing: 8) {
                                    Button(prereqBlocked ? L("批准立项", "Approve to queue") : L("批准开工", "Approve & start")) {
                                        Task { await approve() }
                                    }
                                    .buttonStyle(.borderedProminent)
                                    Button(L("先存着", "Stash")) { Task { await changeStatus("backlog") } }
                                        .buttonStyle(.bordered)
                                    Button(L("不采纳", "Dismiss")) { Task { await changeStatus("closed") } }
                                        .buttonStyle(.bordered)
                                }
                                .controlSize(.small)
                                .disabled(busy)
                            }
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color("Butter").opacity(0.45), in: RoundedRectangle(cornerRadius: 13))
                    }

                    if node.status == "waiting" {
                        TaskWaitView(wait: node.wait, health: node.wait_health)
                    }

                    if node.can_edit == true && ["waiting", "paused", "backlog", "in_review"].contains(node.status) {
                        HStack(spacing: 8) {
                            if node.status == "in_review" {
                                Button(L("确认完成", "Confirm done")) { Task { await changeStatus("done") } }
                                    .buttonStyle(.borderedProminent)
                            }
                            if node.status == "backlog" {
                                Button(L("↑ 提上日程", "↑ Schedule")) { Task { await changeStatus("todo") } }
                                    .buttonStyle(.borderedProminent)
                            }
                            if ["waiting", "paused"].contains(node.status) {
                                Button(L("恢复推进", "Resume")) { Task { await changeStatus("doing") } }
                                    .buttonStyle(.bordered)
                            }
                            if node.status == "waiting" {
                                Button(L("暂缓", "Pause")) { Task { await changeStatus("paused") } }
                                    .buttonStyle(.bordered)
                            }
                            if ["waiting", "paused"].contains(node.status) {
                                Button(L("先存着", "Stash")) { Task { await changeStatus("backlog") } }
                                    .buttonStyle(.bordered)
                            }
                        }
                        .controlSize(.small)
                        .disabled(busy)
                    }

                    if node.can_claim == true && node.status != "proposed" {
                        Button(L("领取任务", "Claim task")) {
                            if node.status == "done" { claiming = true } else { Task { await claim() } }
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                        .disabled(busy)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        taskSectionLabel(node.id == graph.root_node_id && (node.mode != "none" || graph.nodes.count > 1)
                                         ? L("目标说明", "Goal description")
                                         : L("任务说明", "Task description"))
                        if !node.description.isEmpty {
                            MarkdownView(text: node.description, client: client)
                        } else {
                            Text(L("暂无说明", "No description"))
                                .font(.caption).foregroundStyle(NanoTheme.muted)
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 13))

                    if !node.result.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            taskSectionLabel(["done", "closed"].contains(node.status)
                                             ? L("最终结果", "Final outcome")
                                             : L("当前进展", "Current progress"))
                            MarkdownView(text: node.result, client: client)
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 13))
                    }

                    if node.mode != "none" || (node.direct_counts?.total ?? 0) > 0 {
                        NavigationLink {
                            TaskGraphView(client: client, graphID: graph.graph_id, scopeID: node.id, onReference: onReference)
                        } label: {
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text(L("阶段子脉络", "Subtasks")).foregroundStyle(NanoTheme.ink).font(.subheadline.bold())
                                    Spacer()
                                    if let counts = node.direct_counts {
                                        Text(L("已完成 \(counts.done) / \(counts.total)", "\(counts.done) / \(counts.total) done"))
                                            .font(.caption)
                                    }
                                    Image(systemName: "chevron.right").font(.caption)
                                }
                                if let counts = node.direct_counts, counts.total > 0 {
                                    ProgressView(value: Double(counts.done), total: Double(counts.total))
                                }
                            }
                            .padding(14)
                            .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 13))
                        }
                        .buttonStyle(.plain)
                    } else if node.can_edit == true {
                        Button {
                            Task { await expandSingleCardToGoal() }
                        } label: {
                            Label(L("拆成多步目标图", "Expand into multi-step goal"), systemImage: "point.3.connected.trianglepath.dotted")
                                .font(.subheadline.weight(.semibold))
                        }
                        .disabled(busy)
                    }

                    let prereqs = graph.nodes.filter { child in graph.dependencies.contains { $0.from == child.id && $0.to == node.id } }
                    let successors = graph.nodes.filter { child in graph.dependencies.contains { $0.to == child.id && $0.from == node.id } }
                    if !prereqs.isEmpty || !successors.isEmpty || node.derived_from_id != nil || node.selected_candidate_id != nil {
                        VStack(alignment: .leading, spacing: 10) {
                            taskSectionLabel(L("所属目标前后置阶段", "Prerequisite & successor stages"))
                            related(prereqs, title: L("前置", "Prerequisite"))
                            related(successors, title: L("后续", "Successor"))
                            if let derived = node.derived_from_id {
                                related(graph.nodes.filter { $0.id == derived }, title: L("派生来源", "Derived from"))
                            }
                            if let chosen = node.selected_candidate_id {
                                related(graph.nodes.filter { $0.id == chosen }, title: L("已选候选", "Selected candidate"))
                            }
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 13))
                    }

                    DisclosureGroup {
                        VStack(alignment: .leading, spacing: 12) {
                            LabeledContent(L("创建者", "Creator"), value: node.created_by?.taskName ?? "—")
                            LabeledContent(L("修改者", "Updated by"), value: node.updated_by_actor?.taskName ?? node.updated_by)
                            if let note = node.change_note, !note.isEmpty {
                                taskSectionLabel(L("变更说明", "Change note"))
                                Text(note).textSelection(.enabled)
                            }
                            if !node.selection_reason.isEmpty {
                                taskSectionLabel(L("选择理由", "Selection reason"))
                                Text(node.selection_reason).textSelection(.enabled)
                            }
                            ForEach(node.links, id: \.self) { text in
                                if let url = URL(string: text), ["http", "https"].contains(url.scheme ?? "") {
                                    Link(text, destination: url)
                                }
                            }
                        }
                        .font(.subheadline)
                        .padding(.top, 10)
                    } label: {
                        Text(L("创建与修改信息", "Creation and changes")).font(.subheadline).foregroundStyle(NanoTheme.muted)
                    }

                    Button {
                        onReference(node.last_chat_id ?? graph.conversation.id, referenceText(node, graph: graph, base: client.baseURL))
                    } label: {
                        Label(L("回聊天讨论并引用", "Discuss & reference in chat"), systemImage: "arrowshape.turn.up.left")
                    }
                    .font(.subheadline.weight(.semibold))
                }
                .padding(20)
            }
            .background(NanoTheme.surface)
            .safeAreaInset(edge: .bottom) {
                if node.can_edit == true {
                    Button { editing = true } label: {
                        Label(L("编辑任务", "Edit task"), systemImage: "square.and.pencil")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(busy)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(NanoTheme.surface)
                }
            }
            .sheet(isPresented: $editing, onDismiss: { Task { await refresh() } }) {
                NavigationStack {
                    TaskEditorView(client: client, graph: graph, node: node, parentID: nil) {
                        editing = false
                        Task { await refresh() }
                    }
                }
            }
            .confirmationDialog(L("删除任务及整个子树？", "Delete this task and its entire subtree?"), isPresented: $confirmDelete, titleVisibility: .visible) {
                Button(L("删除 \(subtreeCount) 个节点", "Delete \(subtreeCount) nodes"), role: .destructive) { Task { await delete() } }
            } message: {
                Text(L("范围包含「\(node.title)」及全部后代，共 \(subtreeCount) 个节点。删除后无法恢复。",
                       "This removes \(node.title) and all descendants (\(subtreeCount) nodes). This cannot be undone."))
            }
            .alert(L("填写返工原因", "Rework reason"), isPresented: $claiming) {
                TextField(L("返工原因", "Reason"), text: $claimReason)
                Button(L("取消", "Cancel"), role: .cancel) {}
                Button(L("领取", "Claim")) { Task { await claim() } }
            }
            .task {
                while !Task.isCancelled {
                    await refresh()
                    try? await Task.sleep(for: .seconds(3))
                }
            }
            .navigationTitle(L("事项详情", "Task details"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button(L("关闭", "Close")) { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button(L("复制引用", "Copy reference"), systemImage: "link") {
                            UIPasteboard.general.string = referenceText(node, graph: graph, base: client.baseURL)
                        }
                        if node.can_delete == true {
                            Button(L("删除任务及子树", "Delete task and subtree"), systemImage: "trash", role: .destructive) {
                                confirmDelete = true
                            }
                        }
                    } label: { Image(systemName: "ellipsis") }
                    .accessibilityLabel(L("更多操作", "More actions"))
                    .disabled(busy)
                }
            }
        } else {
            ContentUnavailableView(L("任务不可用", "Task unavailable"), systemImage: "exclamationmark.circle",
                                   description: Text(L("该任务已被删除或无法访问。", "This task was deleted or is inaccessible.")))
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("关闭", "Close")) { dismiss() } } }
        }
    }

    private func taskSectionLabel(_ title: String) -> some View {
        Text(title).font(.caption.weight(.bold)).foregroundStyle(NanoTheme.muted)
    }

    private var subtreeCount: Int {
        var ids: Set<String> = [nodeID]
        var oldCount = 0
        while oldCount != ids.count {
            oldCount = ids.count
            for node in currentGraph.nodes where node.container_id.map(ids.contains) == true { ids.insert(node.id) }
        }
        return ids.count
    }

    private func refresh() async {
        guard !editing else { return }
        do {
            let fresh = try await client.taskGraph(graph.graph_id)
            guard !editing else { return }
            updatedGraph = fresh
            error = nil
        } catch {
            guard !editing else { return }
            self.error = error.localizedDescription
            if [403, 404].contains((error as? APIError)?.status ?? 0) { dismiss() }
        }
    }

    private func approve() async {
        busy = true; error = nil; defer { busy = false }
        do {
            try await client.approveTask(graphID: currentGraph.graph_id, revision: currentGraph.revision, nodeID: nodeID)
            await refresh()
        } catch { self.error = error.localizedDescription }
    }

    private func changeStatus(_ status: String) async {
        busy = true; error = nil; defer { busy = false }
        do {
            try await client.applyTask(currentGraph, operations: [TaskOperations.setStatus(nodeID: nodeID, status: status)], key: UUID().uuidString)
            await refresh()
        } catch { self.error = error.localizedDescription }
    }

    private func expandSingleCardToGoal() async {
        busy = true; error = nil; defer { busy = false }
        do {
            try await client.applyTask(currentGraph, operations: [TaskOperations.setMode(nodeID: nodeID, mode: "dag")], key: UUID().uuidString)
            await refresh()
            onOpenGraph?(currentGraph.graph_id, nodeID)
        } catch { self.error = error.localizedDescription }
    }

    private func claim() async {
        if currentGraph.nodes.first(where: { $0.id == nodeID })?.status == "done",
           claimReason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            error = L("请填写返工原因。", "Provide a rework reason.")
            return
        }
        busy = true; defer { busy = false }
        do {
            try await client.applyTask(currentGraph, operations: [.object(["op": .string("claim_task"), "node_id": .string(nodeID)])], note: claimReason, key: UUID().uuidString)
            await refresh()
        } catch { self.error = error.localizedDescription }
    }

    private func delete() async {
        busy = true; defer { busy = false }
        do {
            let _: JSONValue = try await client.send(
                "/im/v1/task-graphs/\(graph.graph_id.pathComponent)",
                method: "DELETE",
                body: [
                    "base_revision": .number(Double(currentGraph.revision)),
                    "request_key": .string(UUID().uuidString),
                    "node_id": .string(nodeID)
                ] as [String: JSONValue]
            )
            client.notifyTaskGraphChanged(graph.graph_id)
            dismiss()
        } catch { self.error = error.localizedDescription }
    }

    private func related(_ nodes: [TaskNode], title: String) -> some View {
        ForEach(nodes) { node in
            NavigationLink {
                TaskNodeView(client: client, graph: currentGraph, nodeID: node.id, onReference: onReference, onOpenGraph: onOpenGraph)
            } label: {
                HStack {
                    TaskStatusBadge(status: node.status)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(node.title).font(.subheadline.weight(.medium)).foregroundStyle(NanoTheme.ink)
                        Text(title).font(.caption2).foregroundStyle(NanoTheme.muted)
                    }
                    Spacer()
                    Image(systemName: "chevron.right").font(.caption2).foregroundStyle(NanoTheme.muted)
                }
            }
            .buttonStyle(.plain)
        }
    }
}

struct GroupTasksView: View {
    let client: IMClient
    let conversationID: String
    var onReference: (String, String) -> Void = { _, _ in }
    @State private var items: [TaskActivity] = []
    @State private var error: String?
    @State private var creating = false
    @State private var canWrite = false

    var body: some View {
        List {
            if let error { ErrorNotice(message: error) }
            ForEach(items) { item in
                NavigationLink {
                    TaskGraphView(client: client, graphID: item.graph_id, scopeID: item.scope_id, initialNodeID: item.node_id, onReference: onReference)
                } label: {
                    HStack(alignment: .top, spacing: 12) {
                        TaskStatusBadge(status: item.status)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(item.title).font(.subheadline.weight(.semibold))
                            Text(item.root_title).font(.caption).foregroundStyle(NanoTheme.muted)
                        }
                    }
                    .padding(.vertical, 6)
                }
            }
            if items.isEmpty, error == nil { Text(L("暂无关联任务", "No related tasks")) }
        }
        .nanoList()
        .navigationTitle(L("本群任务", "Group tasks"))
        .toolbar {
            if canWrite {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { creating = true } label: { Image(systemName: "plus") }
                        .accessibilityLabel(L("创建根任务", "Create root task"))
                }
            }
        }
        .sheet(isPresented: $creating) {
            NavigationStack {
                TaskEditorView(client: client, graph: nil, node: nil, parentID: nil, conversationID: conversationID) {
                    creating = false
                    Task { await load() }
                }
            }
        }
        .task { await load() }
        .refreshable { await load() }
    }

    private func load() async {
        canWrite = (try? await client.get("/im/v1/conversations/\(conversationID.pathComponent)") as Conversation)?.can_write == true
        do {
            let page: ItemsPage<TaskActivity> = try await client.get("/im/v1/conversations/\(conversationID.pathComponent)/task-activity")
            items = page.items
        } catch { self.error = error.localizedDescription }
    }
}
