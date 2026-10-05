import SwiftUI

struct TasksView: View {
    let client: IMClient
    let onReference: (String, String) -> Void
    @State private var items: [TaskSummary] = []
    @State private var cursor: String?
    @State private var query = ""
    @State private var error: String?
    @State private var loading = false
    @State private var loadedPages = 1
    @Environment(\.scenePhase) private var phase
    @State private var visible = true
    var body: some View {
        List {
            NanoSearchField(text: $query, prompt: L("搜索任务", "Search tasks"))
                .listRowSeparator(.hidden).listRowInsets(EdgeInsets(top: 6, leading: 20, bottom: 8, trailing: 20))
            if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } }
            ForEach(items) { item in NavigationLink {
                TaskGraphView(client: client, graphID: item.graph_id, onReference: onReference)
            } label: { VStack(alignment: .leading, spacing: 12) {
                Text(item.title).font(.body.weight(.semibold)).foregroundStyle(NanoTheme.ink)
                HStack(spacing: 8) {
                    Text(taskStatus(item.status)).font(.caption.weight(.medium)).foregroundStyle(NanoTheme.accent)
                        .padding(.horizontal, 8).padding(.vertical, 4).background(NanoTheme.softAccent, in: Capsule())
                    Text(item.mode == "explore" ? L("探索", "Exploration") : L("计划", "Plan")).font(.caption).foregroundStyle(NanoTheme.muted)
                    Spacer()
                    NanoTimestamp(value: item.updated_at)
                }
            }.padding(.vertical, 10) }.listRowInsets(EdgeInsets(top: 6, leading: 20, bottom: 6, trailing: 20)) }
            if cursor != nil { Button(L("加载更多", "Load more")) { Task { await load(more: true) } }.disabled(loading) }
            if items.isEmpty, error == nil, !loading { ContentUnavailableView(L("暂无任务", "No tasks"), systemImage: "point.3.connected.trianglepath.dotted", description: Text(L("在聊天中让 Agent 建立计划。", "Ask an agent to create a plan in chat."))) }
        }.nanoList().nanoRootTitle(L("任务", "Tasks"))
            .refreshable { await load() }
            .onSubmit(of: .search) { Task { await load() } }
            .task(id: "\(phase == .active)-\(visible)") { guard phase == .active, visible else { return }; while !Task.isCancelled { await load(preservePages: true); try? await Task.sleep(for: .seconds(3)) } }
            .onAppear { visible = true }.onDisappear { visible = false }
    }
    private func load(more: Bool = false, preservePages: Bool = false) async {
        guard !loading else { return }; loading = true; defer { loading = false }
        do {
            var nextCursor = more ? cursor : nil
            var refreshed = more ? items : []
            var pages = more ? loadedPages : 0
            let count = !more && preservePages ? loadedPages : 1
            for _ in 0..<count {
                var params = [URLQueryItem(name: "limit", value: "20"), .init(name: "query", value: query)]
                if let nextCursor { params.append(.init(name: "cursor", value: nextCursor)) }
                let page: TaskGraphPage = try await client.get("/im/v1/task-graphs", query: params)
                try Task.checkCancellation()
                for item in page.items { refreshed.removeAll { $0.id == item.id }; refreshed.append(item) }
                pages += 1; nextCursor = page.next_cursor
                if nextCursor == nil { break }
            }
            items = refreshed; cursor = nextCursor; loadedPages = pages; error = nil
        } catch is CancellationError {} catch { self.error = error.localizedDescription; if [403,404].contains((error as? APIError)?.status ?? 0) { items = [] } }
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
    @State private var listMode = false
    @State private var visible = true
    @Environment(\.scenePhase) private var phase
    var body: some View {
        Group {
            if let graph, let scope = graph.nodes.first(where: { $0.id == (scopeID ?? graph.root_node_id) }) {
                let layout = NativeTaskLayout(graph: graph, scopeID: scope.id)
                VStack(alignment: .leading, spacing: 10) {
                    HStack { Text(scope.title).font(.title3.bold()); Spacer(); Text("r\(graph.revision)").font(.caption).foregroundStyle(.secondary) }.padding(.horizontal)
                    Picker(L("视图", "View"), selection: $listMode) { Text(L("关系图", "Graph")).tag(false); Text(L("列表", "List")).tag(true) }.pickerStyle(.segmented).padding(.horizontal)
                    if let error { ErrorNotice(message: error).padding(.horizontal) }
                    if layout.nodes.isEmpty { ScrollView { nodeSummary(scope, graph: graph).padding() } }
                    else if listMode {
                        List(layout.nodes) { node in Button { selected = node } label: { nodeSummary(node, graph: graph) } }
                    } else {
                        ScrollView([.horizontal, .vertical]) {
                            ZStack(alignment: .topLeading) {
                                Canvas { context, _ in
                                    for edge in layout.edges {
                                        guard let from = layout.positions[edge.from], let to = layout.positions[edge.to] else { continue }
                                        let start = CGPoint(x: from.x + 210, y: from.y + 67), end = CGPoint(x: to.x, y: to.y + 67)
                                        var line = Path(); line.move(to: start); line.addCurve(to: end, control1: CGPoint(x: start.x + 30, y: start.y), control2: CGPoint(x: end.x - 30, y: end.y))
                                        context.stroke(line, with: .color(.teal.opacity(0.6)), lineWidth: 2)
                                        var arrow = Path(); arrow.move(to: CGPoint(x: end.x - 8, y: end.y - 5)); arrow.addLine(to: end); arrow.addLine(to: CGPoint(x: end.x - 8, y: end.y + 5)); context.stroke(arrow, with: .color(.teal), lineWidth: 2)
                                    }
                                }.accessibilityHidden(true)
                                ForEach(layout.nodes) { node in
                                    Button { selected = node } label: { VStack(alignment: .leading, spacing: 9) {
                                        Text(node.title).font(.headline).lineLimit(3).foregroundStyle(.primary)
                                        Text(taskStatus(node.status)).font(.caption).foregroundStyle(.teal)
                                        if !node.description.isEmpty { Text(node.description).font(.caption).lineLimit(2).foregroundStyle(.secondary) }
                                    }.padding(12).frame(width: 210, height: 134, alignment: .topLeading).background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 12)).overlay(RoundedRectangle(cornerRadius: 12).stroke(NanoTheme.border)) }.buttonStyle(.plain)
                                        .offset(x: layout.positions[node.id]?.x ?? 0, y: layout.positions[node.id]?.y ?? 0)
                                        .accessibilityLabel(node.title + ", " + taskStatus(node.status))
                                }
                            }.frame(width: layout.size.width, height: layout.size.height, alignment: .topLeading)
                        }.defaultScrollAnchor(.topLeading, for: .alignment)
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading).background(NanoTheme.canvas)
                    }
                }
            } else if let error { ContentUnavailableView { Label(L("任务不可用", "Task unavailable"), systemImage: "exclamationmark.circle") } description: { Text(error) } actions: { Button(L("重试", "Retry")) { Task { await load() } } } }
            else { ProgressView() }
        }.navigationTitle(L("任务图", "Task graph")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
            .task(id: "\(phase == .active)-\(visible)") { guard phase == .active, visible else { return }; while !Task.isCancelled { await load(); try? await Task.sleep(for: .seconds(3)) } }
            .onAppear { visible = true }.onDisappear { visible = false }
            .sheet(item: $selected) { node in if let graph { NavigationStack { TaskNodeView(client: client, graph: graph, nodeID: node.id, onReference: onReference) } } }
    }
    private func nodeSummary(_ node: TaskNode, graph: TaskGraph) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(node.title).font(.headline).foregroundStyle(.primary)
            Text(taskStatus(node.status)).font(.caption).foregroundStyle(.teal)
            if !node.description.isEmpty { Text(node.description).foregroundStyle(.secondary) }
            let predecessors = graph.dependencies.filter { $0.to == node.id }.compactMap { edge in graph.nodes.first { $0.id == edge.from }?.title }
            if !predecessors.isEmpty { Text(L("前置：", "Prerequisites: ") + predecessors.joined(separator: ", ")).font(.caption).foregroundStyle(.secondary) }
            if let chat = node.last_chat_id { Button(L("回到聊天并引用", "Reference in chat")) { onReference(chat, referenceText(node, graph: graph, base: client.baseURL)) } }
            if node.container_id == nil { Button(L("查看详情", "Details")) { selected = node } }
        }
    }
    private func load() async {
        do {
            let value: TaskGraph = try await client.get("/im/v1/task-graphs/\(graphID.pathComponent)", query: [.init(name: "view", value: "all")])
            try Task.checkCancellation()
            guard value.schema_version == 1 else { graph = nil; error = L("暂不支持此任务图版本。", "Unsupported task graph version."); return }
            let first = graph == nil; graph = value; error = nil
            if first, let initialNodeID { selected = value.nodes.first { $0.id == initialNodeID } }
        } catch is CancellationError {} catch { self.error = error.localizedDescription; if [403,404].contains((error as? APIError)?.status ?? 0) { graph = nil; selected = nil } }
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
    var body: some View {
        if let node = graph.nodes.first(where: { $0.id == nodeID }) {
            List {
                Section { Text(node.title).font(.title2.bold()); Text(taskStatus(node.status)).foregroundStyle(.teal); if !node.description.isEmpty { MarkdownView(text: node.description, client: client) } }
                if !node.result.isEmpty { Section(L("结果", "Result")) { MarkdownView(text: node.result, client: client) } }
                if let note = node.change_note, !note.isEmpty { Section(L("变更说明", "Change note")) { Text(note).textSelection(.enabled) } }
                if !node.selection_reason.isEmpty { Section(L("选择理由", "Selection reason")) { Text(node.selection_reason) } }
                Section(L("关系与子任务", "Relations and subtasks")) {
                    related(graph.nodes.filter { child in graph.dependencies.contains { $0.from == child.id && $0.to == node.id } }, title: L("前置", "Prerequisite"))
                    related(graph.nodes.filter { child in graph.dependencies.contains { $0.to == child.id && $0.from == node.id } }, title: L("后续", "Successor"))
                    if let derived = node.derived_from_id { related(graph.nodes.filter { $0.id == derived }, title: L("派生来源", "Derived from")) }
                    if let chosen = node.selected_candidate_id { related(graph.nodes.filter { $0.id == chosen }, title: L("已选候选", "Selected candidate")) }
                    related(graph.nodes.filter { $0.container_id == node.id }, title: L("子任务", "Child"))
                    if node.mode != "none" { NavigationLink(L("进入子图", "Open subgraph")) { TaskGraphView(client: client, graphID: graph.graph_id, scopeID: node.id, onReference: onReference) } }
                }
                if !node.links.isEmpty { Section(L("链接", "Links")) { ForEach(node.links, id: \.self) { text in if let url = URL(string: text), ["http","https"].contains(url.scheme ?? "") { Link(text, destination: url) } } } }
                Section {
                    if let chat = node.last_chat_id { Button(L("回到聊天并引用", "Reference in chat")) { onReference(chat, referenceText(node, graph: graph, base: client.baseURL)); dismiss() } }
                    else { Text(L("尚未关联聊天，可以复制引用到聊天继续讨论。", "No conversation is linked. Copy the reference to continue in chat.")).foregroundStyle(.secondary) }
                    Button(L("复制引用", "Copy reference")) { UIPasteboard.general.string = referenceText(node, graph: graph, base: client.baseURL) }
                }
            }.navigationTitle(L("任务详情", "Task details")).toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("完成", "Done")) { dismiss() } } }
        }
    }
    private func related(_ nodes: [TaskNode], title: String) -> some View {
        ForEach(nodes) { node in NavigationLink { TaskNodeView(client: client, graph: graph, nodeID: node.id, onReference: onReference) } label: { VStack(alignment: .leading) { Text(node.title); Text(title).font(.caption).foregroundStyle(.secondary) } } }
    }
}

struct GroupTasksView: View {
    let client: IMClient
    let conversationID: String
    var onReference: (String, String) -> Void = { _, _ in }
    @State private var items: [TaskActivity] = []
    @State private var error: String?
    var body: some View {
        List {
            if let error { ErrorNotice(message: error) }
            ForEach(items) { item in NavigationLink { TaskGraphView(client: client, graphID: item.graph_id, scopeID: item.scope_id, initialNodeID: item.node_id, onReference: onReference) } label: { VStack(alignment: .leading) { Text(item.title); Text(item.root_title + " · " + taskStatus(item.status)).font(.caption).foregroundStyle(.secondary) } } }
            if items.isEmpty, error == nil { Text(L("暂无关联任务", "No related tasks")) }
        }.navigationTitle(L("群任务", "Group tasks")).task {
            do { let page: ItemsPage<TaskActivity> = try await client.get("/im/v1/conversations/\(conversationID.pathComponent)/task-activity"); items = page.items }
            catch { self.error = error.localizedDescription }
        }
    }
}
