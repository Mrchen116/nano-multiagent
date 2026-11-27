import SwiftUI

private struct AgentConfigSnapshot: Decodable, Sendable {
    let config: AgentConfig
    let display: AgentSettingsRead<JSONValue>
    let live_capabilities: AgentCapabilities?
    let pending_operation: JSONValue?
    let ready: Bool
}

struct AgentConfigView: View {
    let client: IMClient; let agentID: String
    var personal = false
    var onDeleted: (() -> Void)? = nil
    @Environment(\.dismiss) private var dismiss
    @State private var capabilityToast: CapabilityToastMessage?
    @State private var checkingCapability = false
    @State private var config: AgentConfig?
    @State private var draft = AgentDraft()
    @State private var capabilities: AgentCapabilities?
    @State private var settingsRead: AgentSettingsRead<JSONValue>?
    @State private var ready = false
    @State private var error: String?
    @State private var capabilityError: String?
    @State private var busy = false
    @State private var pending = false
    @State private var conflicted = false
    @State private var currentConfig: AgentConfig?
    @State private var confirmLeave = false
    @State private var confirmScopeWiden = false
    @State private var preview: AgentPrompt?
    @State private var saved = false
    @State private var lifecycleUserID: String?
    @State private var lifecycleContact: Contact?
    @State private var deleting = false
    @State private var roleHasUnsavedChanges = false
    private var dirty: Bool {
        guard let config else { return false }
        var baseline = config.draft
        baseline.fixed_tools = draft.fixed_tools
        baseline.tool_allowlist = baseline.sanitizeStaticTools(personal: personal, capabilities: capabilities)
        var current = draft
        current.tool_allowlist = current.sanitizeStaticTools(personal: personal, capabilities: capabilities)
        return current != baseline
    }

    var body: some View {
        ScrollViewReader { proxy in
        Form {
            Section {
                Text(config?.display_name ?? agentID).font(.headline)
                if let contact = lifecycleContact { Text((contact.status == "online" ? L("设备在线", "Device online") : L("设备离线", "Device offline")) + " · " + (contact.node_name ?? "")).font(.caption).foregroundStyle(.secondary) }
                AgentLifecycleControls(client: client, agentID: agentID, canManage: lifecycleUserID != nil && config?.owner_id == lifecycleUserID,
                                       online: lifecycleContact?.status == "online", configuration: true,
                                       deletionName: onDeleted == nil ? nil : config?.display_name,
                                       deletionInProgress: $deleting, onDeleted: onDeleted.map { finished in
                                           { finished(); dismiss() }
                                       })
            }
            if let config {
                if let settingsRead, settingsRead.source != "current" {
                    offlineDetails(settingsRead)
                }
                AgentEditorFields(draft: $draft, capabilities: capabilities, onCapabilityChange: changeCapabilities, personal: personal,
                                  configurationDisabled: !ready || pending || busy || conflicted || deleting,
                                  roleEditor: AgentRoleEditor(client: client, agentID: agentID,
                                                              online: lifecycleContact?.status == "online" && !deleting,
                                                              hasUnsavedChanges: $roleHasUnsavedChanges))
                AgentHeartbeatFields(draft: $draft, client: client, agentID: agentID).disabled(!ready || pending || busy || conflicted || deleting)
                Section {
                    DisclosureGroup(L("配置归属", "Configuration")) {
                        LabeledContent("Agent ID", value: agentID)
                        LabeledContent(L("版本", "Version"), value: String(config.profile_version))
                        LabeledContent(L("工作模式", "Work mode"), value: config.work_mode == "global" ? L("全局模式", "Global") : L("单会话", "Single conversation"))
                        Text(config.workspace_root ?? L("等待电脑确认工作目录", "Waiting for the computer to confirm the working directory")).textSelection(.enabled)
                        Text(L("工作模式和目录在创建后固定。", "Work mode and directory are fixed after creation.")).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Section { NavigationLink(L("插件", "Plugins")) { AgentPluginsView(client: client, agentID: agentID, onChanged: { await load() }) } }
                Section { NavigationLink(L("现有定时任务", "Existing scheduled jobs")) { AgentCronView(client: client, agentID: agentID) } }
                if let capabilityError {
                    Section { ErrorNotice(message: capabilityError); Text(L("能力目录不可用，保留已有配置。重新连接设备后再更改能力。", "Capabilities are unavailable. Existing selections are preserved; reconnect the device to change them.")); Button(L("重读能力", "Reload capabilities")) { Task { await load() } } }
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
                                Text(L("模型", "Model") + ": " + (currentConfig.default_model ?? "—"))
                                Text(L("备用模型", "Fallbacks") + ": " + currentConfig.model_fallbacks.joined(separator: ", "))
                                Text(L("工具", "Tools") + ": " + currentConfig.tool_allowlist.filter { $0 != "memory" }.joined(separator: ", "))
                                Text((currentConfig.skills_selection_mode == "explicit_denylist" ? L("已禁用 Skills: ", "Disabled skills: ") : "Skills: ") + (currentConfig.skills ?? []).joined(separator: ", "))
                                Text(L("Skills 选择模式", "Skill selection mode") + ": " + (currentConfig.skills_selection_mode ?? "default_discovery"))
                                Text(L("推理强度", "Reasoning effort") + ": " + (currentConfig.reasoning_effort ?? L("默认", "Default")))
                                LabeledContent(L("审批模式", "Approval mode"), value: currentConfig.approval_mode ?? L("继承", "Inherited"))
                                Text(L("协作范围", "Collaboration scope") + ": " + (currentConfig.collaboration_scope == "owner_only" ? L("私有（仅自己与名下助手）", "Private (you & your assistants)") : currentConfig.collaboration_scope == "project" ? L("项目级（共处私密群成员）", "Project (shared private group members)") : L("团队公开", "Team public")))
                                ForEach(currentConfig.features.keys.filter { !["memory_curation", "skill_creation"].contains($0) }.sorted(), id: \.self) { key in
                                    LabeledContent(agentFeatureName(key), value: currentConfig.features[key] == true ? L("启用", "Enabled") : L("关闭", "Disabled"))
                                }
                                if let heartbeat = currentConfig.heartbeat_json { Text("Heartbeat: " + heartbeat).font(.caption) }
                                Text(L("版本", "Version") + ": \(currentConfig.profile_version)")
                            }.textSelection(.enabled)
                            Button(L("保留草稿，基于此版本继续编辑", "Keep draft and edit against this version")) { self.config = currentConfig; conflicted = false; self.currentConfig = nil; error = nil }
                            Button(L("使用服务端配置替换草稿", "Replace draft with server configuration"), role: .destructive) { self.config = currentConfig; draft = currentConfig.draft; draft.fixed_tools = capabilities?.fixed_tools ?? []; draft.tool_allowlist = draft.sanitizeStaticTools(personal: personal, capabilities: capabilities); conflicted = false; self.currentConfig = nil; error = nil }
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
        .capabilityToast($capabilityToast)
        .contentMargins(.top, 12, for: .scrollContent).scrollContentBackground(.hidden).background(NanoTheme.canvas)
        .navigationTitle(L("Agent 配置", "Agent configuration")).navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .toolbar { ToolbarItem(placement: .confirmationAction) {
            Button(busy ? L("保存中", "Saving") : L("保存", "Save")) { Task { await save() } }
                .fontWeight(.semibold).disabled(!ready || busy || pending || conflicted || deleting || !dirty || draft.display_name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        } }
        .navigationBarBackButtonHidden(dirty || pending || roleHasUnsavedChanges)
        .toolbar { if dirty || pending || roleHasUnsavedChanges { ToolbarItem(placement: .navigation) { Button(L("返回", "Back")) { confirmLeave = true } } } }
        .confirmationDialog(L("离开并放弃未保存草稿？", "Leave and discard unsaved draft?"), isPresented: $confirmLeave, titleVisibility: .visible) { Button(L("离开", "Leave"), role: .destructive) { dismiss() } }
        .confirmationDialog(L("确认放宽协作范围？", "Confirm widening collaboration scope?"), isPresented: $confirmScopeWiden, titleVisibility: .visible) {
            Button(L("确认放宽并保存", "Confirm and save")) { Task { await save(confirmedScopeWiden: true) } }
        } message: {
            Text(personal
                 ? L("确认将个人助手切换为「团队公开」？切换后团队同事可发现并与该助手对话；你的私人会话与个人助手工作记录仍仅你本人可见。", "Switch your personal assistant to Team public? Teammates will be able to find and chat with it; your private chat and personal assistant Work stay visible only to you.")
                 : config?.work_mode == "global"
                   ? L("放宽全局助手协作范围后，授权范围内的成员可查看其完整全局工作记录与轨迹（含此前私有记录）。", "Widening this Global assistant’s scope lets eligible members view its full Global Work and trajectories, including earlier private task history.")
                   : L("放宽后授权范围内的同事可发现并发起会话；你此前的私有单聊历史不会公开。", "Eligible teammates will be able to discover and chat with this assistant; your existing private direct chat history remains private."))
        }
        .sheet(item: $preview) { value in AgentTextSheet(title: L("提示词预览", "Prompt preview"), text: value.prompt, preview: true) }
        .task { lifecycleUserID = await client.session.currentUser()?.owner_id; await load() }
        .onChange(of: lifecycleContact?.status) { old, new in
            if new != "online" { ready = false }
            if old != nil && old != new { Task { await load() } }
        }
        .refreshable { await load() }
        .task { repeat { lifecycleContact = try? await client.contacts(kind: "agent").first { $0.agent_id == agentID }; try? await Task.sleep(for: .seconds(3)) } while !Task.isCancelled }
    }
    private func offlineDetails(_ settingsRead: AgentSettingsRead<JSONValue>) -> some View {
        Section {
            AgentSettingsNotice(read: settingsRead)
            if let data = settingsRead.data {
                let labels = data["models"].agentArray.map { $0["display_name"].stringValue ?? $0["name"].agentString }.joined(separator: " · ")
                if !labels.isEmpty { LabeledContent(L("已知模型", "Reported models"), value: labels) }
                if let inherited = data["inherited_approval_rules"].stringValue {
                    LabeledContent(L("继承的审批规则", "Inherited approval"), value: ["nano": "CC", "codex": "Codex", "dsh": "DSH"][inherited] ?? inherited)
                }
                DisclosureGroup(L("已报告的能力", "Reported capabilities")) {
                    ForEach(["tools", "skills", "features"], id: \.self) { field in
                        ForEach(data[field].agentArray.indices, id: \.self) { index in
                            let option = data[field].agentArray[index]
                            let label = option["name"].stringValue ?? agentFeatureName(option["key"].agentString)
                            let enabled = option["enabled"].boolValue
                            LabeledContent(label, value: enabled.map { $0 ? L("开启", "On") : L("关闭", "Off") } ?? (field == "tools" ? L("允许", "Allowed") : "—"))
                        }
                    }
                }
            }
        }
    }

    private func changeCapabilities(_ actions: [CapabilityAction]) {
        guard let action = actions.first else { return }
        capabilityToast = nil
        guard let capabilities, !checkingCapability else { return }
        var candidate = draft
        let blocks = candidate.changeCapabilities(actions, capabilities: capabilities, personal: personal)
        if let block = blocks.first { capabilityToast = .init(text: block.message, anchor: action.kind + ":" + action.name); return }
        candidate.tool_allowlist = candidate.sanitizeStaticTools(personal: personal, capabilities: capabilities)
        let removed = candidate.removingCapabilities(from: draft, capabilities: capabilities, personal: personal)
        if removed.isEmpty { draft = candidate; return }
        checkingCapability = true
        Task {
            defer { checkingCapability = false }
            do {
                let usage: CapabilityUsage = try await client.get(agentPath(agentID) + "/capability-usage")
                if let block = usage.blocks(removing: removed).first { capabilityToast = .init(text: block.message, anchor: action.kind + ":" + action.name); return }
                // Apply against the current draft so unrelated edits survive the request.
                let blocks = draft.changeCapabilities(actions, capabilities: capabilities, personal: personal)
                draft.tool_allowlist = draft.sanitizeStaticTools(personal: personal, capabilities: capabilities)
                if let block = blocks.first { capabilityToast = .init(text: block.message, anchor: action.kind + ":" + action.name) }
            } catch { capabilityToast = .init(text: CapabilityBlock(code: "capability_unavailable", target: action.target).message, anchor: action.kind + ":" + action.name) }
        }
    }
    private func load() async {
        do {
            let value: AgentConfigSnapshot = try await client.get(agentPath(agentID) + "/settings")
            try Task.checkCancellation()
            let wasDirty = dirty
            capabilities = value.live_capabilities
            if !wasDirty {
                config = value.config
                draft = value.config.draft
                draft.tool_allowlist = draft.sanitizeStaticTools(personal: personal, capabilities: capabilities)
            } else if config?.profile_version != value.config.profile_version {
                currentConfig = value.config
                conflicted = true
            } else {
                draft.tool_allowlist = draft.sanitizeStaticTools(personal: personal, capabilities: capabilities)
            }
            draft.fixed_tools = capabilities?.fixed_tools ?? []
            settingsRead = value.display; ready = value.ready
            if value.pending_operation != nil { pending = true }
            capabilityError = value.ready || value.pending_operation != nil ? nil : L("等待电脑确认配置", "Waiting for configuration from the computer")
            error = nil
        } catch {
            guard !Task.isCancelled else { return }
            ready = false; self.error = agentError(error)
            if let api = error as? APIError, [401, 403, 404].contains(api.status) {
                config = nil; capabilities = nil; currentConfig = nil; settingsRead = nil; draft = AgentDraft()
            }
        }
    }
    private func save(confirmedScopeWiden: Bool = false) async {
        guard let config, ready, !deleting else { return }
        if !confirmedScopeWiden && config.collaboration_scope == "owner_only" && draft.collaboration_scope != "owner_only" {
            confirmScopeWiden = true
            return
        }
        busy = true; saved = false; error = nil; defer { busy = false }
        do {
            let value: AgentConfig = try await client.send(agentPath(agentID) + "/config", method: "PATCH", body: draft.payload(version: config.profile_version, confirmScopeWiden: confirmedScopeWiden, personal: personal, capabilities: capabilities))
            self.config = value; draft = value.draft; draft.fixed_tools = capabilities?.fixed_tools ?? []; draft.tool_allowlist = draft.sanitizeStaticTools(personal: personal, capabilities: capabilities); saved = true
        }
        catch {
            if (error as? APIError)?.code == "scope_widen_confirmation_required" {
                confirmScopeWiden = true
                return
            }
            if let blocks = (error as? APIError)?.blocks, let block = blocks.first, let capabilities {
                draft.restoreCapabilities(blocks, capabilities: capabilities, personal: personal)
                capabilityToast = .init(text: block.message, anchor: block.target.kind + ":" + actionAnchor(block))
            } else { self.error = agentError(error); pending = (error as? APIError)?.code == "config_apply_pending" || !(error is APIError); conflicted = !pending && isAgentStateConflict(error) }
        }
    }
    private func actionAnchor(_ block: CapabilityBlock) -> String { block.target.name }
    private func reconcile() async {
        busy = true; defer { busy = false }
        do {
            let snapshot: AgentConfigSnapshot = try await client.get(agentPath(agentID) + "/settings")
            capabilities = snapshot.live_capabilities; settingsRead = snapshot.display; ready = snapshot.ready
            guard snapshot.pending_operation == nil else { return }
            pending = false
            let value = snapshot.config
            var current = value.draft
            current.fixed_tools = draft.fixed_tools
            current.tool_allowlist = current.sanitizeStaticTools(personal: personal, capabilities: capabilities)
            if !dirty || current.payload(personal: personal, capabilities: capabilities) == draft.payload(personal: personal, capabilities: capabilities) {
                config = value; draft = current; saved = true; error = nil
            } else if value.profile_version != config?.profile_version {
                currentConfig = value; conflicted = true; saved = false
                error = L("电脑已确认其他配置，请核对当前版本及草稿。", "The computer confirmed different settings. Review the current version against your draft.")
            } else {
                error = L("服务器版本未改变；草稿已保留，可核对后重试。", "The server version is unchanged. Review the preserved draft before retrying.")
            }
        } catch { self.error = agentError(error) }
    }
    private func readConflict() async {
        do { currentConfig = try await client.get(agentPath(agentID) + "/config") } catch { self.error = agentError(error) }
    }
    private func loadPreview() async {
        busy = true; defer { busy = false }
        do { preview = try await client.send(agentPath(agentID) + "/prompt-preview", body: draft.previewPayload(capabilities: capabilities, creating: false, customWorkspace: false, personal: personal)) }
        catch { self.error = agentError(error) }
    }
}

struct AgentEditorFields: View {
    @Binding var draft: AgentDraft
    let capabilities: AgentCapabilities?
    var onCapabilityChange: (([CapabilityAction]) -> Void)? = nil
    var personal = false
    var approvalRules: String? = nil
    var customApprovalWorkspace = false
    var showProfile = true
    var showModels = true
    var showCapabilities = true
    var configurationDisabled = false
    var roleEditor: AgentRoleEditor?
    @State private var addingFallback = ""
    private var models: [AgentModelOption] { capabilities?.models ?? [] }
    private var reasoning: AgentModelOption.Reasoning? { models.first { $0.name == (draft.default_model.isEmpty ? capabilities?.platform_default_model : draft.default_model) }?.reasoning }
    var body: some View {
        Group {
        Group {
        if showProfile { Section(L("基本资料", "Profile")) {
            VStack(alignment: .leading, spacing: 7) {
                Text(L("名称", "Name")).font(.caption).foregroundStyle(NanoTheme.muted)
                TextField(L("名称", "Name"), text: $draft.display_name).disabled(personal)
            }.padding(.vertical, 4)
            VStack(alignment: .leading, spacing: 7) {
                Text(L("描述", "Description")).font(.caption).foregroundStyle(NanoTheme.muted)
                TextField(L("描述", "Description"), text: $draft.description, axis: .vertical).lineLimit(2...6)
            }.padding(.vertical, 4)
            Picker(L("协作范围", "Collaboration scope"), selection: $draft.collaboration_scope) {
                Text(L("团队公开", "Team public")).tag("team")
                if !personal { Text(L("项目级（共处私密群成员）", "Project (shared private group members)")).tag("project") }
                Text(L("私有（仅自己与名下助手）", "Private (you & your assistants)")).tag("owner_only")
            }
            Text(draft.collaboration_scope == "owner_only"
                 ? (personal
                    ? L("对团队同事隐藏且不对外发言；仍按聊天访问范围静默观察你参与的聊天并向你汇报。切为私有时自动退出外部群并冻结同事历史私聊。", "Hidden from teammates and never messages externally; still silently observes chats you allow. Switching to Private exits external groups and makes teammate direct chats read-only.")
                    : L("对团队同事隐藏，仅与你及名下助手通信或组建内部私密群。切为私有时自动退出外部群并冻结同事历史私聊。", "Hidden from teammates; collaborates only with you and your own assistants. Switching to Private exits external groups and makes teammate direct chats read-only."))
                 : draft.collaboration_scope == "project"
                   ? L("仅面向与该助手共处同一私密群的项目同事开放发现与单聊（全局模式下含工作记录）；离开全部共用私密群后自动冻结。", "Visible and open for direct chat (and Global Work in global mode) only to teammates sharing an active private group with this assistant; freezes automatically when no private group is shared.")
                   : L("团队同事可发现并私聊该助手，也可拉入协作群；私聊、@ 或回复会及时提醒，普通群消息合并提醒。", "Teammates can find and message this assistant or add it to groups. Direct messages, mentions and replies arrive promptly; other group messages arrive in batches."))
                .font(.caption).foregroundStyle(NanoTheme.muted)
        } }
        if showModels { Section(L("审批模式", "Approval mode")) {
            let rules = customApprovalWorkspace ? approvalRules : capabilities?.inherited_approval_rules
            let inherited = ["nano": "CC", "codex": "Codex", "dsh": "DSH"][rules ?? ""] ?? L("待电脑确认", "Awaiting computer")
            Picker(L("审查方式", "Review strategy"), selection: $draft.approval_mode) {
                Text(L("沿用电脑", "Use computer setting") + " · " + inherited).tag("")
                Text("CC").tag("cc")
                Text("Codex").tag("codex")
            }
            Text(L("下轮任务生效，自动审批沿用电脑设置。", "Takes effect on the next task. Automatic approval follows the computer’s setting.")).font(.caption).foregroundStyle(.secondary)
        } }
        if showModels { Section(L("模型与推理", "Model and reasoning")) {
            Menu {
                Picker(L("主模型", "Primary model"), selection: $draft.default_model) {
                    Text(defaultModelLabel).tag("")
                    if !draft.default_model.isEmpty && !models.contains(where: { $0.name == draft.default_model }) { Text(draft.default_model + L("（当前不可用）", " (unavailable)")).tag(draft.default_model) }
                    ForEach(models) { model in Text(model.displayLabel).tag(model.name) }
                }
            } label: {
                VStack(alignment: .leading, spacing: 7) {
                    Text(L("主模型", "Primary model")).font(.subheadline).foregroundStyle(.secondary)
                    HStack(alignment: .top) {
                        Text(draft.default_model.isEmpty ? defaultModelLabel : modelLabel(draft.default_model))
                            .fixedSize(horizontal: false, vertical: true)
                        Spacer(minLength: 8)
                        Image(systemName: "chevron.up.chevron.down").font(.caption)
                    }.foregroundStyle(NanoTheme.accent)
                }.frame(maxWidth: .infinity, alignment: .leading)
            }.disabled(capabilities == nil)
            if reasoning?.kind == "selectable" {
                Picker(L("推理强度", "Reasoning effort"), selection: $draft.reasoning_effort) {
                    Text(L("模型默认", "Model default") + (reasoning?.default.map { " · \($0)" } ?? "")).tag("")
                    if !draft.reasoning_effort.isEmpty && !(reasoning?.levels ?? []).contains(draft.reasoning_effort) { Text(draft.reasoning_effort + L("（原配置）", " (stored)")).tag(draft.reasoning_effort) }
                    ForEach(reasoning?.levels ?? [], id: \.self) { Text($0).tag($0) }
                }
            } else { LabeledContent(L("推理强度", "Reasoning effort"), value: draft.reasoning_effort.isEmpty ? L("模型固定或未报告", "Fixed or unreported") : draft.reasoning_effort) }
            DisclosureGroup(L("备用模型", "Fallback models") + " · \(draft.model_fallbacks.count)") {
            ForEach(Array(draft.model_fallbacks.enumerated()), id: \.offset) { index, model in
                HStack {
                    Text("\(index + 1). " + modelLabel(model)).fixedSize(horizontal: false, vertical: true)
                    Spacer()
                    Button { draft.model_fallbacks.swapAt(index, index - 1) } label: { Image(systemName: "arrow.up") }.disabled(index == 0).accessibilityLabel(L("上移备用模型", "Move fallback up"))
                    Button { draft.model_fallbacks.remove(at: index) } label: { Image(systemName: "minus.circle") }.accessibilityLabel(L("移除备用模型", "Remove fallback"))
                }.buttonStyle(.borderless)
            }
            Picker(L("添加备用模型", "Add fallback model"), selection: $addingFallback) {
                Text(L("选择模型", "Select model")).tag("")
                ForEach(models.filter { $0.name != (draft.default_model.isEmpty ? capabilities?.platform_default_model : draft.default_model) && !draft.model_fallbacks.contains($0.name) }) { Text($0.displayLabel).tag($0.name) }
            }.disabled(capabilities == nil)
            .onChange(of: addingFallback) { _, value in if !value.isEmpty { draft.model_fallbacks.append(value); addingFallback = "" } }
            }
        } }
        }.disabled(configurationDisabled)
        if let roleEditor { roleEditor }
        if showCapabilities { Group {
        Section {
            let fixed = capabilities?.fixedTools(mode: draft.work_mode, personal: personal) ?? AgentCapabilities.modeFixedTools(mode: draft.work_mode, personal: personal)
            let effectiveStatic = draft.effectiveSelectedTools(capabilities: capabilities)
            let allowsManager = effectiveStatic.contains("plugin_manager")
            let visibleOptions: [AgentOption] = {
                let base = (capabilities?.tools ?? []).filter { $0.name != "memory" }
                let missingFixed = fixed.filter { name in name != "memory" && !base.contains { $0.name == name } }.map { AgentOption(name: $0) }
                return base + missingFixed
            }()
            let missingStored = draft.sanitizeStaticTools(personal: personal, capabilities: capabilities).filter { tool in tool != "memory" && !visibleOptions.contains { $0.name == tool } }
            let enabledCount = visibleOptions.filter { option in
                if option.source_group == "workspace" { return fixed.contains(option.name) || (allowsManager && option.enabled != false) }
                return fixed.contains(option.name) || effectiveStatic.contains(option.name)
            }.count + missingStored.count
            DisclosureGroup(L("工具", "Tools") + " · \(enabledCount)") {
                ForEach(visibleOptions) { option in
                    let isOn = option.source_group == "workspace"
                        ? (fixed.contains(option.name) || (allowsManager && option.enabled != false))
                        : (fixed.contains(option.name) || effectiveStatic.contains(option.name))
                    VStack(alignment: .leading) {
                        Toggle(option.name, isOn: Binding(get: { isOn }, set: { change(.init(kind: "tool", name: option.name, enabled: $0)) })).capabilityAnchor("tool:" + option.name)
                        if let description = option.description, !description.isEmpty {
                            DisclosureGroup(L("工具说明", "Tool description")) {
                                Text(description).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                            }.font(.caption)
                        }
                    }
                }
                ForEach(missingStored, id: \.self) { Text($0 + L(" · 已保存，目录未报告", " · Stored; not reported in catalog")) }
            }
        }
        Section {
            DisclosureGroup("Skills") {
                Text(L("新技能默认启用；取消勾选的技能保持禁用。", "New skills are enabled by default; unchecked skills stay disabled.")).font(.caption).foregroundStyle(.secondary)
                if let capabilities {
                    let availableSkills = capabilities.skills.filter {
                        $0.name != "skill-creator" && ($0.name != "nano-proactive-care" || personal || draft.work_mode == "global")
                    }
                    let candidateNames = availableSkills.map(\.name)
                    ForEach(["workspace", "global", "compatibility"], id: \.self) { group in
                        let options = availableSkills.filter { $0.skillGroup(workspaceRoot: draft.workspace_root) == group }
                        if !options.isEmpty {
                            DisclosureGroup(agentSkillGroupName(group)) {
                                let enabled = Set(draft.enabledSkills(candidates: candidateNames))
                                let enable = !options.allSatisfy { enabled.contains($0.name) }
                                Button(enable ? L("启用本组全部", "Enable group") : L("禁用本组全部", "Disable group")) {
                                    onCapabilityChange?(options.filter { enabled.contains($0.name) != enable }.map { CapabilityAction(kind: "skill", name: $0.name, enabled: enable) })
                                }
                                ForEach(options) { option in
                                    Toggle(isOn: Binding(get: { draft.enabledSkills(candidates: candidateNames).contains(option.name) }, set: { change(.init(kind: "skill", name: option.name, enabled: $0)) })) {
                                        VStack(alignment: .leading) { Text(option.name); if let location = option.location { Text(location).font(.caption).foregroundStyle(.secondary) }; if let description = option.description { Text(description).font(.caption) } }
                                    }.capabilityAnchor("skill:" + option.name)
                                }
                            }
                        }
                    }
                }
                ForEach(draft.skills.filter { skill in skill != "skill-creator" && (skill != "nano-proactive-care" || personal || draft.work_mode == "global") && !(capabilities?.skills.contains { $0.name == skill } ?? false) }, id: \.self) { Text($0 + L(" · 已保存，目录未报告", " · Stored; not reported in catalog")) }
            }
        }
        Section {
            let resolvedFeatures = draft.effectiveFeatures(capabilities: capabilities, personal: personal)
            DisclosureGroup(L("运行特性", "Runtime features")) {
                ForEach((capabilities?.featuresForMode(mode: draft.work_mode, personal: personal) ?? []).filter { !["memory_curation", "skill_creation"].contains($0.key) }) { feature in
                    VStack(alignment: .leading, spacing: 5) {
                        Toggle(agentFeatureName(feature.key), isOn: Binding(get: { resolvedFeatures[feature.key] ?? draft.isFeatureEnabled(feature) }, set: { change(.init(kind: "feature", name: feature.key, enabled: $0)) }))
                            .capabilityAnchor("feature:" + feature.key)
                        if let subtitle = agentFeatureSubtitle(feature.key, personal: personal, workMode: draft.work_mode) {
                            Text(subtitle).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
        }
        }.disabled(configurationDisabled) }
        }
        .onChange(of: draft.default_model) { _, _ in
            draft.reasoning_effort = ""
            draft.model_fallbacks.removeAll { $0 == (draft.default_model.isEmpty ? capabilities?.platform_default_model : draft.default_model) }
        }
    }
    private var defaultModelLabel: String {
        L("平台默认", "Platform default") + (capabilities?.platform_default_model.map { " · " + modelLabel($0) } ?? "")
    }
    private func modelLabel(_ name: String) -> String { models.first { $0.name == name }?.displayLabel ?? name }
    private func change(_ action: CapabilityAction) {
        onCapabilityChange?([action])
    }

}

func agentFeatureName(_ key: String) -> String {
    switch key {
    case "intelligent_ui": return L("交互式回复", "Intelligent UI")
    case "plugin_management": return L("插件开发与管理", "Plugin development & management")
    case "task_graph": return L("任务图", "Task graphs")
    case "proactive_planning": return L("主动筹划", "Proactive planning")
    case "dreaming": return L("Dreaming · 自动整理记忆", "Dreaming · Automatic memory organization")
    case "cron_scheduling": return L("定时任务", "Scheduled jobs")
    case "heartbeat": return L("心跳", "Heartbeat")
    default: return key
    }
}

func agentFeatureSubtitle(_ key: String, personal: Bool = false, workMode: String = "global") -> String? {
    switch key {
    case "proactive_planning" where personal:
        return L("在对话安静后静默复盘目标进展、建立「待拍板」提议卡，并在合适时机按需提供准备要点。关闭后停止自动复盘与提议立卡；你明确交办的任务与自行设定的定时提醒照常运行。",
                 "Silently reviews goal progress after quiet periods, proposes candidate cards, and prepares notes when helpful. Turning this off stops automatic quiet reviews and proposals; tasks and reminders you explicitly set continue to run.")
    case "proactive_planning":
        return L("在各协作会话安静后原位记账任务进展，并在凌晨 Dreaming 后结合 ROLE.md 在原群或 1 对 1 面板挂出有界「待拍板」提议卡（常规提议静默挂板不发早安问候，仅急需备料或时效风险发工作时段提醒）。关闭后停止自动记账与夜间唤醒；明确交办的任务与既有定时安排照常运行。",
                 "Silently updates task progress in each originating chat after activity settles, then surfaces bounded Proposed cards on the originating group or 1-on-1 board after Dreaming (silent by default with no morning greetings; working-hours nudges only for urgent prep or role-scoped risks). Explicit tasks and schedules continue to run when off.")
    case "task_graph" where personal || workMode == "global":
        return L("承载单卡事项与长线目标脉络（主动筹划开启时需保持启用）。",
                 "Powers single-card tasks and multi-stage goal graphs (required while Proactive planning is on).")
    case "dreaming":
        return L("定期更新长期记忆。关闭后仍可读取已有记忆，也可请求手动整理。",
                 "Periodically update long-term memory. When off, existing memories remain readable and you can request manual organization.")
    default:
        return nil
    }
}

struct AgentHeartbeatFields: View {
    @Binding var draft: AgentDraft
    let client: IMClient; let agentID: String
    @State private var document: AgentPrompt?
    @State private var error: String?
    var body: some View {
        Section(L("心跳设置", "Heartbeat settings")) {
            TextField(L("间隔，例如 30m / 1h", "Interval, e.g. 30m / 1h"), text: Binding(get: { draft.heartbeat.every ?? "" }, set: { draft.heartbeat.every = $0.isEmpty ? nil : $0 })).textInputAutocapitalization(.never)
            TextField(L("活跃开始 HH:mm（可选）", "Active from HH:mm (optional)"), text: hour(\.start))
            TextField(L("活跃结束 HH:mm（可选）", "Active until HH:mm (optional)"), text: hour(\.end))
            Text(L("按你所在地时间", "Uses your local time")).font(.caption).foregroundStyle(.secondary)
            Button(L("查看 HEARTBEAT.md", "View HEARTBEAT.md")) {
                Task {
                    do { let value: AgentHeartbeatDocument = try await client.get(agentPath(agentID) + "/heartbeat-md"); if value.node_online { document = AgentPrompt(prompt: value.content); error = nil } else { error = L("节点离线，无法读取 HEARTBEAT.md", "Node offline; HEARTBEAT.md is unavailable") } }
                    catch { self.error = agentError(error) }
                }
            }
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
