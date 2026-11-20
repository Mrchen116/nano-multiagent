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
    @State private var choosingAppearance = false

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

    private var canSetIdentity: Bool {
        node?.status == "online" && personal != nil && (setup?.ready == true || personal?.creation != nil)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let creationError { ErrorNotice(message: creationError) }
                if let error {
                    ErrorNotice(message: error)
                    Button(L("重新检查", "Check again")) { Task { await refresh() } }
                }
                if let chat = boundChat, let binding = personal?.binding {
                    VStack(spacing: 10) {
                        AssistantPortrait(personal: true, seed: binding.agent_id, selected: binding.avatar_variant, size: 104)
                        Text(binding.display_name).font(.largeTitle.bold())
                        if binding.status == "unavailable" {
                            Label(L("助手暂时不可用", "Assistant temporarily unavailable"), systemImage: "pause.circle").foregroundStyle(.secondary)
                        }
                    }.frame(maxWidth: .infinity).padding(.vertical, 20)
                    Button { openChat(chat) } label: { primaryLabel(L("打开聊天", "Open chat"), symbol: "bubble.left.fill") }
                        .buttonStyle(.plain)
                    if binding.status == "active" {
                        NavigationLink { PersonalAgentManagementView(client: client, agentID: binding.agent_id) } label: {
                            CrewdenDestination(title: L("个人助手设置", "Personal assistant settings"), symbol: "slider.horizontal.3")
                        }.buttonStyle(.plain)
                    }
                } else if let onboarding {
                    if canSetIdentity {
                        assistantIdentity
                        Button { Task { await create() } } label: {
                            primaryLabel(personal?.creation == nil ? L("创建个人助手", "Create personal assistant") : L("继续创建", "Resume setup"), symbol: "arrow.right")
                        }.buttonStyle(.plain)
                            .accessibilityIdentifier("assistant.setup.submit")
                            .disabled(busy || (personal?.binding?.display_name ?? name).trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        DisclosureGroup {
                            VStack(alignment: .leading, spacing: 14) {
                                computerOptions(onboarding)
                                modelOptions
                            }.padding(.vertical, 10)
                        } label: {
                            Label(L("工作电脑与模型", "Computer and model"), systemImage: "desktopcomputer").font(.subheadline.weight(.medium))
                        }
                    } else {
                        VStack(alignment: .leading, spacing: 15) {
                            Label(L("工作电脑", "Work computer"), systemImage: "desktopcomputer").font(.title3.bold())
                            computerOptions(onboarding)
                        }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
                            .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 17))
                        if node?.status == "online" {
                            VStack(alignment: .leading, spacing: 12) {
                                Label(L("模型服务", "Model service"), systemImage: "square.stack.3d.up").font(.title3.bold())
                                modelOptions
                            }
                        }
                    }
                } else if error == nil { ProgressView().frame(maxWidth: .infinity) }
            }.padding(.horizontal, 20).padding(.vertical, 14)
        }.background(NanoTheme.surface)
        .scrollDismissesKeyboard(.interactively)
        .navigationTitle(L("设置个人助手", "Set up your assistant")).navigationBarTitleDisplayMode(.inline)
        .onAppear { restoreDraft() }
        .onChange(of: name) { saveDraft() }
        .onChange(of: variant) { saveDraft() }
        .onChange(of: nodeID) { saveDraft() }
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
        VStack(spacing: 14) {
            if let pending = personal?.binding {
                AssistantPortrait(personal: true, seed: pending.agent_id, selected: pending.avatar_variant, size: 100)
                Text(pending.display_name).font(.title.bold())
            } else {
                Button { choosingAppearance.toggle() } label: {
                    ZStack(alignment: .bottomTrailing) {
                        AssistantPortrait(personal: true, seed: user.id, selected: variant, size: 90)
                        Image(systemName: "paintpalette.fill").font(.caption.bold()).foregroundStyle(NanoTheme.accent)
                            .frame(width: 26, height: 26).background(NanoTheme.surface, in: Circle())
                    }.padding(6)
                }.accessibilityLabel(L("选择形象", "Choose appearance")).buttonStyle(.plain)
                if choosingAppearance {
                    PortraitPicker(personal: true, variant: $variant)
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text(L("助手名称", "Assistant name")).font(.caption.weight(.medium)).foregroundStyle(NanoTheme.muted)
                    TextField(L("助手名称", "Assistant name"), text: $name).font(.title3.bold()).submitLabel(.done)
                }.padding(.horizontal, 14).padding(.vertical, 10)
                    .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 12))
            }
        }.padding(14).frame(maxWidth: .infinity)
            .background(NanoTheme.softAccent, in: RoundedRectangle(cornerRadius: 22))
    }

    private func primaryLabel(_ title: String, symbol: String) -> some View {
        HStack(spacing: 8) {
            if busy { ProgressView().tint(.white) } else { Image(systemName: symbol) }
            Text(title)
        }.font(.headline).padding(.vertical, 14).frame(maxWidth: .infinity)
            .background(NanoTheme.accent, in: RoundedRectangle(cornerRadius: 14)).foregroundStyle(.white)
    }

    @ViewBuilder private func computerOptions(_ onboarding: AssistantOnboarding) -> some View {
        if !onboarding.nodes.isEmpty {
            Picker(L("电脑", "Computer"), selection: $nodeID) {
                ForEach(onboarding.nodes) { item in
                    Text(item.name + " · " + settingsStatus(item.status)).tag(item.id)
                }
            }.pickerStyle(.menu).disabled(personal?.creation != nil || busy)
        }
        if node?.status != "online" {
            Text(node == nil ? L("在电脑上安装 Crewden，然后用绑定链接连接。", "Install Crewden on your computer, then connect it with the binding link.") : L("打开这台电脑上的 Crewden 以继续设置。", "Open Crewden on this computer to continue.")).font(.callout)
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
