import SwiftUI

extension EnvironmentValues {
    @Entry var openTaskOverview: (() -> Void)? = nil
}

struct TasksView: View {
    let client: IMClient
    let onReference: (String, String) -> Void
    @State private var items: [TaskSummary] = []
    @State private var cursor: String?
    @State private var total = 0
    @State private var query = ""
    @State private var error: String?
    @State private var loading = false
    @State private var loaded = false
    @State private var loadedPages = 1
    @State private var visible = true
    @State private var ownerMode = false
    @State private var ownerKey = ""
    @State private var choosingOwner = false
    @State private var contacts: [Contact] = []
    @State private var selected: TaskSummary?
    @State private var creating = false
    @Environment(\.scenePhase) private var phase
    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    NanoSearchField(text: $query, prompt: L("搜索任务", "Search tasks"))
                    Picker(L("任务范围", "Task scope"), selection: $ownerMode) {
                        Text(L("根任务总览", "Root overview")).tag(false)
                        Text(L("按负责人 · 所有层级", "By assignee · all levels")).tag(true)
                    }.pickerStyle(.segmented)
                    if ownerMode {
                        Button { choosingOwner = true } label: {
                            TaskPropertyRow(title: L("负责人", "Assignee")) {
                                if let actor = ownerActors.first(where: { $0.taskKey == ownerKey }) { TaskActorLabel(actor: actor) }
                                else { Text(L("请选择负责人", "Select assignee")).foregroundStyle(NanoTheme.accent) }
                            }
                        }.buttonStyle(.plain)
                    }
                    if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } }
                    if !loaded && error == nil { ProgressView() }
                    if !ownerMode || !ownerKey.isEmpty {
                        if loaded {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(L("已加载 \(items.count) / 共 \(total) 个任务", "Loaded \(items.count) / \(total) tasks") + (partialCounts ? L(" · 以下计数仅含已加载", " · Counts below cover loaded tasks") : ""))
                                    .font(.caption).foregroundStyle(NanoTheme.muted)
                                TaskStatusSummary(counts: statusCounts, partial: partialCounts) { group in
                                    withAnimation { proxy.scrollTo(group, anchor: .top) }
                                }
                            }
                        }
                        ForEach(taskGroups, id: \.self) { group in
                            let rows = items.filter { taskGroupContains(group, status: $0.status) }
                            if !rows.isEmpty {
                                TaskStatusGroup(status: group, count: rows.count, partial: partialCounts, includesPaused: rows.contains { $0.status == "paused" }) {
                                    ForEach(rows) { item in
                                        TaskCompactCard(title: item.title, status: item.status, assignee: item.assignee, source: item.conversation.title,
                                                        parentPath: ownerMode ? item.parent_path?.map(\.title).joined(separator: " › ") : nil,
                                                        open: { selected = item }) {
                                            HStack(spacing: 12) {
                                                NavigationLink {
                                                    TaskGraphView(client: client, graphID: item.graph_id, scopeID: item.node_id ?? item.root_node_id, onReference: onReference)
                                                } label: { TaskSubtaskLabel(counts: item.direct_counts) }
                                                if ownerMode {
                                                    NavigationLink(L("返回所在层", "Open parent scope")) {
                                                        TaskGraphView(client: client, graphID: item.graph_id, scopeID: item.scope_id, initialNodeID: item.node_id, onReference: onReference)
                                                    }.font(.caption)
                                                }
                                            }
                                        }
                                    }
                                }.id(group)
                            }
                        }
                        if loaded && items.isEmpty && error == nil {
                            Text(L("暂无任务", "No tasks")).font(.subheadline).foregroundStyle(NanoTheme.muted).padding(.vertical, 24)
                        }
                    }
                    if cursor != nil { Button(L("加载更多", "Load more")) { Task { await load(more: true) } }.disabled(loading) }
                }.padding(16)
            }
        }.background(NanoTheme.canvas).nanoRootTitle(L("任务", "Tasks"))
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { creating = true } label: { Image(systemName: "plus") }.accessibilityLabel(L("创建根任务", "Create root task")) } }
            .refreshable { await load() }.onSubmit { Task { await load() } }
            .onChange(of: ownerMode) { _, _ in Task { await load() } }
            .onChange(of: ownerKey) { _, _ in Task { await load() } }
            .onChange(of: query) { _, value in if value.isEmpty { Task { await load() } } }
            .task { contacts = (try? await client.contacts()) ?? [] }
            .task(id: "\(phase == .active)-\(visible)") { guard phase == .active, visible else { return }; while !Task.isCancelled { await load(preservePages: true); try? await Task.sleep(for: .seconds(3)) } }
            .onAppear { visible = true }.onDisappear { visible = false }
            .sheet(item: $selected, onDismiss: { Task { await load(preservePages: true) } }) { item in
                NavigationStack { TaskDetailLoader(client: client, graphID: item.graph_id, nodeID: item.node_id ?? item.root_node_id, onReference: { id, text in selected = nil; onReference(id, text) }) }
            }
            .sheet(isPresented: $choosingOwner) { TaskActorPicker(actors: ownerActors, selectedKey: ownerKey, allowUnassigned: false, context: L("筛选所有层级的任务", "Filter tasks at every level")) { ownerKey = $0?.taskKey ?? "" } }
            .sheet(isPresented: $creating) { NavigationStack { TaskEditorView(client: client, graph: nil, node: nil, parentID: nil) { creating = false; Task { await load() } } } }
    }
    private var partialCounts: Bool { cursor != nil || items.count < total }
    private var statusCounts: [String: Int] { Dictionary(grouping: items, by: \.status).mapValues { $0.count } }
    private var ownerActors: [ActorRef] {
        contacts.map { contact in
            var actor = contact.actor
            actor.display_name = contact.display_name
            return actor
        }
    }
    private func load(more: Bool = false, preservePages: Bool = false) async {
        guard !loading else { return }
        if ownerMode && ownerKey.isEmpty { items = []; cursor = nil; total = 0; loaded = true; return }
        loading = true; defer { loading = false }
        let capturedQuery = query, capturedOwner = ownerMode ? ownerKey : ""
        do {
            var nextCursor = more ? cursor : nil
            var refreshed = more ? items : []
            var pages = more ? loadedPages : 0
            var refreshedTotal = total
            for _ in 0..<(!more && preservePages ? loadedPages : 1) {
                var params = [URLQueryItem(name: "limit", value: "50"), .init(name: "query", value: capturedQuery)]
                if !capturedOwner.isEmpty, let actor = contacts.first(where: { $0.actor.taskKey == capturedOwner })?.actor {
                    params += [.init(name: "assignee_type", value: actor.type), .init(name: "assignee_id", value: actor.id)]
                }
                if let nextCursor { params.append(.init(name: "cursor", value: nextCursor)) }
                let page: TaskGraphPage = try await client.get("/im/v1/task-graphs", query: params)
                try Task.checkCancellation()
                guard capturedQuery == query, capturedOwner == (ownerMode ? ownerKey : "") else { return }
                for item in page.items { refreshed.removeAll { $0.id == item.id }; refreshed.append(item) }
                refreshedTotal = page.total
                pages += 1; nextCursor = page.next_cursor
                if nextCursor == nil { break }
            }
            items = refreshed; total = refreshedTotal; cursor = nextCursor; loadedPages = pages; error = nil; loaded = true
        } catch is CancellationError {} catch { self.error = error.localizedDescription; if [403,404].contains((error as? APIError)?.status ?? 0) { items = [] } }
    }
}

struct TaskStatusGroup<Content: View>: View {
    let status: String
    let count: Int
    var partial = false
    var includesPaused = false
    @ViewBuilder var content: () -> Content
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: taskStatusIcon(status)).foregroundStyle(NanoTheme.accent)
                Text(status == "todo" && includesPaused ? L("待办 · 含暂缓", "To do · includes paused") : taskStatus(status)).font(.subheadline.weight(.semibold))
                Spacer()
                Text(partial ? L("已加载 \(count)", "\(count) loaded") : "\(count)").font(.caption).foregroundStyle(NanoTheme.muted)
            }.padding(.horizontal, 4).padding(.vertical, 2)
            content()
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct TaskDetailLoader: View {
    let client: IMClient
    let graphID: String
    let nodeID: String
    let onReference: (String, String) -> Void
    @State private var graph: TaskGraph?
    @State private var error: String?
    var body: some View {
        Group {
            if let graph { TaskNodeView(client: client, graph: graph, nodeID: nodeID, onReference: onReference) }
            else if let error { ContentUnavailableView(L("任务不可用", "Task unavailable"), systemImage: "exclamationmark.circle", description: Text(error)) }
            else { ProgressView() }
        }.task { do { graph = try await client.taskGraph(graphID) } catch { self.error = error.localizedDescription } }
    }
}

struct TaskGraphView: View {
    let client: IMClient
    let graphID: String
    var scopeID: String? = nil
    var initialNodeID: String? = nil
    let onReference: (String, String) -> Void
    @State private var graph: TaskGraph?
    @State private var selected: TaskNode?
    @State private var error: String?
    @Environment(\.openTaskOverview) private var openOverview
    @State private var listMode = true
    @State private var creating = false
    @Environment(\.dismiss) private var dismiss
    @State private var visible = true
    @State private var browsingScopeID: String?
    @Environment(\.scenePhase) private var phase
    @State private var structureOverview = true
    @State private var nodeHeights: [String: CGFloat] = [:]
    @ScaledMetric(relativeTo: .body) private var compactCardHeight = 96.0
    private let cardWidth = 320.0
    var body: some View {
        Group {
            if let graph, let scope = graph.nodes.first(where: { $0.id == (browsingScopeID ?? scopeID ?? graph.root_node_id) }) {
                let height = max(compactCardHeight, graph.nodes.filter { $0.container_id == scope.id }.compactMap { nodeHeights[$0.id] }.max() ?? 0)
                let layout = NativeTaskLayout(graph: graph, scopeID: scope.id, cardWidth: cardWidth, cardHeight: height)
                VStack(alignment: .leading, spacing: 10) {
                    HStack(spacing: 12) {
                        ScrollView(.horizontal, showsIndicators: false) { HStack(spacing: 6) {
                            Button(L("总览", "Overview")) { if let openOverview { openOverview() } else { dismiss() } }
                            Image(systemName: "chevron.right")
                            ForEach(ancestorPath(scope, graph: graph)) { node in
                                if node.id != scope.id { Button(node.title) { browsingScopeID = node.id }; Image(systemName: "chevron.right").foregroundStyle(NanoTheme.muted) }
                                else { Text(node.title).foregroundStyle(NanoTheme.ink) }
                            }
                        }.font(.caption) }
                        Button(L("详情", "Details")) { selected = scope }.font(.caption)
                    }.padding(.horizontal)
                    Picker(L("视图", "View"), selection: $listMode) { Text(L("完成情况", "Progress")).tag(true); Text(L("结构图", "Structure")).tag(false) }.pickerStyle(.segmented).padding(.horizontal)
                    HStack {
                        Text(graph.conversation.title + " · " + (graph.conversation.visibility == "public" ? L("公开", "Public") : L("私密", "Private"))).font(.caption).foregroundStyle(NanoTheme.muted)
                        Spacer()
                        if graph.conversation.can_write { Button(L("添加子任务", "Add subtask")) { creating = true }.font(.caption) }
                    }.padding(.horizontal)
                    if !listMode && !layout.edges.isEmpty { Label(scope.mode == "explore" ? L("箭头表示方案派生关系", "Arrows show how candidates derive") : L("箭头指向依赖前置任务的后续任务", "Arrows point from prerequisites to successors"), systemImage: "arrow.down").font(.caption).foregroundStyle(NanoTheme.muted).padding(.horizontal) }
                    if let error { ErrorNotice(message: error).padding(.horizontal) }
                    if listMode {
                        progressList(layout, scope: scope)
                    } else if layout.nodes.isEmpty { ScrollView { nodeSummary(scope, graph: graph).padding() } }
                    else {
                        HStack(alignment: .top, spacing: 12) {
                            Text(structureOverview ? L("适应屏幕 · 点节点查看完整详情", "Fit to screen · Tap a task for full details") : L("详细视图 · 可横向和纵向浏览", "Detail view · Scroll in both directions"))
                                .font(.caption).foregroundStyle(NanoTheme.muted).frame(maxWidth: .infinity, alignment: .leading)
                            Button { structureOverview.toggle() } label: {
                                Label(structureOverview ? L("详细视图", "Detail view") : L("回到总览", "Fit overview"), systemImage: structureOverview ? "arrow.up.left.and.arrow.down.right" : "arrow.down.right.and.arrow.up.left")
                                    .font(.caption).fixedSize(horizontal: true, vertical: true)
                            }
                        }.padding(.horizontal)
                        GeometryReader { viewport in
                            let scale = structureOverview ? min(1, min(max(0, viewport.size.width - 24) / layout.size.width, max(0, viewport.size.height - 24) / layout.size.height)) : 1
                            ScrollView([.horizontal, .vertical]) {
                                structureCanvas(layout, scope: scope, height: height)
                                    .scaleEffect(scale, anchor: .topLeading)
                                    .frame(width: layout.size.width * scale, height: layout.size.height * scale, alignment: .topLeading)
                                    .padding(12)
                            }.defaultScrollAnchor(.topLeading, for: .alignment)
                        }.background(NanoTheme.canvas)
                    }
                }
            } else if graph != nil {
                ContentUnavailableView(L("任务不可用", "Task unavailable"), systemImage: "exclamationmark.circle", description: Text(L("该层级已被删除或无法访问。", "This scope was deleted or is inaccessible.")))
            } else if let error { ContentUnavailableView { Label(L("任务不可用", "Task unavailable"), systemImage: "exclamationmark.circle") } description: { Text(error) } actions: { Button(L("重试", "Retry")) { Task { await load() } } } }
            else { ProgressView() }
        }.navigationTitle(L("子任务", "Subtasks")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
            .task(id: "\(phase == .active)-\(visible)") { guard phase == .active, visible else { return }; while !Task.isCancelled { await load(); try? await Task.sleep(for: .seconds(3)) } }
            .onAppear { visible = true }.onDisappear { visible = false }
            .sheet(isPresented: $creating) { if let graph { NavigationStack { TaskEditorView(client: client, graph: graph, node: nil, parentID: browsingScopeID ?? scopeID ?? graph.root_node_id) { creating = false; Task { await load() } } } } }
            .sheet(item: $selected, onDismiss: { Task { await load() } }) { node in if let graph {
                NavigationStack { TaskNodeView(client: client, graph: graph, nodeID: node.id, onReference: { chatID, text in
                    selected = nil
                    onReference(chatID, text)
                }) }
            } }
    }
    private func progressList(_ layout: NativeTaskLayout, scope: TaskNode) -> some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text(L("直属子任务 \(layout.nodes.count) · 点状态定位", "\(layout.nodes.count) direct subtasks · Tap a status to locate"))
                        .font(.caption).foregroundStyle(NanoTheme.muted)
                    TaskStatusSummary(counts: Dictionary(grouping: layout.nodes, by: \.status).mapValues { $0.count }) { group in
                        withAnimation { proxy.scrollTo(group, anchor: .top) }
                    }
                    ForEach(taskGroups, id: \.self) { group in
                        let nodes = layout.nodes.filter { taskGroupContains(group, status: $0.status) }
                        if !nodes.isEmpty {
                            TaskStatusGroup(status: group, count: nodes.count, includesPaused: nodes.contains { $0.status == "paused" }) {
                                ForEach(nodes) { node in
                                    TaskCompactCard(title: node.title, status: node.status, assignee: node.assignee,
                                                    selectedCandidate: scope.selected_candidate_id == node.id, open: { selected = node }) {
                                        Button { browsingScopeID = node.id } label: { TaskSubtaskLabel(counts: node.direct_counts) }
                                            .buttonStyle(.plain)
                                    }
                                }
                            }.id(group)
                        }
                    }
                    if layout.nodes.isEmpty {
                        Text(L("暂无直属子任务", "No direct subtasks")).font(.subheadline).foregroundStyle(NanoTheme.muted).padding(.vertical, 24)
                    }
                }.padding(16)
            }.background(NanoTheme.canvas).id(scope.id)
        }
    }
    private func structureCanvas(_ layout: NativeTaskLayout, scope: TaskNode, height: CGFloat) -> some View {
        ZStack(alignment: .topLeading) {
            Canvas { context, _ in
                for edge in layout.edges {
                    guard let from = layout.positions[edge.from], let to = layout.positions[edge.to] else { continue }
                    let start = CGPoint(x: from.x + cardWidth / 2, y: from.y + height), end = CGPoint(x: to.x + cardWidth / 2, y: to.y)
                    var line = Path(); line.move(to: start); line.addCurve(to: end, control1: CGPoint(x: start.x, y: start.y + 22), control2: CGPoint(x: end.x, y: end.y - 22))
                    context.stroke(line, with: .color(NanoTheme.accent.opacity(0.5)), lineWidth: 2)
                    var arrow = Path(); arrow.move(to: CGPoint(x: end.x - 5, y: end.y - 8)); arrow.addLine(to: end); arrow.addLine(to: CGPoint(x: end.x + 5, y: end.y - 8)); context.stroke(arrow, with: .color(NanoTheme.accent), lineWidth: 2)
                }
            }.accessibilityHidden(true)
            ForEach(layout.nodes) { (node: TaskNode) in
                let position = layout.positions[node.id] ?? CGPoint.zero
                let description = [node.title, taskStatus(node.status), node.assignee?.taskName ?? L("未分配", "Unassigned")].joined(separator: ", ")
                Button(action: { selected = node }) { structureNode(node, scope: scope, height: height) }
                    .buttonStyle(.plain)
                    .offset(x: position.x, y: position.y)
                    .accessibilityLabel(Text(description))
                    .accessibilityHint(Text(L("打开完整任务详情", "Open full task details")))
            }
        }.frame(width: layout.size.width, height: layout.size.height, alignment: .topLeading)
            .onPreferenceChange(TaskNodeHeightKey.self) { nodeHeights = $0 }
    }
    private func structureNode(_ node: TaskNode, scope: TaskNode, height: CGFloat) -> some View {
                    VStack(alignment: .leading, spacing: 9) {
                        Text(node.title).font(.headline).foregroundStyle(NanoTheme.ink).fixedSize(horizontal: false, vertical: true)
                        TaskStatusBadge(status: node.status)
                        TaskActorLabel(actor: node.assignee)
                        if scope.selected_candidate_id == node.id {
                            Label(L("已选方案", "Selected candidate"), systemImage: "checkmark.circle.fill").font(.caption).foregroundStyle(NanoTheme.accent)
                        }
                        if !node.description.isEmpty {
                            Text(node.description).font(.caption).foregroundStyle(NanoTheme.muted).fixedSize(horizontal: false, vertical: true)
                        }
                    }.padding(12).frame(width: cardWidth, alignment: .topLeading)
                        .background { GeometryReader { geometry in Color.clear.preference(key: TaskNodeHeightKey.self, value: [node.id: geometry.size.height]) } }
                        .frame(minHeight: height, alignment: .topLeading)
                        .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 12))
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(NanoTheme.border))

    }
    private func ancestorPath(_ node: TaskNode, graph: TaskGraph) -> [TaskNode] {
        var path = [node]
        while let parentID = path.first?.container_id, let parent = graph.nodes.first(where: { $0.id == parentID }) { path.insert(parent, at: 0) }
        return path
    }
    private func nodeSummary(_ node: TaskNode, graph: TaskGraph) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(node.title).font(.headline).foregroundStyle(.primary)
            TaskStatusBadge(status: node.status)
            if !node.description.isEmpty { Text(node.description).foregroundStyle(.secondary) }
            let predecessors = graph.dependencies.filter { $0.to == node.id }.compactMap { edge in graph.nodes.first { $0.id == edge.from }?.title }
            if !predecessors.isEmpty { Text(L("前置：", "Prerequisites: ") + predecessors.joined(separator: ", ")).font(.caption).foregroundStyle(.secondary) }
            if let chat = node.last_chat_id { Button(L("回到聊天并引用", "Reference in chat")) { onReference(chat, referenceText(node, graph: graph, base: client.baseURL)) } }
            if node.container_id == nil { Button(L("查看详情", "Details")) { selected = node } }
        }
    }
    private func load() async {
        guard selected == nil, !creating else { return }
        do {
            let value = try await client.taskGraph(graphID)
            try Task.checkCancellation()
            guard selected == nil, !creating else { return }
            guard value.schema_version == 2 else { graph = nil; error = L("暂不支持此任务图版本。", "Unsupported task graph version."); return }
            let first = graph == nil; graph = value; error = nil
            if first, let initialNodeID { selected = value.nodes.first { $0.id == initialNodeID } }
        } catch is CancellationError {} catch { guard selected == nil, !creating else { return }; self.error = error.localizedDescription; if [403,404].contains((error as? APIError)?.status ?? 0) { graph = nil; selected = nil } }
    }
}

private func referenceText(_ node: TaskNode, graph: TaskGraph, base: URL) -> String {
    var url = URLComponents(url: base, resolvingAgainstBaseURL: false)!
    url.path = "/tasks/\(graph.graph_id)"; url.queryItems = [.init(name: "node", value: node.id)]
    return "[\(node.title)](\(url.url!.absoluteString))"
}

struct TaskNodeView: View {
    let client: IMClient
    let graph: TaskGraph
    let nodeID: String
    let onReference: (String, String) -> Void
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
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    if let error { ErrorNotice(message: error); Button(L("读取最新内容", "Read latest content")) { Task { await refresh() } } }
                    VStack(alignment: .leading, spacing: 16) {
                        Button { onReference(graph.conversation.id, "") } label: {
                            Label(graph.conversation.title, systemImage: "bubble.left.and.bubble.right")
                                .font(.subheadline).foregroundStyle(NanoTheme.muted)
                        }.buttonStyle(.plain)
                        if let parent = graph.nodes.first(where: { $0.id == node.container_id }) {
                            Text(parent.title).font(.subheadline).foregroundStyle(NanoTheme.muted)
                        }
                        Text(node.title).font(.title.bold()).foregroundStyle(NanoTheme.ink).textSelection(.enabled)
                        ViewThatFits(in: .horizontal) {
                            HStack(spacing: 16) { TaskStatusBadge(status: node.status); TaskActorLabel(actor: node.assignee) }
                            VStack(alignment: .leading, spacing: 12) { TaskStatusBadge(status: node.status); TaskActorLabel(actor: node.assignee) }
                        }
                        if !graph.conversation.can_write {
                            Label(graph.conversation.dissolved_at != nil ? L("已解散群 · 历史只读", "Dissolved group · read-only history") : L("加入所属群后可修改", "Join the owning group to edit"), systemImage: "lock")
                                .font(.subheadline).foregroundStyle(NanoTheme.muted)
                        }
                    }
                    if !node.description.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            taskSectionLabel(L("任务说明", "Description"))
                            MarkdownView(text: node.description, client: client)
                        }
                    }
                    if !node.result.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            taskSectionLabel(L("当前结果", "Result"))
                            MarkdownView(text: node.result, client: client).padding(.leading, 14)
                                .overlay(alignment: .leading) { RoundedRectangle(cornerRadius: 2).fill(NanoTheme.accent.opacity(0.45)).frame(width: 3) }
                        }
                    }
                    if node.mode != "none" || node.can_edit == true || (node.direct_counts?.total ?? 0) > 0 {
                        Divider()
                        NavigationLink { TaskGraphView(client: client, graphID: graph.graph_id, scopeID: node.id, onReference: onReference) } label: {
                            VStack(alignment: .leading, spacing: 12) {
                                HStack {
                                    Text(L("子任务", "Subtasks")).foregroundStyle(NanoTheme.ink).font(.headline)
                                    Spacer()
                                    if let counts = node.direct_counts { Text(L("完成 \(counts.done) / \(counts.total)", "\(counts.done) / \(counts.total) done")).font(.subheadline) }
                                    Image(systemName: "chevron.right").font(.caption)
                                }
                                if let counts = node.direct_counts, counts.total > 0 {
                                    ProgressView(value: Double(counts.done), total: Double(counts.total))
                                    Text(L("进行中 \(counts.doing) · 待确认 \(counts.in_review) · 暂缓 \(counts.paused) · 已关闭 \(counts.closed)", "Doing \(counts.doing) · Review \(counts.in_review) · Paused \(counts.paused) · Closed \(counts.closed)"))
                                        .font(.caption).foregroundStyle(NanoTheme.muted)
                                }
                            }.padding(.vertical, 8).contentShape(Rectangle())
                        }.buttonStyle(.plain)
                    }
                    if graph.dependencies.contains(where: { $0.from == node.id || $0.to == node.id }) || node.derived_from_id != nil || node.selected_candidate_id != nil {
                        DisclosureGroup(L("关联任务", "Related tasks")) {
                            VStack(alignment: .leading, spacing: 16) {
                                related(graph.nodes.filter { child in graph.dependencies.contains { $0.from == child.id && $0.to == node.id } }, title: L("前置", "Prerequisite"))
                                related(graph.nodes.filter { child in graph.dependencies.contains { $0.to == child.id && $0.from == node.id } }, title: L("后续", "Successor"))
                                if let derived = node.derived_from_id { related(graph.nodes.filter { $0.id == derived }, title: L("派生来源", "Derived from")) }
                                if let chosen = node.selected_candidate_id { related(graph.nodes.filter { $0.id == chosen }, title: L("已选候选", "Selected candidate")) }
                            }.padding(.top, 12)
                        }.font(.subheadline)
                    }
                    Divider()
                    DisclosureGroup {
                        VStack(alignment: .leading, spacing: 16) {
                            LabeledContent(L("创建者", "Creator"), value: node.created_by?.taskName ?? "—")
                            LabeledContent(L("修改者", "Updated by"), value: node.updated_by_actor?.taskName ?? node.updated_by)
                            if let note = node.change_note, !note.isEmpty { taskSectionLabel(L("变更说明", "Change note")); Text(note).textSelection(.enabled) }
                            if !node.selection_reason.isEmpty { taskSectionLabel(L("选择理由", "Selection reason")); Text(node.selection_reason).textSelection(.enabled) }
                            ForEach(node.links, id: \.self) { text in if let url = URL(string: text), ["http", "https"].contains(url.scheme ?? "") { Link(text, destination: url) } }
                        }.font(.subheadline).padding(.top, 12)
                    } label: { Text(L("创建与修改信息", "Creation and changes")).font(.subheadline).foregroundStyle(NanoTheme.muted) }
                    if let chat = node.last_chat_id { Button { onReference(chat, referenceText(node, graph: graph, base: client.baseURL)) } label: { Label(L("回到聊天并引用", "Reference in chat"), systemImage: "arrowshape.turn.up.left") }.font(.subheadline) }
                    if node.can_claim == true {
                        Button(L("领取任务", "Claim task")) { if node.status == "done" { claiming = true } else { Task { await claim() } } }.buttonStyle(.bordered).disabled(busy)
                    }
                }.padding(24)
            }.background(NanoTheme.surface)
            .safeAreaInset(edge: .bottom) {
                if node.can_edit == true {
                    Button { editing = true } label: { Label(L("编辑任务", "Edit task"), systemImage: "square.and.pencil").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 10) }
                        .buttonStyle(.borderedProminent).disabled(busy).padding(.horizontal, 24).padding(.vertical, 12).background(NanoTheme.surface)
                }
            }.sheet(isPresented: $editing, onDismiss: { Task { await refresh() } }) { NavigationStack { TaskEditorView(client: client, graph: graph, node: node, parentID: nil) { editing = false; Task { await refresh() } } } }
            .confirmationDialog(L("删除任务及整个子树？", "Delete this task and its entire subtree?"), isPresented: $confirmDelete, titleVisibility: .visible) {
                Button(L("删除 \(subtreeCount) 个节点", "Delete \(subtreeCount) nodes"), role: .destructive) { Task { await delete() } }
            } message: { Text(L("范围包含「\(node.title)」及全部后代，共 \(subtreeCount) 个节点，包括其他创建者的任务。删除后无法恢复。", "This removes \(node.title) and all descendants (\(subtreeCount) nodes), including tasks created by others. This cannot be undone.")) }
            .alert(L("填写返工原因", "Rework reason"), isPresented: $claiming) {
                TextField(L("返工原因", "Reason"), text: $claimReason)
                Button(L("取消", "Cancel"), role: .cancel) {}
                Button(L("领取", "Claim")) { Task { await claim() } }
            }
            .task { while !Task.isCancelled { await refresh(); try? await Task.sleep(for: .seconds(3)) } }
            .navigationTitle(L("任务详情", "Task details")).navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button(L("关闭", "Close")) { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button(L("复制引用", "Copy reference"), systemImage: "link") { UIPasteboard.general.string = referenceText(node, graph: graph, base: client.baseURL) }
                        if node.can_delete == true { Button(L("删除任务及子树", "Delete task and subtree"), systemImage: "trash", role: .destructive) { confirmDelete = true } }
                    } label: { Image(systemName: "ellipsis") }.accessibilityLabel(L("更多操作", "More actions")).disabled(busy)
                }
            }
        } else {
            ContentUnavailableView(L("任务不可用", "Task unavailable"), systemImage: "exclamationmark.circle", description: Text(L("该任务已被删除或无法访问。", "This task was deleted or is inaccessible.")))
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("关闭", "Close")) { dismiss() } } }
        }
    }
    private func taskSectionLabel(_ title: String) -> some View {
        Text(title).font(.subheadline.weight(.medium)).foregroundStyle(NanoTheme.muted)
    }
    private var subtreeCount: Int {
        var ids: Set<String> = [nodeID]
        var oldCount = 0
        while oldCount != ids.count { oldCount = ids.count; for node in currentGraph.nodes where node.container_id.map(ids.contains) == true { ids.insert(node.id) } }
        return ids.count
    }
    private func refresh() async {
        // The editor owns its draft, including permission-loss recovery.
        guard !editing else { return }
        do { let fresh = try await client.taskGraph(graph.graph_id); guard !editing else { return }; updatedGraph = fresh; error = nil }
        catch { guard !editing else { return }; self.error = error.localizedDescription; if [403,404].contains((error as? APIError)?.status ?? 0) { dismiss() } }
    }
    private func claim() async {
        if currentGraph.nodes.first(where: { $0.id == nodeID })?.status == "done", claimReason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { error = L("请填写返工原因。", "Provide a rework reason."); return }
        busy = true; defer { busy = false }
        do { try await client.applyTask(currentGraph, operations: [.object(["op": .string("claim_task"), "node_id": .string(nodeID)])], note: claimReason, key: UUID().uuidString); await refresh() }
        catch { self.error = error.localizedDescription }
    }
    private func delete() async {
        busy = true; defer { busy = false }
        do {
            let _: JSONValue = try await client.send("/im/v1/task-graphs/\(graph.graph_id.pathComponent)", method: "DELETE", body: ["base_revision": .number(Double(currentGraph.revision)), "request_key": .string(UUID().uuidString), "node_id": .string(nodeID)] as [String: JSONValue])
            dismiss()
        } catch { self.error = error.localizedDescription }
    }
    private func related(_ nodes: [TaskNode], title: String) -> some View {
        ForEach(nodes) { node in NavigationLink { TaskNodeView(client: client, graph: currentGraph, nodeID: node.id, onReference: onReference) } label: { VStack(alignment: .leading) { Text(node.title); Text(title).font(.caption).foregroundStyle(.secondary) } } }
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
            ForEach(items) { item in NavigationLink { TaskGraphView(client: client, graphID: item.graph_id, scopeID: item.scope_id, initialNodeID: item.node_id, onReference: onReference) } label: { HStack(alignment: .top, spacing: 12) { Image(systemName: taskStatusIcon(item.status)).foregroundStyle(NanoTheme.accent).padding(.top, 3); VStack(alignment: .leading, spacing: 6) { Text(item.title).font(.headline); Text(item.root_title).font(.caption).foregroundStyle(NanoTheme.muted); Text(taskStatus(item.status)).font(.caption).foregroundStyle(NanoTheme.muted) } }.padding(.vertical, 8) } }
            if items.isEmpty, error == nil { Text(L("暂无关联任务", "No related tasks")) }
        }.nanoList().navigationTitle(L("群任务", "Group tasks"))
            .toolbar { if canWrite { ToolbarItem(placement: .topBarTrailing) { Button { creating = true } label: { Image(systemName: "plus") }.accessibilityLabel(L("创建根任务", "Create root task")) } } }
            .sheet(isPresented: $creating) { NavigationStack { TaskEditorView(client: client, graph: nil, node: nil, parentID: nil, conversationID: conversationID) { creating = false; Task { await load() } } } }
            .task { await load() }.refreshable { await load() }
    }
    private func load() async {
            canWrite = (try? await client.get("/im/v1/conversations/\(conversationID.pathComponent)") as Conversation)?.can_write == true
            do { let page: ItemsPage<TaskActivity> = try await client.get("/im/v1/conversations/\(conversationID.pathComponent)/task-activity"); items = page.items }
            catch { self.error = error.localizedDescription }
    }
}
