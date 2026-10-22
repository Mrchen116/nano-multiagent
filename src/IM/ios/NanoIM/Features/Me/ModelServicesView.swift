import SwiftUI

/// Select one of the signed-in owner's computers before managing its model services.
struct ModelServicesNodesView: View {
    let client: IMClient
    let ownerID: String
    @State private var nodes: [SettingsNode] = []
    @State private var loaded = false
    @State private var error: String?

    var body: some View {
        List {
            Section {
                Text(L("选择电脑，管理这台电脑上助手可用的模型服务。", "Choose a computer to manage model services available to its assistants."))
                    .foregroundStyle(.secondary)
            }
            if let error {
                Section {
                    ErrorNotice(message: error)
                    if loaded { Text(L("保留上次读取的设备列表，请重新检查连接。", "The last device list is preserved. Check the connection again.")).font(.footnote) }
                    Button(L("重试", "Retry")) { Task { await load() } }
                }
            }
            if !loaded && error == nil { ProgressView(L("正在读取本人设备", "Loading your computers")) }
            if loaded && nodes.isEmpty {
                ContentUnavailableView(L("尚未绑定设备", "No computers yet"), systemImage: "desktopcomputer",
                    description: Text(L("返回“我的”，使用电脑提供的链接绑定。", "Return to Me and bind using the link from your computer.")))
            }
            ForEach(nodes) { node in
                NavigationLink {
                    ModelServicesView(client: client, nodeID: node.node_id)
                } label: {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: "desktopcomputer").foregroundStyle(NanoTheme.accent)
                        VStack(alignment: .leading, spacing: 5) {
                            Text(node.name).font(.headline).fixedSize(horizontal: false, vertical: true)
                            Text(settingsStatus(node.status)).font(.subheadline).foregroundStyle(node.status == "online" ? .green : .secondary)
                            if node.status != "online" {
                                Text(L("电脑恢复连接后可读取和修改。", "Reconnect the computer to read and edit services."))
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }.padding(.vertical, 4)
                }
            }
        }
        .navigationTitle(L("模型服务", "Model services")).navigationBarTitleDisplayMode(.inline)
        .toolbar(.hidden, for: .tabBar)
        .task { await load() }
        .refreshable { await load() }
    }

    @MainActor private func load() async {
        do {
            let all = try await client.settingsNodes()
            try Task.checkCancellation()
            nodes = all.filter { $0.owner_id == ownerID }; loaded = true; error = nil
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
}

/// Native service list and editor, using the same node setup contract as Web settings.
struct ModelServicesView: View {
    let client: IMClient
    let nodeID: String
    @State private var state: ModelServicesState
    @State private var removing: ModelService?
    @State private var removalRevision = ""
    @State private var confirmLeave = false
    @Environment(\.scenePhase) private var scenePhase

    init(client: IMClient, nodeID: String) {
        self.client = client; self.nodeID = nodeID
        _state = State(initialValue: ModelServicesState(client: client, nodeID: nodeID))
    }

    var body: some View {
        ScrollViewReader { proxy in
            Form {
                if state.draft != nil {
                    editor
                    feedback.id("model-feedback")
                    if state.conflict { conflictReview }
                    if state.dirty && !state.pending {
                        Section { Button(L("放弃修改", "Discard changes"), role: .destructive) { confirmLeave = true } }
                    }
                } else {
                    feedback.id("model-feedback")
                    serviceList
                }
            }
            .onChange(of: state.error) { _, value in if value != nil { proxy.scrollTo("model-feedback", anchor: .top) } }
            .onChange(of: state.readError) { _, value in if value != nil { proxy.scrollTo("model-feedback", anchor: .top) } }
            .onChange(of: state.notice) { _, value in if value != nil { proxy.scrollTo("model-feedback", anchor: .top) } }
        }
        .navigationTitle(state.draft == nil ? L("模型服务", "Model services") : state.draft?.provider == nil ? L("添加模型服务", "Add model service") : L("编辑模型服务", "Edit model service"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .navigationBarBackButtonHidden(state.draft != nil)
        .toolbar {
            if state.draft != nil {
                ToolbarItem(placement: .navigation) {
                    Button(L("模型服务", "Services"), systemImage: "chevron.left") {
                        if state.dirty || state.pending || state.busy { confirmLeave = true } else { state.closeEditor() }
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(state.busy || state.pending ? L("验证中…", "Verifying…") : L("测试并保存", "Test and save")) {
                        Task { await state.save() }
                    }.fontWeight(.semibold).disabled(!state.canWrite || state.conflict || !state.dirty)
                }
            } else {
                ToolbarItem(placement: .confirmationAction) {
                    Button(L("添加服务", "Add service"), systemImage: "plus") { state.open() }
                        .disabled(!state.canWrite)
                }
            }
        }
        .confirmationDialog(L("放弃未保存的草稿并返回服务列表？", "Discard the unsaved draft and return to services?"), isPresented: $confirmLeave, titleVisibility: .visible) {
            Button(L("放弃并返回", "Discard and go back"), role: .destructive) { state.closeEditor() }
            Button(L("继续编辑", "Keep editing"), role: .cancel) {}
        } message: {
            if state.pending || state.busy {
                Text(L("电脑上的验证可能继续。返回列表后仍需重读结果，不能立即再次保存。", "Verification may continue on the computer. Reload its result before saving again."))
            }
        }
        .confirmationDialog(L("移除模型服务？", "Remove model service?"), isPresented: Binding(get: { removing != nil }, set: { if !$0 { removing = nil } }), titleVisibility: .visible) {
            if let service = removing {
                Button(L("移除 \(service.display_name)", "Remove \(service.display_name)"), role: .destructive) {
                    let revision = removalRevision
                    Task { await state.remove(service, revision: revision) }
                    removing = nil
                }
            }
            Button(L("保留服务", "Keep service"), role: .cancel) { removing = nil }
        } message: {
            Text(removing?.provider == "openai-codex"
                ? L("只移除这台电脑上的模型路由，保留订阅授权。在用模型需先为对应助手更换。", "Remove model routes from this computer while keeping subscription authorization. Assistants using its models must switch first.")
                : L("移除这台电脑上的服务和密钥。在用模型需先为对应助手更换。", "Remove the service and key from this computer. Assistants using its models must switch first."))
        }
        .task(id: scenePhase) { if scenePhase == .active { await state.load() } }
        .task(id: state.shouldPoll && scenePhase == .active) {
            guard state.shouldPoll, scenePhase == .active else { return }
            while !Task.isCancelled && state.shouldPoll {
                do { try await Task.sleep(for: .seconds(1)) } catch { return }
                await state.load()
            }
        }
        .refreshable { await state.load() }
    }

    @ViewBuilder private var serviceList: some View {
        if let status = state.status {
            Section {
                Text(L("服务只作用于所选电脑；在助手配置中选择具体模型。", "Services apply to this computer. Choose individual models in assistant settings."))
                    .font(.footnote).foregroundStyle(.secondary)
            }
            if status.services.isEmpty && state.readError == nil {
                Section {
                    ContentUnavailableView(L("还没有模型服务", "No model services yet"), systemImage: "cpu",
                        description: Text(L("添加 API 服务，供这台电脑上的助手使用。", "Add an API service for assistants on this computer.")))
                    Button(L("添加服务", "Add service")) { state.open() }.disabled(!state.canWrite)
                }
            }
            ForEach(status.services) { service in
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(service.display_name).font(.headline).fixedSize(horizontal: false, vertical: true)
                        Text(service.provider == "openai-codex" ? L("订阅连接", "Subscription connection") : service.source == "custom" ? L("自定义 API", "Custom API") : state.catalog.first(where: { $0.provider == service.source })?.display_name ?? service.source)
                            .font(.caption).foregroundStyle(.secondary)
                        ForEach(service.models, id: \.id) { model in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(model.display_name ?? model.id).font(.subheadline)
                                if model.display_name != nil { Text(model.id).font(.caption.monospaced()).foregroundStyle(.secondary) }
                            }.textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    if service.provider != "openai-codex" {
                        Button(L("编辑服务", "Edit service")) { state.open(service) }.disabled(!state.canWrite)
                    }
                    Button(L("移除服务", "Remove service"), role: .destructive) {
                        state.clearFeedback(); removalRevision = status.revision; removing = service
                    }.disabled(!state.canWrite)
                }
            }
        } else if state.readError == nil {
            Section { ProgressView(L("正在读取模型服务", "Loading model services")) }
        }
    }

    @ViewBuilder private var editor: some View {
        if let draft = state.draft {
            ModelServiceEditorFields(draft: Binding(get: { state.draft ?? draft }, set: { state.draft = $0 }),
                catalog: draft.provider == nil ? state.availableCatalog : state.catalog)
                .disabled(state.busy || state.pending)
        }
    }

    @ViewBuilder private var feedback: some View {
        if let readError = state.readError {
            Section {
                ErrorNotice(message: readError)
                Text(L("请在这台电脑启动 Nano 并检查连接。已读取配置和当前草稿保留；无法连接不表示没有服务。", "Start Nano on this computer and check the connection. Saved snapshots and drafts are preserved; an unavailable computer is not an empty service list."))
                    .font(.footnote).foregroundStyle(.secondary)
                Button(L("重新检查连接与结果", "Check connection and result again")) { Task { await state.load() } }.disabled(state.reading || state.busy)
            }
        }
        if let error = state.error {
            Section {
                ErrorNotice(message: modelServiceError(error))
                if let dependencies = error.dependencies, !dependencies.isEmpty {
                    Text(L("请先为以下助手更换模型：", "Choose another model for these assistants first:"))
                    ForEach(dependencies) { dependency in
                        if dependency.agent_id.hasPrefix("system:") {
                            Text(dependency.display_name).foregroundStyle(.secondary)
                        } else {
                            NavigationLink {
                                AgentConfigView(client: client, agentID: dependency.agent_id)
                            } label: { Label(dependency.display_name + L(" · 配置", " · Settings"), systemImage: "slider.horizontal.3") }
                        }
                    }
                }
            }
        }
        if let notice = state.notice {
            Section { Text(notice).foregroundStyle(state.pending ? .secondary : NanoTheme.accent) }
        }
        if state.pending || state.busy {
            Section {
                if state.busy { ProgressView(L("正在提交", "Submitting")) }
                else if state.stoppedWaiting {
                    Text(L("等待已停止，操作结果尚未确认。", "Waiting stopped; the result is not yet confirmed."))
                } else if state.uncertainSubmission {
                    Text(L("提交结果未确认，请重读状态后核对最新配置。", "The submission result is unknown. Reload status and review the latest configuration."))
                } else if let trackedID = state.trackedID, state.status?.operation?.id != trackedID {
                    Text(L("当前返回的操作与本次操作不同，尚无法确认本次结果。请重读状态。", "The returned operation differs from this page's operation. Its result is still unknown; reload status."))
                } else {
                    ProgressView(state.trackedID == nil ? L("电脑正在处理模型修改", "The computer is processing a model change") : L("正在验证模型连接", "Verifying model connections"))
                    Text(L("验证成功后才保存，原有服务继续可用。", "Changes save after verification succeeds. Existing services remain available.")).font(.footnote).foregroundStyle(.secondary)
                }
                if !state.busy {
                    Button(L("重读操作结果", "Reload operation result")) { Task { await state.load() } }.disabled(state.reading)
                    if state.shouldPoll {
                        Button(L("停止等待", "Stop waiting")) { state.stopWaiting() }
                    }
                }
            }
        }
        if state.status?.catalog_error != nil {
            Section {
                Text(L("内置服务商目录暂不可用，可使用自定义 API。", "The built-in provider catalog is unavailable. You can use a custom API."))
                    .font(.footnote).foregroundStyle(.secondary)
                Button(L("重新读取目录", "Reload catalog")) { Task { await state.load() } }.disabled(state.reading || state.busy)
            }
        }
    }

    @ViewBuilder private var conflictReview: some View {
        if let draft = state.draft {
            Section(L("核对最新配置", "Review latest configuration")) {
                Text(L("另一页面或刚才的操作可能已更新配置。表单仍是你的草稿；读取最新内容并选择如何继续。", "Another page or the previous operation may have changed configuration. The form still contains your draft. Read the latest version and choose how to continue."))
                    .font(.footnote)
                Button(L("读取最新配置", "Read latest configuration")) { Task { await state.load(compare: true) } }.disabled(state.reading || state.busy)
                ModelServiceComparison(title: L("你的草稿", "Your draft"), draft: draft)
                if let latest = state.comparison {
                    if let provider = draft.provider {
                        if let service = latest.services.first(where: { $0.provider == provider }) {
                            ModelServiceComparison(title: L("电脑上的最新配置", "Latest configuration on the computer"), draft: .init(service: service, revision: latest.revision))
                        } else { Text(L("此服务已从电脑移除，不能直接重新应用。请保留所需内容后新增服务。", "This service was removed from the computer. Preserve the content you need and add a new service.")) }
                    } else if latest.services.isEmpty {
                        Text(L("电脑上的最新配置：尚无服务。", "Latest configuration on the computer: no services."))
                    } else {
                        ForEach(latest.services) { service in
                            ModelServiceComparison(title: L("电脑上的最新配置", "Latest configuration on the computer"), draft: .init(service: service, revision: latest.revision))
                        }
                    }
                    Button(L("保留草稿，基于最新版本继续", "Keep draft against the latest version")) { state.keepDraft() }
                        .disabled(state.pending || state.readError != nil || (draft.provider != nil && !latest.services.contains(where: { $0.provider == draft.provider })))
                    Button(draft.provider == nil ? L("放弃新增，使用最新配置", "Discard addition and use latest configuration") : L("用最新配置整份替换草稿", "Replace the entire draft with latest configuration"), role: .destructive) {
                        if draft.provider == nil || !latest.services.contains(where: { $0.provider == draft.provider }) { state.closeEditor(); state.clearFeedback() }
                        else { state.replaceDraft() }
                    }.disabled(state.pending || state.readError != nil)
                }
            }
        }
    }
}

private struct ModelServiceEditorFields: View {
    @Binding var draft: ModelServiceDraft
    let catalog: [ModelServiceCatalog]
    private var provider: ModelServiceCatalog? { catalog.first { $0.provider == draft.source } }

    var body: some View {
        Section {
            Text(L("先测试连接，验证成功后才保存。密钥只保存在所选电脑，不会回显。", "Connections are tested before saving. Keys stay on the selected computer and are never shown again."))
                .font(.footnote).foregroundStyle(.secondary)
            if draft.provider == nil {
                Picker(L("连接方式", "Connection type"), selection: Binding(get: { draft.source }, set: { source in
                    if let item = catalog.first(where: { $0.provider == source }) { draft = .init(catalog: item, revision: draft.revision) }
                    else { draft = .init(revision: draft.revision) }
                })) {
                    Text(L("自定义 API", "Custom API")).tag("custom")
                    ForEach(catalog) { item in Text(item.display_name).tag(item.provider) }
                }
            } else {
                LabeledContent(L("服务商", "Provider"), value: draft.source == "custom" ? L("自定义 API", "Custom API") : provider?.display_name ?? draft.source)
            }
            modelTextField(L("服务名称", "Service name"), prompt: L("例如：团队模型服务", "For example: Team models"), text: $draft.display_name)
            if draft.source == "custom" {
                modelTextField(L("API 地址", "API URL"), prompt: "https://api.example.com/v1", text: $draft.base_url, url: true)
                Picker(L("协议", "Protocol"), selection: Binding(get: { draft.protocolName ?? "openai-completions" }, set: { draft.protocolName = $0 })) {
                    Text("OpenAI Chat Completions").tag("openai-completions")
                    Text("OpenAI Responses").tag("openai-responses")
                    Text("Anthropic Messages").tag("anthropic-messages")
                }
            }
            VStack(alignment: .leading, spacing: 7) {
                Text("API Key").font(.subheadline).foregroundStyle(.secondary)
                SecureField(draft.credential_stored ? L("留空保留当前密钥", "Leave blank to keep the saved key") : L("粘贴 API Key；免密服务可留空", "Paste API key; blank for keyless services"), text: $draft.api_key)
                    .textContentType(nil).textInputAutocapitalization(.never).autocorrectionDisabled()
                Text(draft.credential_stored ? L("已保存 · 留空保留，输入新密钥则替换。", "Key saved · leave blank to keep it, or enter a replacement.") : L("保存后不会显示密钥。", "The saved key will not be displayed."))
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        ForEach($draft.models, id: \.editorID) { $model in
            let number = (draft.models.firstIndex(where: { $0.editorID == model.editorID }) ?? 0) + 1
            Section(L("模型 \(number)", "Model \(number)")) {
                modelTextField(L("模型 ID", "Model ID"), prompt: L("服务提供的模型 ID", "Upstream model ID"), text: $model.id)
                if let provider, !provider.models.isEmpty {
                    Menu(L("从服务商目录选择", "Choose from provider catalog")) {
                        ForEach(provider.models) { catalogModel in
                            Button(catalogModel.name.map { "\($0) · \(catalogModel.id)" } ?? catalogModel.id) {
                                let rowID = model.editorID
                                model = catalogModel.draft; model.editorID = rowID
                            }
                        }
                    }
                }
                modelTextField(L("模型显示名称", "Model display name"), prompt: L("可选，只影响显示", "Optional; changes its label only"), text: Binding(get: { model.display_name ?? "" }, set: { model.display_name = $0 }))
                DisclosureGroup(L("模型能力", "Model capabilities")) {
                    VStack(alignment: .leading, spacing: 7) {
                        Text(L("上下文窗口", "Context window")).font(.subheadline).foregroundStyle(.secondary)
                        TextField(L("留空使用默认值", "Blank for default"), value: $model.context_window, format: .number).keyboardType(.numberPad)
                    }
                    VStack(alignment: .leading, spacing: 7) {
                        Text(L("最大输出 token", "Maximum output tokens")).font(.subheadline).foregroundStyle(.secondary)
                        TextField(L("留空使用默认值", "Blank for default"), value: $model.max_tokens, format: .number).keyboardType(.numberPad)
                    }
                    Toggle(L("支持图片输入", "Supports image input"), isOn: Binding(get: { model.input?.contains("image") == true }, set: { model.input = $0 ? ["text", "image"] : ["text"] }))
                }
                Button(L("移除此模型", "Remove this model"), role: .destructive) { draft.models.removeAll { $0.editorID == model.editorID } }
            }
        }
        Section {
            Button(L("添加模型", "Add model"), systemImage: "plus.circle") { draft.models.append(.init(id: "", input: ["text"])) }
        }
        if draft.source != "custom" {
            Section {
                DisclosureGroup(L("高级设置", "Advanced settings")) {
                    modelTextField(L("API 地址覆盖", "API URL override"), prompt: L("留空使用服务商默认地址", "Blank for provider default"), text: $draft.base_url, url: true)
                }
            }
        }
    }

    private func modelTextField(_ title: String, prompt: String, text: Binding<String>, url: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(title).font(.subheadline).foregroundStyle(.secondary)
            TextField(prompt, text: text).textInputAutocapitalization(.never).autocorrectionDisabled()
                .keyboardType(url ? .URL : .default)
        }.padding(.vertical, 3)
    }
}

private struct ModelServiceComparison: View {
    let title: String
    let draft: ModelServiceDraft
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title).font(.subheadline.bold())
            Text(draft.display_name.isEmpty ? L("未命名服务", "Unnamed service") : draft.display_name)
            Text(draft.base_url.isEmpty ? L("服务商默认地址", "Provider default URL") : draft.base_url)
            Text(modelServiceProtocolName(draft.protocolName))
            ForEach(draft.models.indices, id: \.self) { index in
                let model = draft.models[index]
                Text((model.display_name.map { "\($0) · " } ?? "") + (model.id.isEmpty ? L("未填写模型 ID", "No model ID") : model.id))
            }
            Text(!draft.api_key.isEmpty ? L("密钥：已输入新密钥，不显示内容", "Key: replacement entered; hidden") : draft.credential_stored ? L("密钥：已保存", "Key: saved") : L("密钥：未保存", "Key: not saved"))
                .font(.caption).foregroundStyle(.secondary)
        }.font(.footnote).textSelection(.enabled).fixedSize(horizontal: false, vertical: true).padding(.vertical, 5)
    }
}

private func modelServiceProtocolName(_ value: String?) -> String {
    switch value {
    case "openai-completions": return "OpenAI Chat Completions"
    case "openai-responses": return "OpenAI Responses"
    case "anthropic-messages": return "Anthropic Messages"
    default: return value ?? L("服务商默认协议", "Provider default protocol")
    }
}

private func modelServiceError(_ error: ModelServiceSetupError) -> String {
    switch error.code {
    case "connection_failed": return L("连接验证失败。请检查 API 地址、模型和密钥后重试；草稿与原配置保留。", "Connection verification failed. Check the API URL, models and key; your draft and existing configuration are preserved.")
    case "in_use": return L("此服务或模型仍被助手或工具审批使用，请先更换对应模型。", "This service or model is used by assistants or tool approval. Switch those models first.")
    case "busy": return L("这台电脑正在处理另一项模型修改，请等待完成后重读状态。", "The computer is processing another model change. Wait for it to finish and reload status.")
    case "conflict": return L("模型配置已更新，请读取最新配置并与草稿核对后再保存。", "Model configuration changed. Read the latest version and compare it with your draft before saving.")
    default: return error.message
    }
}
