import SwiftUI

struct AuthView: View {
    @Bindable var model: AppModel
    @State private var server = ""
    @State private var username = ""
    @State private var password = ""
    @State private var displayName = ""
    @State private var register = false
    @State private var now = Date()
    @AppStorage("nano.locale") private var locale = "zh"
    var body: some View {
        NavigationStack {
            Form {
                Section { VStack(alignment: .leading, spacing: 8) {
                    Text("Nano IM").font(.largeTitle.bold())
                    Text(L("与你的 Agent 保持连接", "Stay connected to your agents")).foregroundStyle(.secondary)
                }.padding(.vertical, 16) }
                Section {
                    TextField(L("用户名", "Username"), text: $username).textContentType(.username).textInputAutocapitalization(.never).autocorrectionDisabled()
                    SecureField(L("密码", "Password"), text: $password).textContentType(register ? .newPassword : .password)
                    if register { TextField(L("显示名称", "Display name"), text: $displayName) }
                }
                if let error = model.error { Section { ErrorNotice(message: error) } }
                Section {
                    Button { Task { await model.authenticate(server: server, username: username, password: password, displayName: register ? displayName : nil); if model.user != nil { password = "" } } } label: {
                        HStack { Spacer(); if model.busy { ProgressView() }; Text(register ? L("注册", "Create account") : L("登录", "Sign in")); Spacer() }
                    }.disabled(model.busy || username.isEmpty || password.isEmpty || (register && displayName.isEmpty) || (model.retryUntil ?? .distantPast) > now)
                    if let until = model.retryUntil, until > now { Text(L("请稍后重试：", "Try again in ") + "\(Int(ceil(until.timeIntervalSince(now))))s").foregroundStyle(.secondary) }
                    Button(register ? L("已有账号，登录", "Already have an account? Sign in") : L("创建账号", "Create an account")) { register.toggle(); model.error = nil }
                }
                Section(L("连接设置", "Connection")) {
                    TextField(L("服务地址", "Server URL"), text: $server).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Picker(L("语言", "Language"), selection: $locale) { Text("中文").tag("zh"); Text("English").tag("en") }
                }
                if model.error != nil {
                    Section {
                        Button(L("重试恢复登录", "Retry session recovery")) { Task { await model.retryRestore() } }
                        Button(L("清除本机登录", "Clear local sign-in"), role: .destructive) { Task { await model.signOut() } }
                    }
                }
            }.navigationTitle(register ? L("创建账号", "Create account") : L("欢迎", "Welcome"))
                .onAppear { server = model.client.baseURL.absoluteString }
                .task { while !Task.isCancelled { try? await Task.sleep(for: .seconds(1)); now = Date() } }
        }
    }
}
struct MembershipView: View {
    @Bindable var model: AppModel
    let user: AuthUser
    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Image(systemName: user.membership_status == "pending" ? "hourglass" : "person.crop.circle.badge.exclamationmark").font(.system(size: 48))
                Text(user.display_name).font(.title2)
                Text(user.membership_status == "pending" ? L("账号正在等待管理员批准。", "Your account is awaiting administrator approval.") : L("账号已被停用，请联系管理员。", "Your account is suspended. Contact your administrator."))
                if let error = model.error { ErrorNotice(message: error) }
                Button(L("刷新状态", "Refresh status")) { Task { await model.refreshUser() } }.buttonStyle(.borderedProminent)
                Button(L("退出登录", "Sign out")) { Task { await model.signOut() } }
            }.padding().navigationTitle("Nano IM")
        }
    }
}
