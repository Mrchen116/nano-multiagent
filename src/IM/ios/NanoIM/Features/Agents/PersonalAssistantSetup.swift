import SwiftUI

struct AssistantOnboarding: Decodable, Sendable {
    struct Computer: Decodable, Identifiable, Sendable {
        let node_id: String
        let node_name: String
        let alias: String?
        let status: String
        var id: String { node_id }
        var name: String { alias ?? node_name }
    }
    struct Install: Decodable, Sendable { let available: Bool; let command: String }
    let nodes: [Computer]
    let install: Install
}

struct PersonalAssistantSetup: View {
    let client: IMClient
    let user: AuthUser
    let openChat: (String) -> Void
    @Environment(\.scenePhase) private var phase
    @State private var personal: NativePersonalAgentState?
    @State private var onboarding: AssistantOnboarding?
    @State private var nodeID = ""
    @State private var name = L("小助理", "My assistant")
    @State private var variant = 0
    @State private var setup: ModelState?
    @State private var error: String?
    @State private var creationError: String?
    @State private var busy = false
    @State private var requestKey = UUID().uuidString
    @State private var copyDone = false

    private struct ModelState: Decodable {
        struct Choice: Decodable { let model: String }
        let default_model: String
        let models: [Choice]
        var ready: Bool { models.contains { !$0.model.isEmpty && $0.model == default_model } }
    }
    private var draftKey: String { "crewden.pa-setup:\(client.baseURL.absoluteString):\(user.id)" }
    private var node: AssistantOnboarding.Computer? { onboarding?.nodes.first { $0.id == nodeID } }
    private var boundChat: String? {
        guard personal?.creation == nil else { return nil }
        return personal?.binding?.conversation_id
    }

    var body: some View {
        Form {
            if let creationError { Section { ErrorNotice(message: creationError) } }
            if let error { Section { ErrorNotice(message: error); Button(L("重新检查", "Check again")) { Task { await refresh() } } } }
            if let chat = boundChat, let binding = personal?.binding {
                Section {
                    HStack {
                        AssistantPortrait(personal: true, seed: binding.agent_id, selected: binding.avatar_variant)
                        Text(binding.display_name).font(.headline)
                    }
                    Button(L("打开聊天", "Open chat")) { openChat(chat) }
                }
            } else if let onboarding {
                if node?.status == "online", personal != nil, setup?.ready == true || personal?.creation != nil {
                    assistantIdentity
                    Section {
                        DisclosureGroup(L("工作电脑与模型", "Computer and model")) {
                            computerOptions(onboarding)
                            modelOptions
                        }
                    }
                } else {
                    Section(L("工作电脑", "Work computer")) { computerOptions(onboarding) }
                    if node?.status == "online" {
                        Section(L("模型服务", "Model service")) { modelOptions }
                    }
                }
            } else if error == nil { ProgressView() }
        }
        .navigationTitle(L("设置个人助手", "Set up your assistant")).navigationBarTitleDisplayMode(.inline)
        .onAppear { restoreDraft() }
        .onChange(of: name) { saveDraft() }
        .onChange(of: variant) { saveDraft() }
        .task(id: nodeID) { setup = nil; await readModel() }
        .task(id: phase) {
            guard phase == .active else { return }
            repeat {
                if !busy { await refresh() }
                try? await Task.sleep(for: .seconds(5))
            } while !Task.isCancelled
        }
    }

    private var assistantIdentity: some View {
        Section {
            if let pending = personal?.binding {
                HStack(spacing: 14) {
                    AssistantPortrait(personal: true, seed: pending.agent_id, selected: pending.avatar_variant, size: 54)
                    Text(pending.display_name).font(.title3.bold())
                }
            } else {
                HStack {
                    AssistantPortrait(personal: true, seed: user.id, selected: variant, size: 54)
                    TextField(L("助手名称", "Assistant name"), text: $name).font(.title3.bold())
                }
                DisclosureGroup(L("选择形象", "Choose appearance")) { PortraitPicker(personal: true, variant: $variant) }
            }
            Button(personal?.creation == nil ? L("创建个人助手", "Create personal assistant") : L("继续创建", "Resume setup")) { Task { await create() } }
                .accessibilityIdentifier("assistant.setup.submit")
                .disabled(busy || name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            if busy { ProgressView() }
        }
    }

    @ViewBuilder private func computerOptions(_ onboarding: AssistantOnboarding) -> some View {
        if !onboarding.nodes.isEmpty {
            Picker(L("电脑", "Computer"), selection: $nodeID) {
                ForEach(onboarding.nodes) { item in
                    Text(item.name + " · " + settingsStatus(item.status)).tag(item.id)
                }
            }.disabled(personal?.creation != nil || busy)
        }
        if node?.status != "online" {
            Text(L("助手在你的电脑上执行任务。请先在电脑上完成安装并保持在线。", "Install Crewden on the computer where your assistant will work and keep it online.")).font(.callout)
            ShareLink(item: client.baseURL.appendingPathComponent("onboarding")) { Label(L("发送设置链接到电脑", "Share computer setup link"), systemImage: "square.and.arrow.up") }
            NavigationLink(L("已有电脑绑定链接", "I have a binding link")) {
                SettingsBindingView(client: client, user: user, onAccountUpdated: { Task { await refresh() } })
            }
            if onboarding.install.available {
                DisclosureGroup(L("用命令安装", "Install with a command")) {
                    Button(copyDone ? L("已复制安装命令", "Installation command copied") : L("复制电脑安装命令", "Copy computer install command"), systemImage: "doc.on.doc") {
                        UIPasteboard.general.string = onboarding.install.command
                        copyDone = true
                    }
                }
            }
        }
    }

    @ViewBuilder private var modelOptions: some View {
        if let setup, setup.ready { Label(setup.default_model, systemImage: "checkmark.circle").font(.subheadline) }
        NavigationLink(L("设置模型服务", "Configure model services")) { ModelServicesView(client: client, nodeID: nodeID) }
    }

    private func restoreDraft() {
        let saved = UserDefaults.standard.dictionary(forKey: draftKey)
        name = saved?["name"] as? String ?? name
        requestKey = saved?["key"] as? String ?? requestKey
        nodeID = saved?["node"] as? String ?? nodeID
        variant = saved?["variant"] as? Int ?? AssistantPortrait.variant(for: user.id)
    }
    private func saveDraft() {
        guard boundChat == nil else { return }
        UserDefaults.standard.set(["key": requestKey, "name": name, "node": nodeID, "variant": variant], forKey: draftKey)
    }
    private func refresh() async {
        do {
            let state: NativePersonalAgentState = try await client.get("/im/v1/personal-agent")
            try Task.checkCancellation()
            personal = state
            if boundChat != nil { error = nil; UserDefaults.standard.removeObject(forKey: draftKey); return }
            let devices: AssistantOnboarding = try await client.get("/im/v1/onboarding")
            try Task.checkCancellation()
            onboarding = devices
            let selected = state.binding?.node_id ?? devices.nodes.first { $0.id == nodeID }?.id
                ?? devices.nodes.first { $0.status == "online" }?.id ?? devices.nodes.first?.id ?? ""
            error = nil
            if nodeID == selected { await readModel() } else { nodeID = selected; setup = nil; saveDraft() }
        } catch { if !Task.isCancelled { personal = nil; self.error = error.localizedDescription } }
    }
    private func readModel() async {
        guard let node, node.status == "online" else { setup = nil; return }
        do {
            let value: ModelState = try await client.send("/im/v1/nodes/\(node.id.pathComponent)/setup", body: ModelServiceSetupInput(action: .status))
            try Task.checkCancellation()
            if nodeID == node.id { setup = value }
        } catch { if !Task.isCancelled && nodeID == node.id { setup = nil; self.error = error.localizedDescription } }
    }
    private func create() async {
        guard !busy, personal != nil else { return }
        busy = true; creationError = nil; error = nil; saveDraft()
        defer { busy = false }
        let binding = personal?.binding
        let key = personal?.creation?["request_key"].stringValue ?? requestKey
        var payload: [String: JSONValue] = [
            "node_id": .string(binding?.node_id ?? nodeID),
            "display_name": .string(binding?.display_name ?? name.trimmingCharacters(in: .whitespacesAndNewlines)),
            "request_key": .string(key)
        ]
        if binding == nil || key == requestKey { payload["avatar_variant"] = .number(Double(variant)) }
        do {
            personal = try await client.send("/im/v1/personal-agent", body: payload)
            if let id = boundChat {
                UserDefaults.standard.removeObject(forKey: draftKey)
                openChat(id)
            }
        } catch { creationError = error.localizedDescription; await refresh() }
    }
}
