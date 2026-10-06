import SwiftUI
import Observation

@main
struct NanoIMApp: App {
    @State private var model = AppModel()
    @AppStorage("nano.locale") private var locale = "zh"
    var body: some Scene {
        WindowGroup {
            Group {
                if !model.ready { ProgressView(L("恢复登录…", "Restoring session…")) }
                else if let user = model.user {
                    if user.membership_status == "active" {
                        RootTabs(client: model.client, user: user, accountUpdated: { Task { await model.refreshUser() } }, signOut: { Task { await model.signOut() } })
                            .id("\(model.client.baseURL)-\(user.id)")
                    } else { MembershipView(model: model, user: user) }
                } else { AuthView(model: model) }
            }
            .scrollContentBackground(.hidden).background(NanoTheme.canvas)
            .tint(NanoTheme.accent)
            .environment(\.locale, Locale(identifier: locale == "zh" ? "zh-Hans" : "en"))
            .task { await model.restore() }
        }
    }
}

@MainActor @Observable
final class AppModel {
    var client: IMClient
    var user: AuthUser?
    var ready = false
    var error: String?
    var busy = false
    var retryUntil: Date?
    private var observation: Task<Void, Never>?
    init() {
        let saved = UserDefaults.standard.string(forKey: "nano.server") ?? "https://im.nanoim.win"
        #if DEBUG
        let input = ProcessInfo.processInfo.environment["NANO_IM_BASE_URL"] ?? saved
        let origin = (try? ServerOrigin.parse(input, allowLoopback: true)) ?? URL(string: "https://im.nanoim.win")!
        #else
        let origin = (try? ServerOrigin.parse(saved)) ?? URL(string: "https://im.nanoim.win")!
        #endif
        client = IMClient(baseURL: origin)
    }
    private func observe() {
        observation?.cancel()
        let current = client
        observation = Task { [weak self] in
            for await user in await current.session.updates() {
                guard !Task.isCancelled, let self else { return }
                self.user = user
                if let user { UserDefaults.standard.set(user.locale.hasPrefix("zh") ? "zh" : "en", forKey: "nano.locale") }
            }
        }
    }
    func restore() async {
        guard !ready else { return }
        observe()
        do { user = try await client.session.restore(); error = nil }
        catch { self.error = error.localizedDescription }
        ready = true
    }
    func retryRestore() async { ready = false; await restore() }
    func authenticate(server: String, username: String, password: String, displayName: String?) async {
        guard !busy else { return }; busy = true; error = nil
        defer { busy = false }
        do {
            #if DEBUG
            let origin = try ServerOrigin.parse(server, allowLoopback: true)
            #else
            let origin = try ServerOrigin.parse(server)
            #endif
            if origin != client.baseURL {
                observation?.cancel(); _ = await client.session.signOut()
                client = IMClient(baseURL: origin); observe()
            }
            UserDefaults.standard.set(origin.absoluteString, forKey: "nano.server")
            user = try await client.session.login(username: username.trimmingCharacters(in: .whitespacesAndNewlines), password: password,
                displayName: displayName, locale: UserDefaults.standard.string(forKey: "nano.locale") ?? "zh")
        } catch {
            switch (error as? APIError)?.status {
            case 429: self.error = L("请求过于频繁，请稍后重试。", "Too many requests. Wait before retrying.")
            case 503: self.error = L("服务暂时不可用，请稍后重试。", "The service is temporarily unavailable. Please retry.")
            default: self.error = error.localizedDescription
            }
            if let e = error as? APIError, e.retryAfter > 0 { retryUntil = Date().addingTimeInterval(e.retryAfter) }
        }
    }
    func refreshUser() async {
        do { user = try await client.session.updateUser(); error = nil }
        catch { self.error = error.localizedDescription }
    }
    func signOut() async {
        user = nil
        let revoked = await client.session.signOut()
        if !revoked { error = L("已退出本机；服务器登录撤销尚未确认。", "Signed out locally; server revocation could not be confirmed.") }
    }
}

private struct RootTabs: View {
    let client: IMClient
    let user: AuthUser
    let accountUpdated: () -> Void
    let signOut: () -> Void
    @State private var chat: ChatStore
    @State private var selectedTab = 0
    @State private var chatPath: [String] = []
    @State private var taskLink: NativeTaskLink?
    @State private var agentLink: Contact?
    @Environment(\.scenePhase) private var scenePhase
    init(client: IMClient, user: AuthUser, accountUpdated: @escaping () -> Void, signOut: @escaping () -> Void) {
        self.client = client; self.user = user; self.accountUpdated = accountUpdated; self.signOut = signOut
        _chat = State(initialValue: ChatStore(client: client, user: user))
    }
    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack(path: $chatPath) {
                ChatListView(store: chat, open: openChat)
                    .navigationDestination(for: String.self) { id in ConversationView(store: chat, conversationID: id, openChat: openChat) }
            }.tabItem { Label(L("聊天", "Chats"), systemImage: "bubble.left.and.bubble.right") }.tag(0)
                .badge(chat.conversations.reduce(0) { $0 + $1.unread_count })
            NavigationStack { TasksView(client: client, onReference: reference) }
                .tabItem { Label(L("任务", "Tasks"), systemImage: "point.3.connected.trianglepath.dotted") }.tag(1)
            NavigationStack { AgentsView(client: client, user: user, onOpenChat: openChat) }
                .tabItem { Label("Agent", systemImage: "person.crop.square") }.tag(2)
            NavigationStack { MeView(client: client, user: user, onAccountUpdated: accountUpdated, onSignOut: signOut) }
                .tabItem { Label(L("我的", "Me"), systemImage: "person.crop.circle") }.tag(3)
        }
        .environment(\.openURL, OpenURLAction { url in
            guard ServerOrigin.same(client.baseURL, url) else {
                return ["http", "https", "mailto", "tel"].contains(url.scheme ?? "") ? .systemAction : .discarded
            }
            let parts = url.path.split(separator: "/").map(String.init)
            if parts.count == 2, parts[0] == "chat" { openChat(parts[1]); return .handled }
            if parts.count == 2, parts[0] == "tasks" {
                let query = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
                taskLink = NativeTaskLink(id: parts[1], scope: query.first { $0.name == "scope" }?.value, node: query.first { $0.name == "node" }?.value)
                return .handled
            }
            if parts.count == 3, parts[0] == "settings", parts[1] == "agents" {
                Task {
                    do { let contacts = try await client.contacts(kind: "agent"); agentLink = contacts.first { $0.agent_id == parts[2] } }
                    catch { chat.listError = error.localizedDescription }
                }
                return .handled
            }
            return .systemAction
        })
        .sheet(item: $taskLink) { link in
            NavigationStack {
                TaskGraphView(client: client, graphID: link.id, scopeID: link.scope, initialNodeID: link.node, onReference: { id, text in taskLink = nil; reference(id, text) })
                    .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("完成", "Done")) { taskLink = nil } } }
            }
        }
        .sheet(item: $agentLink) { contact in
            NavigationStack {
                AgentProfileView(client: client, user: user, contact: contact, onOpenChat: { id in agentLink = nil; openChat(id) })
                    .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("完成", "Done")) { agentLink = nil } } }
            }
        }
        .overlay(alignment: .top) {
            if let banner = chat.banner {
                Button { chat.banner = nil; openChat(banner.conversationID) } label: {
                    HStack(spacing: 10) {
                        if let conversation = chat.conversations.first(where: { $0.id == banner.conversationID }) {
                            AvatarView(name: conversation.avatarName(selfID: user.id), kind: conversation.type == "group" ? "group" : conversation.category == "agent" ? "agent" : "person", size: 32)
                            Text(conversation.title).font(.callout.weight(.semibold)).lineLimit(1)
                        }
                        Text(L("新消息", "New message")).font(.caption).foregroundStyle(NanoTheme.muted)
                    }.padding(12).background(.regularMaterial, in: Capsule())
                }
                    .padding(.top, 8).task(id: banner.id) { try? await Task.sleep(for: .seconds(3)); if !Task.isCancelled, chat.banner?.id == banner.id { chat.banner = nil } }
            }
        }
        .task(id: scenePhase) { if scenePhase == .active { await chat.run() } }
        .onChange(of: scenePhase) { _, value in if value != .active { chat.stop() } }
        .onDisappear { chat.clear() }
        .onOpenURL { url in
            guard ServerOrigin.same(client.baseURL, url) else { return }
            let parts = url.path.split(separator: "/")
            if parts.count == 2, parts[0] == "chat" { openChat(String(parts[1])) }
        }
    }
    private func openChat(_ id: String) { selectedTab = 0; chatPath = [id] }
    private func reference(_ id: String, _ text: String) {
        chat.drafts[id] = [chat.drafts[id] ?? "", text].filter { !$0.isEmpty }.joined(separator: "\n\n")
        openChat(id)
    }
}

private struct NativeTaskLink: Identifiable { let id: String; let scope: String?; let node: String? }
