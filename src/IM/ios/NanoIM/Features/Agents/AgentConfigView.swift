import SwiftUI

struct AgentConfigView: View {
    let client: IMClient; let agentID: String
    @Environment(\.dismiss) private var dismiss
    @State private var config: AgentConfig?
    @State private var draft = AgentDraft()
    @State private var capabilities: AgentCapabilities?
    @State private var error: String?
    @State private var capabilityError: String?
    @State private var busy = false
    @State private var pending = false
    @State private var conflicted = false
    @State private var currentConfig: AgentConfig?
    @State private var confirmLeave = false
    @State private var preview: AgentPrompt?
    @State private var saved = false
    private var dirty: Bool { config != nil && draft != config!.draft }

    var body: some View {
        ScrollViewReader { proxy in
        Form {
            if let config {
                AgentEditorFields(draft: $draft, capabilities: capabilities).disabled(pending || busy || conflicted)
                AgentHeartbeatFields(draft: $draft, client: client, agentID: agentID, capabilities: capabilities).disabled(pending || busy || conflicted)
                Section {
                    DisclosureGroup(L("配置归属", "Configuration")) {
                        LabeledContent("Agent ID", value: agentID)
                        LabeledContent(L("版本", "Version"), value: String(config.profile_version))
                        LabeledContent(L("工作模式", "Work mode"), value: config.work_mode == "global" ? L("全局模式 · 实验", "Global · Experimental") : L("单 Thread", "Single Thread"))
                        Text(config.workspace_root ?? L("等待节点确认 workspace", "Waiting for the node to confirm the workspace")).textSelection(.enabled)
                        Text(L("模式和 workspace 创建后不可改。", "Mode and workspace are fixed after creation.")).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Section { NavigationLink(L("现有定时任务", "Existing scheduled jobs")) { AgentCronView(client: client, agentID: agentID) } }
                if let capabilityError {
                    Section { ErrorNotice(message: capabilityError); Text(L("能力目录不可用，保留已有配置。重新连接设备后再更改能力。", "Capabilities are unavailable. Existing selections are preserved; reconnect the device to change them.")); Button(L("重读能力", "Reload capabilities")) { Task { await loadCapabilities() } } }
                }
                Section {
                    if let error { ErrorNotice(message: error) }
                    if saved { Text(L("配置已由节点确认；聊天在下一轮采用新配置。", "Configuration confirmed by the node. Chats adopt it on the next turn.")).foregroundStyle(.green) }
                    if pending {
                        Text(L("已提交，等待节点确认。请勿重复保存。", "Submitted; waiting for node confirmation. Do not save again."))
                        Button(L("重读确认状态", "Reload confirmation status")) { Task { await reconcile() } }
                    } else if conflicted {
                        Text(L("草稿仍在。先重读服务端版本，然后核对差异。", "Your draft is preserved. Reload the server version and review the differences."))
                        Button(L("重读最新配置", "Reload latest configuration")) { Task { await readConflict() } }
                        if let currentConfig {
                            DisclosureGroup(L("查看服务端配置", "Inspect server configuration")) {
                                Text(currentConfig.display_name).font(.headline)
                                Text(currentConfig.description)
                                Text(currentConfig.custom_prompt ?? "")
                                Text(L("模型", "Model") + ": " + (currentConfig.default_model ?? "—"))
                                Text(L("备用模型", "Fallbacks") + ": " + currentConfig.model_fallbacks.joined(separator: ", "))
                                Text(L("工具", "Tools") + ": " + currentConfig.tool_allowlist.joined(separator: ", "))
                                Text("Skills: " + currentConfig.skills.joined(separator: ", "))
                                Text(L("Skills 选择模式", "Skill selection mode") + ": " + (currentConfig.skills_selection_mode ?? "default_discovery"))
                                Text(L("推理强度", "Reasoning effort") + ": " + (currentConfig.reasoning_effort ?? L("默认", "Default")))
                                Text(L("群回复策略", "Group reply policy") + ": " + currentConfig.group_reply_policy)
                                ForEach(currentConfig.features.keys.sorted(), id: \.self) { key in
                                    LabeledContent(agentFeatureName(key), value: currentConfig.features[key] == true ? L("启用", "Enabled") : L("关闭", "Disabled"))
                                }
                                if let heartbeat = currentConfig.heartbeat_json { Text("Heartbeat: " + heartbeat).font(.caption) }
                                Text(L("版本", "Version") + ": \(currentConfig.profile_version)")
                            }.textSelection(.enabled)
                            Button(L("保留草稿，基于此版本继续编辑", "Keep draft and edit against this version")) { self.config = currentConfig; conflicted = false; self.currentConfig = nil; error = nil }
                            Button(L("使用服务端配置替换草稿", "Replace draft with server configuration"), role: .destructive) { self.config = currentConfig; draft = currentConfig.draft; conflicted = false; self.currentConfig = nil; error = nil }
                        }
                    } else {
                        Button(L("提示词预览", "Preview prompt")) { Task { await loadPreview() } }.disabled(capabilities == nil || busy)
                    }
                    if busy { ProgressView() }
                }.id("configuration-status")
            } else {
                if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } } else { ProgressView() }
            }
        }
        .onChange(of: error) { _, value in if value != nil { proxy.scrollTo("configuration-status", anchor: .top) } }
        .onChange(of: saved) { _, value in if value { proxy.scrollTo("configuration-status", anchor: .top) } }
        }
        .contentMargins(.top, 12, for: .scrollContent).scrollContentBackground(.hidden).background(NanoTheme.canvas)
        .navigationTitle(L("Agent 配置", "Agent configuration")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .toolbar { ToolbarItem(placement: .confirmationAction) {
            Button(busy ? L("保存中", "Saving") : L("保存", "Save")) { Task { await save() } }
                .fontWeight(.semibold).disabled(config == nil || busy || pending || conflicted || !dirty || draft.display_name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        } }
        .navigationBarBackButtonHidden(dirty || pending)
        .toolbar { if dirty || pending { ToolbarItem(placement: .navigation) { Button(L("返回", "Back")) { confirmLeave = true } } } }
        .confirmationDialog(L("离开并放弃未保存草稿？", "Leave and discard unsaved draft?"), isPresented: $confirmLeave, titleVisibility: .visible) { Button(L("离开", "Leave"), role: .destructive) { dismiss() } }
        .sheet(item: $preview) { value in AgentTextSheet(title: L("提示词预览", "Prompt preview"), text: value.prompt, preview: true) }
        .task { await load() }
    }
    private func load() async {
        do { let value: AgentConfig = try await client.get(agentPath(agentID) + "/config", query: [URLQueryItem(name: "source", value: "mirror")]); config = value; draft = value.draft; error = nil; await loadCapabilities() }
        catch { self.error = agentError(error) }
    }
    private func loadCapabilities() async {
        do { capabilities = try await client.get(agentPath(agentID) + "/capabilities"); capabilityError = nil }
        catch { capabilityError = agentError(error); capabilities = nil }
    }
    private func save() async {
        guard let config else { return }
        busy = true; saved = false; error = nil; defer { busy = false }
        do { let value: AgentConfig = try await client.send(agentPath(agentID) + "/config", method: "PATCH", body: draft.payload(version: config.profile_version)); self.config = value; draft = value.draft; saved = true }
        catch { self.error = agentError(error); pending = (error as? APIError)?.code == "config_apply_pending" || !(error is APIError); conflicted = !pending && (error as? APIError)?.status == 409 }
    }
    private func reconcile() async {
        busy = true; defer { busy = false }
        do {
            let value: AgentConfig = try await client.get(agentPath(agentID) + "/config")
            if value.profile_version > (config?.profile_version ?? 0) { config = value; draft = value.draft; pending = false; saved = true; error = nil }
            else { pending = false; error = L("服务器版本未改变；草稿已恢复，可核对后重试保存。", "The server version is unchanged. The draft is restored; review it before retrying.") }
        } catch { self.error = agentError(error) }
    }
    private func readConflict() async {
        do { currentConfig = try await client.get(agentPath(agentID) + "/config") } catch { self.error = agentError(error) }
    }
    private func loadPreview() async {
        busy = true; defer { busy = false }
        do { preview = try await client.send(agentPath(agentID) + "/prompt-preview", body: draft.previewPayload(capabilities: capabilities, creating: false, customWorkspace: false)) }
        catch { self.error = agentError(error) }
    }
}

struct AgentEditorFields: View {
    @Binding var draft: AgentDraft
    let capabilities: AgentCapabilities?
    @State private var addingFallback = ""
    private var models: [AgentModelOption] { capabilities?.models ?? [] }
    private var reasoning: AgentModelOption.Reasoning? { models.first { $0.name == (draft.default_model.isEmpty ? capabilities?.platform_default_model : draft.default_model) }?.reasoning }
    var body: some View {
        Section(L("基本资料", "Profile")) {
            VStack(alignment: .leading, spacing: 7) {
                Text(L("名称", "Name")).font(.caption).foregroundStyle(NanoTheme.muted)
                TextField(L("名称", "Name"), text: $draft.display_name)
            }.padding(.vertical, 4)
            VStack(alignment: .leading, spacing: 7) {
                Text(L("描述", "Description")).font(.caption).foregroundStyle(NanoTheme.muted)
                TextField(L("描述", "Description"), text: $draft.description, axis: .vertical).lineLimit(2...6)
            }.padding(.vertical, 4)
            Picker(L("群回复策略", "Group reply policy"), selection: $draft.group_reply_policy) {
                Text(L("仅被提及", "When mentioned")).tag("MENTION")
                Text(L("始终回复", "Always reply")).tag("ALWAYS")
                Text(L("不回复", "Do not reply")).tag("NO_REPLY")
            }
        }
        Section(L("模型与推理", "Model and reasoning")) {
            Picker(L("主模型", "Primary model"), selection: $draft.default_model) {
                Text(L("平台默认", "Platform default") + (capabilities?.platform_default_model.map { " · \($0)" } ?? "")).tag("")
                if !draft.default_model.isEmpty && !models.contains(where: { $0.name == draft.default_model }) { Text(draft.default_model + L("（当前不可用）", " (unavailable)")).tag(draft.default_model) }
                ForEach(models) { model in Text(model.name + (model.provider.map { " · \($0)" } ?? "")).tag(model.name) }
            }.disabled(capabilities == nil)
            if reasoning?.kind == "selectable" {
                Picker(L("推理强度", "Reasoning effort"), selection: $draft.reasoning_effort) {
                    Text(L("模型默认", "Model default") + (reasoning?.default.map { " · \($0)" } ?? "")).tag("")
                    if !draft.reasoning_effort.isEmpty && !(reasoning?.levels ?? []).contains(draft.reasoning_effort) { Text(draft.reasoning_effort + L("（原配置）", " (stored)")).tag(draft.reasoning_effort) }
                    ForEach(reasoning?.levels ?? [], id: \.self) { Text($0).tag($0) }
                }
            } else { LabeledContent(L("推理强度", "Reasoning effort"), value: draft.reasoning_effort.isEmpty ? L("模型固定或未报告", "Fixed or unreported") : draft.reasoning_effort) }
            ForEach(Array(draft.model_fallbacks.enumerated()), id: \.offset) { index, model in
                HStack {
                    Text("\(index + 1). \(model)")
                    Spacer()
                    Button { draft.model_fallbacks.swapAt(index, index - 1) } label: { Image(systemName: "arrow.up") }.disabled(index == 0).accessibilityLabel(L("上移备用模型", "Move fallback up"))
                    Button { draft.model_fallbacks.remove(at: index) } label: { Image(systemName: "minus.circle") }.accessibilityLabel(L("移除备用模型", "Remove fallback"))
                }.buttonStyle(.borderless)
            }
            Picker(L("添加备用模型", "Add fallback model"), selection: $addingFallback) {
                Text(L("选择模型", "Select model")).tag("")
                ForEach(models.filter { $0.name != (draft.default_model.isEmpty ? capabilities?.platform_default_model : draft.default_model) && !draft.model_fallbacks.contains($0.name) }) { Text($0.name).tag($0.name) }
            }.disabled(capabilities == nil)
            .onChange(of: addingFallback) { _, value in if !value.isEmpty { draft.model_fallbacks.append(value); addingFallback = "" } }
        }
        Section(L("指令与能力", "Instructions and capabilities")) {
            DisclosureGroup(L("自定义指令", "Custom instructions")) {
                TextEditor(text: $draft.custom_prompt).frame(minHeight: 160).accessibilityLabel(L("自定义指令", "Custom instructions"))
            }
        }
        Section {
            DisclosureGroup(L("工具", "Tools") + " · \(draft.tool_allowlist.count)") {
                if let capabilities {
                    ForEach(capabilities.tools) { option in
                        let fixed = draft.work_mode == "global" && ["inbox", "conversations", "send_message", "agent"].contains(option.name)
                        VStack(alignment: .leading) {
                            Toggle(option.name, isOn: selection(option.name, keyPath: \.tool_allowlist, fixed: fixed)).disabled(fixed)
                            if let description = option.description, !description.isEmpty {
                                DisclosureGroup(L("工具说明", "Tool description")) {
                                    Text(description).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                                }.font(.caption)
                            }
                        }
                    }
                    if draft.work_mode == "global" { Text(L("全局模式固定保留 inbox、conversations、send_message、agent。", "Global mode always retains inbox, conversations, send_message, and agent.")).font(.caption).foregroundStyle(.secondary) }
                }
                ForEach(draft.tool_allowlist.filter { tool in !(capabilities?.tools.contains { $0.name == tool } ?? false) }, id: \.self) { Text($0 + L(" · 已保存，目录未报告", " · Stored; not reported in catalog")) }
            }
        }
        Section {
            DisclosureGroup("Skills") {
                Picker(L("选择方式", "Selection mode"), selection: $draft.skills_selection_mode) {
                    Text(L("默认发现", "Default discovery")).tag("default_discovery")
                    Text(L("显式名单（可为空）", "Explicit allowlist (may be empty)")).tag("explicit_allowlist")
                }.disabled(capabilities == nil)
                if draft.skills_selection_mode == "explicit_allowlist", let capabilities {
                    ForEach(["workspace", "global", "compatibility", "unknown"], id: \.self) { group in
                        let options = capabilities.skills.filter { ($0.source_group ?? "unknown") == group }
                        if !options.isEmpty {
                            DisclosureGroup(agentSkillGroupName(group)) {
                                ForEach(options) { option in
                                    Toggle(isOn: selection(option.name, keyPath: \.skills)) {
                                        VStack(alignment: .leading) { Text(option.name); if let location = option.location { Text(location).font(.caption).foregroundStyle(.secondary) }; if let description = option.description { Text(description).font(.caption) } }
                                    }
                                }
                            }
                        }
                    }
                }
                ForEach(draft.skills.filter { skill in !(capabilities?.skills.contains { $0.name == skill } ?? false) }, id: \.self) { Text($0 + L(" · 已保存，目录未报告", " · Stored; not reported in catalog")) }
            }
        }
        Section {
            DisclosureGroup(L("运行特性", "Runtime features")) {
                ForEach(capabilities?.features ?? []) { feature in
                    let available = feature.requires_tool.map { required in capabilities?.tools.contains { $0.name == required } ?? false } ?? true
                    Toggle(isOn: Binding(get: { draft.features[feature.key] ?? feature.default_on }, set: { draft.setFeature(feature, enabled: $0) })) {
                        VStack(alignment: .leading) {
                            Text(agentFeatureName(feature.key))
                            if let tool = feature.requires_tool { Text(L("需要工具：", "Requires tool: ") + tool).font(.caption).foregroundStyle(.secondary) }
                            if !available { Text(L("当前不可用，保留已存选择", "Unavailable; stored selection is preserved")).font(.caption).foregroundStyle(.secondary) }
                        }
                    }.disabled(!available)
                }
            }
        }
        .onChange(of: draft.default_model) { _, _ in
            draft.reasoning_effort = ""
            draft.model_fallbacks.removeAll { $0 == (draft.default_model.isEmpty ? capabilities?.platform_default_model : draft.default_model) }
        }
    }
    private func selection(_ name: String, keyPath: WritableKeyPath<AgentDraft, [String]>, fixed: Bool = false) -> Binding<Bool> {
        Binding(get: { fixed || draft[keyPath: keyPath].contains(name) }, set: { selected in if selected { if !draft[keyPath: keyPath].contains(name) { draft[keyPath: keyPath].append(name) } } else { draft[keyPath: keyPath].removeAll { $0 == name } } })
    }
}

func agentFeatureName(_ key: String) -> String {
    switch key {
    case "task_graph": return L("任务图", "Task graphs")
    case "memory_curation": return L("记忆维护", "Memory curation")
    case "skill_creation": return L("Skill 创建", "Skill creation")
    case "cron_scheduling": return L("定时任务", "Scheduled jobs")
    case "heartbeat": return L("心跳", "Heartbeat")
    default: return key
    }
}

struct AgentHeartbeatFields: View {
    @Binding var draft: AgentDraft
    let client: IMClient; let agentID: String; let capabilities: AgentCapabilities?
    @State private var document: AgentPrompt?
    @State private var error: String?
    var body: some View {
        Section(L("心跳与定时任务", "Heartbeat and scheduled jobs")) {
            Toggle(L("启用心跳", "Enable heartbeat"), isOn: Binding(get: { draft.features["heartbeat"] ?? false }, set: { draft.features["heartbeat"] = $0 }))
            TextField(L("间隔，例如 30m / 1h", "Interval, e.g. 30m / 1h"), text: Binding(get: { draft.heartbeat.every ?? "" }, set: { draft.heartbeat.every = $0.isEmpty ? nil : $0 })).textInputAutocapitalization(.never)
            TextField(L("活跃开始 HH:mm（可选）", "Active from HH:mm (optional)"), text: hour(\.start))
            TextField(L("活跃结束 HH:mm（可选）", "Active until HH:mm (optional)"), text: hour(\.end))
            TextField(L("时区（可选）", "Timezone (optional)"), text: hour(\.timezone)).textInputAutocapitalization(.never).autocorrectionDisabled()
            Button(L("查看 HEARTBEAT.md", "View HEARTBEAT.md")) {
                Task {
                    do { let value: AgentHeartbeatDocument = try await client.get(agentPath(agentID) + "/heartbeat-md"); if value.node_online { document = AgentPrompt(prompt: value.content); error = nil } else { error = L("节点离线，无法读取 HEARTBEAT.md", "Node offline; HEARTBEAT.md is unavailable") } }
                    catch { self.error = agentError(error) }
                }
            }
            Toggle(L("启用定时任务", "Enable scheduled jobs"), isOn: Binding(get: { draft.features["cron_scheduling"] ?? false }, set: { value in if let feature = capabilities?.features.first(where: { $0.key == "cron_scheduling" }) { draft.setFeature(feature, enabled: value) } else { draft.features["cron_scheduling"] = value } }))
            if let error { ErrorNotice(message: error) }
        }.sheet(item: $document) { AgentTextSheet(title: "HEARTBEAT.md", text: $0.prompt) }
    }
    private func hour(_ key: WritableKeyPath<AgentHeartbeat.Hours, String?>) -> Binding<String> {
        Binding(get: { draft.heartbeat.active_hours?[keyPath: key] ?? "" }, set: { value in var hours = draft.heartbeat.active_hours ?? .init(); hours[keyPath: key] = value.isEmpty ? nil : value; draft.heartbeat.active_hours = hours.start == nil && hours.end == nil && hours.timezone == nil ? nil : hours })
    }
}

func agentSkillGroupName(_ group: String) -> String {
    switch group { case "workspace": return L("工作区", "Workspace"); case "global": return L("全局", "Global"); case "compatibility": return L("兼容来源", "Compatibility"); default: return L("其他来源", "Other sources") }
}
