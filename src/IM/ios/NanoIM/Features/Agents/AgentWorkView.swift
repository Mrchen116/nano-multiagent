import SwiftUI

/// Refresh visible Work only; original chat navigation still requires server authorization.
struct AgentWorkView: View {
    let client: IMClient; let agentID: String; let canManage: Bool; let onOpenChat: @MainActor (String) -> Void
    var sessionID: String? = nil
    var focus: AgentWorkFocus? = nil
    var displayName: String? = nil
    @State private var delegation = false
    @State private var revealedFocus = false
    @State private var root: AgentWorkPage?
    @State private var controls: [AgentWorkItem] = []
    @State private var loaded = false
    @State private var error: String?
    @State private var executionDeleted = false
    @State private var loadingEarlier: Set<String> = []
    @State private var earlierErrors: [String: String] = [:]
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
        var query = [URLQueryItem(name: "view", value: "summary"), URLQueryItem(name: "catalog", value: "separate")]
        if sessionID == nil { query.append(URLQueryItem(name: "timeline", value: "combined")) }
        return query
    }
    private var base: String { agentPath(agentID) + "/work" }
    private var path: String { sessionID.map { base + "/sessions/" + agentSegment($0) + "/turns" } ?? base }
    private var online: Bool { root?.node_connection_state == "online" }
    var body: some View {
        VStack(spacing: 0) {
            if sessionID == nil {
                HStack(spacing: 24) {
                    workTab(L("工作记录", "Work records"), showDelegation: false)
                    workTab(L("派工关系", "Delegation"), showDelegation: true)
                    Spacer(minLength: 0)
                    if let root {
                        Text(online ? agentWorkStatus(root.main_execution ?? "unknown") : L("离线", "Offline"))
                            .font(.caption).foregroundStyle(NanoTheme.muted)
                    }
                }
                .padding(.horizontal, 20)
                Divider()
            }
            ZStack {
                ScrollViewReader { proxy in
                    recordList.onChange(of: focusedTurnLoaded, initial: true) { _, available in
                        guard available, !revealedFocus, let focus else { return }
                        revealedFocus = true
                        proxy.scrollTo(focus.turn.id, anchor: .top)
                    }
                }
                .refreshable { await refresh() }
                .workRefresh(client: client, agentID: agentID, every: 3, enabled: !delegation) { await refresh() }
                .opacity(delegation ? 0 : 1).allowsHitTesting(!delegation).accessibilityHidden(delegation)
                if delegation {
                    AgentDelegationView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat)
                }
            }
        }
        .background(NanoTheme.surface)
        .navigationTitle(sessionID == nil ? displayName ?? L("工作", "Work") : selectedSession?.label ?? L("工作记录", "Work records"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .toolbar {
            if let root, !delegation {
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink {
                        List { workDetails(root) }
                            .navigationTitle(L("更多工作信息", "Work details")).navigationBarTitleDisplayMode(.inline)
                    } label: { Image(systemName: "ellipsis") }
                    .accessibilityLabel(L("更多工作信息", "More work details"))
                }
            }
        }
    }
    private func workTab(_ title: String, showDelegation: Bool) -> some View {
        let selected = delegation == showDelegation
        return Button { delegation = showDelegation } label: {
            Text(title).font(.headline).foregroundStyle(selected ? NanoTheme.ink : NanoTheme.muted)
                .frame(minHeight: 46)
                .overlay(alignment: .bottomLeading) {
                    if selected { Capsule().fill(NanoTheme.accent).frame(height: 3) }
                }
        }.buttonStyle(.plain).accessibilityAddTraits(selected ? .isSelected : [])
    }
    private var focusedTurnLoaded: Bool {
        guard let focus else { return false }
        return visibleTurns.contains { $0.id == focus.turn.id }
    }
    private var recordList: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 16) {
                if let root, !online || root.record_sync_state != "current" {
                    Text(!online ? L("电脑离线，显示已保存的记录。暂时无法处理授权。", "Computer offline. Saved records are available, approvals are paused.")
                        : root.record_sync_state == "catching_up" ? L("正在补齐最近的记录…", "Catching up on recent work…")
                        : L("显示已保存的记录，最新进度尚未确认。", "Showing saved work. Latest progress unconfirmed."))
                        .font(.footnote).foregroundStyle(.secondary)
                }
                if executionDeleted { Text(L("执行记录已删除", "Execution record deleted")).foregroundStyle(.secondary) }
                else if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await refresh() } } }
                if !loaded { ProgressView() }
                let displayed = visibleTurns
                ForEach(Array(displayed.enumerated()), id: \.element.id) { index, turn in
                    if index > 0 && executionHistory?.hasGap(after: displayed[index - 1], before: turn) == true {
                        earlierPage(displayed[index - 1])
                        Text(L("中间轮次尚未加载", "Turns between these records have not loaded")).font(.caption).foregroundStyle(.secondary)
                    }
                    if let day = turn.startDay, index == 0 || displayed[index - 1].startDay != day {
                        HStack(spacing: 10) {
                            Text(day, format: .dateTime.month().day().weekday(.wide))
                                .fixedSize().accessibilityAddTraits(.isHeader)
                            Rectangle().frame(height: 1).foregroundStyle(NanoTheme.border)
                        }.font(.subheadline.weight(.medium)).foregroundStyle(NanoTheme.muted)
                    }
                    AgentWorkTurnView(client: client, agentID: agentID, turn: turn, sessions: root?.other_executions ?? [], online: online,
                        canManage: canManage, onOpenChat: onOpenChat, separate: separate,
                        active: headTurnIDs.contains(turn.id) && ["running", "waiting_permission", "unknown"].contains(turn.status),
                        headUpdate: headUpdate, focused: focus?.turn.id == turn.id, previewLatest: index == 0)
                        .id(turn.id)
                }
                if loaded && displayed.isEmpty && !executionDeleted && error == nil {
                    VStack(alignment: .leading, spacing: 14) {
                        Image(systemName: "book.pages").font(.system(size: 34)).foregroundStyle(NanoTheme.accent)
                        Text(L("还没有工作记录", "No work records yet")).font(.title3.bold())
                        Text(L("助手处理过的消息和任务会出现在这里。", "Messages and tasks your assistant works on will appear here."))
                            .font(.subheadline).foregroundStyle(.secondary)
                    }.padding(22).frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color("Butter").opacity(0.65), in: RoundedRectangle(cornerRadius: 18))
                }
                if let last = displayed.last, executionHistory?.hasEarlier(after: last) == true { earlierPage(last) }
            }.padding(.horizontal, 20).padding(.top, 22).padding(.bottom, 32)
        }.accessibilityIdentifier("work.records")
    }
    @ViewBuilder private func workDetails(_ root: AgentWorkPage) -> some View {
        DisclosureGroup(L("执行信息与上下文", "Execution details and context")) {
            LabeledContent("Agent", value: agentID).textSelection(.enabled)
            if let sessionID {
                if let selectedSession { Text(selectedSession.label).font(.caption) }
                Text(sessionID).font(.caption).textSelection(.enabled)
            }
            if sessionID == nil { AgentWorkUsage(value: root.latest_main_usage, title: L("最近上下文", "Latest context")) }
        }.font(.subheadline)
        if separate {
            DisclosureGroup(L("浏览关联执行", "Browse related executions"), isExpanded: $catalogOpen) {
                executionLinks
                if catalogLoading { ProgressView() }
                if let catalogError { ErrorNotice(message: catalogError); Button(L("重试", "Retry")) { Task { await loadCatalog() } } }
                if catalogLoaded { Button(L("刷新目录", "Refresh directory")) { Task { await loadCatalog(reset: true) } }.disabled(catalogLoading) }
                if catalogCursor != nil && catalogError == nil { Button(L("加载更多", "Load more")) { Task { await loadCatalog() } }.disabled(catalogLoading) }
            }.onChange(of: catalogOpen) { _, open in if open && !catalogLoaded { Task { await loadCatalog() } } }
        } else { executionLinks }
        if sessionID == nil {
            VStack(alignment: .leading, spacing: 4) {
                AgentLifecycleControls(client: client, agentID: agentID, canManage: canManage, online: online, groupDisableAction: true)
            }
        }
        if separate, let executionID {
            AgentWorkControls(client: client, base: base, sessionID: executionID, onOpenChat: onOpenChat).id(executionID)
        }
        if !controls.isEmpty {
            Section(L("控制记录", "Control records")) {
                ForEach(controls) { item in DisclosureGroup(item.kind) { JSONDetailView(value: .object(item.payload)).textSelection(.enabled) } }
            }
        }
    }
    @ViewBuilder private var executionLinks: some View {
        ForEach(sessions.filter { $0.id != sessionID }) { session in
            NavigationLink {
                AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: session.id)
            } label: { VStack(alignment: .leading) { Text(session.label); Text(agentScopeName(session.scope)).font(.caption).foregroundStyle(.secondary) } }
        }
    }
    private func earlierPage(_ turn: AgentWorkTurn) -> some View {
        VStack(alignment: .leading) {
            if loadingEarlier.contains(turn.id) {
                ProgressView()
            } else if let error = earlierErrors[turn.id] {
                ErrorNotice(message: error)
                Button(L("重试", "Retry")) { Task { await loadMore(turn) } }
            } else {
                Color.clear.frame(height: 1).accessibilityHidden(true)
            }
        }
        .id("earlier:" + turn.id)
        .listRowSeparator(.hidden)
        .onAppear {
            guard earlierErrors[turn.id] == nil else { return }
            Task { await loadMore(turn) }
        }
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
            if let id = sessionID ?? page.main_session_id {
                history[id, default: AgentWorkHistory()].merge(page)
                if let focus, focus.turn.session_id == id { history[id]?.merge(focus) }
            }
            controls = page.control_items ?? []
            root = nextRoot
            headTurnIDs = Set(page.turns.map(\.id)); headUpdate += 1
            loaded = true; error = nil
        } catch {
            guard !Task.isCancelled else { return }
            self.error = agentError(error); loaded = true
            if let api = error as? APIError, [401, 403, 404, 409, 410].contains(api.status) {
                clearRecords()
                executionDeleted = api.status == 410 && (api.code == "agent_execution_deleted" || api.detail == "agent_execution_deleted")
            }
        }
    }
    private func loadMore(_ turn: AgentWorkTurn) async {
        guard let id = executionID, loadingEarlier.insert(turn.id).inserted else { return }
        defer { loadingEarlier.remove(turn.id) }
        let combined = root?.timeline == "combined" && sessionID == nil
        let useCatalog = separate
        let pagePath = combined ? base : base + "/sessions/" + agentSegment(id) + "/turns"
        let cursor = combined ? URLQueryItem(name: "before_seq", value: turn.seq.map(String.init)) : URLQueryItem(name: "before_turn", value: turn.turn_id)
        do {
            let page: AgentWorkPage = try await client.get(pagePath, query: (useCatalog ? summaryQuery.filter { combined || $0.name != "timeline" } : []) + [cursor])
            guard !executionDeleted, loaded, executionID == id, separate == useCatalog, useCatalog == (page.catalog == "separate") else { return }
            history[id, default: AgentWorkHistory()].merge(page, after: turn)
            earlierErrors[turn.id] = nil
        } catch {
            if workAccessLost(error) { clearRecords() }
            earlierErrors[turn.id] = agentError(error)
            if workAccessLost(error) { self.error = agentError(error) }
        }
    }
    private func loadCatalog(reset: Bool = false) async {
        guard separate, !catalogLoading else { return }
        catalogLoading = true; defer { catalogLoading = false }
        do {
            let page: AgentWorkCatalogPage = try await client.get(base + "/sessions", query: (reset ? nil : catalogCursor).map { [URLQueryItem(name: "after_session", value: $0)] } ?? [])
            guard separate else { return }
            catalog = reset ? page.sessions : catalog + page.sessions
            catalogCursor = page.next_cursor; catalogLoaded = true; catalogError = nil
        } catch {
            if workAccessLost(error) { clearRecords(); self.error = agentError(error) }
            else { catalogError = agentError(error) }
        }
    }

    private func clearRecords() {
        root = nil; controls = []; history = [:]; catalog = []
        catalogLoaded = false; catalogCursor = nil; selectedSession = nil
    }
}

private struct AgentWorkControls: View {
    let client: IMClient; let base: String; let sessionID: String
    let onOpenChat: @MainActor (String) -> Void
    @State private var expanded = false
    @State private var loading = false
    @State private var items: [AgentWorkItem] = []
    @State private var cursor: String? = "0"
    @State private var error: String?
    var body: some View {
        DisclosureGroup(L("查看控制记录", "View control records"), isExpanded: $expanded) {
            ForEach(items) { item in
                DisclosureGroup(item.kind == "cron_delivery" ? L("定时任务投递", "Scheduled task delivery") : item.kind) {
                    JSONDetailView(value: .object(item.payload)).textSelection(.enabled)
                    if let chat = item.payload["conversation_id"]?.stringValue, !chat.isEmpty {
                        WorkSourceLink(client: client, conversation: chat, message: item.payload["message_id"]?.stringValue, onOpenChat: onOpenChat)
                    }
                }
            }
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

private let workClock = Date.VerbatimFormatStyle(
    format: "\(hour: .twoDigits(clock: .twentyFourHour, hourCycle: .zeroBased)):\(minute: .twoDigits):\(second: .twoDigits)",
    timeZone: .autoupdatingCurrent, calendar: .autoupdatingCurrent
)

struct AgentWorkTurnView: View {
    let client: IMClient; let agentID: String; let turn: AgentWorkTurn; let sessions: [AgentWorkSession]
    let online: Bool; let canManage: Bool; let onOpenChat: @MainActor (String) -> Void
    let separate: Bool; let active: Bool; let headUpdate: Int
    var focused = false
    var previewLatest = false
    @State private var preview: String?

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
    private var delivery: WorkDelivery? { items.reversed().lazy.compactMap(WorkDelivery.init).first }
    private var turnTiming: String {
        var parts: [String] = []
        let times = [turn.started_at, turn.finished_at].compactMap { $0.flatMap(nanoDate)?.formatted(workClock) }
        if !times.isEmpty { parts.append(times.joined(separator: " – ")) }
        let hasAllItems = separate ? didLoad && extraCursor == nil : (didLoad ? extraCursor : turn.next_items_cursor) == nil
        let count = turn.tool_count ?? (hasAllItems ? items.filter { $0.kind == "tool" }.count : nil)
        if let count { parts.append(L("\(count) 次工具", "\(count) tool calls")) }
        return parts.joined(separator: " · ")
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if focused { Label(L("这条回复的工作", "Work for this reply"), systemImage: "arrowshape.turn.up.left").font(.caption) }
            DisclosureGroup {
                Text(turn.turn_id).textSelection(.enabled)
                if let model = turn.model_id { Text(model) }
                if let origin = turn.origin { JSONDetailView(value: origin) }
                if let trigger = turn.trigger { JSONDetailView(value: .object(trigger)) }
            } label: {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(turn.title).font(.headline).foregroundStyle(NanoTheme.ink)
                        Spacer(minLength: 8)
                        Text(agentWorkStatus(state)).font(.caption.weight(.medium))
                    }
                    if !turnTiming.isEmpty { Text(turnTiming).monospacedDigit() }
                    if let stage = turn.maintenance_stage { Text(stage) }
                }
            }.disclosureGroupStyle(WorkInlineDisclosure()).font(.caption)
                .foregroundStyle(NanoTheme.muted).accessibilityIdentifier("work.turn." + turn.id)
            let previewSource = previewLatest ? delivery : nil
            ForEach(items) { item in
                AgentWorkItemView(client: client, agentID: agentID, sessionID: turn.session_id, item: item, sessions: sessions, online: online, canManage: canManage, onOpenChat: onOpenChat, separate: separate,
                    excerpt: previewSource != nil && WorkDelivery(item) == previewSource ? preview : nil)
            }
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
            let elapsed = turn.elapsed_ms.map { ms in
                let units: Set<Duration.UnitsFormatStyle.Unit> = ms < 1000 ? [.milliseconds] : [.minutes, .seconds]
                return Duration.milliseconds(ms).formatted(.units(allowed: units, width: .abbreviated))
            }
            if let usage = turn.usage, usage != .null {
                AgentWorkUsage(value: usage, title: [L("本轮统计", "Turn statistics"), elapsed].compactMap { $0 }.joined(separator: " · "))
                    .disclosureGroupStyle(WorkInlineDisclosure()).font(.caption).foregroundStyle(NanoTheme.muted)
            } else if let elapsed { Text(elapsed).font(.caption).foregroundStyle(NanoTheme.muted) }
            Divider()
        }
        .foregroundStyle(NanoTheme.ink)
        .task { if separate && !didLoad { await loadMore() } }
        .task(id: previewLatest ? delivery : nil) {
            preview = nil
            guard previewLatest, let delivery else { return }
            struct Reply: Decodable { let message: ChatMessage }
            let reply: Reply? = try? await client.get("/im/v1/conversations/" + agentSegment(delivery.conversation) + "/messages/" + agentSegment(delivery.message))
            guard !Task.isCancelled else { return }
            preview = reply?.message.availableReply?.preview(participants: [])
        }
        .onChange(of: headUpdate) { _, _ in
            if separate && (active || wasActive || moreChanges) { Task { await refreshItems() } }
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

/// Keep the full summary tappable while preserving the timeline's quiet reading layout.
private struct WorkInlineDisclosure: DisclosureGroupStyle {
    func makeBody(configuration: Configuration) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                configuration.isExpanded.toggle()
            } label: {
                configuration.label.frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityValue(configuration.isExpanded ? L("已展开", "Expanded") : L("已收起", "Collapsed"))
            if configuration.isExpanded { configuration.content }
        }
    }
}

struct AgentWorkItemView: View {
    let client: IMClient; let agentID: String; let sessionID: String; let item: AgentWorkItem; let sessions: [AgentWorkSession]
    let online: Bool; let canManage: Bool; let onOpenChat: @MainActor (String) -> Void
    private var p: [String: JSONValue] { item.payload }
    private func text(_ key: String) -> String { p[key]?.agentString ?? "" }
    let separate: Bool
    var excerpt: String?
    @ViewBuilder private var toolDetails: some View {
        let detail = p["detail"]?.agentObject ?? [:]
        let messages = detail["messages"]?.agentArray
        let sources = (detail["sources"] ?? detail["conversations"])?.agentArray
        let threads = detail["threads"]?.agentArray
        let inboxResult = ["inbox", "conversations", "read_messages", "search_messages", "threads"].contains(toolName)
            && (messages != nil || sources != nil || threads != nil)
            && text("status") == "completed" && detail["error"]?.stringValue == nil
        if inboxResult {
            if (messages ?? []).isEmpty && (sources ?? []).isEmpty && (threads ?? []).isEmpty { Text(L("没有匹配记录", "No matching records")) }
            ForEach(Array((sources ?? []).enumerated()), id: \.offset) { _, source in
                Text((source["name"].stringValue ?? source["target"].stringValue) ?? "")
            }
            ForEach(Array((threads ?? []).enumerated()), id: \.offset) { _, thread in
                VStack(alignment: .leading, spacing: 2) {
                    Text(thread["parent_name"].stringValue ?? thread["target"].stringValue ?? "").font(.caption).foregroundStyle(.secondary)
                    if let excerpt = thread["root_excerpt"].stringValue, !excerpt.isEmpty { Text(excerpt).lineLimit(2) }
                }
            }
            ForEach(Array((messages ?? []).enumerated()), id: \.offset) { _, message in
                if let sender = message["sender"]["name"].stringValue ?? message["sender"]["display_name"].stringValue ?? message["sender"].stringValue {
                    Text(sender).font(.caption).foregroundStyle(.secondary)
                }
                if let parts = message["content"].arrayValue {
                    ForEach(Array(parts.enumerated()), id: \.offset) { _, part in
                        if let label = part["text"].stringValue ?? part["file_name"].stringValue { Text(label).textSelection(.enabled) }
                        else { JSONDetailView(value: part) }
                    }
                } else { JSONDetailView(value: message["content"]) }
                if let rawTarget = message["source"]["conversation_id"].stringValue ?? message["target"].stringValue ?? detail["target"]?.stringValue ?? input["target"]?.stringValue,
                   !rawTarget.isEmpty, !rawTarget.hasPrefix("external:"), !rawTarget.hasPrefix("local:"),
                   let id = message["message_id"].stringValue ?? message["id"].stringValue, !id.isEmpty {
                    let target = rawTarget.split(separator: ":", maxSplits: 1).first.map(String.init) ?? rawTarget
                    chatLink(target, message: id)
                }
            }
        } else if toolName == "skill", let name = input["name"]?.stringValue {
            LabeledContent(L("技能", "Skill"), value: name)
        } else if toolName == "send_message", let message = (input["text"] ?? input["message"])?.stringValue {
            Text(L("消息内容", "Message text")).font(.caption).foregroundStyle(.secondary)
            Text(message).textSelection(.enabled)
        } else if let args = p["input"] ?? p["arguments"] {
            Text(L("参数", "Arguments")).font(.caption).foregroundStyle(.secondary)
            JSONDetailView(value: args)
        }
        if toolName == "send_message", let status = p["detail"]?.agentObject["status"]?.stringValue {
            LabeledContent(L("发送结果", "Delivery status"), value: status == "sent" ? L("已发送", "Sent") : agentBusinessStatus(status))
            if let error = p["detail"]?.agentObject["error"], error != .null { JSONDetailView(value: error) }
        } else if !inboxResult,
                  let output = p["output"] ?? p["summary"] {
            Text(L("结果", "Result")).font(.caption).foregroundStyle(.secondary)
            JSONDetailView(value: output)
        }
        if let approval = p["approval"] { LabeledContent(L("授权结果", "Approval"), value: approval.prettyPrinted) }
        if let duration = p["duration_ms"] ?? p["elapsed_ms"] { LabeledContent(L("耗时（毫秒）", "Duration (ms)"), value: duration.prettyPrinted) }
        DisclosureGroup(L("原始数据", "Raw data")) {
            JSONDetailView(value: .object(p))
            toolLinks(late: true)
        }.disclosureGroupStyle(WorkInlineDisclosure())
    }
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
    @ViewBuilder private func timed<Content: View>(showTime: Bool = true, @ViewBuilder _ content: () -> Content) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            if let observed = item.observed_at, let time = nanoDate(observed) {
                Text(time.formatted(workClock))
                    .font(.caption2.monospacedDigit()).foregroundStyle(NanoTheme.muted).fixedSize()
                    .opacity(showTime ? 1 : 0).accessibilityHidden(!showTime)
            }
            content()
        }
    }
    var body: some View {
        if item.kind == "tool" {
            VStack(alignment: .leading, spacing: 0) {
                DisclosureGroup {
                    VStack(alignment: .leading, spacing: 7) {
                        toolDetails
                        workFacts
                    }
                    .font(.footnote).padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 10))
                } label: {
                    timed {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(toolTitle).font(.subheadline.weight(.semibold))
                            if let note = toolNote { Text(note).font(.footnote).foregroundStyle(NanoTheme.muted).lineLimit(3) }
                        }
                    }
                }.disclosureGroupStyle(WorkInlineDisclosure())
                if let delivery = WorkDelivery(item) {
                    timed(showTime: false) {
                        VStack(alignment: .leading, spacing: 2) {
                            if let excerpt { Text(verbatim: excerpt).font(.footnote).lineLimit(2) }
                            WorkSourceLink(client: client, conversation: delivery.conversation, message: delivery.message, onOpenChat: onOpenChat)
                                .font(.footnote.weight(.medium)).foregroundStyle(NanoTheme.accent)
                        }
                    }.padding(.vertical, 4)
                }
                toolLinks()
            }
        } else {
            timed { otherActivity }
        }
    }
    private var otherActivity: some View {
        VStack(alignment: .leading, spacing: 8) {
            if item.kind == "permission" {
                AgentWorkPermissionView(client: client, agentID: agentID, payload: p, enabled: online && canManage)
            } else if ["message", "message_delta", "text_delta", "assistant_message", "thinking", "thinking_delta", "reasoning"].contains(item.kind) {
                if !text("reasoning_content").isEmpty { DisclosureGroup(L("思考", "Reasoning")) { Text(text("reasoning_content")).textSelection(.enabled) } }
                let body = [text("text"), text("content"), text("delta")].first { !$0.isEmpty } ?? ""
                if !body.isEmpty {
                    if ["thinking", "thinking_delta", "reasoning"].contains(item.kind) { DisclosureGroup(L("思考", "Reasoning")) { Text(body).textSelection(.enabled) } }
                    else {
                        VStack(alignment: .leading, spacing: 4) {
                            if text("role") == "assistant" { Text(L("助手记录", "Assistant note")).font(.caption.weight(.semibold)).foregroundStyle(NanoTheme.muted) }
                            MarkdownView(text: body, client: client)
                        }.padding(10).frame(maxWidth: .infinity, alignment: .leading)
                            .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 10))
                    }
                }
                links(id: text("source_session_id"))
                backgroundReturns
            } else if item.kind == "background_return" {
                AgentBackgroundResult(value: .object(p))
                links(id: text("child_session_id"), agent: text("agent_id"))
            } else if item.kind == "injection_consumed" {
                if (p["user_message_count"]?.doubleValue ?? 0) > 0 { Text(L("收到补充输入", "Received additional input")) }
                links(id: text("source_session_id")); backgroundReturns
            }
            else if item.kind == "recording_degraded" { Label(L("工作记录存在缺口", "Work recording has gaps"), systemImage: "exclamationmark.triangle") }
            else {
                DisclosureGroup(item.kind) { JSONDetailView(value: .object(p)) }
                if !text("conversation_id").isEmpty { chatLink(text("conversation_id"), message: text("message_id")) }
            }

        }
    }
    private var toolName: String { text("name").isEmpty ? text("tool_name") : text("name") }
    private var input: [String: JSONValue] { (p["input"] ?? p["arguments"])?.agentObject ?? [:] }
    private var toolTitle: String {
        let action = input["action"]?.stringValue
        switch toolName {
        case "inbox" where action == "check": return L("检查新消息", "Check for new messages")
        case "inbox" where action == "read": return L("读取新消息", "Read new messages")
        case "read": return L("读取文件", "Read file")
        case "edit": return L("编辑文件", "Edit file")
        case "write": return L("写入文件", "Write file")
        case "skill": return L("使用技能", "Use skill")
        case "send_message": return L("发送消息", "Send message")
        case "conversations" where action == "list": return L("查找聊天", "Find conversations")
        case "conversations" where action == "info": return L("查看聊天信息", "Inspect conversation")
        case "conversations" where action == "create": return L("创建群聊", "Create group")
        case "conversations" where action == "join": return L("加入群聊", "Join group")
        case "read_messages": return L("读取历史消息", "Read messages")
        case "search_messages": return L("搜索历史消息", "Search messages")
        case "threads" where action == "list": return L("查看关注的话题", "List followed threads")
        case "threads" where action == "follow": return L("关注话题", "Follow thread")
        case "threads" where action == "unfollow": return L("取消关注话题", "Unfollow thread")
        default: return toolName.isEmpty ? L("工具调用", "Tool call") : toolName
        }
    }
    private var toolNote: String? {
        let result = p["detail"]?.agentObject ?? [:]
        var notes: [String] = []
        if text("approval") == "user_deny" || text("reason") == "denied" { notes.append(L("已拒绝", "Denied")) }
        else if text("reason") == "interrupted" { notes.append(agentWorkStatus("interrupted")) }
        else if text("status") == "failed" || p["is_error"] == .bool(true) || result["success"] == .bool(false) || (result["error"] != nil && result["error"] != .null && result["error"] != .string("")) {
            notes.append(agentWorkStatus("failed"))
        } else if text("status") != "completed" { notes.append(agentWorkStatus(text("status").isEmpty ? "unknown" : text("status"))) }
        if let business = result["status"]?.stringValue, !["ok", "completed", "success"].contains(business) {
            notes.append(business == "sent" ? L("已发送", "Sent") : agentBusinessStatus(business))
        }
        if toolName == "skill", let name = input["name"]?.stringValue { notes.append(name) }
        else if ["read", "edit", "write"].contains(toolName),
                let path = (input["file_path"] ?? input["path"])?.stringValue, !path.isEmpty {
            notes.append((path as NSString).lastPathComponent)
        }
        else if ["inbox", "read_messages", "search_messages"].contains(toolName), let count = result["messages"]?.agentArray.count { notes.append(L("共 " + String(count) + " 条消息", String(count) + " messages")) }
        else if toolName == "threads", let count = result["threads"]?.agentArray.count { notes.append(L("共 " + String(count) + " 个话题", String(count) + " threads")) }
        else if let summary = (p["summary"] ?? p["output"])?.stringValue?.trimmingCharacters(in: .whitespacesAndNewlines),
                !summary.isEmpty, !summary.hasPrefix("{"), !summary.hasPrefix("["), summary != toolName {
            notes.append(summary)
        }
        return notes.isEmpty ? nil : notes.joined(separator: " · ")
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
                if let text = (fact["text"] ?? fact["draft"])?.stringValue, !text.isEmpty { Text(text).textSelection(.enabled) }
                if let target = (fact["conversation_id"] ?? fact["target"])?.agentString, !target.isEmpty { chatLink(target, message: fact["message_id"]?.stringValue) }
                ForEach(Array((fact["source_refs"]?.agentArray ?? []).enumerated()), id: \.offset) { _, reference in
                    if let target = reference.agentObject["conversation_id"]?.agentString, !target.isEmpty { chatLink(target, message: reference.agentObject["message_id"]?.stringValue) }
                }
            }
        }
    }
    private func childLink(_ id: String, label: String) -> some View {
        NavigationLink(L("查看关联执行：", "Open related execution: ") + label) { AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: id) }
    }
    private func chatLink(_ id: String, message: String?) -> some View {
        WorkSourceLink(client: client, conversation: id, message: message, onOpenChat: onOpenChat)
    }

}

private struct WorkSourceLink: View {
    let client: IMClient
    let conversation: String
    let message: String?
    let onOpenChat: @MainActor (String) -> Void
    @Environment(\.openURL) private var openURL
    @State private var error: String?
    var body: some View {
        Button(message?.isEmpty == false ? L("查看原消息", "View original message") : L("打开来源聊天", "Open source chat")) {
            Task {
                do {
                    let _: AgentChatCreated = try await client.get("/im/v1/conversations/" + agentSegment(conversation))
                    // The presenting Activity sheet may need to close before the root resolves an exact message.
                    onOpenChat(conversation)
                    if let message, !message.isEmpty {
                        let url = client.baseURL.appending(path: "chat").appending(component: conversation)
                            .appending(queryItems: [.init(name: "message_id", value: message)])
                        openURL(url)
                    }
                    error = nil
                } catch { self.error = agentError(error) }
            }
        }
        if let error { ErrorNotice(message: error) }
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
