import SwiftUI

struct MeView: View {
    let client: IMClient
    let user: AuthUser
    let onAccountUpdated: @MainActor () -> Void
    var openChat: (String) -> Void
    let onSignOut: @MainActor () -> Void
    @State private var personal: NativePersonalAgentState?
    @State private var confirmSignOut = false
    @State private var applying = false
    @State private var membershipError: String?

    private var assistant: NativePersonalAgentState.Binding? {
        guard personal?.creation == nil, personal?.binding?.status == "active" else { return nil }
        return personal?.binding
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                if user.accountEnabled {
                    NavigationLink { SettingsAccountView(client: client, onAccountUpdated: onAccountUpdated) } label: {
                        identity
                    }.accessibilityHint(L("编辑个人资料与语言", "Edit profile and language"))
                    if let chatID = assistant?.conversation_id {
                        Button { openChat(chatID) } label: { assistantPanel }
                    } else {
                        NavigationLink { PersonalAssistantSetup(client: client, user: user, openChat: openChat) } label: { assistantPanel }
                    }
                } else { identity }

                VStack(spacing: 0) {
                    if user.accountEnabled {
                        NavigationLink { SettingsNodesView(client: client, user: user, accountUpdated: onAccountUpdated) } label: {
                            CrewdenDestination(title: L("我的电脑", "My computers"), symbol: "laptopcomputer",
                                detail: user.owned_node_ids.isEmpty ? nil : L("\(user.owned_node_ids.count) 台", "\(user.owned_node_ids.count)"))
                        }
                    }
                    if user.membership_status == "active" {
                        NavigationLink {
                            List {
                                if user.is_company_admin {
                                    NavigationLink(L("团队成员", "Team members")) {
                                        SettingsCompanyView(client: client, user: user, onAccountUpdated: onAccountUpdated)
                                    }
                                }
                                NavigationLink(L("团队设置", "Team settings")) {
                                    SettingsPoliciesView(client: client, isAdmin: user.is_company_admin)
                                }
                            }.navigationTitle(L("我的团队", "My team")).toolbar(.hidden, for: .tabBar)
                        } label: {
                            CrewdenDestination(title: L("我的团队", "My team"), symbol: "person.2",
                                detail: user.is_company_admin ? L("管理员", "Admin") : nil)
                        }
                    } else if user.membership_status == "none" {
                        Button { Task { await applyToTeam() } } label: {
                            CrewdenDestination(title: L("加入团队", "Join a team"), symbol: "person.2")
                        }.disabled(applying)
                    } else {
                        Button { onAccountUpdated() } label: {
                            CrewdenDestination(title: L("团队申请", "Team membership"), symbol: "person.2", detail: settingsStatus(user.membership_status))
                        }.accessibilityHint(L("刷新状态", "Refresh status"))
                    }
                    if let membershipError { ErrorNotice(message: membershipError) }
                }
            }.padding(.horizontal, 22).padding(.top, 12).padding(.bottom, 36)
        }
        .buttonStyle(.plain).background(NanoTheme.surface)
        .navigationTitle(L("我的", "Me")).navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                NavigationLink { preferences } label: { Image(systemName: "gearshape") }
                    .accessibilityLabel(L("设置", "Settings"))
            }
        }
        .task { if user.accountEnabled { personal = try? await client.get("/im/v1/personal-agent") } }
    }

    private var identity: some View {
        HStack(spacing: 16) {
            AvatarView(name: user.display_name, size: 62)
            VStack(alignment: .leading, spacing: 4) {
                Text(user.display_name).font(.title.bold()).foregroundStyle(NanoTheme.ink)
                Text("@" + user.username).font(.subheadline).foregroundStyle(.secondary)
            }
            Spacer()
            if user.accountEnabled { Image(systemName: "chevron.right").font(.caption.bold()).foregroundStyle(.secondary) }
        }.padding(.vertical, 10).contentShape(Rectangle())
    }

    private var assistantPanel: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 12) {
                Text(assistant?.display_name ?? L("我的个人助手", "My assistant"))
                    .font(.title3.bold()).foregroundStyle(NanoTheme.ink)
                Label(assistant?.conversation_id != nil ? L("打开聊天", "Open chat") :
                        personal == nil ? L("查看助手", "View assistant") :
                        personal?.creation == nil ? L("创建助手", "Create assistant") : L("继续设置", "Continue setup"),
                      systemImage: assistant?.conversation_id != nil ? "bubble.left" : "arrow.right")
                    .font(.subheadline.weight(.semibold)).foregroundStyle(NanoTheme.accent)
            }
            Spacer(minLength: 4)
            AssistantPortrait(personal: true, seed: assistant?.agent_id ?? user.id, selected: assistant?.avatar_variant, size: 76)
        }.padding(20).background(NanoTheme.softAccent, in: RoundedRectangle(cornerRadius: 20))
    }

    private var preferences: some View {
        List {
            if user.accountEnabled {
                NavigationLink(L("个人资料与语言", "Profile and language")) { SettingsAccountView(client: client, onAccountUpdated: onAccountUpdated) }
                NavigationLink(L("模型服务", "Model services")) { ModelServicesNodesView(client: client, ownerID: user.owner_id) }
            }
            NavigationLink(L("提醒与安装", "Reminders and installation")) { SettingsHelpView() }
            Section { Button(L("退出登录", "Sign out"), role: .destructive) { confirmSignOut = true } }
        }.navigationTitle(L("设置", "Settings")).toolbar(.hidden, for: .tabBar)
        .confirmationDialog(L("退出当前账号？", "Sign out of this account?"), isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button(L("退出登录", "Sign out"), role: .destructive) { onSignOut() }
        } message: {
            Text(L("本机的会话和待发内容将清除。服务端聊天历史会保留。", "Local session and unsent content will be cleared. Server chat history is retained."))
        }
    }
    private func applyToTeam() async {
        guard !applying else { return }
        applying = true; defer { applying = false }
        do {
            let _: AuthUser = try await client.send("/im/v1/company/join", body: SettingsActionBody())
            membershipError = nil; onAccountUpdated()
        } catch { membershipError = settingsError(error) }
    }

}

struct SettingsAccountView: View {
    let client: IMClient
    let onAccountUpdated: @MainActor () -> Void
    @State private var profile: SettingsAccount?
    @State private var nodes: [SettingsNode] = []
    @State private var name = ""
    @State private var defaultNode = ""
    @State private var locale = "zh"
    @State private var error: String?
    @State private var success: String?
    @State private var busy = false

    private var dirty: Bool {
        guard let profile else { return false }
        return name != profile.display_name || defaultNode != (profile.default_entry_node_id ?? "") || locale != profile.locale
    }
    var body: some View {
        Form {
            if let profile {
                SettingsFeedback(error: error, success: success)
                Section(L("个人资料", "Profile")) {
                    LabeledContent(L("用户名", "Username"), value: profile.username)
                    VStack(alignment: .leading, spacing: 6) { Text(L("显示名称", "Display name")).font(.caption).foregroundStyle(NanoTheme.muted); TextField(L("显示名称", "Display name"), text: $name) }.padding(.vertical, 4)
                    DisclosureGroup(L("账号信息", "Account information")) {
                        LabeledContent(L("账号 ID", "Account ID"), value: profile.user_id).textSelection(.enabled)
                        LabeledContent(L("创建时间", "Created")) { NanoDateTime(value: profile.created_at) }
                    }
                }
                Section {
                    Picker(L("默认入口设备", "Default entry device"), selection: $defaultNode) {
                        Text(L("不指定", "None")).tag("")
                        ForEach(nodes.filter { profile.owned_node_ids.contains($0.node_id) }) { node in
                            Text(node.name + " · " + settingsStatus(node.status)).tag(node.node_id)
                        }
                        if let current = profile.default_entry_node_id, !nodes.contains(where: { $0.node_id == current }) {
                            Text(current).tag(current)
                        }
                    }
                    Picker(L("语言", "Language"), selection: $locale) {
                        Text("中文").tag(locale.hasPrefix("zh") ? locale : "zh")
                        Text("English").tag(locale.hasPrefix("en") ? locale : "en")
                    }
                } header: { Text(L("偏好", "Preferences")) } footer: {
                    Text(L("保存后，语言选择会同步到账号。", "Your language preference is saved to your account."))
                }
                if dirty { Section {
                    Button(L("放弃修改", "Discard changes")) { reset(profile); error = nil; success = nil }.disabled(busy)
                } }
            } else { SettingsLoading(retry: { Task { await load() } }, error: error) }
        }
        .navigationTitle(L("个人资料与语言", "Profile and language"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .nanoUnsavedChanges(dirty)
        .toolbar { ToolbarItem(placement: .confirmationAction) { Button(busy ? L("保存中…", "Saving…") : L("保存", "Save")) { Task { await save() } }.disabled(busy || !dirty || name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) } }
        .task { await load() }
    }

    private func reset(_ value: SettingsAccount) {
        name = value.display_name
        defaultNode = value.default_entry_node_id ?? ""
        locale = value.locale
    }
    @MainActor private func load() async {
        error = nil
        do {
            async let account = client.settingsAccount()
            async let available = client.settingsNodes()
            let (loaded, list) = try await (account, available)
            try Task.checkCancellation()
            profile = loaded; nodes = list; reset(loaded)
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
    @MainActor private func save() async {
        busy = true; error = nil; success = nil
        defer { busy = false }
        do {
            let updated = try await client.saveSettingsAccount(SettingsAccountUpdate(
                display_name: name.trimmingCharacters(in: .whitespacesAndNewlines),
                default_entry_node_id: defaultNode.isEmpty ? nil : defaultNode, locale: locale))
            try Task.checkCancellation()
            profile = updated; reset(updated)
            UserDefaults.standard.set(updated.locale, forKey: "nano.locale")
            success = L("已保存", "Saved")
            onAccountUpdated()
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
}

struct SettingsHelpView: View {
    @AppStorage("nano.foregroundReminders") private var reminders = true
    var body: some View {
        Form {
            Section(L("版本", "Version")) {
                LabeledContent("Crewden", value: (Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "") + " (" + (Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "") + ")")
                if let revision = Bundle.main.object(forInfoDictionaryKey: "NanoIMBuildRevision") as? String { LabeledContent(L("代码版本", "Source revision"), value: revision).font(.caption).textSelection(.enabled) }
            }
            Section {
                Toggle(L("前台新消息提醒", "Foreground message reminders"), isOn: $reminders)
            } header: { Text(L("消息提醒", "Message reminders")) } footer: {
                Text(L("App 打开时，提示其他未静音聊天的新消息，不显示正文。后台或锁屏时暂不提供系统推送；重新打开后会同步消息。", "While the app is active, show reminders for new messages in other unmuted chats without message text. Chat works with reminders off. This version does not guarantee system notifications in the background, on the lock screen or after termination. Messages catch up when you return."))
            }
            Section(L("免费安装", "Free installation")) {
                Text(L("通过 AltStore 安装和管理 Crewden。首次安装时，在 Mac 上运行 AltServer，并用 USB 连接手机完成配对。Apple 账号和验证码请只在系统或 AltStore 中输入。", "Install and manage Crewden with AltStore. For first installation, run AltServer on your Mac and pair your iPhone over USB. Enter Apple credentials only in the system or AltStore."))
                Text(L("首次安装：USB 连接并信任 iPhone，在 Mini 的 AltServer 菜单选择 Install AltStore。按系统提示启用开发者模式，然后在 AltStore 的 My Apps 使用 + 选择本次构建的 IPA。", "First installation: connect and trust your iPhone over USB, then choose Install AltStore from Mini’s AltServer menu. Enable Developer Mode when prompted, then use + in AltStore → My Apps to select the built IPA."))
                Text(L("免费签名通常有效 7 天。请在 AltStore 的 My Apps 查看 Crewden 的实际到期时间和刷新结果。", "Free signing typically lasts 7 days. Check Crewden’s actual expiration and refresh result in AltStore → My Apps."))
            }
            Section(L("同一 Wi-Fi 下续签", "Refresh on the same Wi-Fi")) {
                Label(L("让 Mini 与 iPhone 连到同一局域网，并保持 AltServer 运行。", "Connect Mini and iPhone to the same local network and keep AltServer running."), systemImage: "1.circle")
                Label(L("先完成 USB 配对并开启 Wi-Fi 同步；在 AltStore 的 My Apps 手动刷新 Crewden。", "Pair over USB first and enable Wi-Fi sync. Refresh Crewden in AltStore → My Apps."), systemImage: "2.circle")
                Label(L("在 AltStore 检查新的到期时间，再打开 Crewden。自动刷新依赖系统调度，不保证每次成功。", "Check the new expiration in AltStore, then open Crewden. Automatic refresh depends on system scheduling and may not succeed every time."), systemImage: "3.circle")
            }
            Section(L("失败与过期恢复", "Failure and expiration recovery")) {
                Text(L("找不到 AltServer：检查同网连接、Mini 是否唤醒及 AltServer 是否运行；必要时重新通过 USB 连接并确认设备信任。账号或签名错误按 AltStore 提示在系统界面处理。", "If AltServer cannot be found, check the network, ensure Mini is awake and AltServer is running. Reconnect over USB and confirm device trust if needed. Resolve account or signing errors through the AltStore and system prompts."))
                Text(L("如果 Crewden 已无法打开，若 AltStore 也已过期，USB 连接后从 AltServer 菜单重新安装 AltStore，再以同一 Apple 账号和 App 标识重新签名安装。不要先删除 App；服务端历史仍保留，重新登录后可继续访问有权限的聊天。续签不需要删除聊天数据或重启 Mini 的 IM/Gateway。", "If Crewden can no longer open, if AltStore is also expired, reconnect over USB and reinstall AltStore from AltServer’s menu, then re-sign the app with the same Apple account and app identity. Do not delete the app first. Server history is retained and authorized chats remain accessible after signing in. Refreshing does not require deleting chat data or restarting Mini’s IM/Gateway."))
                Link(L("AltStore 官方帮助", "Official AltStore help"), destination: URL(string: "https://faq.altstore.io/altstore-classic/your-altstore")!)
            }
        }
        .navigationTitle(L("提醒与安装", "Reminders and installation"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
    }
}
