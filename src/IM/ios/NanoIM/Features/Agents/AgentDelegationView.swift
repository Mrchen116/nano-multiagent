import SwiftUI

struct AgentDelegationView: View {
    let client: IMClient
    let agentID: String
    let canManage: Bool
    let onOpenChat: @MainActor (String) -> Void
    @State private var window = "3d"
    var body: some View {
        AgentDelegationWindow(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, window: $window)
            .id(window)
    }
}

private struct AgentDelegationWindow: View {
    let client: IMClient
    let agentID: String
    let canManage: Bool
    let onOpenChat: @MainActor (String) -> Void
    @Binding var window: String
    @State private var head: AgentDelegationPage?
    @State private var nodes: [String: AgentDelegationNode] = [:]
    @State private var cursor: String?
    @State private var loadingMore = false
    @State private var expanded = Set<String>()
    @State private var error: String?
    private var rootNodes: [AgentDelegationNode] {
        sort(nodes.values.filter { $0.parent_session_id.flatMap { nodes[$0] } == nil })
    }
    private func sort(_ values: [AgentDelegationNode]) -> [AgentDelegationNode] {
        values.sorted { a, b in
            if (a.id == head?.main_session_id) != (b.id == head?.main_session_id) { return a.id == head?.main_session_id }
            if a.last_active_at == b.last_active_at { return a.id < b.id }
            return (a.last_active_at ?? "") > (b.last_active_at ?? "")
        }
    }
    private var visibleRows: [(node: AgentDelegationNode, depth: Int, hasChildren: Bool)] {
        let children = Dictionary(grouping: nodes.values, by: \.parent_session_id)
        var rows: [(AgentDelegationNode, Int, Bool)] = []
        func append(_ node: AgentDelegationNode, depth: Int) {
            let children = sort(children[node.id] ?? [])
            rows.append((node, depth, !children.isEmpty))
            if expanded.contains(node.id) { children.forEach { append($0, depth: depth + 1) } }
        }
        rootNodes.forEach { append($0, depth: 0) }
        return rows
    }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 14) {
                HStack {
                    Text(L("协作动态", "Working together")).font(.title.bold()).accessibilityAddTraits(.isHeader)
                    Spacer(minLength: 4)
                    Menu {
                        Picker(L("活动范围", "Activity window"), selection: $window) {
                            Text(L("最近 3 天", "Last 3 days")).tag("3d")
                            Text(L("最近 2 小时", "Last 2 hours")).tag("2h")
                        }
                    } label: {
                        Label(window == "3d" ? L("最近 3 天", "Last 3 days") : L("最近 2 小时", "Last 2 hours"),
                              systemImage: "calendar").font(.footnote.weight(.semibold)).frame(minHeight: 44)
                    }
                }
                if let head {
                    HStack { NanoDateTime(value: head.from); Text("–"); NanoDateTime(value: head.until) }
                        .font(.caption).foregroundStyle(.secondary)
                    if head.record_sync_state != "current" {
                        Label(head.record_sync_state == "catching_up" ? L("记录同步中", "Syncing records") : L("已保存记录", "Saved records"),
                              systemImage: "clock").font(.caption).foregroundStyle(.secondary)
                    }
                }
                if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await read(more: false) } } }
                if head == nil && error == nil { ProgressView() }
                if head != nil {
                    Section {
                        if nodes.isEmpty {
                            Label(L("这段时间还没有派工", "No delegations during this period"), systemImage: "point.3.connected.trianglepath.dotted")
                                .padding(.vertical, 18).foregroundStyle(.secondary)
                        }
                        ForEach(visibleRows, id: \.node.id) { row in
                            HStack(spacing: 2) {
                                if row.hasChildren {
                                    Button {
                                        if !expanded.insert(row.node.id).inserted { expanded.remove(row.node.id) }
                                    } label: {
                                        Image(systemName: expanded.contains(row.node.id) ? "chevron.down" : "chevron.right")
                                            .font(.caption.weight(.bold)).frame(width: 44, height: 44)
                                    }
                                    .buttonStyle(.borderless)
                                    .accessibilityLabel(expanded.contains(row.node.id) ? L("收起子执行", "Collapse children") : L("展开子执行", "Expand children"))
                                } else if row.depth > 0 {
                                    Image(systemName: "arrow.turn.down.right").font(.caption).foregroundStyle(.tertiary).frame(width: 24)
                                }
                                if row.node.canOpenRecords {
                                    NavigationLink {
                                        AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: row.node.id)
                                    } label: { nodeLabel(row.node) }
                                    .accessibilityIdentifier("work.delegation." + row.node.id)
                                } else { nodeLabel(row.node) }
                            }
                            .padding(12)
                            .background(row.node.id == head?.main_session_id ? NanoTheme.softAccent : NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 12))
                            .padding(.leading, CGFloat(min(row.depth, 3)) * 12)
                        }
                        if cursor != nil {
                            Button(L("加载更多派工", "Load more delegations")) { Task { await read(more: true) } }.disabled(loadingMore)
                        }
                    }
                    Section {
                        Divider().padding(.top, 12)
                        AgentHistoricalSessions(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat)
                    }
                }
            }.padding(.horizontal, 20).padding(.vertical, 16)
        }
        .background(NanoTheme.surface)
        .refreshable { await read(more: false) }
        .workRefresh(client: client, agentID: agentID, every: 30) { await read(more: false) }
    }

    private func nodeLabel(_ node: AgentDelegationNode) -> some View {
        let isMain = node.id == head?.main_session_id
        let title = isMain ? L("主助手", "Lead assistant") : node.title ?? node.id
        let ambiguous = !isMain && nodes.values.contains { $0.id != node.id && $0.title != nil && $0.title == node.title }
        return VStack(alignment: .leading, spacing: 5) {
            Text(ambiguous ? title + " · " + node.id.suffix(8) : title).font(.headline)
            HStack {
                Text(agentWorkStatus(node.status))
                if let runtime = node.runtime { Text(runtime) }
                if let time = node.last_active_at { NanoTimestamp(value: time) }
            }.font(.caption).foregroundStyle(.secondary)
            if let usage = node.usage {
                let tokens = usage.total_tokens.map { $0.formatted() + " tok" } ?? L("Token 未报告", "Tokens unreported")
                Text(L("\(usage.turns) 轮累计 · \(tokens)", "\(usage.turns) turns · \(tokens)")).font(.subheadline)
                if usage.missing_turns > 0 {
                    Text(L("\(usage.reported_turns)/\(usage.turns) 轮已报告用量", "Usage reported for \(usage.reported_turns)/\(usage.turns) turns")).font(.caption).foregroundStyle(.secondary)
                }
            } else { Text(L("用量尚未报告", "Usage not reported yet")).font(.caption).foregroundStyle(.secondary) }
            if node.ancestor_only == true { Text(L("仅显示派工路径", "Ancestor on this path")).font(.caption).foregroundStyle(.secondary) }
        }.frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
    }

    private func read(more: Bool) async {
        let requestedWindow = window, original = head, next = cursor
        var query = [URLQueryItem(name: "window", value: requestedWindow), URLQueryItem(name: "limit", value: "8")]
        if more {
            guard let next, let original, !loadingMore else { return }
            loadingMore = true
            query += [.init(name: "after_session", value: next), .init(name: "until", value: original.until)]
        }
        defer { if more { loadingMore = false } }
        do {
            let page: AgentDelegationPage = try await client.get(agentPath(agentID) + "/work/delegation", query: query)
            guard !Task.isCancelled, window == requestedWindow else { return }
            if more {
                guard head?.until == original?.until, cursor == next else { return }
            } else {
                let firstRead = head == nil
                // Keep an already-paged window intact across unchanged heartbeat reads.
                if let head, head.revision == page.revision, head.record_sync_state == page.record_sync_state,
                   head.node_connection_state == page.node_connection_state,
                   head.nodes.map(\.id) == page.nodes.map(\.id), self.cursor != head.next_cursor {
                    error = nil; return
                }
                head = page
                nodes.removeAll(keepingCapacity: true)
                if firstRead, let main = page.main_session_id { expanded.insert(main) }
            }
            for node in page.nodes where nodes[node.id] == nil || node.ancestor_only != true { nodes[node.id] = node }
            cursor = page.next_cursor
            error = nil
        } catch {
            guard !Task.isCancelled, window == requestedWindow else { return }
            if workAccessLost(error) { head = nil; nodes = [:]; cursor = nil }
            self.error = agentError(error)
        }
    }
}

private struct AgentHistoricalSessions: View {
    let client: IMClient
    let agentID: String
    let canManage: Bool
    let onOpenChat: @MainActor (String) -> Void
    @State private var expanded = false
    @State private var sessions: [AgentWorkSession] = []
    @State private var cursor: String?
    @State private var loaded = false
    @State private var loading = false
    @State private var error: String?
    var body: some View {
        DisclosureGroup(L("历史主执行与定时任务", "Historical sessions and scheduled tasks"), isExpanded: $expanded) {
            ForEach(sessions) { session in
                NavigationLink(session.label) {
                    AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: session.id)
                }
            }
            if loading { ProgressView() }
            if let error { ErrorNotice(message: error) }
            if loaded && sessions.isEmpty && error == nil { Text(L("暂无历史执行", "No historical sessions")).foregroundStyle(.secondary) }
            if cursor != nil || error != nil {
                Button(error == nil ? L("加载更多", "Load more") : L("重试", "Retry")) { Task { await load() } }.disabled(loading)
            }
        }.task(id: expanded) { if expanded && !loaded { await load() } }
    }
    private func load() async {
        guard !loading else { return }
        loading = true
        defer { loading = false }
        var query = [URLQueryItem(name: "historical", value: "1")]
        if let cursor { query.append(.init(name: "after_session", value: cursor)) }
        do {
            let page: AgentWorkCatalogPage = try await client.get(agentPath(agentID) + "/work/sessions", query: query)
            guard !Task.isCancelled else { return }
            sessions += page.sessions
            cursor = page.next_cursor
            loaded = true; error = nil
        } catch {
            if workAccessLost(error) { sessions = []; cursor = nil; loaded = false }
            self.error = agentError(error)
        }
    }
}
