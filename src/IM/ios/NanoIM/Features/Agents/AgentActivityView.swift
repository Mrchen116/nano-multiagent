import SwiftUI

/// Lightweight activity opened from a chat avatar. Full records load on navigation.
struct AgentActivityView: View {
    let client: IMClient
    let contact: Contact
    let canManage: Bool
    let onOpenChat: @MainActor (String) -> Void
    static let compactDetent = PresentationDetent.height(184)
    @Binding var detent: PresentationDetent
    @Environment(\.dynamicTypeSize) private var typeSize
    private var agentID: String { contact.agent_id ?? contact.id }
    private var path: String { agentPath(agentID) + "/work/activity" }
    @State private var page: AgentActivityPage?
    @State private var sessions: [AgentActivitySession] = []
    @State private var cursor: String?
    @State private var expanded = true
    @State private var paging = false
    @State private var error: String?

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack(alignment: .center, spacing: 10) {
                    AvatarView(id: .contact(contact), size: 70, online: page?.node_connection_state == "online")
                    VStack(alignment: .leading, spacing: 5) {
                        Text(contact.display_name).font(.subheadline.weight(.medium)).foregroundStyle(.secondary)
                        if let page {
                            Text(error == nil ? headline(page) : L("暂时无法更新近况", "Activity could not be refreshed")).font(.title3.bold()).fixedSize(horizontal: false, vertical: true)
                        } else if error == nil {
                            ProgressView(L("正在查看近况…", "Checking activity…")).font(.footnote)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                    Button { dismiss() } label: {
                        Image(systemName: "xmark").font(.subheadline.weight(.semibold))
                            .frame(width: 32, height: 32).background(NanoTheme.canvas, in: Circle())
                            .frame(width: 44, height: 44)
                    }.accessibilityLabel(L("关闭", "Close"))
                }
                if let error {
                    ErrorNotice(message: error)
                    Button(L("重试", "Retry")) { Task { await refresh() } }
                }
                if let page {
                    if page.node_connection_state == "online", ["running", "waiting_permission"].contains(page.main_execution), let tool = page.latest_tool {
                        Label([tool.label ?? tool.name, tool.status.map(agentWorkStatus)].compactMap { $0 }.joined(separator: " · "),
                              systemImage: "wrench.and.screwdriver").font(.subheadline)
                    }
                    if page.confirmedChildren, let running = page.running_count, let waiting = page.waiting_permission_count {
                        if running + waiting > 0 {
                            DisclosureGroup(isExpanded: $expanded) {
                                VStack(alignment: .leading, spacing: 12) {
                                    ForEach(sessions) { session in
                                        if session.canOpenRecords {
                                            NavigationLink {
                                                AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: session.id)
                                                    .onAppear { detent = .large }
                                            } label: { sessionLabel(session) }
                                        } else {
                                            NavigationLink {
                                                AgentDelegationView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat)
                                                    .navigationTitle(L("派工关系", "Delegations")).onAppear { detent = .large }
                                            } label: { sessionLabel(session) }
                                        }
                                    }
                                    if cursor != nil {
                                        Button(L("查看更多", "Show more")) { Task { await loadMore() } }.disabled(paging)
                                    }
                                }.frame(maxWidth: .infinity, alignment: .leading).padding(.top, 8)
                            } label: {
                                Text([running > 0 ? L("\(running) 项协作进行中", "\(running) in progress") : nil,
                                      waiting > 0 ? L("\(waiting) 项待授权", "\(waiting) awaiting permission") : nil]
                                    .compactMap { $0 }.joined(separator: " · ")).font(.subheadline.weight(.medium))
                            }
                        }
                    } else if page.node_connection_state == "online" {
                        Text(page.record_sync_state == "catching_up" ? L("正在同步协作进度…", "Syncing delegated work…") : L("协作进度暂未确认", "Delegated work status is unavailable"))
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                    HStack(spacing: 10) {
                        NavigationLink {
                            AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, displayName: contact.display_name)
                                .onAppear { detent = .large }
                        } label: {
                            Label(L("查看工作记录", "View work records"), systemImage: "clock.arrow.circlepath")
                                .font(.headline).frame(maxWidth: .infinity, minHeight: 48)
                                .foregroundStyle(.white).background(NanoTheme.accent, in: Capsule())
                        }
                        if canManage {
                            NavigationLink {
                                AgentConfigView(client: client, agentID: agentID, personal: contact.role == "personal").onAppear { detent = .large }
                            } label: {
                                Image(systemName: "gearshape").font(.title3).frame(width: 48, height: 48)
                                    .background(NanoTheme.surface, in: Circle())
                                    .overlay { Circle().strokeBorder(NanoTheme.border) }
                                    .accessibilityLabel(L("助手设置", "Assistant settings"))
                            }
                        }
                    }
                }
            }.padding(.horizontal, 22).padding(.top, 30).padding(.bottom, 14)
        }
        .background {
            LinearGradient(colors: [Color("Butter").opacity(0.4), NanoTheme.surface, NanoTheme.surface], startPoint: .topLeading, endPoint: .bottomTrailing)
                .ignoresSafeArea()
        }.foregroundStyle(NanoTheme.ink).buttonStyle(.plain)
        .toolbar(.hidden, for: .navigationBar).toolbar(.hidden, for: .tabBar)
        .onAppear { detent = summaryDetent }
        .onChange(of: summaryDetent) { _, next in if detent != .large { detent = next } }
        .workRefresh(client: client, agentID: agentID, every: 15) { await refresh() }
    }

    private var summaryDetent: PresentationDetent {
        if typeSize.isAccessibilitySize { return .large }
        if error != nil { return .medium }
        guard let page, page.node_connection_state == "online" else { return Self.compactDetent }
        let hasActivity = (page.running_count ?? 0) + (page.waiting_permission_count ?? 0) > 0
        let showsTool = page.latest_tool != nil && ["running", "waiting_permission"].contains(page.main_execution)
        return hasActivity || showsTool || !page.confirmedChildren ? .medium : Self.compactDetent
    }

    private func headline(_ page: AgentActivityPage) -> String {
        guard page.node_connection_state == "online" else { return L("电脑离线，暂时看不到近况", "Computer offline. Activity is unavailable.") }
        switch page.main_execution {
        case "idle":
            if page.confirmedChildren && page.running_count == 0 && page.waiting_permission_count == 0 {
                return L("现在有空，可以聊聊", "Free for a chat")
            }
            return L("助手当前空闲", "The assistant is idle")
        case "running": return L("正在处理工作", "Working on a task")
        case "waiting_permission": return L("需要授权才能继续", "Waiting for permission to continue")
        case "unknown": return L("暂时看不到近况", "Activity is unavailable")
        default: return agentWorkStatus(page.main_execution)
        }
    }

    private func sessionLabel(_ session: AgentActivitySession) -> some View {
        VStack(alignment: .leading) {
            Text(session.title ?? L("协作任务", "Delegated task"))
            Text(agentWorkStatus(session.status))
                .font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
        .contentShape(Rectangle())
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
