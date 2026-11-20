import SwiftUI

struct AuthView: View {
    @Bindable var model: AppModel
    @State private var server = ""
    @State private var username = ""
    @State private var password = ""
    @State private var displayName = ""
    @State private var register = false
    @State private var connectionSettings = false
    @State private var now = Date()
    @AppStorage("nano.locale") private var locale = "zh"
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private enum Field { case username, password, name }
    @FocusState private var field: Field?

    private var coolingDown: Bool { (model.retryUntil ?? .distantPast) > now }

    private func submit() {
        guard !model.busy && !coolingDown else { return }
        if username.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { field = .username; return }
        if register && displayName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { field = .name; return }
        if password.isEmpty || (register && password.unicodeScalars.count < 8) { field = .password; return }
        field = nil
        Task {
            await model.authenticate(server: server, username: username, password: password, displayName: register ? displayName : nil)
            if model.user != nil { password = "" }
        }
    }

    private func switchMode() {
        field = nil
        model.error = nil
        withAnimation(reduceMotion ? nil : .easeOut(duration: 0.22)) { register.toggle() }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 0) {
                    VStack(spacing: 8) {
                        HStack {
                            HStack(spacing: 7) {
                                Image("CrewdenMark").resizable().scaledToFit().frame(width: 28, height: 28)
                                    .foregroundStyle(NanoTheme.accent)
                                Text("Crewden").font(.system(.title3, design: .rounded, weight: .bold))
                            }.accessibilityElement(children: .combine)
                            Spacer()
                            Menu {
                                Picker(L("语言", "Language"), selection: $locale) {
                                    Text("中文").tag("zh")
                                    Text("English").tag("en")
                                }
                                Button(L("连接设置", "Connection settings"), systemImage: "network") { connectionSettings = true }
                            } label: {
                                Image(systemName: "ellipsis").font(.headline).frame(width: 44, height: 44)
                            }.accessibilityLabel(L("语言与连接设置", "Language and connection settings"))
                        }
                        WelcomeCrew(compact: field != nil, registering: register)
                        if field == nil {
                            Text(register ? L("很高兴认识你！", "Nice to meet you!") : L("你好呀！", "Hi there!"))
                                .font(.system(.largeTitle, design: .rounded, weight: .bold))
                                .accessibilityAddTraits(.isHeader)
                        }
                    }
                    .padding(.horizontal, 24).padding(.top, 5).padding(.bottom, field == nil ? 27 : 8)
                    .frame(maxWidth: .infinity)
                    .background(alignment: .bottom) {
                        LinearGradient(colors: [NanoTheme.softAccent.opacity(0.65), Color("Butter").opacity(0.24), NanoTheme.surface],
                                       startPoint: .topLeading, endPoint: .bottomTrailing).ignoresSafeArea(edges: .top)
                    }
                    VStack(alignment: .leading, spacing: 16) {
                        ViewThatFits(in: .horizontal) {
                            HStack { formTitle; Spacer(minLength: 12); modeButton }
                            VStack(alignment: .leading, spacing: 4) { formTitle; modeButton }
                        }
                        VStack(spacing: 0) {
                            inputRow(symbol: "person", active: field == .username) {
                                TextField(L("输入用户名", "Enter your username"), text: $username)
                                    .textContentType(.username).textInputAutocapitalization(.never).autocorrectionDisabled()
                                    .focused($field, equals: .username).submitLabel(.next)
                                    .onSubmit { field = register ? .name : .password }
                            }
                            Divider().padding(.leading, 47)
                            if register {
                                inputRow(symbol: "face.smiling", active: field == .name) {
                                    TextField(L("其他人看到的名字", "Name shown to others"), text: $displayName)
                                        .focused($field, equals: .name).submitLabel(.next).onSubmit { field = .password }
                                }
                                Divider().padding(.leading, 47)
                            }
                            inputRow(symbol: "lock", active: field == .password) {
                                SecureField(L("输入密码", "Enter your password"), text: $password)
                                    .textContentType(register ? .newPassword : .password)
                                    .focused($field, equals: .password).submitLabel(.go).onSubmit { submit() }
                            }
                        }
                        .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 16))
                        if register {
                            Text(L("密码至少 8 个字符", "Use at least 8 characters for your password"))
                                .font(.footnote).foregroundStyle(NanoTheme.muted)
                        }
                        if let error = model.error { ErrorNotice(message: error) }
                        Button(action: submit) {
                            HStack(spacing: 9) {
                                if model.busy { ProgressView().tint(.white) }
                                Text(register ? L("创建账号", "Create account") : L("登录", "Sign in")).font(.headline)
                                if !model.busy { Image(systemName: "arrow.right").font(.subheadline.weight(.semibold)) }
                            }
                            .frame(maxWidth: .infinity).padding(.vertical, 15)
                            .foregroundStyle(.white).background(NanoTheme.accent, in: RoundedRectangle(cornerRadius: 16))
                        }.buttonStyle(.plain).disabled(model.busy || coolingDown)
                        if let until = model.retryUntil, coolingDown {
                            Text(L("请稍后重试：", "Try again in ") + "\(Int(ceil(until.timeIntervalSince(now))))s")
                                .font(.caption).foregroundStyle(NanoTheme.muted)
                        }
                        if model.needsLocalRecovery {
                            Button(L("重试恢复登录", "Retry session recovery")) { Task { await model.retryRestore() } }
                            Button(L("清除本机登录", "Clear local sign-in"), role: .destructive) { Task { await model.signOut() } }
                        }
                    }.padding(.horizontal, 26).padding(.top, 6).padding(.bottom, 28)
                        .frame(maxWidth: 480)
                }.frame(maxWidth: .infinity)
            }
            .background(NanoTheme.surface).foregroundStyle(NanoTheme.ink).toolbar(.hidden, for: .navigationBar)
            .scrollDismissesKeyboard(.interactively)
            .onAppear { server = model.client.baseURL.absoluteString }
            .task(id: model.retryUntil) {
                while let until = model.retryUntil, now < until {
                    do { try await Task.sleep(for: .seconds(1)) } catch { return }
                    now = Date()
                }
            }
            .sheet(isPresented: $connectionSettings) {
                NavigationStack {
                    Form { TextField(L("服务地址", "Server URL"), text: $server).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled() }
                        .navigationTitle(L("连接设置", "Connection settings")).navigationBarTitleDisplayMode(.inline)
                        .toolbar {
                            ToolbarItem(placement: .confirmationAction) { Button(L("完成", "Done")) { connectionSettings = false } }
                        }
                }.presentationDetents([.medium, .large])
            }
        }
    }

    private var formTitle: some View {
        Text(register ? L("创建账号", "Create an account") : L("登录 Crewden", "Sign in to Crewden"))
            .font(.title3.weight(.bold)).accessibilityAddTraits(.isHeader)
    }

    private var modeButton: some View {
        Button(action: switchMode) {
            HStack(spacing: 4) {
                Text(register ? L("已有账号？登录", "Already a member? Sign in") : L("创建账号", "Create an account"))
                Image(systemName: "arrow.up.right").font(.caption)
            }.font(.subheadline.weight(.semibold)).frame(minHeight: 44)
        }
        .accessibilityLabel(register ? L("已有账号？登录", "Already a member? Sign in") : L("还没有账号？创建账号", "New here? Create an account"))
        .disabled(model.busy)
    }

    private func inputRow<Content: View>(symbol: String, active: Bool, @ViewBuilder content: () -> Content) -> some View {
        HStack(spacing: 12) {
            Image(systemName: symbol).frame(width: 19).foregroundStyle(active ? NanoTheme.accent : NanoTheme.muted)
            content().padding(.vertical, 16)
        }.padding(.horizontal, 16)
    }
}

private struct WelcomeCrew: View {
    let compact: Bool
    let registering: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var appeared = false

    var body: some View {
        ZStack {
            if !compact {
                Capsule().fill(NanoTheme.softAccent.opacity(0.75)).frame(width: 174, height: 12).offset(y: 47)
                AssistantPortrait(personal: false, seed: "", selected: 9, size: 65)
                    .rotationEffect(.degrees(appeared ? -12 : -20)).offset(x: -68, y: 15)
                AssistantPortrait(personal: false, seed: "", selected: 13, size: 69)
                    .rotationEffect(.degrees(registering ? 16 : 9)).offset(x: 66, y: 12)
            }
            AssistantPortrait(personal: true, seed: "", selected: 0, size: compact ? 43 : 102)
                .rotationEffect(.degrees(compact ? -6 : registering ? 5 : -4))
                .offset(y: appeared ? 0 : 7)
        }.frame(maxWidth: .infinity).frame(height: compact ? 44 : 128)
            .accessibilityHidden(true)
            .onAppear {
                withAnimation(reduceMotion ? nil : .spring(duration: 0.45, bounce: 0.23)) { appeared = true }
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
            }.padding().navigationTitle("Crewden")
        }
    }
}
