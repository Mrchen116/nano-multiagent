import Foundation
import JavaScriptCore
import Observation

/// Runs the shipped OpenUI evaluator while Session remains the only network owner.
@MainActor @Observable
final class InteractiveRuntime {
    let client: IMClient
    let message: ChatMessage
    let chat: ChatStore
    var root: JSONValue = .null
    var state: [String: JSONValue] = [:]
    var busy = false
    var composing = false
    var readOnly: Bool
    var error: String?
    var loaded = false
    var conflict = false
    var submitted = false
    var pendingCompose: ChatStore.ComposeRequest?
    @ObservationIgnored private var context: JSContext?
    @ObservationIgnored private var engine: JSValue?
    @ObservationIgnored private var revision = 0
    @ObservationIgnored private var sessionRevision: Int?
    @ObservationIgnored private var edited = 0
    @ObservationIgnored private var saved = 0
    @ObservationIgnored private var editedAt: Double = 0
    @ObservationIgnored private var saveTimer: Task<Void, Never>?
    @ObservationIgnored private var saveFlight: Task<Void, Never>?
    @ObservationIgnored private var queryTask: Task<Void, Never>?
    @ObservationIgnored private var queryPoll: Task<Void, Never>?
    @ObservationIgnored private var queryDue: [String: Date] = [:]
    @ObservationIgnored private var querySignatures: [String: String] = [:]
    @ObservationIgnored private var queries: [JSONValue] = []
    @ObservationIgnored private var generation = UUID()
    var openURL: ((URL) -> Void)?

    init(client: IMClient, message: ChatMessage, chat: ChatStore, readOnly: Bool) {
        self.client = client; self.message = message; self.chat = chat
        self.readOnly = readOnly || message.interactive?.read_only == true || message.interactive?.superseded_by != nil
    }
    var hasPending: Bool { chat.interactionAttempt(message.conversation_id, sourceMessageID: message.id) != nil }

    func load() async {
        let token = UUID(); generation = token
        sessionRevision = await client.session.revision()
        error = nil; conflict = false; loaded = false
        do {
            guard let source = message.interactive, source.format == "openui", source.catalog_version == "nano-1" else {
                throw APIError(status: 422, detail: L("此交互回复版本暂不支持，仍可阅读上方文字。", "This interactive version is unsupported. The text remains readable."))
            }
            let draft = try await client.interactionDraft(message.conversation_id, messageID: message.id)
            guard token == generation, await current() else { return }
            guard let url = Bundle.main.url(forResource: "InteractiveRuntime", withExtension: "js"), let js = JSContext() else { throw URLError(.cannotDecodeContentData) }
            js.evaluateScript(try String(contentsOf: url, encoding: .utf8))
            if let exception = js.exception { throw runtimeError(exception.toString()) }
            let instance = js.objectForKeyedSubscript("NanoInteractive")?.invokeMethod("create", withArguments: [source.source, JSONValue.object(draft.state).foundationObject])
            if let exception = js.exception { throw runtimeError(exception.toString()) }
            guard let instance, !instance.isUndefined else { throw URLError(.cannotParseResponse) }
            context = js; engine = instance
            revision = draft.draft_revision; submitted = draft.submission_message_id != nil
            edited = 0; saved = 0; querySignatures = [:]
            let formatter = ISO8601DateFormatter(); formatter.formatOptions.insert(.withFractionalSeconds)
            editedAt = draft.updated_at.flatMap { formatter.date(from: $0) ?? ISO8601DateFormatter().date(from: $0) }?.timeIntervalSince1970 ?? 0
            editedAt *= 1000
            try receive(call("snapshot")); loaded = true
            select(); refreshQueries(); pollQueries()
        } catch { if token == generation { self.error = error.localizedDescription } }
    }
    func setReadOnly(_ value: Bool) {
        readOnly = value || message.interactive?.read_only == true || message.interactive?.superseded_by != nil
        if readOnly { saveTimer?.cancel(); chat.interactionSelections[message.id] = nil }
    }
    func fieldValue(_ node: JSONValue, form: String?, property: String = "value") -> JSONValue {
        let value = node["props"][property]
        return value == .null ? node["props"]["value"] : value
    }
    func edit(_ node: JSONValue, form: String?, value: JSONValue, property: String = "value") {
        guard !busy, !hasPending else { return }
        do {
            try receive(call("edit", [node["id"].stringValue ?? "", property, value.foundationObject]))
            changed(); refreshQueries()
        } catch { self.error = error.localizedDescription }
    }
    func activate(_ node: JSONValue, form: String?) {
        guard !busy, !hasPending else { return }
        do {
            let before = state
            let result: JSONValue
            if node["typeName"].stringValue == "EditableTable" {
                result = .object(["events": .array([.object(["type": .string("continue_conversation"), "message": .string("Updated " + (form ?? node["props"]["name"].stringValue ?? "table")), "form": .string(form ?? ""), "state": .object(state)])])])
            } else { result = try call("activate", [node["id"].stringValue ?? ""]); try receive(result) }
            if state != before { changed() }
            let events = result["events"].arrayValue ?? []
            let business = events.contains { ["custom_action", "legacy", "mutation", "continue_conversation"].contains($0["type"].stringValue ?? "") }
            if business && (readOnly || conflict) {
                error = L("请先读取最新内容；历史回复不能发起新请求。", "Load the latest content first. Historical replies cannot submit requests."); return
            }
            composing = events.contains { $0["type"].stringValue == "custom_action" }
            busy = business
            let token = generation
            Task {
                defer { if token == generation { busy = false; composing = false } }
                do {
                    if business { await flush(); guard !conflict, saved == edited, token == generation, await current() else { return } }
                    for event in events {
                        guard token == generation, await current() else { return }
                        switch event["type"].stringValue {
                        case "open_url":
                            if let value = event["url"].stringValue, let url = URL(string: value), ["http", "https"].contains(url.scheme?.lowercased() ?? "") { openURL?(url) }
                            else { throw runtimeError(L("链接不可打开。", "This link cannot be opened.")) }
                        case "query": querySignatures[event["id"].stringValue ?? ""] = nil
                        case "custom_action":
                            guard event["name"].stringValue == "ComposeMessage",
                                  let target = event["params"]["target"].stringValue, let text = event["params"]["text"].stringValue else { throw runtimeError("Invalid compose action") }
                            try await compose(target, text: text)
                        case "legacy", "mutation", "continue_conversation":
                            var input = InteractionReplyInput(source_message_id: message.id, state: event["state"].objectValue ?? state)
                            let label = node["props"]["label"].stringValue ?? node["props"]["name"].stringValue ?? L("向 Agent 提问", "Ask Agent")
                            if event["type"].stringValue == "legacy" { input.action_id = event["action_id"].stringValue }
                            else {
                                let mutation = event["type"].stringValue == "mutation"
                                let request = mutation ? event["args"] : event
                                guard let text = request["message"].stringValue else { throw runtimeError("message required") }
                                var details: [String: JSONValue] = ["type": .string("continue_conversation"), "message": .string(text), "label": .string(label)]
                                if request["context"] != .null { details["context"] = request["context"] }
                                if let name = event["form"].stringValue, !name.isEmpty { details["form_name"] = .string(name) }
                                input.event = .object(details)
                            }
                            let receipt = try await chat.submitInteraction(message.conversation_id, input: input, key: UUID().uuidString)
                            guard token == generation, await current() else { return }
                            if let id = event["id"].stringValue {
                                try receive(call("result", [id, "", ["message_id":receipt.id, "delivery_status":receipt.delivery_status]]))
                            }
                            submitted = true; saved = edited
                            await syncRevision()
                        default: throw runtimeError(L("此动作未接入。", "This action is not connected."))
                        }
                    }
                    if token == generation { refreshQueries() }
                } catch { if token == generation { self.error = error.localizedDescription } }
            }
        } catch { self.error = error.localizedDescription }
    }
    /// Adoption remains local; fresh source and target access are checked at the click boundary.
    func compose(_ target: String, text: String, replacing: Bool = false) async throws {
        guard !readOnly, !conflict else { throw runtimeError(L("此回复仅供阅读。", "This reply is read only.")) }
        let latest = try await client.interactionDraft(message.conversation_id, messageID: message.id)
        guard latest.can_interact == true, latest.read_only != true, latest.superseded_by == nil else {
            throw runtimeError(L("此回复已不可交互，请查看最新内容。", "This reply is no longer interactive. Open the latest content."))
        }
        try await chat.checkComposeTarget(target)
        guard await current() else { return }
        if !replacing && chat.hasComposeConflict(target, text: text) { pendingCompose = ChatStore.ComposeRequest(target: target, text: text); return }
        chat.adoptCompose(target, text: text)
    }
    func replaceCompose(_ request: ChatStore.ComposeRequest) async {
        pendingCompose = nil
        do { try await compose(request.target, text: request.text, replacing: true) }
        catch { self.error = error.localizedDescription }
    }
    func retry() async {
        guard !busy, !readOnly else { return }
        busy = true; error = nil
        defer { busy = false }
        do {
            _ = try await chat.retryInteraction(message.conversation_id, sourceMessageID: message.id)
            guard await current() else { return }; submitted = true
            await syncRevision()
        } catch { self.error = error.localizedDescription }
    }
    func flush() async {
        if let saveFlight { await saveFlight.value; return }
        guard loaded, !readOnly, !conflict, !hasPending, edited != saved else { return }
        let token = generation
        let flight = Task { [self] in
            while token == generation, !readOnly, !conflict, saved != edited, await current() {
                let serial = edited, value = state
                do {
                    let result = try await client.saveInteractionDraft(message.conversation_id, messageID: message.id, revision: revision, state: value)
                    guard token == generation, await current() else { return }
                    revision = result.draft_revision; saved = serial; error = nil
                } catch {
                    if token == generation {
                        conflict = (error as? APIError)?.status == 409
                        self.error = conflict ? L("其他设备已更新这张卡片，请读取最新内容。", "This card changed on another device. Load the latest content.") : error.localizedDescription
                    }
                    return
                }
            }
        }
        saveFlight = flight; await flight.value; saveFlight = nil
    }
    func leave() {
        saveTimer?.cancel(); queryTask?.cancel(); queryPoll?.cancel()
        // Finish the latest private edit; Session's generation still fences logout.
        Task { await flush() }
    }
    func retryContent() async {
        if !loaded || conflict { await load() }
        else { error = nil; querySignatures = [:]; refreshQueries(); await flush() }
    }
    private func changed() {
        guard !readOnly else { return }
        edited += 1; submitted = false; editedAt = Date().timeIntervalSince1970 * 1000; select()
        saveTimer?.cancel()
        saveTimer = Task { try? await Task.sleep(for: .milliseconds(500)); if !Task.isCancelled { await flush() } }
    }
    private func select() {
        guard !readOnly else { return }
        chat.interactionSelections[message.id] = InteractionSelection(conversationID: message.conversation_id, source_message_id: message.id, state: state, editedAt: editedAt)
    }
    private func syncRevision() async {
        do {
            let draft = try await client.interactionDraft(message.conversation_id, messageID: message.id)
            guard await current() else { return }; revision = draft.draft_revision
        } catch { self.error = error.localizedDescription }
    }
    private func current() async -> Bool {
        guard let sessionRevision, await client.session.revision() == sessionRevision,
              await client.session.currentUser()?.id == chat.user.id, !chat.revokedChats.contains(message.conversation_id) else { return false }
        return true
    }
    private func receive(_ result: JSONValue) throws {
        root = result["root"]; state = result["state"].objectValue ?? state
        queries = result["queries"].arrayValue ?? []
    }
    private func call(_ method: String, _ arguments: [Any] = []) throws -> JSONValue {
        context?.exception = nil
        let result = engine?.invokeMethod(method, withArguments: arguments)
        if let exception = context?.exception { throw runtimeError(exception.toString()) }
        guard let text = result?.toString(), let data = text.data(using: .utf8) else { throw URLError(.cannotParseResponse) }
        return try JSONDecoder().decode(JSONValue.self, from: data)
    }
    private func runtimeError(_ text: String?) -> APIError { APIError(status: 422, detail: text ?? L("无法呈现交互内容。", "Could not render this reply.")) }
    private func refreshQueries() {
        queryTask?.cancel()
        let token = generation
        queryTask = Task {
            for query in queries {
                guard token == generation, !Task.isCancelled, await current() else { return }
                let id = query["id"].stringValue ?? "", signature = query["signature"].stringValue ?? ""
                guard querySignatures[id] != signature else { continue }
                querySignatures[id] = signature
                queryDue[id] = Date().addingTimeInterval(max(1, query["refresh"].doubleValue ?? 0))
                do {
                    guard query["tool"].stringValue == "conversation_messages" else { throw runtimeError(L("此查询工具未接入。", "This query tool is not connected.")) }
                    let limit = max(1, min(100, query["args"]["limit"].intValue ?? 20))
                    let page: MessagePage = try await client.get("/im/v1/conversations/\(message.conversation_id.pathComponent)/messages", query: [.init(name: "limit", value: String(limit))])
                    guard token == generation, !Task.isCancelled, await current() else { return }
                    let rows: [[String: Any]] = page.items.compactMap(\.message).map { ["id":$0.id, "sender":$0.sender.display_name ?? $0.sender.id, "content":$0.content, "delivery_status":$0.delivery_status] }
                    try receive(call("result", [id, signature, rows]))
                } catch { if !Task.isCancelled, token == generation { self.error = error.localizedDescription } }
            }
            if token == generation, !Task.isCancelled, queries.contains(where: { querySignatures[$0["id"].stringValue ?? ""] != $0["signature"].stringValue }) { refreshQueries() }
        }
    }
    private func pollQueries() {
        queryPoll?.cancel()
        let token = generation
        guard queries.contains(where: { ($0["refresh"].doubleValue ?? 0) > 0 }) else { return }
        queryPoll = Task {
            while token == generation, !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1))
                guard token == generation, !Task.isCancelled else { return }
                var due = false
                for query in queries where (query["refresh"].doubleValue ?? 0) > 0 {
                    let id = query["id"].stringValue ?? ""
                    if (queryDue[id] ?? .distantPast) <= Date() { querySignatures[id] = nil; due = true }
                }
                if due { refreshQueries() }
            }
        }
    }
}
