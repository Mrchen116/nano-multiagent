import XCTest
@testable import NanoIM

@MainActor
final class InteractiveRuntimeTests: XCTestCase {
    private let source = """
    $minutes = "20"
    root = Stack([FormControl("每天阅读", Input("minutes", "", "number", {required:true}, $minutes)), TextContent(($minutes * 7) + " 分钟"), Button("安排阅读", Action([@Set($minutes, "30"), @ToAssistant("制定计划", {kind:"reading"})]))])
    """

    func testNativeBindingAndContinuationUseCurrentStateAndAuthenticatedTransport() async throws {
        let (runtime, transport) = try await makeRuntime()
        await runtime.load()
        XCTAssertTrue(runtime.loaded, runtime.error ?? "not loaded")
        runtime.edit(try XCTUnwrap(find("Input", runtime.root)), form: nil, value: .string("35"))
        XCTAssertEqual(runtime.state["$minutes"], .string("35"))
        XCTAssertTrue(runtime.root.prettyPrinted.contains("245 分钟"))
        await runtime.flush()
        runtime.activate(try XCTUnwrap(find("Button", runtime.root)), form: nil)
        for _ in 0..<100 where runtime.busy { try await Task.sleep(for: .milliseconds(10)) }
        XCTAssertFalse(runtime.busy)
        XCTAssertTrue(runtime.submitted, runtime.error ?? "not submitted")
        let sends = await transport.sends
        XCTAssertEqual(sends.count, 1)
        XCTAssertEqual(sends[0]["interaction_reply"]["state"]["$minutes"], .string("30"))
        XCTAssertEqual(sends[0]["interaction_reply"]["event"]["message"], .string("制定计划"))
        XCTAssertEqual(sends[0]["interaction_reply"]["event"]["label"], .string("安排阅读"))
        XCTAssertEqual(sends[0]["interaction_reply"]["event"]["context"], .object(["kind": .string("reading")]))
        runtime.leave()
    }

    func testConflictKeepsLocalEditUntilExplicitlyLoadingLatest() async throws {
        let (runtime, transport) = try await makeRuntime()
        await runtime.load()
        await transport.setConflict(true)
        runtime.edit(try XCTUnwrap(find("Input", runtime.root)), form: nil, value: .string("45"))
        await runtime.flush()
        XCTAssertTrue(runtime.conflict)
        XCTAssertEqual(runtime.state["$minutes"], .string("45"))
        await runtime.flush()
        let puts = await transport.puts
        XCTAssertEqual(puts, 1)
        await transport.setConflict(false)
        await runtime.load()
        XCTAssertFalse(runtime.conflict)
        XCTAssertEqual(runtime.state["$minutes"], .string("20"))
        runtime.leave()
    }

    func testReadOnlyExplorationDoesNotSaveOrSubmit() async throws {
        let (runtime, transport) = try await makeRuntime(readOnly: true)
        await runtime.load()
        runtime.edit(try XCTUnwrap(find("Input", runtime.root)), form: nil, value: .string("40"))
        XCTAssertTrue(runtime.root.prettyPrinted.contains("280 分钟"))
        runtime.activate(try XCTUnwrap(find("Button", runtime.root)), form: nil)
        await runtime.flush()
        let puts = await transport.puts, sends = await transport.sends
        XCTAssertEqual(puts, 0)
        XCTAssertTrue(sends.isEmpty)
        XCTAssertNotNil(runtime.error)
        runtime.leave()
    }

    func testLogoutFencesAnExistingCardFromSavingOrContinuing() async throws {
        let (runtime, transport) = try await makeRuntime()
        await runtime.load()
        _ = await runtime.client.session.signOut()
        runtime.edit(try XCTUnwrap(find("Input", runtime.root)), form: nil, value: .string("50"))
        await runtime.flush()
        runtime.activate(try XCTUnwrap(find("Button", runtime.root)), form: nil)
        for _ in 0..<100 where runtime.busy { try await Task.sleep(for: .milliseconds(10)) }
        let puts = await transport.puts, sends = await transport.sends
        XCTAssertEqual(puts, 0)
        XCTAssertTrue(sends.isEmpty)
        runtime.leave()
    }

    func testComposeUsesEditedValueAndRequiresExplicitReplacementWithoutSending() async throws {
        let source = "$draft = \"Initial\"\nroot = Stack([TextArea(\"body\", \"\", 4, null, $draft), Button(\"Adopt\", @ComposeMessage(\"chat\", $draft))])"
        let (runtime, transport) = try await makeRuntime(source: source)
        await runtime.load()
        runtime.chat.drafts["chat"] = "Existing"
        runtime.chat.attachments["chat"] = [ChatAttachment(url: "/old.png")]
        runtime.edit(try XCTUnwrap(find("TextArea", runtime.root)), form: nil, value: .string("Edited"))
        runtime.activate(try XCTUnwrap(find("Button", runtime.root)), form: nil)
        for _ in 0..<100 where runtime.busy { try await Task.sleep(for: .milliseconds(10)) }
        let request = try XCTUnwrap(runtime.pendingCompose, runtime.error ?? "Expected replacement choice")
        XCTAssertEqual(runtime.chat.drafts["chat"], "Existing")
        XCTAssertEqual(runtime.state["$draft"], .string("Edited"))
        // Cancel retains both sides; a second click can explicitly replace.
        runtime.pendingCompose = nil
        XCTAssertEqual(runtime.chat.attachments["chat"]?.count, 1)
        try await runtime.compose(request.target, text: request.text)
        await runtime.replaceCompose(try XCTUnwrap(runtime.pendingCompose))
        XCTAssertEqual(runtime.chat.drafts["chat"], "Edited")
        XCTAssertEqual(runtime.chat.attachments["chat"], [])
        XCTAssertEqual(runtime.chat.composeRequest?.target, "chat")
        XCTAssertFalse(runtime.submitted)
        let sends = await transport.sends
        XCTAssertTrue(sends.isEmpty)
        await transport.setCanInteract(false)
        do { try await runtime.compose("chat", text: "Rejected"); XCTFail("Expired source accepted") } catch {}
        XCTAssertEqual(runtime.chat.drafts["chat"], "Edited")
        await transport.setCanInteract(true)
        await transport.setTargetWritable(false)
        do { try await runtime.compose("chat", text: "Denied"); XCTFail("Read-only target accepted") } catch {}
        XCTAssertEqual(runtime.state["$draft"], .string("Edited"))
        runtime.leave()
    }

    private func find(_ kind: String, _ value: JSONValue) -> JSONValue? {
        if value["typeName"].stringValue == kind { return value }
        for child in value.arrayValue ?? Array(value.objectValue?.values ?? [:].values) {
            if let found = find(kind, child) { return found }
        }
        return nil
    }
    private func makeRuntime(readOnly: Bool = false, source override: String? = nil) async throws -> (InteractiveRuntime, InteractiveTestTransport) {
        let user = AuthUser(id: "viewer", username: "viewer", display_name: "Viewer", owner_id: "viewer", locale: "zh", membership_status: "active", is_company_admin: false, owned_node_ids: [], created_at: "now")
        let pair = TokenPair(access_token: "test", refresh_token: "test", user: user)
        let transport = InteractiveTestTransport(pair: try JSONEncoder().encode(pair))
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        let session = Session(baseURL: URL(string: "https://im.example.test")!, transport: transport, credentials: InteractiveTestCredentials(), sendAttempts: SendAttemptStore(directory: directory))
        _ = try await session.login(username: "viewer", password: "test")
        let client = IMClient(baseURL: session.baseURL, session: session)
        let chat = ChatStore(client: client, user: user)
        var message = try JSONDecoder().decode(ChatMessage.self, from: Data(#"{"id":"card","conversation_id":"chat","sender":{"type":"agent","id":"agent"},"sender_user_id":"agent","sender_type":"agent","content":"阅读安排","attachments":[],"delivery_status":"completed","created_at":"now"}"#.utf8))
        message.interactive = MessageInteractive(format: "openui", catalog_version: "nano-1", source: override ?? source)
        return (InteractiveRuntime(client: client, message: message, chat: chat, readOnly: readOnly), transport)
    }
}

private final class InteractiveTestCredentials: CredentialStore, @unchecked Sendable {
    private var value: StoredSession?
    func load() throws -> StoredSession? { value }
    func save(_ value: StoredSession) throws { self.value = value }
    func remove() throws { value = nil }
}

private actor InteractiveTestTransport: HTTPTransport {
    let pair: Data
    var puts = 0
    var sends: [JSONValue] = []
    private var conflict = false
    private var canInteract = true
    private var targetWritable = true
    private var revision = 0
    private var state: JSONValue = .object([:])
    init(pair: Data) { self.pair = pair }
    func setCanInteract(_ value: Bool) { canInteract = value }
    func setTargetWritable(_ value: Bool) { targetWritable = value }
    func setConflict(_ value: Bool) { conflict = value }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let path = request.url!.path
        var status = 200, data = Data("{}".utf8)
        if path.hasSuffix("/login") || path.hasSuffix("/refresh") { data = pair }
        else if path.hasSuffix("/interaction-state") {
            if request.httpMethod == "PUT" {
                puts += 1
                if conflict { status = 409; data = Data(#"{"detail":{"code":"interaction_draft_conflict","message":"Draft changed"}}"#.utf8) }
                else { revision += 1; state = try JSONDecoder().decode(JSONValue.self, from: request.httpBody!)["state"] }
            }
            if status == 200 { data = try JSONEncoder().encode(JSONValue.object(["draft_revision": .number(Double(revision)), "state": state, "submission_message_id": .null, "can_interact": .bool(canInteract)])) }
        } else if path.hasSuffix("/messages") && request.httpMethod == "POST" {
            sends.append(try JSONDecoder().decode(JSONValue.self, from: request.httpBody!))
            revision += 1
            data = Data(#"{"id":"submitted","conversation_id":"chat","sender":{"type":"user","id":"viewer"},"sender_user_id":"viewer","sender_type":"user","content":"安排阅读","attachments":[],"delivery_status":"pending","created_at":"now"}"#.utf8)
        } else if path.hasSuffix("/conversations/chat") {
            if !targetWritable { return (Data(#"{"detail":"No write permission"}"#.utf8), HTTPURLResponse(url: request.url!, statusCode: 403, httpVersion: nil, headerFields: nil)!) }
            data = Data(#"{"id":"chat","title":"Chat","participants":[],"participant_ids":["viewer"],"type":"direct","owner_id":"viewer","creator_id":"viewer","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now","can_write":true}"#.utf8)
        } else if path.contains("message-attempts") { status = 404 }
        return (data, HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!)
    }
}
