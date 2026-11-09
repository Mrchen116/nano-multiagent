import XCTest
@testable import NanoIM

@MainActor
final class InteractionDraftLifecycleTests: XCTestCase {
    private let t1 = "2026-11-01T10:00:00.001Z"
    private let t2 = "2026-11-01T10:00:00.002Z"
    private let t3 = "2026-11-01T10:00:00.003Z"

    func testComposerConflictUsesReadableComparisonAndExplicitAdoptionBeforeSending() async throws {
        let (runtime, transport) = try await fixture()
        let chat = runtime.chat
        await transport.setRemote("thu", updatedAt: t3)
        await transport.setStatus(409)
        try await edit(runtime, "fri")
        chat.drafts["chat"] = "keep the question"
        await chat.send("chat")
        let blockedPosts = await transport.posts
        XCTAssertTrue(blockedPosts.isEmpty)
        XCTAssertEqual(chat.interactionDrafts.failure("chat")?.reason, .conflict)
        XCTAssertEqual(runtime.state["$slot"], .string("fri"))
        XCTAssertEqual(chat.drafts["chat"], "keep the question")
        await runtime.adoptRemote() // Adoption is unavailable until a successful comparison.
        XCTAssertEqual(runtime.state["$slot"], .string("fri"))
        let columns = try await runtime.describeConflict()
        XCTAssertEqual(columns, [DraftConflictColumn(name: "$slot", label: "会议时间", remote: "周四 14:00", local: "周五 15:00")])
        XCTAssertEqual(runtime.state["$slot"], .string("fri"))
        XCTAssertEqual(chat.drafts["chat"], "keep the question")
        XCTAssertTrue(chat.interactionDrafts.watermarks.isEmpty, "Reading another device's draft does not own its discard watermark")
        await transport.setStatus(200)
        await runtime.adoptRemote()
        XCTAssertNil(chat.interactionDrafts.failure("chat"))
        XCTAssertNil(chat.errors["chat"])
        XCTAssertEqual(runtime.state["$slot"], .string("thu"))
        await chat.send("chat")
        let posts = await transport.posts
        XCTAssertEqual(posts.count, 1)
        XCTAssertNil(posts.first?.objectValue?["interaction_contexts"])
        chat.clear()
    }

    func testComposerFreezesOriginalTextBeforeWaitingForDraftFlush() async throws {
        let (runtime, transport) = try await fixture()
        await transport.gateNextSave(timestamp: t1)
        try await edit(runtime, "thu")
        runtime.chat.drafts["chat"] = "original question"
        let send = Task { await runtime.chat.send("chat") }
        let started = await transport.waitForGatedSave(); XCTAssertTrue(started)
        runtime.chat.drafts["chat"] = "new draft typed while saving"
        await transport.releaseSave(); await send.value
        let posts = await transport.posts
        XCTAssertEqual(posts.first?["content"], .string("original question"))
        XCTAssertEqual(runtime.chat.drafts["chat"], "new draft typed while saving")
        runtime.chat.clear()
    }

    func testFailedRemoteAdoptionDoesNotClearConflictOrReleaseSending() async throws {
        let (runtime, transport) = try await fixture()
        await transport.setStatus(409)
        try await edit(runtime, "fri")
        runtime.chat.drafts["chat"] = "do not send"
        await runtime.chat.send("chat")
        _ = try await runtime.describeConflict()
        await transport.setReadStatus(503)
        await runtime.adoptRemote()
        XCTAssertTrue(runtime.conflict)
        XCTAssertEqual(runtime.state["$slot"], .string("fri"))
        XCTAssertNotNil(runtime.chat.interactionDrafts.failure("chat"))
        await runtime.chat.send("chat")
        let posts = await transport.posts
        XCTAssertTrue(posts.isEmpty)
        XCTAssertEqual(runtime.chat.drafts["chat"], "do not send")
        runtime.chat.clear()
    }

    func testTransientComposerFailureRetainsBothDraftsAndRetrySavingUnblocksConversation() async throws {
        let (runtime, transport) = try await fixture()
        await transport.setStatus(503)
        try await edit(runtime, "fri")
        runtime.chat.drafts["chat"] = "unrelated follow-up"
        await runtime.chat.send("chat")
        let blocked = await transport.posts
        XCTAssertTrue(blocked.isEmpty)
        XCTAssertEqual(runtime.chat.interactionDrafts.failure("chat")?.reason, .transient)
        XCTAssertEqual(runtime.chat.drafts["chat"], "unrelated follow-up")
        XCTAssertEqual(runtime.state["$slot"], .string("fri"))
        await transport.setStatus(200)
        _ = await runtime.flush()
        XCTAssertNil(runtime.chat.interactionDrafts.failure("chat"))
        XCTAssertNil(runtime.chat.errors["chat"])
        await runtime.chat.send("chat")
        let posts = await transport.posts, events = await transport.events
        XCTAssertEqual(posts.count, 1)
        XCTAssertEqual(events.suffix(2), ["saved:card", "send"])
        runtime.chat.clear()
    }

    func testLeaveFlushesBeforeDiscardAndRestoresOwnedMaximumAcrossStoreRecreation() async throws {
        let (runtime, transport) = try await fixture()
        await transport.setTimestamp(t2)
        try await edit(runtime, "thu")
        runtime.chat.selectedID = "other"
        await runtime.chat.interactionDrafts.awaitPendingDiscard("chat")
        let events = await transport.events, through = await transport.discards
        XCTAssertEqual(events, ["put:card", "saved:card", "discard:\(t2)"])
        XCTAssertEqual(through, [t2])
        runtime.chat.selectedID = "chat"
        await transport.setTimestamp(t1)
        try await edit(runtime, "fri")
        _ = await runtime.flush()
        XCTAssertEqual(runtime.chat.interactionDrafts.watermarks["chat"], t2)
        let reopened = ChatStore(client: runtime.client, user: runtime.chat.user)
        XCTAssertTrue(reopened.interactionDrafts.watermarks.isEmpty, "Constructing the first-paint store must not synchronously load the card ledger")
        await reopened.interactionDrafts.foreground(activeConversation: nil)
        XCTAssertEqual(reopened.interactionDrafts.watermarks["chat"], t2)
        reopened.selectedID = "chat"; reopened.selectedID = "other"
        await reopened.interactionDrafts.awaitPendingDiscard("chat")
        let all = await transport.discards
        XCTAssertEqual(all, [t2, t2])
        reopened.clear(); runtime.chat.clear()
    }

    func testFailedLeaveUsesOnlyPreviouslyConfirmedWatermark() async throws {
        let (runtime, transport) = try await fixture()
        await transport.setTimestamp(t1)
        try await edit(runtime, "thu"); _ = await runtime.flush()
        await transport.setStatus(503)
        try await edit(runtime, "fri")
        runtime.chat.selectedID = "other"
        await runtime.chat.interactionDrafts.awaitPendingDiscard("chat")
        let through = await transport.discards
        XCTAssertEqual(through, [t1])
        XCTAssertEqual(runtime.state["$slot"], .string("fri"))
        runtime.chat.clear()
    }

    func testTimedOutLeaveDoesNotCancelPutAndLateSuccessRediscardsOnlyThatEdit() async throws {
        let (runtime, transport) = try await fixture()
        await transport.setTimestamp(t1)
        try await edit(runtime, "thu"); _ = await runtime.flush()
        runtime.chat.interactionDrafts.leaveTimeout = .milliseconds(20)
        await transport.gateNextSave(timestamp: t2)
        try await edit(runtime, "fri")
        runtime.chat.selectedID = "other"
        let started = await transport.waitForGatedSave(); XCTAssertTrue(started)
        await runtime.chat.interactionDrafts.awaitPendingDiscard("chat")
        let baseline = await transport.discards
        XCTAssertEqual(baseline, [t1], "The bounded wait must return while PUT is still in flight")
        runtime.chat.selectedID = "chat"
        try await edit(runtime, "wed") // This future active edit must not be included in the old departure.
        await transport.releaseSave()
        let received = await transport.waitForDiscards(2); XCTAssertTrue(received, "The late successful PUT must be re-discarded")
        let late = await transport.discards
        XCTAssertEqual(late, [t1, t2], "A late acknowledgement must trigger the second bounded discard")
        await transport.setTimestamp(t3)
        _ = await runtime.flush()
        await runtime.chat.interactionDrafts.awaitPendingDiscard("chat")
        let active = await transport.discards
        XCTAssertEqual(active, [t1, t2], "Returning and editing again must not clear that new edit")
        XCTAssertEqual(runtime.chat.interactionDrafts.watermarks["chat"], t3)
        runtime.chat.selectedID = "other"
        await runtime.chat.interactionDrafts.awaitPendingDiscard("chat")
        let final = await transport.discards
        XCTAssertEqual(final.last, t3)
        runtime.chat.clear()
    }

    func testObservedOtherDeviceDraftNeverAdvancesOrCreatesDiscardOwnership() async throws {
        let (runtime, transport) = try await fixture()
        await transport.setRemote("thu", updatedAt: t3)
        await runtime.load()
        runtime.chat.selectedID = "other"
        await runtime.chat.interactionDrafts.awaitPendingDiscard("chat")
        let unowned = await transport.discards
        XCTAssertTrue(unowned.isEmpty)
        runtime.chat.selectedID = "chat"
        await transport.setTimestamp(t1)
        try await edit(runtime, "fri"); _ = await runtime.flush()
        await transport.setRemote("thu", updatedAt: t3)
        await runtime.load()
        let afterRead = await transport.discards
        XCTAssertTrue(afterRead.isEmpty)
        XCTAssertEqual(runtime.chat.interactionDrafts.watermarks["chat"], t1)
        runtime.chat.selectedID = "other"
        await runtime.chat.interactionDrafts.awaitPendingDiscard("chat")
        let owned = await transport.discards
        XCTAssertEqual(owned, [t1], "Never clear the observed, newer other-device watermark")
        runtime.chat.clear()
    }

    func testDiscard404And501AreSilentAndDoNotBlockOrdinarySending() async throws {
        for status in [404, 501] {
            let (runtime, transport) = try await fixture()
            try await edit(runtime, "thu"); _ = await runtime.flush()
            await transport.setDiscardStatus(status)
            runtime.chat.selectedID = "other"
            await runtime.chat.interactionDrafts.awaitPendingDiscard("chat")
            runtime.chat.selectedID = "chat"
            runtime.chat.drafts["chat"] = "still send"
            await runtime.chat.send("chat")
            let posts = await transport.posts
            XCTAssertEqual(posts.count, 1)
            XCTAssertNil(runtime.chat.errors["chat"])
            XCTAssertNotNil(runtime.chat.interactionDrafts.watermarks["chat"])
            runtime.chat.clear()
        }
    }

    func testOutOfOrderResponsesFromTwoCardsKeepTheMaximumDiscardWatermark() async throws {
        let (first, transport) = try await fixture()
        await transport.gateNextSave(timestamp: t1)
        try await edit(first, "thu")
        let slow = Task { await first.flush() }
        let started = await transport.waitForGatedSave(); XCTAssertTrue(started)
        var message = first.message; message.id = "second-card"
        let second = InteractiveRuntime(client: first.client, message: message, chat: first.chat, readOnly: false)
        await second.load(); await transport.setTimestamp(t2)
        try await edit(second, "fri"); _ = await second.flush()
        await transport.releaseSave(); _ = await slow.value
        XCTAssertEqual(first.chat.interactionDrafts.watermarks["chat"], t2)
        first.chat.selectedID = "other"
        await first.chat.interactionDrafts.awaitPendingDiscard("chat")
        let through = await transport.discards
        XCTAssertEqual(through, [t2])
        first.chat.clear()
    }

    func testClearingStoreFencesWaitingComposerAndLateDraftAcknowledgementsWithoutRecreatingPrivateState() async throws {
        let (runtime, transport) = try await fixture(); await transport.gateNextSave(timestamp: t2)
        try await edit(runtime, "thu")
        runtime.chat.drafts["chat"] = "old question awaiting card save"
        let save = Task { await runtime.chat.send("chat") }
        let started = await transport.waitForGatedSave(); XCTAssertTrue(started)
        runtime.chat.clear()
        await transport.releaseSave(); _ = await save.value
        let posts = await transport.posts; XCTAssertTrue(posts.isEmpty, "A cleared store must not resume its waiting composer send")
        XCTAssertTrue(runtime.chat.interactionDrafts.watermarks.isEmpty)
        XCTAssertTrue(runtime.chat.interactionDrafts.failures.isEmpty)
        XCTAssertTrue(try runtime.client.session.sendAttempts.loadDraftWatermarks(origin: runtime.client.baseURL, userID: "viewer").isEmpty)
    }

    func testGroupDraftFailureCannotBlockOrAttachToAnOrdinaryMessage() async throws {
        let (runtime, transport) = try await fixture()
        runtime.chat.conversations[0].type = "group"
        await transport.setStatus(503)
        try await edit(runtime, "fri"); _ = await runtime.flush()
        runtime.chat.drafts["chat"] = "public text only"
        await runtime.chat.send("chat")
        let posts = await transport.posts
        XCTAssertEqual(posts.count, 1)
        XCTAssertNil(posts.first?.objectValue?["interaction_contexts"])
        runtime.chat.clear()
    }

    func testDurableWatermarksAreCappedAccountAndServiceIsolatedAndRemovedOnLogout() async throws {
        let (runtime, _) = try await fixture()
        let disk = runtime.client.session.sendAttempts, origin = runtime.client.baseURL
        for index in 0..<130 {
            _ = try disk.noteDraftSaved("chat-\(index)", updatedAt: String(format: "2026-11-01T10:00:00.%03dZ", index), origin: origin, userID: "viewer")
        }
        let values = try disk.loadDraftWatermarks(origin: origin, userID: "viewer")
        XCTAssertEqual(values.count, 128)
        XCTAssertNil(values["chat-0"]); XCTAssertNil(values["chat-1"])
        _ = try disk.noteDraftSaved("chat-129", updatedAt: t1, origin: origin, userID: "viewer")
        XCTAssertEqual(try disk.loadDraftWatermarks(origin: origin, userID: "viewer")["chat-129"], values["chat-129"])
        XCTAssertTrue(try disk.loadDraftWatermarks(origin: origin, userID: "other").isEmpty)
        XCTAssertTrue(try disk.loadDraftWatermarks(origin: URL(string: "https://other.example.test")!, userID: "viewer").isEmpty)
        try disk.remove(origin: origin, userID: "viewer", conversationID: "chat-129")
        XCTAssertNil(try disk.loadDraftWatermarks(origin: origin, userID: "viewer")["chat-129"])
        _ = await runtime.client.session.signOut()
        XCTAssertTrue(try disk.loadDraftWatermarks(origin: origin, userID: "viewer").isEmpty)
        runtime.chat.clear()
    }

    func testForegroundRetriesOnlyAnExplicitLeaveIntentNotEverySavedDraft() async throws {
        let (runtime, transport) = try await fixture()
        try await edit(runtime, "thu"); _ = await runtime.flush()
        let reopened = ChatStore(client: runtime.client, user: runtime.chat.user)
        await reopened.interactionDrafts.foreground(activeConversation: nil)
        let untouched = await transport.discards
        XCTAssertTrue(untouched.isEmpty, "Restart alone must preserve a saved, unsent draft")
        await transport.setDiscardStatus(503)
        runtime.chat.selectedID = "other"
        await runtime.chat.interactionDrafts.awaitPendingDiscard("chat")
        let before = await transport.discards
        XCTAssertEqual(before, [t1])
        runtime.chat.selectedID = "chat"
        await transport.setTimestamp(t2)
        try await edit(runtime, "fri"); _ = await runtime.flush()
        XCTAssertEqual(runtime.chat.interactionDrafts.watermarks["chat"], t2)
        let retry = ChatStore(client: runtime.client, user: runtime.chat.user)
        await transport.setDiscardStatus(200)
        await retry.interactionDrafts.foreground(activeConversation: "chat")
        let retried = await transport.discards
        XCTAssertEqual(retried, [t1, t1], "A failed explicit leave survives process recreation")
        let confirmed = ChatStore(client: runtime.client, user: runtime.chat.user)
        await confirmed.interactionDrafts.foreground(activeConversation: nil)
        let done = await transport.discards
        XCTAssertEqual(done, retried, "A confirmed discard must not become a fresh discard on every launch")
        runtime.chat.clear(); reopened.clear(); retry.clear(); confirmed.clear()
    }

    func edit(_ runtime: InteractiveRuntime, _ slot: String) async throws {
        let sequence = runtime.editSerial + 1
        _ = try await runtime.webRequest(.object(["type": .string("state"), "sequence": .number(Double(sequence)), "touched": .bool(true), "state": .object(["$slot": .string(slot)])]), generation: runtime.webID)
    }
    func fixture(wrapping wrap: ((DraftLifecycleTransport) -> any HTTPTransport)? = nil) async throws -> (InteractiveRuntime, DraftLifecycleTransport) {
        let user = AuthUser(id: "viewer", username: "viewer", display_name: "Viewer", owner_id: "viewer", locale: "zh", membership_status: "active", is_company_admin: false, owned_node_ids: [], created_at: "now")
        let transport = DraftLifecycleTransport(pair: try JSONEncoder().encode(TokenPair(access_token: "t", refresh_token: "r", user: user)))
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        let session = Session(baseURL: URL(string: "https://draft.example.test")!, transport: wrap?(transport) ?? transport, credentials: DraftLifecycleCredentials(), sendAttempts: SendAttemptStore(directory: directory))
        _ = try await session.login(username: "viewer", password: "test")
        let client = IMClient(baseURL: session.baseURL, session: session), chat = ChatStore(client: IMClient(baseURL: session.baseURL, session: session), user: user)
        await chat.loadConversations(); chat.selectedID = "chat"
        var message = try JSONDecoder().decode(ChatMessage.self, from: transport.message)
        message.id = "card"
        message.interactive = MessageInteractive(format: "openui", catalog_version: "nano-iui-1", source: "$slot = \"wed\"\nroot = Text($slot)")
        let runtime = InteractiveRuntime(client: client, message: message, chat: chat, readOnly: false)
        await runtime.load()
        return (runtime, transport)
    }
}

private final class DraftLifecycleCredentials: CredentialStore, @unchecked Sendable {
    private var stored: StoredSession?
    func load() throws -> StoredSession? { stored }
    func save(_ value: StoredSession) throws { stored = value }
    func remove() throws { stored = nil }
}

actor DraftLifecycleTransport: HTTPTransport {
    let pair: Data
    nonisolated let message = Data(#"{"id":"sent","conversation_id":"chat","sender":{"type":"user","id":"viewer"},"sender_user_id":"viewer","sender_type":"user","content":"安排会议","attachments":[],"delivery_status":"pending","created_at":"now"}"#.utf8)
    var posts: [JSONValue] = []
    var events: [String] = []
    var discards: [String] = []
    private var state: [String: JSONValue] = ["$slot": .string("wed")]
    private var revision = 0, status = 200, readStatus = 200, discardStatus = 200
    private var timestamp = "2026-11-01T10:00:00.001Z"
    private var observedTimestamp: String?
    private var gated = false, gateStarted = false
    private var saveRelease: CheckedContinuation<Void, Never>?
    private var saveStart: CheckedContinuation<Bool, Never>?
    private var discardWait: (Int, CheckedContinuation<Bool, Never>)?
    init(pair: Data) { self.pair = pair }
    func setStatus(_ value: Int) { status = value }
    func setReadStatus(_ value: Int) { readStatus = value }
    func setTimestamp(_ value: String) { timestamp = value }
    func setRemote(_ slot: String, updatedAt: String) { state = ["$slot": .string(slot)]; observedTimestamp = updatedAt; revision += 1 }
    func setDiscardStatus(_ value: Int) { discardStatus = value }
    func gateNextSave(timestamp value: String) { gated = true; timestamp = value }
    func waitForGatedSave() async -> Bool {
        if gateStarted { return true }
        return await withCheckedContinuation { continuation in
            saveStart = continuation
            Task { try? await Task.sleep(for: .seconds(2)); saveStart?.resume(returning: false); saveStart = nil }
        }
    }
    func releaseSave() { saveRelease?.resume(); saveRelease = nil }
    func waitForDiscards(_ count: Int) async -> Bool {
        if discards.count >= count { return true }
        return await withCheckedContinuation { continuation in
            discardWait = (count, continuation)
            Task { try? await Task.sleep(for: .seconds(2)); discardWait?.1.resume(returning: false); discardWait = nil }
        }
    }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let path = request.url!.path
        var code = 200, data = Data("{}".utf8)
        if path.contains("/auth/") { data = pair }
        else if path.hasSuffix("/interaction-state") {
            if request.httpMethod == "GET" { code = readStatus }
            if request.httpMethod == "PUT" {
                events.append("put:card")
                code = status
                let value = try JSONDecoder().decode(JSONValue.self, from: request.httpBody!)["state"].objectValue!
                let at = timestamp
                if gated {
                    gated = false
                    await withCheckedContinuation { saveRelease = $0; gateStarted = true; saveStart?.resume(returning: true); saveStart = nil }
                }
                if code == 200 { state = value; revision += 1; observedTimestamp = at; events.append("saved:card") }
            }
            let options = ["wed": "周三 13:00", "thu": "周四 14:00", "fri": "周五 15:00"]
            let slot = state["$slot"]?.stringValue ?? "wed"
            data = try JSONEncoder().encode(InteractionDraft(can_interact: true, draft_revision: revision, updated_at: observedTimestamp, state: state,
                fields: [InteractionDraftField(name: "$slot", label: "会议时间", value: .string(slot), display_value: options[slot], options: options.map { .init(label: $0.value, value: $0.key) })]))
        } else if path.hasSuffix("/interaction-background/discard") {
            let at = try JSONDecoder().decode(JSONValue.self, from: request.httpBody!)["through"].stringValue!
            discards.append(at); events.append("discard:\(at)"); code = discardStatus
            if let (count, continuation) = discardWait, discards.count >= count { discardWait = nil; continuation.resume(returning: true) }
        } else if path.hasSuffix("/messages") && request.httpMethod == "POST" {
            posts.append(try JSONDecoder().decode(JSONValue.self, from: request.httpBody!)); events.append("send"); data = message
        } else if path.hasSuffix("/messages") { data = Data(#"{"items":[]}"#.utf8) }
        else if path == "/im/v1/conversations" { data = Data(#"{"items":[{"id":"chat","title":"Chat","participants":[],"participant_ids":["viewer"],"type":"direct","owner_id":"viewer","creator_id":"viewer","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now","can_write":true}]}"#.utf8) }
        else { code = 404 }
        return (data, HTTPURLResponse(url: request.url!, statusCode: code, httpVersion: nil, headerFields: nil)!)
    }
}
