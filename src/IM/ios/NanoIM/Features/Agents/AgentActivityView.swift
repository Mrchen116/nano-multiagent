import SwiftUI

/// Lightweight activity opened from a chat avatar. Full records load on navigation.
struct AgentActivityView: View {
    let client: IMClient
    let contact: Contact
    let canManage: Bool
    let onOpenChat: @MainActor (String) -> Void
    var onExpand: () -> Void = {}
    private var agentID: String { contact.agent_id ?? contact.id }
    private var path: String { agentPath(agentID) + "/work/activity" }
    @State private var page: AgentActivityPage?
    @State private var sessions: [AgentActivitySession] = []
    @State private var cursor: String?
    @State private var expanded = false
    @State private var paging = false
    @State private var error: String?

    var body: some View {
        List {
            Section {
                HStack(spacing: 12) {
                    AvatarView(name: contact.display_name, online: page?.node_connection_state == "online", kind: "agent", agentID: agentID, role: contact.role, variant: contact.avatar_variant)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(contact.display_name).font(.headline)
                        if let node = contact.node_name { Label(node, systemImage: "desktopcomputer").font(.subheadline).foregroundStyle(.secondary) }
                    }
                }.padding(.vertical, 6)
                if let page {
                    LabeledContent(L("主 Agent", "Main agent"), value: page.node_connection_state == "online" ? agentWorkStatus(page.main_execution) : L("离线", "Offline"))
                    if page.node_connection_state == "online", ["running", "waiting_permission"].contains(page.main_execution), let tool = page.latest_tool {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(L("最近工具", "Latest tool")).font(.caption).foregroundStyle(.secondary)
                            Text([tool.name, tool.label, tool.status.map(agentWorkStatus)].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · "))
                        }
                    }
                    if page.confirmedChildren, let running = page.running_count, let waiting = page.waiting_permission_count {
                        if running + waiting > 0 {
                            DisclosureGroup(isExpanded: $expanded) {
                                ForEach(sessions) { session in
                                    NavigationLink {
                                        AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: session.id)
                                            .onAppear(perform: onExpand)
                                    } label: {
                                        VStack(alignment: .leading) {
                                            Text(session.title ?? session.id)
                                            Text(agentWorkStatus(session.status)).font(.caption).foregroundStyle(.secondary)
                                        }
                                    }
                                }
                                if cursor != nil {
                                    Button(L("更多子执行", "More child executions")) { Task { await loadMore() } }.disabled(paging)
                                }
                            } label: {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(L("子执行", "Child executions"))
                                    Text(L("\(running) 个运行中 · \(waiting) 个等待授权", "\(running) running · \(waiting) awaiting permission")).font(.subheadline).foregroundStyle(.secondary)
                                }
                            }
                        } else { LabeledContent(L("子执行", "Child executions"), value: L("0 个运行中", "0 running")) }
                    } else {
                        LabeledContent(L("子执行", "Child executions"), value: page.record_sync_state == "catching_up" ? L("记录同步中", "Syncing records") : L("未知", "Unknown"))
                    }
                } else if error == nil { ProgressView(L("正在读取活动", "Loading activity")) }
                if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await refresh() } } }
            }
            if page != nil {
                Section {
                    NavigationLink {
                        AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, displayName: contact.display_name)
                            .onAppear(perform: onExpand)
                    } label: { Label(L("查看工作记录", "View work records"), systemImage: "list.bullet.rectangle") }
                    if canManage {
                        NavigationLink { AgentConfigView(client: client, agentID: agentID).onAppear(perform: onExpand) } label: { Label(L("配置", "Configuration"), systemImage: "slider.horizontal.3") }
                    }
                }
            }
        }.listStyle(.insetGrouped).scrollContentBackground(.hidden).background(NanoTheme.canvas)
        .navigationTitle(L("当前活动", "Current activity")).navigationBarTitleDisplayMode(.inline)
        .toolbar(.hidden, for: .tabBar)
        .workRefresh(client: client, agentID: agentID, every: 15) { await refresh() }
    }

    private func refresh() async {
        do {
            let next: AgentActivityPage = try await client.get(path)
            guard !Task.isCancelled else { return }
            if page?.revision != next.revision || page?.confirmedChildren != next.confirmedChildren {
                sessions = next.sessions
                cursor = next.next_cursor
            }
            page = next
            error = nil
        } catch {
            guard !Task.isCancelled else { return }
            if workAccessLost(error) { page = nil; sessions = []; cursor = nil }
            self.error = agentError(error)
        }
    }

    private func loadMore() async {
        guard let cursor, let revision = page?.revision, !paging else { return }
        paging = true
        defer { paging = false }
        do {
            let next: AgentActivityPage = try await client.get(path, query: [.init(name: "after_session", value: cursor)])
            guard !Task.isCancelled, page?.confirmedChildren == true, page?.revision == revision else { return }
            guard next.revision == revision else { await refresh(); return }
            let known = Set(sessions.map(\.id))
            sessions += next.sessions.filter { !known.contains($0.id) }
            self.cursor = next.next_cursor
            error = nil
        } catch {
            if workAccessLost(error) { page = nil; sessions = []; self.cursor = nil }
            self.error = agentError(error)
        }
    }
}

/// Resolve a historic delivery to its real execution before showing any turns.
struct AgentMessageWorkView: View {
    let client: IMClient
    let agentID: String
    let messageID: String
    let canManage: Bool
    let onOpenChat: @MainActor (String) -> Void
    @State private var focus: AgentWorkFocus?
    @State private var loaded = false
    @State private var error: String?
    var body: some View {
        Group {
            if let focus {
                AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat,
                              sessionID: focus.turn.session_id, focus: focus)
            } else {
                VStack(spacing: 12) {
                    if let error { ErrorNotice(message: error) }
                    else if loaded {
                        ContentUnavailableView(L("这条回复暂无工作记录", "No work record for this reply"), systemImage: "doc.text.magnifyingglass")
                    } else { ProgressView() }
                    if loaded { Button(L("重新查找", "Check again")) { Task { await resolve() } } }
                }.padding().navigationTitle(L("回复的工作记录", "Work for this reply"))
                .workRefresh(client: client, agentID: agentID, every: 15) { await resolve() }
            }
        }.toolbar(.hidden, for: .tabBar)
    }
    private func resolve() async {
        struct Reply: Decodable { let focus: AgentWorkFocus? }
        do {
            let response: Reply = try await client.get(agentPath(agentID) + "/work/focus", query: [
                .init(name: "message_id", value: messageID), .init(name: "catalog", value: "separate")
            ])
            guard !Task.isCancelled else { return }
            focus = response.focus
            error = nil; loaded = true
        } catch {
            guard !Task.isCancelled else { return }
            if let api = error as? APIError, api.status == 410 {
                self.error = L("这条回复的执行记录已删除。", "The execution record for this reply was deleted.")
            } else { self.error = agentError(error) }
            loaded = true
        }
    }
}
