import SwiftUI
import Observation

@main
struct NanoIMApp: App {
    @State private var model = AppModel()
    @AppStorage("nano.locale") private var locale = "zh"
    var body: some Scene {
        WindowGroup {
            Group {
                // `ready` now means "the local start finished", not "the network answered":
                // the launch spinner is only the pre-bootstrap frame and carries no wording
                // that could be mistaken for restoring a login.
                if !model.ready { ProgressView() }
                else if let user = model.user {
                    if user.accountEnabled, let chat = model.chat {
                        RootTabs(client: model.client, user: user, chat: chat, accountUpdated: { Task { await model.refreshUser() } }, signOut: { Task { await model.signOut() } })
                            .id("\(model.client.baseURL)-\(user.id)")
                    } else { MembershipView(model: model, user: user) }
                } else { AuthView(model: model) }
            }
            .scrollContentBackground(.hidden).background(NanoTheme.canvas)
            .tint(NanoTheme.accent)
            .environment(\.locale, Locale(identifier: locale == "zh" ? "zh-Hans" : "en"))
            .task { await model.start() }
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
    /// The only owner of the local chat partition. Replaced together with `client`, because a
    /// partition identity is `(origin, userID)` and a new origin must never reuse the old one.
    var storage: ChatStorageController
    /// View reconstruction must not create or attach a second store to this account.
    private(set) var chat: ChatStore?
    @ObservationIgnored private var chatPartition: ChatPartition?
    @ObservationIgnored private var observation: Task<Void, Never>?
    @ObservationIgnored private var clientGeneration = 0
    init(client: IMClient? = nil, storage: ChatStorageController? = nil) {
        if let client {
            self.client = client
            self.storage = storage ?? ChatStorageController(client: client)
            return
        }
        let saved = UserDefaults.standard.string(forKey: "nano.server") ?? "https://im.nanoim.win"
        #if DEBUG
        let input = ProcessInfo.processInfo.environment["NANO_IM_BASE_URL"] ?? saved
        let origin = (try? ServerOrigin.parse(input, allowLoopback: true)) ?? URL(string: "https://im.nanoim.win")!
        #else
        let origin = (try? ServerOrigin.parse(saved)) ?? URL(string: "https://im.nanoim.win")!
        #endif
        let client = IMClient(baseURL: origin)
        self.client = client
        self.storage = storage ?? ChatStorageController(client: client)
    }
    private func observe() {
        observation?.cancel()
        let current = client
        let generation = clientGeneration
        observation = Task { [weak self] in
            for await user in await current.session.updates() {
                guard !Task.isCancelled, let self, self.clientGeneration == generation else { return }
                await self.apply(user, from: current)
            }
        }
    }

    /// Turns one session publish into screen state. The partition is registered *before*
    /// `user` is assigned so `RootTabs` can never attach a store to the previous account's
    /// repository; deletion is only ever decided by `ChatStorageController`.
    private func apply(_ user: AuthUser?, from client: IMClient) async {
        guard client === self.client else { return }
        let revision = await client.session.revision()
        let actual = await client.session.currentUser()
        // Stream entries carry values, not authority. A queued old nil/disabled publish must
        // not tear down a newer login that already replaced it in Session.
        guard actual?.id == user?.id, actual?.accountEnabled == user?.accountEnabled else { return }
        guard let user else {
            let termination = await client.session.termination
            guard client === self.client, revision == (await client.session.revision()),
                  await client.session.currentUser() == nil else { return }
            self.user = nil
            clearChat()
            await storage.purge(reason: termination == .credentials ? .credentials : .signedOut)
            return
        }
        if user.accountEnabled {
            await storage.activate(ChatPartition(origin: client.baseURL, userID: user.id))
        } else {
            clearChat()
            await storage.purge(reason: .deactivated)
        }
        guard client === self.client, revision == (await client.session.revision()),
              (await client.session.currentUser())?.id == user.id else { return }
        if user.accountEnabled { installChat(user) }
        self.user = user
        UserDefaults.standard.set(user.locale.hasPrefix("zh") ? "zh" : "en", forKey: "nano.locale")
    }

    private func installChat(_ user: AuthUser) {
        let partition = ChatPartition(origin: client.baseURL, userID: user.id)
        guard chat == nil || chatPartition != partition else { return }
        clearChat()
        chatPartition = partition
        chat = ChatStore(client: client, user: user, controller: storage)
    }

    private func clearChat() {
        chat?.resetProjection()
        chat = nil
        chatPartition = nil
    }

    /// Two phases on purpose: the local start must not wait for any network round trip, and a
    /// network failure must not be reported as a missing login.
    func start() async {
        guard !ready else { return }
        await bootstrapLocal()
        await correctSession()
    }

    /// The complete network-free stage: when `ready` is published the stable UI store already
    /// contains its cached seed, rather than scheduling another read from a View initializer.
    func bootstrapLocal() async {
        guard !ready else { return }
        observe()
        let current = client
        let revision = await current.session.revision()
        defer { if current === client { ready = true } }
        do {
            let stored = try await current.session.storedUser()
            if let stored, stored.accountEnabled {
                await storage.activate(ChatPartition(origin: current.baseURL, userID: stored.id))
                guard current === client, revision == (await current.session.revision()),
                      (await current.session.currentUser())?.id == stored.id else { return }
                installChat(stored)
            } else {
                clearChat()
                if stored != nil { await storage.purge(reason: .deactivated) }
            }
            guard current === client, revision == (await current.session.revision()) else { return }
            user = stored
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func correctSession() async {
        let current = client
        do {
            if let user = try await current.session.restore() { await apply(user, from: current) }
        } catch is CancellationError {
        } catch {
            // Keep the local content and let `ChatStore.run()` report the connection: a
            // transport failure says nothing about whether these credentials are valid.
        }
    }
    func retryRestore() async { ready = false; await start() }
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
                observation?.cancel()
                clearChat()
                self.user = nil
                _ = await client.session.signOut()
                // Switching destinations removes the previous origin's partition, not just
                // its credentials: old content must not be readable under the new server.
                await storage.purge(reason: .signedOut)
                clientGeneration += 1
                let next = IMClient(baseURL: origin)
                client = next
                storage = ChatStorageController(client: next)
                observe()
            }
            UserDefaults.standard.set(origin.absoluteString, forKey: "nano.server")
            let user = try await client.session.login(username: username.trimmingCharacters(in: .whitespacesAndNewlines), password: password,
                displayName: displayName, locale: UserDefaults.standard.string(forKey: "nano.locale") ?? "zh")
            // Both this path and the session observer use the same idempotent owner setup.
            await apply(user, from: client)
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
        let current = client
        do { await apply(try await current.session.updateUser(), from: current); error = nil }
        catch { self.error = error.localizedDescription }
    }
    func signOut() async {
        let current = client
        user = nil
        clearChat()
        let revocation = Task { await current.session.signOut() }
        await storage.purge(reason: .signedOut)
        let revoked = await revocation.value
        guard current === client else { return }
        if !revoked { error = L("已退出本机；服务器登录撤销尚未确认。", "Signed out locally; server revocation could not be confirmed.") }
    }
}

private struct RootTabs: View {
    let client: IMClient
    let user: AuthUser
    let chat: ChatStore
    let accountUpdated: () -> Void
    let signOut: () -> Void
    @State private var selectedTab = 0
    @State private var chatPath: [String] = []
    @State private var taskLink: NativeTaskLink?
    @State private var taskNavigationID = UUID()
    @State private var agentLink: Contact?
    @Environment(\.scenePhase) private var scenePhase
    init(client: IMClient, user: AuthUser, chat: ChatStore, accountUpdated: @escaping () -> Void, signOut: @escaping () -> Void) {
        self.client = client; self.user = user; self.chat = chat
        self.accountUpdated = accountUpdated; self.signOut = signOut
    }
    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack(path: $chatPath) {
                ChatListView(store: chat, open: openChat)
                    .navigationDestination(for: String.self) { id in ConversationView(store: chat, conversationID: id, openChat: openChat) }
            }.tabItem { Label(L("聊天", "Chats"), systemImage: "bubble.left.and.bubble.right") }.tag(0)
                .badge(chat.conversations.reduce(0) { $0 + $1.unread_count })
            NavigationStack { TasksView(client: client, onReference: reference) }.id(taskNavigationID)
                .tabItem { Label(L("任务", "Tasks"), systemImage: "point.3.connected.trianglepath.dotted") }.tag(1)
            NavigationStack { AgentsView(client: client, user: user, onOpenChat: openChat) }
                .tabItem { Label("Agent", systemImage: "person.crop.square") }.tag(2)
            NavigationStack { MeView(client: client, user: user, onAccountUpdated: accountUpdated, onSignOut: signOut) }
                .tabItem { Label(L("我的", "Me"), systemImage: "person.crop.circle") }.tag(3)
        }
        .onChange(of: chat.composeRequest?.id) { _, _ in
            if let request = chat.composeRequest { openChat(request.target) }
        }
        .environment(\.openTaskOverview, { taskLink = nil; taskNavigationID = UUID(); selectedTab = 1 })
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
        .task(id: scenePhase) { if scenePhase == .active { try? await client.syncTimeZone() } }
        .onChange(of: scenePhase) { _, value in
            guard value != .active else { return }
            // Backgrounding is a draft flush point: the process may not get another turn.
            Task { await chat.flushDrafts() }
            chat.stop()
        }
        .onDisappear { chat.stop() }
        .onOpenURL { url in
            guard ServerOrigin.same(client.baseURL, url) else { return }
            let parts = url.path.split(separator: "/")
            if parts.count == 2, parts[0] == "chat" { openChat(String(parts[1])) }
        }
    }
    private func openChat(_ id: String) { selectedTab = 0; chatPath = [id] }
    private func reference(_ id: String, _ text: String) {
        chat.setDraft(id, [chat.drafts[id] ?? "", text].filter { !$0.isEmpty }.joined(separator: "\n\n"))
        openChat(id)
    }
}

private struct NativeTaskLink: Identifiable { let id: String; let scope: String?; let node: String? }
