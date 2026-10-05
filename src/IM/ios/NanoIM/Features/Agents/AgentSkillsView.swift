import SwiftUI
import Charts

struct AgentSkillsView: View {
    let client: IMClient; let agentID: String; let canManage: Bool; let global: Bool; let onOpenChat: @MainActor (String) -> Void
    @State private var usage: AgentSkillUsage?
    @State private var error: String?
    @State private var view = "list"
    @State private var showArchived = false
    @State private var source = "all"
    var body: some View {
        List {
            if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } }
            if let usage {
                if !usage.node_online { Text(L("节点离线，使用统计暂不可用。", "Node offline; usage statistics are unavailable.")) }
                Picker(L("视图", "View"), selection: $view) {
                    Text(L("列表", "List")).tag("list"); Text("Agent").tag("agent"); Text(L("健康度", "Health")).tag("health")
                }.pickerStyle(.segmented)
                if view == "list" {
                    Picker(L("来源", "Source"), selection: $source) {
                        Text(L("全部", "All")).tag("all")
                        ForEach(Array(Set(usage.skills.map(\.source))).sorted(), id: \.self) { Text(sourceName($0)).tag($0) }
                    }
                    Toggle(L("显示已归档", "Show archived"), isOn: $showArchived)
                    ForEach(usage.skills.filter { (showArchived || $0.state != "archived") && (source == "all" || $0.source == source) }) { skill in skillRow(skill) }
                } else if view == "agent" {
                    Section(L("使用趋势 · 按服务端桶顺序", "Usage trend · server bucket order")) {
                        AgentUsageChart(values: usage.heatmap_data)
                        LabeledContent(L("调用总数", "Total calls"), value: String(usage.heatmap_data.reduce(0, +)))
                    }
                    Section(L("自动 Skills", "Automated Skills")) { ForEach(usage.skills.filter { ["F3", "F4"].contains($0.source) }) { skillRow($0) } }
                } else {
                    Section(L("自动 Skills 健康度", "Automated Skill health")) {
                        LabeledContent(L("累计创建", "Created"), value: String(usage.health.created_auto_total))
                        LabeledContent(L("仍活跃", "Still active"), value: String(usage.health.active_auto_total))
                        LabeledContent(L("至少使用一次", "Used at least once"), value: String(usage.health.used_auto_total))
                        LabeledContent(L("创建后使用比例", "Used / created"), value: usage.health.created_auto_total > 0 ? "\(usage.health.used_auto_total) / \(usage.health.created_auto_total)" : L("暂无数据", "No data"))
                    }
                    ForEach(usage.skills.filter { ["F3", "F4"].contains($0.source) }) { skillRow($0) }
                }
                if usage.skills.isEmpty && usage.node_online { Text(L("暂无 Skill 使用记录", "No Skill usage records")) }
            } else if error == nil { ProgressView() }
        }.navigationTitle(L("Skills 使用情况", "Skill usage")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .task { await load() }.refreshable { await load() }
    }
    @ViewBuilder private func skillRow(_ skill: AgentSkillUsage.Skill) -> some View {
        DisclosureGroup {
            LabeledContent(L("来源", "Source"), value: sourceName(skill.source))
            LabeledContent(L("状态", "State"), value: skill.state)
            LabeledContent(L("使用次数", "Uses"), value: String(skill.use_count))
            LabeledContent(L("最近使用", "Last used"), value: skill.last_used_at ?? L("未使用", "Never"))
            if let date = skill.created_at { LabeledContent(L("创建时间", "Created"), value: date) }
            if let date = skill.archived_at { LabeledContent(L("归档时间", "Archived"), value: date) }
            if let error = skill.archive_error, !error.isEmpty { ErrorNotice(message: error) }
            AgentUsageChart(values: skill.trend_buckets)
            ForEach(Array(skill.session_refs.enumerated()), id: \.offset) { _, reference in
                VStack(alignment: .leading) {
                    if let session = reference.session_id {
                        Text(L("会话：", "Session: ") + session).textSelection(.enabled)
                        if global { NavigationLink(L("查看关联工作记录", "View related Work")) { AgentWorkView(client: client, agentID: agentID, canManage: canManage, onOpenChat: onOpenChat, sessionID: session) } }
                    }
                    if let call = reference.tool_call_id { Text(L("工具调用：", "Tool call: ") + call).font(.caption).textSelection(.enabled) }
                    if let time = reference.timestamp { Text(time).font(.caption) }
                }
            }
            if !skill.recent_call_keys.isEmpty { DisclosureGroup(L("最近调用标识", "Recent call keys")) { ForEach(skill.recent_call_keys, id: \.self) { Text($0).font(.caption).textSelection(.enabled) } } }
        } label: { VStack(alignment: .leading) { Text(skill.name).font(.headline); Text("\(sourceName(skill.source)) · \(skill.state) · \(skill.use_count)").font(.caption).foregroundStyle(.secondary) } }
    }
    private func sourceName(_ source: String) -> String {
        switch source { case "F1": return L("用户创建", "User created"); case "F2": return L("历史会话蒸馏", "Conversation distilled"); case "F3": return L("自动创建", "Automatically created"); case "F4": return L("自动批量优化", "Automatically optimized"); default: return source == "unknown" ? L("未知来源", "Unknown source") : source }
    }
    private func load() async {
        do { usage = try await client.get(agentPath(agentID) + "/skills/usage"); error = nil } catch { self.error = agentError(error); if let api = error as? APIError, [401, 403, 404].contains(api.status) { usage = nil } }
    }
}

struct AgentUsageChart: View {
    let values: [Int]
    var body: some View {
        if values.isEmpty { Text(L("暂无趋势数据", "No trend data")).font(.caption) }
        else {
            Chart(Array(values.enumerated()), id: \.offset) { index, count in
                BarMark(x: .value(L("时间桶", "Bucket"), index + 1), y: .value(L("调用次数", "Calls"), count)).foregroundStyle(.teal)
            }.frame(height: 120).accessibilityLabel(L("使用趋势，按时间桶从旧到新", "Usage trend, oldest to newest buckets"))
        }
    }
}

struct AgentCronView: View {
    let client: IMClient; let agentID: String
    @State private var jobs: [AgentCronJob] = []
    @State private var online: Bool?
    @State private var error: String?
    @State private var loaded = false
    @State private var deleting: AgentCronJob?
    @State private var busy = false
    var body: some View {
        List {
            if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } }
            if !loaded { ProgressView() }
            if online == false { Text(L("节点离线；任务空列表不能代表设备没有任务。", "Node offline. An empty response does not mean the device has no jobs.")) }
            if online == nil && loaded { Text(L("节点状态未知；空列表也可能表示读取超时。", "Node state unknown; an empty response may also indicate a timeout.")) }
            ForEach(jobs) { job in
                DisclosureGroup(job.name) {
                    Text(job.instruction).textSelection(.enabled)
                    LabeledContent("ID", value: job.id)
                    LabeledContent(L("启用", "Enabled"), value: job.enabled ? L("是", "Yes") : L("否", "No"))
                    LabeledContent(L("执行后删除", "Delete after run"), value: job.delete_after_run ? L("是", "Yes") : L("否", "No"))
                    ForEach(job.schedule.keys.sorted(), id: \.self) { key in LabeledContent(key, value: job.schedule[key]?.agentString.isEmpty == false ? job.schedule[key]!.agentString : job.schedule[key]?.prettyPrinted ?? "—") }
                    Button(L("删除此任务", "Delete this job"), role: .destructive) { deleting = job }.disabled(busy || online != true)
                }
            }
            if loaded && jobs.isEmpty && online == true { Text(L("暂无返回的任务（节点读取超时也可能返回空列表）。", "No jobs returned (a node read timeout can also return an empty list).")) }
            Text(L("此页仅查看和删除现有任务；通过 Agent 对话安排任务。", "View and delete existing jobs here. Arrange jobs through the Agent conversation.")).font(.caption).foregroundStyle(.secondary)
        }.navigationTitle(L("定时任务", "Scheduled jobs")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .task { await load() }.refreshable { await load() }
        .confirmationDialog(L("确认删除所选定时任务？", "Delete the selected scheduled job?"), isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }), titleVisibility: .visible) {
            if let deleting { Button(deleting.name, role: .destructive) { Task { await remove(deleting) } } }
        }
    }
    private func load() async {
        do {
            let config: AgentConfig = try await client.get(agentPath(agentID) + "/config", query: [URLQueryItem(name: "source", value: "mirror")])
            let nodes: [AgentNode] = try await client.get("/im/v1/nodes")
            online = nodes.first { $0.id == config.node_id }.map { $0.status == "online" }
            jobs = try await client.get(agentPath(agentID) + "/cron/jobs"); loaded = true; error = nil
        } catch { self.error = agentError(error); loaded = true }
    }
    private func remove(_ job: AgentCronJob) async {
        busy = true; defer { busy = false }
        do { let _: EmptyResponse = try await client.delete(agentPath(agentID) + "/cron/jobs/" + agentSegment(job.id)); deleting = nil; await load() }
        catch { self.error = agentError(error) }
    }
}
