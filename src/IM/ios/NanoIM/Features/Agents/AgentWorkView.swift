import SwiftUI
import QuickLook

/// Refresh visible Work only; original chat navigation still requires server authorization.
struct AgentWorkView: View {
    let client: IMClient; let agentID: String; let canManage: Bool; let onOpenChat: @MainActor (String) -> Void
    var sessionID: String? = nil
    @Environment(\.scenePhase) private var scenePhase
    @State private var root: AgentWorkPage?
    @State private var controls: [AgentWorkItem] = []
    @State private var loaded = false
    @State private var error: String?
    @State private var executionDeleted = false
    @State private var loadingMore = false
    @State private var history: [String: AgentWorkHistory] = [:]
    @State private var headTurnIDs = Set<String>()
    @State private var headUpdate = 0
    @State private var refreshing = false
    @State private var selectedSession: AgentWorkSession?
    @State private var catalog: [AgentWorkSession] = []
    @State private var catalogCursor: String?
    @State private var catalogLoaded = false
    @State private var catalogOpen = false
    @State private var catalogLoading = false
    @State private var catalogError: String?
    private var separate: Bool { root?.catalog == "separate" }
    private var executionID: String? { sessionID ?? root?.main_session_id }
    private var executionHistory: AgentWorkHistory? { executionID.flatMap { history[$0] } }
    private var visibleTurns: [AgentWorkTurn] { executionHistory?.turns ?? [] }
    private var sessions: [AgentWorkSession] { separate ? catalog : root?.other_executions ?? [] }
    private var summaryQuery: [URLQueryItem] {
        [URLQueryItem(name: "catalog", value: "separate")]
    }
    private var base: String { agentPath(agentID) + "/work" }
    private var path: String { sessionID.map { base + "/sessions/" + agentSegment($0) + "/turns" } ?? base }
    private var online: Bool { root?.node_connection_state == "online" }
    var body: some View {
        List {
            Section {
                Text(agentID).font(.headline)
                if let root {
                    HStack(spacing: 8) {
                        Circle().fill(online ? NanoTheme.accent : NanoTheme.muted).frame(width: 7, height: 7)
                        Text(online ? L("在线", "Online") : L("离线 · 活动状态未知", "Offline · activity unknown"))
                        Text("·").foregroundStyle(.secondary)
                        Text(agentWorkStatus(root.main_execution ?? (online ? visibleTurns.first?.status : nil) ?? "unknown"))
                    }.font(.subheadline)
                    if !online { Text(L("显示已保存的记录，授权暂不可处理。", "Showing saved records. Permissions are unavailable while offline.")).font(.caption).foregroundStyle(.secondary) }
                    if online && root.record_sync_state != "current" {
                        Text(root.record_sync_state == "catching_up"
                            ? L("工作记录正在补齐，当前显示已保存内容。", "Work records are catching up. Showing saved content.")
                            : L("当前显示已保存记录，最新进度尚未确认。", "Showing saved records. The latest progress has not been confirmed."))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    DisclosureGroup(L("执行信息与上下文", "Execution details and context")) {
                        LabeledContent("Agent", value: agentID).textSelection(.enabled)
                        if let sessionID {
                            if let selectedSession { Text(selectedSession.label).font(.caption) }
                            Text(sessionID).font(.caption).textSelection(.enabled)
                        }
                        if sessionID == nil { AgentWorkUsage(value: root.latest_main_usage, title: L("最近上下文", "Latest context")) }
                    }.font(.subheadline)
                }
                AgentLifecycleControls(client: client, agentID: agentID, canManage: canManage, online: online)
            }
            if executionDeleted { Text(L("执行记录已删除", "Execution record deleted")).foregroundStyle(.secondary) }
            else if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await refresh() } } }
            if !loaded { ProgressView() }
            if separate || !sessions.isEmpty {
                Section(L("关联执行", "Related executions")) {
                    if separate {
                        DisclosureGroup(L("浏览关联执行", "Browse related executions"), isExpanded: $catalogOpen) {
                            executionLinks
                            if catalogLoading { ProgressView() }
                            if let catalogError { ErrorNotice(message: catalogError); Button(L("重试", "Retry")) { Task { await loadCatalog() } } }
                            if catalogLoaded { Button(L("刷新目录", "Refresh directory")) { Task { await loadCatalog(reset: true) } }.disabled(catalogLoading) }
                            if catalogCursor != nil && catalogError == nil { Button(L("加载更多", "Load more")) { Task { await loadCatalog() } }.disabled(catalogLoading) }
                        }.onChange(of: catalogOpen) { _, open in if open && !catalogLoaded { Task { await loadCatalog() } } }
                    } else { executionLinks }
                }
            }
            Section(L("执行轮次 · 最新在前", "Turns · newest first")) {
                let displayed = visibleTurns
                ForEach(Array(displayed.enumerated()), id: \.element.id) { index, turn in
                    if index > 0 && executionHistory?.hasGap(after: displayed[index - 1], before: turn) == true {
                        earlierButton(displayed[index - 1].turn_id)
                        Text(L("中间轮次尚未加载", "Turns between these records have not loaded")).font(.caption).foregroundStyle(.secondary)
                    }
                    AgentWorkTurnView(client: client, agentID: agentID, turn: turn, sessions: root?.other_executions ?? [], online: online,
                        canManage: canManage, onOpenChat: onOpenChat, separate: separate,
                        active: headTurnIDs.contains(turn.id) && ["running", "waiting_permission", "unknown"].contains(turn.status), headUpdate: headUpdate)
                }
                if loaded && displayed.isEmpty && !executionDeleted { Text(L("尚未报告执行轮次", "No reported turns")) }
                if let last = displayed.last, executionHistory?.hasEarlier(after: last) == true { earlierButton(last.turn_id) }
            }
            if separate, let executionID {
                Section(L("控制记录", "Control records")) { AgentWorkControls(client: client, base: base, sessionID: executionID).id(executionID) }
            }
            if let execution = sessionID ?? root?.main_session_id, root != nil {
                AgentWorkOriginals(client: client, agentID: agentID, sessionID: execution)
            }
            if !controls.isEmpty {
                Section(L("控制记录", "Control records")) {
                    ForEach(controls) { item in DisclosureGroup(item.kind) { JSONDetailView(value: .object(item.payload)).textSelection(.enabled) } }
                }
            }
        }.navigationTitle(sessionID == nil ? L("工作轨迹", "Work") : L("关联执行", "Related execution"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar).refreshable { await refresh() }
        .task(id: scenePhase) { guard scenePhase == .active else { return }; repeat { await refresh(); try? await Task.sleep(for: .seconds(3)) } while !Task.isCancelled }
    }
    @ViewBuilder private var executionLinks: some View {
        ForEach(sessions.filter { $0.id != sessionID }) { session in
            NavigationLink {
                AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: session.id)
            } label: { VStack(alignment: .leading) { Text(session.label); Text(agentScopeName(session.scope)).font(.caption).foregroundStyle(.secondary) } }
        }
    }
    private func earlierButton(_ before: String) -> some View {
        Button(L("更早轮次", "Earlier turns")) { Task { await loadMore(before) } }.disabled(loadingMore)
    }
    private func refresh() async {
        guard !refreshing, !executionDeleted else { return }
        refreshing = true; defer { refreshing = false }
        do {
            let page: AgentWorkPage
            let nextRoot: AgentWorkPage
            if let sessionID {
                // A selected execution can negotiate on its own head and only
                // needs the legacy root catalog if the old center answered.
                page = try await client.get(path, query: summaryQuery)
                if page.catalog == "separate" {
                    nextRoot = page
                    if selectedSession == nil {
                        selectedSession = try await client.get(base + "/sessions/" + agentSegment(sessionID))
                    }
                } else {
                    nextRoot = try await client.get(base)
                }
            } else {
                page = try await client.get(path, query: summaryQuery)
                nextRoot = page
            }
            guard !Task.isCancelled else { return }
            if loaded && separate != (page.catalog == "separate") { history = [:] }
            if let id = sessionID ?? page.main_session_id { history[id, default: AgentWorkHistory()].merge(page) }
            controls = page.control_items ?? []
            root = nextRoot
            headTurnIDs = Set(page.turns.map(\.id)); headUpdate += 1
            loaded = true; error = nil
        } catch {
            guard !Task.isCancelled else { return }
            self.error = agentError(error); loaded = true
            if let api = error as? APIError, [401, 403, 404, 409, 410].contains(api.status) {
                root = nil; controls = []; history = [:]; catalog = []
                catalogLoaded = false; catalogCursor = nil; selectedSession = nil
                executionDeleted = api.status == 410 && (api.code == "agent_execution_deleted" || api.detail == "agent_execution_deleted")
            }
        }
    }
    private func loadMore(_ before: String) async {
        guard !loadingMore, let id = executionID else { return }
        let useCatalog = separate
        let pagePath = base + "/sessions/" + agentSegment(id) + "/turns"
        loadingMore = true; defer { loadingMore = false }
        do {
            let page: AgentWorkPage = try await client.get(pagePath, query: (useCatalog ? summaryQuery : []) + [URLQueryItem(name: "before_turn", value: before)])
            guard !executionDeleted, loaded, executionID == id, separate == useCatalog, useCatalog == (page.catalog == "separate") else { return }
            history[id, default: AgentWorkHistory()].merge(page, before: before)
            error = nil
        } catch { self.error = agentError(error) }
    }
    private func loadCatalog(reset: Bool = false) async {
        guard separate, !catalogLoading else { return }
        catalogLoading = true; defer { catalogLoading = false }
        do {
            let page: AgentWorkCatalogPage = try await client.get(base + "/sessions", query: (reset ? nil : catalogCursor).map { [URLQueryItem(name: "after_session", value: $0)] } ?? [])
            guard separate else { return }
            catalog = reset ? page.sessions : catalog + page.sessions
            catalogCursor = page.next_cursor; catalogLoaded = true; catalogError = nil
        } catch { catalogError = agentError(error) }
    }
}

private struct AgentWorkControls: View {
    let client: IMClient; let base: String; let sessionID: String
    @State private var expanded = false
    @State private var loading = false
    @State private var items: [AgentWorkItem] = []
    @State private var cursor: String? = "0"
    @State private var error: String?
    var body: some View {
        DisclosureGroup(L("查看控制记录", "View control records"), isExpanded: $expanded) {
            ForEach(items) { item in DisclosureGroup(item.kind) { JSONDetailView(value: .object(item.payload)).textSelection(.enabled) } }
            if loading { ProgressView() }
            if let error { ErrorNotice(message: error) }
            if cursor != nil { Button(error == nil ? L("加载更多", "Load more") : L("重试", "Retry")) { Task { await load() } }.disabled(loading) }
        }.onChange(of: expanded) { _, open in if open && cursor == "0" { Task { await load() } } }
    }
    private func load() async {
        guard !loading, let cursor else { return }
        loading = true; defer { loading = false }
        do {
            let page: AgentWorkItemPage = try await client.get(base + "/sessions/" + agentSegment(sessionID) + "/controls",
                query: [URLQueryItem(name: "after_seq", value: cursor)])
            items += page.items; self.cursor = page.next_cursor; error = nil
        } catch { self.error = agentError(error) }
    }
}

struct AgentWorkTurnView: View {
    let client: IMClient; let agentID: String; let turn: AgentWorkTurn; let sessions: [AgentWorkSession]
    let online: Bool; let canManage: Bool; let onOpenChat: @MainActor (String) -> Void
    let separate: Bool; let active: Bool; let headUpdate: Int
    @State private var expanded = false
    @State private var extra: [String: AgentWorkItem] = [:]
    @State private var extraCursor: String?
    @State private var didLoad = false
    @State private var busy = false
    @State private var error: String?
    @State private var revision: Int?
    @State private var moreChanges = false
    @State private var wasActive = false
    @State private var changesError: String?
    private var path: String { agentPath(agentID) + "/work/sessions/" + agentSegment(turn.session_id) + "/turns/" + agentSegment(turn.turn_id) + "/items" }
    private var items: [AgentWorkItem] {
        var map = extra
        for item in turn.items where (map[item.id]?.revision ?? 0) <= (item.revision ?? 0) { map[item.id] = item }
        return agentVisibleWorkItems(Array(map.values))
    }
    private var state: String { !online && ["running", "waiting_permission"].contains(turn.status) ? "unknown" : turn.status }
    private var recentSummary: String? {
        for item in items.reversed() {
            let keys = item.kind == "tool" ? ["output", "summary"] : ["text", "content"]
            for key in keys {
                if case .string(let text)? = item.payload[key], !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return text }
            }
        }
        return nil
    }

    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            VStack(alignment: .leading, spacing: 12) {
                DisclosureGroup(L("执行信息", "Execution information")) {
                    Text(turn.turn_id).font(.caption).textSelection(.enabled)
                    Text(turn.model_id ?? L("模型未报告", "Model unreported")).font(.caption)
                    if let origin = turn.origin { JSONDetailView(value: origin) }
                    if let trigger = turn.trigger { JSONDetailView(value: .object(trigger)) }
                    if let start = turn.started_at { NanoDateTime(value: start) }
                    if let finish = turn.finished_at { NanoDateTime(value: finish) }
                }
                ForEach(items) { item in
                    AgentWorkItemView(client: client, agentID: agentID, sessionID: turn.session_id, item: item, sessions: sessions, online: online, canManage: canManage, onOpenChat: onOpenChat, separate: separate)
                    Divider()
                }
                if expanded { AgentWorkOriginals(client: client, agentID: agentID, sessionID: turn.session_id, turnID: turn.turn_id) }
                AgentWorkUsage(value: turn.usage, title: L("本轮统计", "Turn statistics"))
                if let elapsed = turn.elapsed_ms { LabeledContent(L("耗时", "Duration"), value: String(format: "%.2f s", elapsed / 1000)) }
                if (didLoad ? extraCursor : turn.next_items_cursor) != nil { Button(L("加载更多过程", "Load more process")) { Task { await loadMore() } }.disabled(busy) }
                if busy && separate && !didLoad { ProgressView() }
                if let error {
                    ErrorNotice(message: error)
                    Button(L("重试", "Retry")) { Task { await loadMore() } }.disabled(busy)
                }
                if let changesError { ErrorNotice(message: changesError) }
                if moreChanges || changesError != nil {
                    Button(changesError == nil ? L("加载更多更新", "Load more updates") : L("重试", "Retry")) { Task { await refreshItems() } }.disabled(busy)
                }
            }.padding(.vertical, 8)
        } label: {
            VStack(alignment: .leading) {
                Text(turn.title).font(.headline)
                HStack { Text(agentWorkStatus(state)).font(.caption).foregroundStyle(.secondary); if let start = turn.started_at { NanoDateTime(value: start).font(.caption2) } }
                if let summary = recentSummary { Text(summary).font(.subheadline).foregroundStyle(.secondary).lineLimit(2) }
            }
        }.onChange(of: state, initial: true) { _, value in if value == "waiting_permission" { expanded = true } }
            .onChange(of: expanded) { _, open in if open && separate && !didLoad { Task { await loadMore() } } }
            .onChange(of: headUpdate) { _, _ in
                if separate && expanded && (active || wasActive || moreChanges) { Task { await refreshItems() } }
            }
    }
    private func store(_ items: [AgentWorkItem]) {
        for item in items where (extra[item.id]?.revision ?? 0) <= (item.revision ?? 0) { extra[item.id] = item }
    }
    private func loadMore() async {
        guard !busy else { return }
        let after = didLoad ? extraCursor : separate ? "0" : turn.next_items_cursor
        guard let after else { return }
        busy = true; defer { busy = false }
        var query = [URLQueryItem(name: "after_seq", value: after)]
        if separate { query.append(URLQueryItem(name: "catalog", value: "separate")) }
        do {
            let page: AgentWorkItemPage = try await client.get(path, query: query)
            store(page.items)
            if !didLoad { revision = page.revision; wasActive = active }
            extraCursor = page.next_cursor; didLoad = true; error = nil
        } catch { self.error = agentError(error) }
    }
    private func refreshItems() async {
        guard !busy, let revision else { return }
        busy = true; defer { busy = false }
        do {
            let page: AgentWorkItemPage = try await client.get(path, query: [
                URLQueryItem(name: "catalog", value: "separate"),
                URLQueryItem(name: "after_revision", value: String(revision)),
            ])
            store(page.items)
            self.revision = page.revision ?? revision
            moreChanges = page.next_cursor != nil; wasActive = active; changesError = nil
        } catch { changesError = agentError(error) }
    }
}

private struct WorkOriginalEntry: Decodable, Identifiable, Sendable {
    let revision: Int
    let type: String
    let observed_at: String?
    let total_bytes: Int
    let state: String
    var id: Int { revision }
}
private struct WorkOriginalPage: Decodable, Sendable {
    let items: [WorkOriginalEntry]
    let next_cursor: Int?
}

private struct AgentWorkOriginals: View {
    let client: IMClient
    let agentID: String
    let sessionID: String
    var turnID: String? = nil
    @State private var expanded = false
    @State private var page: [WorkOriginalEntry] = []
    @State private var cursor: Int?
    @State private var error: String?
    @State private var loading = false
    private var path: String { agentPath(agentID) + "/work/sessions/" + agentSegment(sessionID) + "/originals" }

    var body: some View {
        DisclosureGroup(L("大型原文", "Large originals"), isExpanded: $expanded) {
            if expanded {
                ForEach(page) { entry in
                    AgentWorkOriginal(client: client, entry: entry, path: path + "/" + String(entry.revision))
                }
                if loading { ProgressView() }
                else if let error {
                    ErrorNotice(message: error)
                    Button(L("重试", "Retry")) { Task { await load() } }
                } else if page.isEmpty { Text(L("没有大型原文", "No large originals")) }
                if let cursor { Button(L("加载更多原文", "Load more originals")) { Task { await load(after: cursor) } }.disabled(loading) }
            }
        }.task(id: expanded) { if expanded { await load() } }
    }

    private func load(after: Int? = nil) async {
        loading = true; defer { loading = false }
        var query: [URLQueryItem] = []
        if let turnID { query.append(.init(name: "turn_id", value: turnID)) }
        if let after { query.append(.init(name: "after_revision", value: String(after))) }
        do {
            let result: WorkOriginalPage = try await client.get(path, query: query)
            try Task.checkCancellation()
            if after == nil { page = result.items } else { page += result.items }
            cursor = result.next_cursor; error = nil
        } catch is CancellationError {} catch {
            page = []; cursor = nil; self.error = agentError(error)
        }
    }
}

private struct AgentWorkOriginal: View {
    let client: IMClient
    let entry: WorkOriginalEntry
    let path: String
    @State private var download: Task<Void, Never>?
    @State private var file: URL?
    @State private var viewer: URL?
    @State private var excerpt: String?
    @State private var error: String?
    var body: some View {
        VStack(alignment: .leading) {
            HStack {
                Text(entry.type)
                Text(String(format: "%.1f MiB", Double(entry.total_bytes) / 1048576))
                if let observed = entry.observed_at { NanoDateTime(value: observed) }
            }.font(.caption)
            if entry.state == "complete" {
                if let file {
                    Button(L("打开原文文件", "Open original file")) { viewer = file }
                    ShareLink(item: file) { Label(L("保存原文", "Save original"), systemImage: "square.and.arrow.up") }
                    if let excerpt {
                        DisclosureGroup(L("原文开头", "Beginning of original")) {
                            Text(excerpt).font(.caption.monospaced()).textSelection(.enabled)
                        }
                    }
                } else if download != nil {
                    ProgressView()
                    Button(L("取消", "Cancel")) { download?.cancel() }
                } else {
                    Button(L("下载原文", "Download original")) { download = Task { await open() } }
                }
            } else {
                Text(entry.state == "pending"
                    ? L("原文待补齐，可在网页版 Work 的原生轨迹中查看", "Mirror pending. Open the native trajectory in Work on the web.")
                    : L("原文仅在节点，可在网页版 Work 的原生轨迹中查看", "Stored on the node. Open the native trajectory in Work on the web."))
                    .font(.caption).foregroundStyle(.secondary)
            }
            if let error { ErrorNotice(message: error) }
        }.quickLookPreview($viewer)
            .onDisappear {
                download?.cancel()
                if let file { try? FileManager.default.removeItem(at: file.deletingLastPathComponent()) }
                file = nil; viewer = nil; excerpt = nil
            }
    }

    private func open() async {
        error = nil
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("nano-work-" + UUID().uuidString, isDirectory: true)
        let destination = dir.appendingPathComponent("work-\(entry.revision).json")
        defer { download = nil; if file == nil { try? FileManager.default.removeItem(at: dir) } }
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            try await client.session.download(path: path, to: destination)
            try Task.checkCancellation()
            let handle = try FileHandle(forReadingFrom: destination)
            defer { try? handle.close() }
            excerpt = String(decoding: try handle.read(upToCount: 8192) ?? Data(), as: UTF8.self)
            file = destination
        } catch is CancellationError {} catch { self.error = agentError(error) }
    }
}

struct AgentWorkItemView: View {
    let client: IMClient; let agentID: String; let sessionID: String; let item: AgentWorkItem; let sessions: [AgentWorkSession]
    let online: Bool; let canManage: Bool; let onOpenChat: @MainActor (String) -> Void
    @State private var navigationError: String?
    private var p: [String: JSONValue] { item.payload }
    private func text(_ key: String) -> String { p[key]?.agentString ?? "" }
    let separate: Bool
    @ViewBuilder private func toolLinks(late: Bool = false) -> some View {
        let detail = p["detail"]?.agentObject ?? [:]
        let input = (p["input"] ?? p["arguments"])?.agentObject ?? [:]
        let id = [text("child_session_id"), detail["child_session_id"]?.agentString ?? ""].first { !$0.isEmpty } ?? ""
        let call = [text("id"), text("call_id"), text("tool_call_id")].first { !$0.isEmpty } ?? ""
        let agent = [detail["agent_id"]?.agentString, input["agent_id"]?.agentString].compactMap { $0 }.first { !$0.isEmpty } ?? ""
        let name = text("name") + text("tool_name")
        let known = item.has_exact_child == true || !agent.isEmpty || name.contains("agent") || name.contains("workflow")
        if late {
            // An exact link can arrive after this historical item was loaded.
            if separate, id.isEmpty, !known, !call.isEmpty {
                links(id: "", parent: sessionID, call: call)
            }
        } else {
            links(id: id, parent: sessionID, call: call, agent: agent, canResolve: known)
        }
    }
    @ViewBuilder private func links(id: String, parent: String = "", call: String = "", agent: String = "", canResolve: Bool = true) -> some View {
        if !id.isEmpty {
            childLink(id, label: sessions.first { $0.id == id }?.label ?? id)
        } else if separate, canResolve, !call.isEmpty || !agent.isEmpty {
            let query = [("parent_session_id", parent), ("tool_call_id", call), ("child_agent_id", agent)]
                .filter { !$0.1.isEmpty }.map { URLQueryItem(name: $0.0, value: $0.1) }
            AgentWorkLinkMatches(client: client, agentID: agentID, query: query) { child in childLink(child.id, label: child.distinctLabel) }
        } else if !separate {
            let exact = sessions.filter { !call.isEmpty && $0.parent_session_id == parent && $0.parent_tool_call_id == call }
            let candidates = exact.isEmpty ? sessions.filter { !agent.isEmpty && $0.child_agent_id == agent && (parent.isEmpty || $0.parent_session_id == parent) } : exact
            ForEach(candidates) { child in childLink(child.id, label: candidates.count > 1 ? child.distinctLabel : child.label) }
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if item.kind == "permission" {
                AgentWorkPermissionView(client: client, agentID: agentID, payload: p, enabled: online && canManage)
            } else if item.kind == "tool" {
                DisclosureGroup {

                    if let output = p["output"] ?? p["summary"] { Text(L("结果", "Result")).font(.caption); JSONDetailView(value: output) }
                    DisclosureGroup(L("技术详情", "Technical details")) {
                        if let input = p["input"] ?? p["arguments"] { Text(L("参数", "Arguments")).font(.caption); JSONDetailView(value: input) }
                        if let detail = p["detail"] { JSONDetailView(value: detail) }
                        toolLinks(late: true)
                    }.font(.subheadline)
                    if let approval = p["approval"] { DisclosureGroup(L("授权结果", "Approval result")) { JSONDetailView(value: approval) } }
                    if let duration = p["duration_ms"] ?? p["elapsed_ms"] { LabeledContent(L("耗时（毫秒）", "Duration (ms)"), value: duration.prettyPrinted) }
                    let business = p["detail"]?.agentObject["status"]?.agentString ?? ""
                    if !business.isEmpty { Text(agentBusinessStatus(business)).font(.caption) }
                    Text(L("工具结果与聊天发送分别记录。", "Tool results and chat deliveries are recorded separately.")).font(.caption).foregroundStyle(.secondary)
                    workFacts
                } label: { Text((text("name").isEmpty ? text("tool_name") : text("name")) + " · " + (text("status") == "completed" ? L("调用完成", "Call completed") : agentWorkStatus(text("status").isEmpty ? "unknown" : text("status")))) }
                toolLinks()
            } else if ["message", "message_delta", "text_delta", "assistant_message", "thinking", "thinking_delta", "reasoning"].contains(item.kind) {
                if !text("reasoning_content").isEmpty { DisclosureGroup(L("思考", "Reasoning")) { Text(text("reasoning_content")).textSelection(.enabled) } }
                let body = [text("text"), text("content"), text("delta")].first { !$0.isEmpty } ?? ""
                if !body.isEmpty {
                    if ["thinking", "thinking_delta", "reasoning"].contains(item.kind) { DisclosureGroup(L("思考", "Reasoning")) { Text(body).textSelection(.enabled) } }
                    else { MarkdownView(text: body, client: client) }
                }
                links(id: text("source_session_id"))
                backgroundReturns
            } else if item.kind == "background_return" {
                AgentBackgroundResult(value: .object(p))
                links(id: text("child_session_id"), agent: text("agent_id"))
            } else if item.kind == "injection_consumed" { links(id: text("source_session_id")); backgroundReturns }
            else if item.kind == "recording_degraded" { Label(L("工作记录存在缺口", "Work recording has gaps"), systemImage: "exclamationmark.triangle") }
            else {
                DisclosureGroup(item.kind) { JSONDetailView(value: .object(p)) }
                if !text("conversation_id").isEmpty { chatLink(text("conversation_id")) }
            }
            if let observed = item.observed_at { NanoTimestamp(value: observed) }
            if let navigationError { ErrorNotice(message: navigationError) }
        }
    }
    @ViewBuilder private var backgroundReturns: some View {
        ForEach(Array((p["background_returns"]?.agentArray ?? []).enumerated()), id: \.offset) { _, value in
            AgentBackgroundResult(value: value)
            let data = value.agentObject
            links(id: data["child_session_id"]?.agentString ?? "", agent: data["agent_id"]?.agentString ?? "")
        }
    }
    @ViewBuilder private var workFacts: some View {
        ForEach(Array((p["work_facts"]?.agentArray ?? []).enumerated()), id: \.offset) { _, value in
            let fact = value.agentObject
            let kind = fact["type"]?.agentString ?? ""
            if kind != "inbox_read_committed" {
                Text(kind == "draft_withheld" ? L("原草稿 · 未发送", "Original draft · not sent") : L("实际投递确认", "Actual delivery confirmation")).font(.caption)
                if kind == "draft_withheld" { Text((fact["text"] ?? fact["draft"])?.agentString ?? "").textSelection(.enabled) }
                if let target = (fact["conversation_id"] ?? fact["target"])?.agentString, !target.isEmpty { chatLink(target) }
                ForEach(Array((fact["source_refs"]?.agentArray ?? []).enumerated()), id: \.offset) { _, reference in
                    if let target = reference.agentObject["conversation_id"]?.agentString, !target.isEmpty { chatLink(target) }
                }
            }
        }
    }
    private func childLink(_ id: String, label: String) -> some View {
        NavigationLink(L("查看关联执行：", "Open related execution: ") + label) { AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: id) }
    }
    private func chatLink(_ id: String) -> some View {
        Button(L("打开来源聊天", "Open source chat")) {
            Task { do { let _: AgentChatCreated = try await client.get("/im/v1/conversations/" + agentSegment(id)); onOpenChat(id) } catch { navigationError = agentError(error) } }
        }
    }
}

private struct AgentWorkLinkMatches<Link: View>: View {
    let client: IMClient; let agentID: String; let query: [URLQueryItem]; let link: (AgentWorkSession) -> Link
    @State private var matches: [AgentWorkSession] = []
    @State private var cursor: String?
    @State private var loaded = false
    @State private var loading = false
    @State private var error: String?
    var body: some View {
        ForEach(matches, content: link)
        if loading { ProgressView() }
        if let error { ErrorNotice(message: error) }
        if !loading, !loaded || cursor != nil || error != nil || matches.isEmpty {
            Button(error != nil ? L("重试", "Retry") : loaded && cursor != nil ? L("加载更多", "Load more") : L("查找关联执行", "Find related executions")) {
                Task { await load() }
            }
        }
    }
    private func load() async {
        guard !loading else { return }
        loading = true; defer { loading = false }
        do {
            let page: AgentWorkCatalogPage = try await client.get(agentPath(agentID) + "/work/sessions",
                query: query + (cursor.map { [URLQueryItem(name: "after_session", value: $0)] } ?? []))
            matches += page.sessions
            cursor = page.next_cursor; loaded = true
            error = matches.isEmpty ? L("关联执行暂不可用", "Related execution is unavailable") : nil
        } catch { self.error = agentError(error) }
    }
}

struct AgentBackgroundResult: View {
    let value: JSONValue
    var body: some View {
        let data = value.agentObject
        DisclosureGroup {
            Text(L("后台结果不代表已向聊天发送。", "A background result is not a chat delivery.")).font(.caption).foregroundStyle(.secondary)
            if let result = data["result"] { JSONDetailView(value: result) }
            if let error = data["error"], error != .null { JSONDetailView(value: error) }
            DisclosureGroup(L("执行归属", "Execution ownership")) { JSONDetailView(value: value) }
        } label: { Text((data["description"] ?? data["task_type"])?.agentString ?? L("后台返回", "Background result")); Text(agentWorkStatus(data["status"]?.agentString ?? "unknown")).font(.caption) }
    }
}
struct AgentWorkUsage: View {
    let value: JSONValue?; let title: String
    var body: some View {
        DisclosureGroup(title) {
            if let value, value != .null {
                let data = value.agentObject
                LabeledContent(L("最近一次输入的上下文", "Most recent input context"), value: count(data["context_used"]))
                LabeledContent(L("上下文窗口", "Context window"), value: count(data["context_window"]))
                LabeledContent(L("本轮累计输出", "Accumulated turn output"), value: count(data["output"]))
                LabeledContent(L("累计缓存读取", "Accumulated cache reads"), value: count(data["cache_read_tokens"]))
                LabeledContent(L("缓存统计输入总量", "Cache metric input total"), value: count(data["cache_total_input_tokens"]))
                if let used = data["context_used"]?.doubleValue, let window = data["context_window"]?.doubleValue, window > 0 {
                    ProgressView(value: min(used / window, 1)).accessibilityLabel(L("上下文占用", "Context utilization"))
                    Text(String(format: "%.1f%%", used / window * 100)).font(.caption)
                }
                if let read = data["cache_read_tokens"]?.doubleValue, let total = data["cache_total_input_tokens"]?.doubleValue, total > 0 {
                    LabeledContent(L("缓存命中率", "Cache hit rate"), value: String(format: "%.1f%%", read / total * 100))
                }
                Text(L("上下文为本轮最近一次输入，输出和缓存为本轮累计；主、子执行分别统计，不代表计费总量。", "Context is the most recent input; output and cache are accumulated for this turn. Main and child statistics are separate, not billing totals.")).font(.caption).foregroundStyle(.secondary)
            } else { Text(L("尚未报告；主、子执行统计分别展示。", "Not reported. Main and child statistics are separate.")) }
        }
    }
    private func count(_ value: JSONValue?) -> String {
        if let number = value?.doubleValue { return number.formatted(.number.precision(.fractionLength(0))) }
        return L("未报告", "Unreported")
    }
}
func agentBusinessStatus(_ status: String) -> String {
    switch status { case "async_launched": return L("子执行已启动", "Child execution started"); case "message_queued": return L("补充输入已排队", "Follow-up input queued"); case "held_for_revalidation": return L("未发送，等待重新核对", "Not sent; awaiting revalidation"); case "pending_revalidation": return L("待发送，等待重新核对", "Pending delivery and revalidation"); default: return status }
}
func agentWorkStatus(_ status: String) -> String {
    switch status { case "running": return L("运行中", "Running"); case "waiting_permission": return L("等待授权", "Awaiting permission"); case "completed": return L("已完成", "Completed"); case "failed": return L("失败", "Failed"); case "interrupted": return L("已中断", "Interrupted"); case "idle": return L("空闲", "Idle"); case "unknown": return L("未知", "Unknown"); default: return status }
}

struct AgentWorkPermissionView: View {
    let client: IMClient; let agentID: String; let payload: [String: JSONValue]; let enabled: Bool
    @State private var reason = ""
    @State private var submitting = false
    @State private var submitted = false
    @State private var chosen = ""
    @State private var error: String?
    private var status: String { payload["status"]?.agentString ?? "pending" }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(payload["tool_name"]?.agentString ?? L("权限请求", "Permission request"), systemImage: "lock.shield")
            if let input = payload["tool_input"] { JSONDetailView(value: input) }
            if status == "resolved" { Text(L("已确认：", "Confirmed: ") + (payload["decision"]?.agentString ?? "")) }
            else if submitted || status == "submitted" { Text(L("已提交，等待确认；决定可能已经生效。", "Submitted, awaiting confirmation; the decision may already be effective.")); Text(chosen) }
            else {
                TextField(L("拒绝理由（可选）", "Reason for denial (optional)"), text: $reason, axis: .vertical)
                ForEach(Array((payload["options"]?.agentArray ?? []).enumerated()), id: \.offset) { _, value in
                    let option = value.agentObject
                    let id = option["id"]?.agentString ?? ""
                    Button(optionLabel(id, fallback: option["label"]?.agentString ?? id)) { Task { await decide(id) } }.disabled(!enabled || submitting || id.isEmpty)
                }
                if !enabled { Text(L("仅在线节点的管理者可处理。", "Only the owner can act while the node is online.")).font(.caption) }
            }
            if let error { ErrorNotice(message: error) }
        }
    }
    private func optionLabel(_ id: String, fallback: String) -> String {
        switch id { case "allow_once": return L("允许一次", "Allow once"); case "allow_session": return L("本会话内允许", "Allow for session"); case "allow_always": return L("总是允许", "Always allow"); case "deny": return L("拒绝", "Deny"); default: return fallback }
    }
    private func decide(_ decision: String) async {
        submitting = true; chosen = optionLabel(decision, fallback: decision); error = nil; defer { submitting = false }
        do {
            let body = ["decision": decision, "reason": decision == "deny" ? reason.trimmingCharacters(in: .whitespacesAndNewlines) : ""]
            let _: JSONValue = try await client.send(agentPath(agentID) + "/work/permissions/" + agentSegment(payload["request_id"]?.agentString ?? ""), body: body)
            submitted = true
        } catch {
            // An unconfirmed decision may already be effective; never offer a second approval.
            if (error as? APIError)?.detail.contains("decision_unconfirmed") == true || (error as? APIError)?.detail.contains("request_in_progress") == true || !(error is APIError) { submitted = true }
            self.error = agentError(error)
        }
    }
}
