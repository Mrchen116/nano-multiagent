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
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    HStack(spacing: 10) {
                        Image(systemName: "checkmark").font(.system(size: 21, weight: .bold)).foregroundStyle(.white)
                            .frame(width: 42, height: 42).background(NanoTheme.accent, in: RoundedRectangle(cornerRadius: 14))
                        Text("Nano IM").font(.title3.bold())
                        Spacer()
                        Menu { Picker(L("语言", "Language"), selection: $locale) { Text("中文").tag("zh"); Text("English").tag("en") } }
                            label: { Label(locale == "zh" ? "中文" : "EN", systemImage: "globe").font(.subheadline).foregroundStyle(NanoTheme.muted) }
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        Text(register ? L("创建你的账号", "Create your account") : L("欢迎回来", "Welcome back")).font(.largeTitle.bold())
                        Text(L("与你的 Agent 保持连接", "Stay connected to your agents")).font(.subheadline).foregroundStyle(NanoTheme.muted)
                    }.padding(.top, 20)
                    VStack(alignment: .leading, spacing: 18) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(L("用户名", "Username")).font(.subheadline.weight(.medium))
                            TextField(L("输入用户名", "Enter your username"), text: $username).textContentType(.username)
                                .textInputAutocapitalization(.never).autocorrectionDisabled().authInput()
                        }
                        VStack(alignment: .leading, spacing: 8) {
                            Text(L("密码", "Password")).font(.subheadline.weight(.medium))
                            SecureField(L("输入密码", "Enter your password"), text: $password).textContentType(register ? .newPassword : .password).authInput()
                        }
                        if register {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(L("显示名称", "Display name")).font(.subheadline.weight(.medium))
                                TextField(L("其他人看到的名字", "Name shown to others"), text: $displayName).authInput()
                            }
                        }
                        if let error = model.error { ErrorNotice(message: error) }
                        Button { Task { await model.authenticate(server: server, username: username, password: password, displayName: register ? displayName : nil); if model.user != nil { password = "" } } } label: {
                            HStack { Spacer(); if model.busy { ProgressView().tint(.white) }; Text(register ? L("创建账号", "Create account") : L("登录", "Sign in")).fontWeight(.semibold); Spacer() }
                                .padding(.vertical, 15).foregroundStyle(.white).background(NanoTheme.accent, in: RoundedRectangle(cornerRadius: 13))
                        }.buttonStyle(.plain)
                            .disabled(model.busy || username.isEmpty || password.isEmpty || (register && displayName.isEmpty) || (model.retryUntil ?? .distantPast) > now)
                            .opacity(model.busy || username.isEmpty || password.isEmpty ? 0.6 : 1)
                        if let until = model.retryUntil, until > now { Text(L("请稍后重试：", "Try again in ") + "\(Int(ceil(until.timeIntervalSince(now))))s").font(.caption).foregroundStyle(NanoTheme.muted) }
                        Button(register ? L("已有账号？登录", "Have an account? Sign in") : L("还没有账号？创建账号", "New here? Create an account")) { register.toggle(); model.error = nil }
                            .font(.subheadline).frame(maxWidth: .infinity).padding(.top, 2)
                    }
                    DisclosureGroup {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(L("服务地址", "Server URL")).font(.caption).foregroundStyle(NanoTheme.muted)
                            TextField(L("服务地址", "Server URL"), text: $server).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled().authInput()
                        }.padding(.top, 12)
                    } label: { Label(L("连接设置", "Connection settings"), systemImage: "network").font(.subheadline).foregroundStyle(NanoTheme.muted) }
                        .padding(.top, 4)
                    if model.error != nil {
                        VStack(alignment: .leading, spacing: 12) {
                            Button(L("重试恢复登录", "Retry session recovery")) { Task { await model.retryRestore() } }
                            Button(L("清除本机登录", "Clear local sign-in"), role: .destructive) { Task { await model.signOut() } }
                        }.font(.subheadline)
                    }
                }.padding(.horizontal, 28).padding(.top, 28).padding(.bottom, 40).frame(maxWidth: 480)
                    .frame(maxWidth: .infinity)
            }.background(NanoTheme.surface).toolbar(.hidden, for: .navigationBar)
                .scrollDismissesKeyboard(.interactively)
                .onAppear { server = model.client.baseURL.absoluteString }
                .task { while !Task.isCancelled { try? await Task.sleep(for: .seconds(1)); now = Date() } }
        }
    }
}

private extension View {
    func authInput() -> some View {
        font(.body).padding(14).frame(maxWidth: .infinity, alignment: .leading)
            .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(NanoTheme.border, lineWidth: 1))
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
