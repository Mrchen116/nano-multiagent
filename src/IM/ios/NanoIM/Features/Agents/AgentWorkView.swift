import SwiftUI

/// Refresh visible Work only; original chat navigation still requires server authorization.
struct AgentWorkView: View {
    let client: IMClient; let agentID: String; let canManage: Bool; let onOpenChat: @MainActor (String) -> Void
    var sessionID: String? = nil
    @Environment(\.scenePhase) private var scenePhase
    @State private var root: AgentWorkPage?
    @State private var turns: [AgentWorkTurn] = []
    @State private var controls: [AgentWorkItem] = []
    @State private var cursor: String?
    @State private var loaded = false
    @State private var error: String?
    @State private var loadingMore = false
    @State private var pageCount = 1
    private var base: String { agentPath(agentID) + "/work" }
    private var path: String { sessionID.map { base + "/sessions/" + agentSegment($0) + "/turns" } ?? base }
    private var online: Bool { root?.node_connection_state == "online" }
    var body: some View {
        List {
            if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await refresh() } } }
            if !loaded { ProgressView() }
            if let root {
                Section(L("执行归属", "Execution ownership")) {
                    LabeledContent("Agent", value: agentID)
                    if let sessionID { Text(sessionID).font(.caption).textSelection(.enabled) }
                    LabeledContent(L("节点", "Node"), value: online ? L("在线", "Online") : L("离线 · 活动状态未知", "Offline · active status unknown"))
                    LabeledContent(L("主执行", "Main execution"), value: agentWorkStatus(root.main_execution ?? "unknown"))
                    if !online { Text(L("显示已保存的记录，授权暂不可处理。", "Showing saved records. Permissions cannot be processed while offline.")).font(.caption) }
                    if sessionID == nil { AgentWorkUsage(value: root.latest_main_usage, title: L("最近已报告的主上下文", "Latest reported main context")) }
                }
                if !(root.other_executions ?? []).isEmpty {
                    Section(L("关联执行", "Related executions")) {
                        ForEach(root.other_executions ?? []) { session in
                            if session.id != sessionID {
                                NavigationLink {
                                    AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: session.id)
                                } label: { VStack(alignment: .leading) { Text(session.label); Text(session.scope + " · " + session.id).font(.caption).foregroundStyle(.secondary); if let parent = session.parent_session_id { Text(L("父会话：", "Parent session: ") + parent).font(.caption) } } }
                            }
                        }
                    }
                }
            }
            Section(L("执行轮次 · 最新在前", "Turns · newest first")) {
                ForEach(turns) { turn in
                    AgentWorkTurnView(client: client, agentID: agentID, turn: turn, sessions: root?.other_executions ?? [], online: online, canManage: canManage, onOpenChat: onOpenChat)
                }
                if loaded && turns.isEmpty { Text(L("尚未报告执行轮次", "No reported turns")) }
                if cursor != nil { Button(L("更早轮次", "Earlier turns")) { Task { await loadMore() } }.disabled(loadingMore) }
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
    private func refresh() async {
        do {
            let page: AgentWorkPage = try await client.get(path)
            let nextRoot: AgentWorkPage
            if sessionID != nil { nextRoot = try await client.get(base) } else { nextRoot = page }
            var all = page.turns
            var nextCursor = page.next_cursor
            if pageCount > 1 {
                for _ in 1..<pageCount {
                    guard let before = nextCursor else { break }
                    let older: AgentWorkPage = try await client.get(path, query: [URLQueryItem(name: "before_turn", value: before)])
                    let ids = Set(all.map(\.id)); all += older.turns.filter { !ids.contains($0.id) }; nextCursor = older.next_cursor
                }
            }
            guard !Task.isCancelled else { return }
            root = nextRoot; controls = page.control_items ?? []
            turns = all; cursor = nextCursor
            loaded = true; error = nil
        } catch { if !Task.isCancelled { self.error = agentError(error); loaded = true; if let api = error as? APIError, [401, 403, 404].contains(api.status) { root = nil; turns = []; controls = [] } } }
    }
    private func loadMore() async {
        guard let cursor else { return }; loadingMore = true; defer { loadingMore = false }
        do {
            let page: AgentWorkPage = try await client.get(path, query: [URLQueryItem(name: "before_turn", value: cursor)])
            let existing = Set(turns.map(\.id)); turns += page.turns.filter { !existing.contains($0.id) }; self.cursor = page.next_cursor; pageCount += 1
        } catch { self.error = agentError(error) }
    }
}

struct AgentWorkTurnView: View {
    let client: IMClient; let agentID: String; let turn: AgentWorkTurn; let sessions: [AgentWorkSession]
    let online: Bool; let canManage: Bool; let onOpenChat: @MainActor (String) -> Void
    @State private var expanded = false
    @State private var extra: [AgentWorkItem] = []
    @State private var extraCursor: String?
    @State private var didLoad = false
    @State private var busy = false
    @State private var error: String?
    private var items: [AgentWorkItem] {
        var map = Dictionary(uniqueKeysWithValues: extra.map { ($0.id, $0) })
        for item in turn.items { map[item.id] = item }
        return agentVisibleWorkItems(Array(map.values))
    }
    private var state: String { !online && ["running", "waiting_permission"].contains(turn.status) ? "unknown" : turn.status }
    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            VStack(alignment: .leading, spacing: 12) {
                Text(turn.turn_id).font(.caption).textSelection(.enabled)
                Text(turn.model_id ?? L("模型未报告", "Model unreported")).font(.caption)
                if let origin = turn.origin { Text(L("触发来源：", "Origin: ") + (origin.agentString.isEmpty ? origin.prettyPrinted : origin.agentString)).font(.caption) }
                if let trigger = turn.trigger { DisclosureGroup(L("触发详情", "Trigger details")) { JSONDetailView(value: .object(trigger)) } }
                ForEach(items) { item in
                    AgentWorkItemView(client: client, agentID: agentID, sessionID: turn.session_id, item: item, sessions: sessions, online: online, canManage: canManage, onOpenChat: onOpenChat)
                    Divider()
                }
                AgentWorkUsage(value: turn.usage, title: L("本轮统计", "Turn statistics"))
                if let elapsed = turn.elapsed_ms { LabeledContent(L("耗时", "Duration"), value: String(format: "%.2f s", elapsed / 1000)) }
                if (didLoad ? extraCursor : turn.next_items_cursor) != nil { Button(L("加载更多过程", "Load more process")) { Task { await loadMore() } }.disabled(busy) }
                if let error { ErrorNotice(message: error) }
            }.padding(.vertical, 8)
        } label: {
            VStack(alignment: .leading) {
                Text(turn.description ?? turn.scope ?? L("执行轮次", "Execution turn")).font(.headline)
                Text(agentWorkStatus(state) + " · " + (turn.started_at ?? L("时间未报告", "Time unreported"))).font(.caption).foregroundStyle(.secondary)
                if let finish = turn.finished_at { Text(finish).font(.caption).foregroundStyle(.secondary) }
            }
        }
    }
    private func loadMore() async {
        busy = true; defer { busy = false }
        let after = didLoad ? extraCursor ?? String(items.last?.seq ?? 0) : String(items.last?.seq ?? 0)
        do {
            let page: AgentWorkItemPage = try await client.get(agentPath(agentID) + "/work/sessions/" + agentSegment(turn.session_id) + "/turns/" + agentSegment(turn.turn_id) + "/items", query: [URLQueryItem(name: "after_seq", value: after)])
            let existing = Set(extra.map(\.id)); extra += page.items.filter { !existing.contains($0.id) }; extraCursor = page.next_cursor; didLoad = true; error = nil
        } catch { self.error = agentError(error) }
    }
}

struct AgentWorkItemView: View {
    let client: IMClient; let agentID: String; let sessionID: String; let item: AgentWorkItem; let sessions: [AgentWorkSession]
    let online: Bool; let canManage: Bool; let onOpenChat: @MainActor (String) -> Void
    @State private var navigationError: String?
    private var p: [String: JSONValue] { item.payload }
    private func text(_ key: String) -> String { p[key]?.agentString ?? "" }
    private var children: [AgentWorkSession] {
        let detail = p["detail"]?.agentObject ?? [:]
        let input = (p["input"] ?? p["arguments"])?.agentObject ?? [:]
        let childID = text("child_session_id").isEmpty ? detail["child_session_id"]?.agentString ?? "" : text("child_session_id")
        return sessions.filter { $0.id == childID || ($0.parent_session_id == sessionID && ($0.parent_tool_call_id == text("id") || ($0.child_agent_id != nil && $0.child_agent_id == (detail["agent_id"] ?? input["agent_id"])?.agentString))) }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if item.kind == "permission" {
                AgentWorkPermissionView(client: client, agentID: agentID, payload: p, enabled: online && canManage)
            } else if item.kind == "tool" {
                DisclosureGroup {
                    if let input = p["input"] ?? p["arguments"] { Text(L("参数", "Arguments")).font(.caption); JSONDetailView(value: input) }
                    if let output = p["output"] ?? p["summary"] { Text(L("结果", "Result")).font(.caption); JSONDetailView(value: output) }
                    if let detail = p["detail"] { DisclosureGroup(L("详细过程", "Process details")) { JSONDetailView(value: detail) } }
                    if let approval = p["approval"] { DisclosureGroup(L("授权结果", "Approval result")) { JSONDetailView(value: approval) } }
                    if let duration = p["duration_ms"] ?? p["elapsed_ms"] { LabeledContent(L("耗时（毫秒）", "Duration (ms)"), value: duration.prettyPrinted) }
                    let business = p["detail"]?.agentObject["status"]?.agentString ?? ""
                    if !business.isEmpty { Text(agentBusinessStatus(business)).font(.caption) }
                    Text(L("工具调用完成不代表子执行完成，也不代表已向聊天发送。", "A completed tool call does not mean its child execution completed or a chat message was delivered.")).font(.caption).foregroundStyle(.secondary)
                    ForEach(children) { child in childLink(child) }
                    workFacts
                } label: { Text((text("name").isEmpty ? text("tool_name") : text("name")) + " · " + (text("status") == "completed" ? L("调用完成", "Call completed") : agentWorkStatus(text("status").isEmpty ? "unknown" : text("status")))) }
            } else if ["message", "message_delta", "text_delta", "assistant_message", "thinking", "thinking_delta", "reasoning"].contains(item.kind) {
                if !text("reasoning_content").isEmpty { DisclosureGroup(L("思考", "Reasoning")) { Text(text("reasoning_content")).textSelection(.enabled) } }
                let body = [text("text"), text("content"), text("delta")].first { !$0.isEmpty } ?? ""
                if !body.isEmpty {
                    if ["thinking", "thinking_delta", "reasoning"].contains(item.kind) { DisclosureGroup(L("思考", "Reasoning")) { Text(body).textSelection(.enabled) } }
                    else { MarkdownView(text: body, client: client) }
                }
                backgroundReturns
            } else if item.kind == "background_return" {
                AgentBackgroundResult(value: .object(p))
                ForEach(sessions.filter { $0.id == text("child_session_id") || ($0.child_agent_id != nil && $0.child_agent_id == text("agent_id")) }) { childLink($0) }
            } else if item.kind == "injection_consumed" { backgroundReturns }
            else if item.kind == "recording_degraded" { Label(L("工作记录存在缺口", "Work recording has gaps"), systemImage: "exclamationmark.triangle") }
            else {
                DisclosureGroup(item.kind) { JSONDetailView(value: .object(p)) }
                if !text("conversation_id").isEmpty { chatLink(text("conversation_id")) }
            }
            if let observed = item.observed_at { Text(observed).font(.caption2).foregroundStyle(.secondary) }
            if let navigationError { ErrorNotice(message: navigationError) }
        }
    }
    @ViewBuilder private var backgroundReturns: some View {
        ForEach(Array((p["background_returns"]?.agentArray ?? []).enumerated()), id: \.offset) { _, value in
            AgentBackgroundResult(value: value)
            let data = value.agentObject
            ForEach(sessions.filter { $0.id == data["child_session_id"]?.agentString || ($0.child_agent_id != nil && $0.child_agent_id == data["agent_id"]?.agentString) }) { childLink($0) }
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
    private func childLink(_ child: AgentWorkSession) -> some View {
        NavigationLink(L("查看关联执行：", "Open related execution: ") + child.label) { AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: child.id) }
    }
    private func chatLink(_ id: String) -> some View {
        Button(L("打开来源聊天", "Open source chat")) {
            Task { do { let _: AgentChatCreated = try await client.get("/im/v1/conversations/" + agentSegment(id)); onOpenChat(id) } catch { navigationError = agentError(error) } }
        }
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
