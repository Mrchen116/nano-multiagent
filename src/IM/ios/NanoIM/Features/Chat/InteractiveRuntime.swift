import Foundation
import JavaScriptCore
import Observation
import UIKit

/// Runs the shipped OpenUI evaluator while Session remains the only network owner.
@MainActor @Observable
final class InteractiveRuntime {
    let client: IMClient
    let message: ChatMessage
    let chat: ChatStore
    private let chatEpoch: UUID
    var isCurrentStore: Bool { chat.interactionEpoch == chatEpoch }
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
    var attachmentPreview: UIImage?
    private var visibleAttachmentIndexes: Set<Int> = []
    @ObservationIgnored private var left = false
    @ObservationIgnored private var context: JSContext?
    @ObservationIgnored private var engine: JSValue?
    @ObservationIgnored private var revision = 0
    @ObservationIgnored private var sessionRevision: Int?
    @ObservationIgnored private var edited = 0
    @ObservationIgnored private var saved = 0
    private(set) var conflictColumns: [DraftConflictColumn]?
    private(set) var inspectingConflict = false
    @ObservationIgnored private var lastConfirmedUpdate: String?
    @ObservationIgnored private var offlineFailure = false
    var editSerial: Int { edited }
    @ObservationIgnored private var saveTimer: Task<Void, Never>?
    @ObservationIgnored private var saveFlight: Task<Void, Never>?
    @ObservationIgnored private var saveFlightID = UUID()
    @ObservationIgnored private var queryTask: Task<Void, Never>?
    @ObservationIgnored private var queryPoll: Task<Void, Never>?
    @ObservationIgnored private var queryDue: [String: Date] = [:]
    @ObservationIgnored private var querySignatures: [String: String] = [:]
    @ObservationIgnored private var queries: [JSONValue] = []
    @ObservationIgnored private var generation = UUID()
    // Recycling a page must revoke its bridge without invalidating an acknowledged draft PUT.
    private var rendererGeneration = UUID()
    @ObservationIgnored private var webSequence = 0
    @ObservationIgnored private var callerReadOnly: Bool
    @ObservationIgnored private var draftReadOnly = false
    var openURL: ((URL) -> Void)?

    init(client: IMClient, message: ChatMessage, chat: ChatStore, readOnly: Bool) {
        self.client = client; self.message = message; self.chat = chat; self.chatEpoch = chat.interactionEpoch
        callerReadOnly = readOnly
        self.readOnly = readOnly || message.interactive?.read_only == true || message.interactive?.superseded_by != nil
    }
    var hasPending: Bool { chat.interactionAttempt(message.conversation_id, sourceMessageID: message.id) != nil }
    var usesWebRenderer: Bool { message.interactive?.catalog_version == "nano-iui-1" }
    var webID: UUID { rendererGeneration }
    var webDisabled: Bool { readOnly || busy || hasPending || conflict }
    var fallbackAttachmentIndexes: [Int] {
        let shown = Set(visibleAttachmentIndexes.map { message.attachments[$0].url })
        return message.attachments.indices.filter { !shown.contains(message.attachments[$0].url) }
    }

    func load(adoptingRemote: Bool = false) async {
        guard isCurrentStore else { return }
        left = false
        // Reactivation preserves an unresolved edit until the save path reconciles it.
        guard !loaded || saved == edited || (adoptingRemote && conflictColumns != nil) else { return }
        chat.interactionDrafts.register(self)
        let token = UUID(); generation = token; rendererGeneration = token
        resetAttachmentPresentation()
        sessionRevision = await client.session.revision()
        if !loaded { error = nil }
        do {
            guard let source = message.interactive, source.format == "openui", ["nano-1", "nano-iui-1"].contains(source.catalog_version) else {
                throw APIError(status: 422, detail: L("此交互回复版本暂不支持，请更新客户端或在聊天中要求重新发送。", "This interactive version is unsupported. Update the app or ask for a new reply in the chat."))
            }
            let draft = try await client.interactionDraft(message.conversation_id, messageID: message.id)
            guard token == generation, await current() else { return }
            try applyDraft(draft, source: source.source)
        } catch { if token == generation { self.error = error.localizedDescription } }
    }
    private func applyDraft(_ draft: InteractionDraft, source: String) throws {
        revision = draft.draft_revision; submitted = draft.submission_message_id != nil
        saved = edited; querySignatures = [:]; webSequence = 0
        // A GET may describe another device's edit. It must never advance our discard watermark.
        conflict = false; conflictColumns = nil; offlineFailure = false; error = nil
        chat.interactionDrafts.record(self, reason: nil)
        if usesWebRenderer {
            // An unavailable Agent still permits private edits, just as on Web.
            draftReadOnly = draft.read_only == true || draft.superseded_by != nil
            setReadOnly(callerReadOnly)
            state = draft.state; loaded = true
            return
        }
        guard let url = Bundle.main.url(forResource: "InteractiveRuntime", withExtension: "js"), let js = JSContext() else { throw URLError(.cannotDecodeContentData) }
        js.evaluateScript(try String(contentsOf: url, encoding: .utf8))
        if let exception = js.exception { throw runtimeError(exception.toString()) }
        let instance = js.objectForKeyedSubscript("NanoInteractive")?.invokeMethod("create", withArguments: [source, JSONValue.object(draft.state).foundationObject])
        if let exception = js.exception { throw runtimeError(exception.toString()) }
        guard let instance, !instance.isUndefined else { throw URLError(.cannotParseResponse) }
        context = js; engine = instance
        try receive(call("snapshot")); loaded = true
        refreshQueries(); pollQueries()
    }
    /// The bundled renderer supplies values, never credentials or arbitrary API access.
    func webRequest(_ request: JSONValue, generation token: UUID) async throws -> JSONValue {
        guard usesWebRenderer, loaded, await current(), !left, token == rendererGeneration else {
            throw runtimeError("This card session is no longer active")
        }
        let type = request["type"].stringValue ?? ""
        if type == "ready" {
            return .object(["source": .string(message.interactive?.source ?? ""), "state": .object(state), "disabled": .bool(webDisabled)])
        }
        if type == "error" { error = request["message"].stringValue; return .null }
        if ["attachment-image", "attachment-open", "attachment-visible"].contains(type) {
            return try await attachmentRequest(type, request, generation: token)
        }
        if let value = request["state"].objectValue, let sequence = request["sequence"].intValue,
           sequence > webSequence, !webDisabled {
            webSequence = sequence
            let different = state != value
            state = value
            if different && request["touched"].boolValue == true { changed() }
        }
        if type == "state" { return .null }
        if type == "resource" {
            guard let path = request["path"].stringValue, let parts = URLComponents(string: path),
                  parts.scheme == nil, parts.host == nil, parts.fragment == nil,
                  ["/im/v1/intelligent-ui/api/wiki", "/im/v1/intelligent-ui/api/image-search", "/im/v1/intelligent-ui/api/street-route"].contains(parts.path) else {
                throw runtimeError("This resource is not connected")
            }
            return try await client.get(parts.path, query: parts.queryItems ?? [])
        }
        let action = type == "action" ? request["event"] : .null
        let name = type == "tool" ? request["name"].stringValue : action["type"].stringValue
        let args = type == "tool" ? request["args"] : action["params"]
        if name == "conversation_messages", type == "tool" {
            let limit = max(1, min(100, args["limit"].intValue ?? 20))
            let page: MessagePage = try await client.get("/im/v1/conversations/\(message.conversation_id.pathComponent)/messages", query: [.init(name: "limit", value: String(limit))])
            return .array(page.items.compactMap(\.message).map { .object(["id": .string($0.id), "sender": .string($0.sender.display_name ?? $0.sender.id), "content": .string($0.content), "delivery_status": .string($0.delivery_status)]) })
        }
        guard !webDisabled else { throw runtimeError("This card cannot perform actions right now") }
        if name == "open_url" {
            guard let text = args["url"].stringValue, let url = URL(string: text), ["https", "http"].contains(url.scheme?.lowercased() ?? "") else { throw runtimeError("This link cannot be opened") }
            openURL?(url); return .null
        }
        if name == "CopyToClipboard" {
            guard let text = args["text"].stringValue else { throw runtimeError("text required") }
            UIPasteboard.general.string = text; return .bool(true)
        }
        guard ["ComposeMessage", "SendToChat", "continue_conversation"].contains(name ?? "") else { throw runtimeError("This action is not connected") }
        busy = true; composing = name == "ComposeMessage"; error = nil
        // Busy serializes actions across reloads; replacing a page must not strand its owner.
        defer { busy = false; composing = false }
        await flush()
        guard token == rendererGeneration, await current(), !readOnly, !conflict, saved == edited else { throw runtimeError("Load the latest card before continuing") }
        if name == "ComposeMessage" {
            guard let target = args["target"].stringValue, let text = args["text"].stringValue else { throw runtimeError("target and text required") }
            try await compose(target, text: text); return .null
        }
        guard let text = type == "tool" || name == "SendToChat" ? args["message"].stringValue : action["humanFriendlyMessage"].stringValue else { throw runtimeError("message required") }
        var details: [String: JSONValue] = ["type": .string("continue_conversation"), "message": .string(text), "label": request["label"].stringValue.map(JSONValue.string) ?? .string(L("发送到聊天", "Send to chat"))]
        if args["context"] != .null { details["context"] = args["context"] }
        if let form = action["formName"].stringValue { details["form_name"] = .string(form) }
        var submittedState = state
        if let form = action["formState"].objectValue { submittedState.merge(form) { _, new in new } }
        let receipt = try await chat.submitInteraction(message.conversation_id,
            input: InteractionReplyInput(source_message_id: message.id, event: .object(details), state: submittedState), key: UUID().uuidString)
        guard token == rendererGeneration, await current() else { throw runtimeError("This card session is no longer active") }
        submitted = true; saved = edited
        await syncRevision()
        return .object(["message_id": .string(receipt.id), "delivery_status": .string(receipt.delivery_status)])
    }
    /// Card media uses the current message and native credentials, even in read-only history.
    private func attachmentRequest(_ type: String, _ request: JSONValue, generation token: UUID) async throws -> JSONValue {
        guard let value = request["index"].doubleValue, let position = Int(exactly: value),
              position > 0, position <= message.attachments.count else {
            throw runtimeError("This image is not attached to the message")
        }
        let index = position - 1
        let attachment = message.attachments[index]
        let imageTypes = ["image/png", "image/jpeg", "image/webp", "image/gif"]
        let url = try ServerOrigin.resource(attachment.url, base: client.baseURL)
        let path = url.pathComponents
        guard imageTypes.contains(attachment.content_type ?? ""),
              url.query == nil, url.fragment == nil, path.count == 7,
              Array(path.prefix(5)) == ["/", "im", "v1", "conversations", message.conversation_id],
              ["images", "attachments"].contains(path[5]) else {
            throw runtimeError("This image is not attached to the message")
        }
        if type == "attachment-visible" {
            guard let visible = request["visible"].boolValue else { throw runtimeError("Image visibility is required") }
            if visible { visibleAttachmentIndexes.insert(index) } else { visibleAttachmentIndexes.remove(index) }
            return .null
        }
        let (data, mime) = try await client.protectedResource(attachment.url)
        guard await current(), !left, loaded, token == rendererGeneration else {
            throw runtimeError("This card session is no longer active")
        }
        guard imageTypes.contains(mime) else { throw URLError(.cannotDecodeContentData) }
        if type == "attachment-open" {
            guard let image = UIImage(data: data) else { throw URLError(.cannotDecodeContentData) }
            attachmentPreview = image
            return .null
        }
        return .object(["data": .string(data.base64EncodedString()), "mime": .string(mime)])
    }

    func resetAttachmentPresentation() {
        visibleAttachmentIndexes.removeAll()
        attachmentPreview = nil
    }

    func setReadOnly(_ value: Bool) {
        callerReadOnly = value
        readOnly = value || draftReadOnly || message.interactive?.read_only == true || message.interactive?.superseded_by != nil
        if readOnly { saveTimer?.cancel() }
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
            let token = generation, renderer = rendererGeneration
            Task {
                defer { if token == generation { busy = false; composing = false } }
                do {
                    if business { await flush(); guard !conflict, saved == edited, token == generation, renderer == rendererGeneration, await current() else { return } }
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
                            let label = node["props"]["label"].stringValue ?? node["props"]["name"].stringValue ?? L("发送到聊天", "Send to chat")
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
    @discardableResult
    func flush(through limit: Int? = nil) async -> DraftFlushResult {
        saveTimer?.cancel()
        let autoSync = !chat.isGroupConversation(message.conversation_id)
        if let saveFlight {
            let id = saveFlightID
            await saveFlight.value
            if saveFlightID == id { self.saveFlight = nil }
            // An old leave-flight may finish after this conversation became active again.
            // Flush the new edit, but never include it in that departure's cutoff.
            if error == nil, saved != edited, !conflict, !readOnly,
               limit == nil || edited <= limit! { return await flush(through: limit) }
            return flushResult
        }
        guard loaded, !readOnly, (!conflict || autoSync), !hasPending, edited != saved,
              limit == nil || edited <= limit! else { return flushResult }
        let token = generation
        let flight = Task { [self] in
            while token == generation, !readOnly, !hasPending, saved != edited,
                  limit == nil || edited <= limit!, await current() {
                if conflict {
                    guard autoSync, let source = message.interactive?.source else { return }
                    do {
                        let draft = try await client.interactionDraft(message.conversation_id, messageID: message.id)
                        guard token == generation, await current(), !hasPending else { return }
                        // A stale renderer must not submit its old form after adopting the server draft.
                        try applyDraft(draft, source: source)
                        rendererGeneration = UUID()
                    } catch { /* The next send or reconnect retries the read, not the stale write. */ }
                    return
                }
                let serial = edited, value = state
                do {
                    let result = try await client.saveInteractionDraft(message.conversation_id, messageID: message.id, revision: revision, state: value)
                    guard token == generation, await current() else { return }
                    revision = result.draft_revision; saved = serial; error = nil; offlineFailure = false
                    if let updatedAt = result.updated_at, let sessionRevision {
                        lastConfirmedUpdate = max(lastConfirmedUpdate ?? "", updatedAt)
                        await chat.interactionDrafts.noteSaved(self, serial: serial, updatedAt: updatedAt, revision: sessionRevision)
                    }
                    guard token == generation, await current() else { return }
                    if saved == edited { chat.interactionDrafts.record(self, reason: nil) }
                } catch {
                    guard token == generation, await current() else { return }
                    conflict = (error as? APIError)?.status == 409
                    offlineFailure = [-1009, -1005, -1004].contains((error as? URLError)?.errorCode ?? 0)
                    if !autoSync {
                        self.error = conflict ? L("其他设备已更新这张卡片，请查看最新改动后决定是否放弃本机编辑。", "This card changed on another device. Compare drafts before discarding your local edits.") : error.localizedDescription
                    }
                    chat.interactionDrafts.record(self, reason: conflict ? .conflict : .transient, offline: offlineFailure)
                    if autoSync, conflict { continue }
                    return
                }
            }
        }
        let id = UUID(); saveFlightID = id; saveFlight = flight
        await flight.value
        if saveFlightID == id { saveFlight = nil }
        return flushResult
    }
    private var flushResult: DraftFlushResult {
        DraftFlushResult(updatedAt: lastConfirmedUpdate, reason: conflict ? .conflict : (loaded && !readOnly && saved != edited ? .transient : nil))
    }
    func leave() {
        left = true; rendererGeneration = UUID(); webSequence = 0
        resetAttachmentPresentation()
        saveTimer?.cancel(); queryTask?.cancel(); queryPoll?.cancel()
        // Row recycling is not a conversation switch. The store owns discard ordering.
        Task {
            let result = await flush()
            if result.reason != nil { chat.interactionDrafts.retainUnresolved(self) }
        }
    }
    func retrySaving() async {
        // A save started before the tap may still return its old failure.
        if saveFlight != nil { _ = await flush() }
        if flushResult.reason == .transient || (conflict && !chat.isGroupConversation(message.conversation_id)) { _ = await flush() }
    }
    func retryContent() async {
        if !loaded || (usesWebRenderer && edited == saved) { await load() }
        else if !conflict { error = nil; querySignatures = [:]; refreshQueries(); await retrySaving() }
    }
    /// Reads a comparison without applying the remote revision or changing either draft.
    func describeConflict() async throws -> [DraftConflictColumn] {
        inspectingConflict = true
        defer { inspectingConflict = false }
        let draft = try await client.interactionDraft(message.conversation_id, messageID: message.id)
        guard await current() else { throw CancellationError() }
        let columns = (draft.fields ?? []).compactMap { field -> DraftConflictColumn? in
            let local = state[field.name] ?? .null
            guard local != field.value else { return nil }
            return DraftConflictColumn(name: field.name, label: field.label,
                remote: field.display_value ?? readable(field.value, options: field.options),
                local: readable(local, options: field.options))
        }
        conflictColumns = columns
        return columns
    }
    /// Only explicit adoption after comparison may replace a conflicting local draft.
    @discardableResult
    func adoptRemote() async -> Bool {
        guard conflictColumns != nil else { return false }
        await load(adoptingRemote: true)
        return !conflict && saved == edited
    }
    private func readable(_ value: JSONValue, options: [InteractionDraftFieldOption]?) -> String {
        if let array = value.arrayValue { return array.map { readable($0, options: options) }.joined(separator: "、") }
        if let text = value.stringValue { return options?.first { $0.value == text }?.label ?? text }
        if let flag = value.boolValue { return flag ? L("是", "Yes") : L("否", "No") }
        return value == .null ? "—" : value.prettyPrinted
    }
    private func changed() {
        guard !readOnly else { return }
        edited += 1; submitted = false; conflictColumns = nil
        saveTimer?.cancel()
        saveTimer = Task { try? await Task.sleep(for: .milliseconds(500)); if !Task.isCancelled { _ = await flush() } }
    }
    private func syncRevision() async {
        do {
            let draft = try await client.interactionDraft(message.conversation_id, messageID: message.id)
            guard await current() else { return }; revision = draft.draft_revision
        } catch { self.error = error.localizedDescription }
    }
    private func current() async -> Bool {
        guard isCurrentStore, let sessionRevision, await client.session.revision() == sessionRevision,
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
