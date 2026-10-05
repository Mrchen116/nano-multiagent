import SwiftUI

struct MeView: View {
    let client: IMClient
    let user: AuthUser
    let onAccountUpdated: @MainActor () -> Void
    let onSignOut: @MainActor () -> Void
    @AppStorage("nano.locale") private var locale = "zh"
    @State private var confirmSignOut = false

    var body: some View {
        List {
            Section {
                HStack(spacing: 16) {
                    AvatarView(name: user.display_name)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(user.display_name).font(.title3.bold())
                        Text("@" + user.username).font(.subheadline).foregroundStyle(NanoTheme.muted)
                        Text(user.is_company_admin ? L("管理员", "Administrator") : settingsStatus(user.membership_status)).font(.caption).foregroundStyle(NanoTheme.accent)
                    }
                }.padding(.vertical, 8)
            }
            if user.membership_status == "active" {
                Section(L("账号与设备", "Account and devices")) {
                    NavigationLink {
                        SettingsAccountView(client: client, onAccountUpdated: onAccountUpdated)
                    } label: { Label(L("个人资料与语言", "Profile and language"), systemImage: "person.text.rectangle") }
                    NavigationLink {
                        SettingsNodesView(client: client, ownerID: user.owner_id)
                    } label: { Label(L("我的设备", "My devices"), systemImage: "desktopcomputer") }
                    NavigationLink {
                        SettingsBindingView(client: client, user: user, onAccountUpdated: onAccountUpdated)
                    } label: { Label(L("绑定设备", "Bind a device"), systemImage: "link") }
                }
                Section(L("公司", "Company")) {
                    NavigationLink {
                        SettingsCompanyView(client: client, user: user, onAccountUpdated: onAccountUpdated)
                    } label: { Label(L("公司成员", "Company members"), systemImage: "person.3") }
                    NavigationLink {
                        SettingsPoliciesView(client: client, isAdmin: user.is_company_admin)
                    } label: { Label(L("系统策略", "System policies"), systemImage: "slider.horizontal.3") }
                }
            }
            Section {
                NavigationLink {
                    SettingsHelpView()
                } label: { Label(L("提醒与安装", "Reminders and installation"), systemImage: "bell.badge") }
                Button(role: .destructive) { confirmSignOut = true } label: {
                    Label(L("退出登录", "Sign out"), systemImage: "rectangle.portrait.and.arrow.right")
                }
            }
        }
        .listStyle(.insetGrouped).contentMargins(.top, 12, for: .scrollContent).scrollContentBackground(.hidden).background(NanoTheme.canvas)
        .nanoRootTitle(L("我的", "Me"))
        .confirmationDialog(L("退出当前账号？", "Sign out of this account?"), isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button(L("退出登录", "Sign out"), role: .destructive) { onSignOut() }
            Button(L("取消", "Cancel"), role: .cancel) {}
        } message: {
            Text(L("本机的会话和待发内容将清除。服务端聊天历史会保留。", "Local session and unsent content will be cleared. Server chat history is retained."))
        }
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
                    LabeledContent(L("账号 ID", "Account ID"), value: profile.user_id).textSelection(.enabled)
                    TextField(L("显示名称", "Display name"), text: $name)
                    LabeledContent(L("创建时间", "Created"), value: profile.created_at)
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
                        Text("中文").tag("zh")
                        Text("English").tag("en")
                    }
                } header: { Text(L("偏好", "Preferences")) } footer: {
                    Text(L("保存后，语言选择会同步到账号。", "Your language preference is saved to your account."))
                }
                Section {
                    Button(busy ? L("保存中…", "Saving…") : L("保存", "Save")) { Task { await save() } }
                        .disabled(busy || !dirty || name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    Button(L("放弃修改", "Discard changes")) { reset(profile); error = nil; success = nil }
                        .disabled(busy || !dirty)
                }
            } else { SettingsLoading(retry: { Task { await load() } }, error: error) }
        }
        .navigationTitle(L("个人资料与语言", "Profile and language"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
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
            Section {
                Toggle(L("前台新消息提醒", "Foreground message reminders"), isOn: $reminders)
            } header: { Text(L("消息提醒", "Message reminders")) } footer: {
                Text(L("仅在 App 活跃时提示其他未静音聊天的新消息，不显示正文。关闭提醒仍可正常聊天。后台、锁屏或 App 被终止时，首版不保证系统新消息推送；回到前台后补齐消息。", "While the app is active, show reminders for new messages in other unmuted chats without message text. Chat works with reminders off. This version does not guarantee system notifications in the background, on the lock screen or after termination. Messages catch up when you return."))
            }
            Section(L("免费安装", "Free installation")) {
                Text(L("当前 Mac 构建 Nano IM；Mac mini 通过 AltServer 为 AltStore Classic 提供安装与续签。Apple 账号登录、协议、设备信任和开发者模式需由你在系统界面完成。不要在聊天中提供密码或验证码。", "The current Mac builds Nano IM. Mac mini runs AltServer for installation and refresh through AltStore Classic. Complete Apple account sign-in, agreements, device trust and Developer Mode in the system UI. Do not share passwords or verification codes in chat."))
                Text(L("首次安装：USB 连接并信任 iPhone，在 Mini 的 AltServer 菜单选择 Install AltStore。按系统提示启用开发者模式，然后在 AltStore 的 My Apps 使用 + 选择本次构建的 IPA。", "First installation: connect and trust your iPhone over USB, then choose Install AltStore from Mini’s AltServer menu. Enable Developer Mode when prompted, then use + in AltStore → My Apps to select the built IPA."))
                Text(L("免费签名通常在 7 天后到期，以 AltStore 内该 App 显示的实际到期时间为准。构建日期不等于签名到期日，本页不会假报续签成功或剩余天数。", "Free signing typically expires after 7 days. Check this app’s actual expiration in AltStore. The build date is not the signing expiration date; this page does not claim a successful refresh or a remaining lifetime."))
            }
            Section(L("同一 Wi-Fi 下续签", "Refresh on the same Wi-Fi")) {
                Label(L("让 Mini 与 iPhone 连到同一局域网，并保持 AltServer 运行。", "Connect Mini and iPhone to the same local network and keep AltServer running."), systemImage: "1.circle")
                Label(L("先完成 USB 配对并开启 Wi-Fi 同步；在 AltStore 的 My Apps 手动刷新 Nano IM。", "Pair over USB first and enable Wi-Fi sync. Refresh Nano IM in AltStore → My Apps."), systemImage: "2.circle")
                Label(L("在 AltStore 检查新的到期时间，再打开 Nano IM。自动刷新依赖系统调度，不保证每次成功。", "Check the new expiration in AltStore, then open Nano IM. Automatic refresh depends on system scheduling and may not succeed every time."), systemImage: "3.circle")
            }
            Section(L("失败与过期恢复", "Failure and expiration recovery")) {
                Text(L("找不到 AltServer：检查同网连接、Mini 是否唤醒及 AltServer 是否运行；必要时重新通过 USB 连接并确认设备信任。账号或签名错误按 AltStore 提示在系统界面处理。", "If AltServer cannot be found, check the network, ensure Mini is awake and AltServer is running. Reconnect over USB and confirm device trust if needed. Resolve account or signing errors through the AltStore and system prompts."))
                Text(L("如果 Nano IM 已无法打开，若 AltStore 也已过期，USB 连接后从 AltServer 菜单重新安装 AltStore，再以同一 Apple 账号和 App 标识重新签名安装。不要先删除 App；服务端历史仍保留，重新登录后可继续访问有权限的聊天。续签不需要删除聊天数据或重启 Mini 的 IM/Gateway。", "If Nano IM can no longer open, if AltStore is also expired, reconnect over USB and reinstall AltStore from AltServer’s menu, then re-sign the app with the same Apple account and app identity. Do not delete the app first. Server history is retained and authorized chats remain accessible after signing in. Refreshing does not require deleting chat data or restarting Mini’s IM/Gateway."))
                Link(L("AltStore 官方帮助", "Official AltStore help"), destination: URL(string: "https://faq.altstore.io/altstore-classic/your-altstore")!)
            }
        }
        .navigationTitle(L("提醒与安装", "Reminders and installation"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
    }
}
