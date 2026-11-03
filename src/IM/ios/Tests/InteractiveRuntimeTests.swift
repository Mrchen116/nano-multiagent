import XCTest
import SwiftUI
import WebKit
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

    func testIntelligentUIWebKitRendersReferenceCardsAndSVGAtPhoneWidth() async throws {
        for name in ["hotel", "dashboard"] {
            let url = try XCTUnwrap(Bundle(for: Self.self).url(forResource: name, withExtension: "json"))
            let source = try JSONDecoder().decode(JSONValue.self, from: Data(contentsOf: url))["source"].stringValue
            let (runtime, transport) = try await makeRuntime(source: try XCTUnwrap(source), catalog: "nano-iui-1")
            await runtime.load()
            let (view, coordinator, window) = mount(runtime)
            try await waitFor(view, "document.querySelectorAll('button').length > 0 && document.body.innerText.length > 100")
            XCTAssertNil(runtime.error)
            let width = try await view.evaluateJavaScript("document.documentElement.scrollWidth") as? Double
            XCTAssertLessThanOrEqual(try XCTUnwrap(width), 394, "\(name) spills outside phone width")
            if name == "hotel" {
                // Network photos may arrive later; external availability is not a renderer assertion.
                if ProcessInfo.processInfo.environment["NANO_IOS_VISUAL_NETWORK"] == "1" {
                    try await waitFor(view, "document.images[0]?.complete && document.images[0].naturalWidth > 0")
                }
                _ = try await view.evaluateJavaScript("Array.from(document.querySelectorAll('button,[role=button]')).find(button => button.textContent === 'Book').click()")
                try await waitFor(view, "document.body.innerText.includes('预订交互演示')")
            } else {
                let count = try await view.evaluateJavaScript("document.querySelectorAll('svg path,svg circle,svg rect').length") as? Int
                XCTAssertGreaterThan(try XCTUnwrap(count), 10, "Chart / funnel must contain real geometry")
            }
            let image = try await view.takeSnapshot(configuration: nil)
            let attachment = XCTAttachment(image: try XCTUnwrap(image)); attachment.name = "iOS-\(name)-393px"; attachment.lifetime = .keepAlways
            add(attachment)
            let sends = await transport.sends
            XCTAssertTrue(sends.isEmpty, "Local exploration must not call the Agent")
            _ = coordinator
            window.isHidden = true
            view.configuration.userContentController.removeScriptMessageHandler(forName: "intelligentUI", contentWorld: .page)
            runtime.leave()
        }
    }

    func testIntelligentUIWebKitMeetingEditsRestoreAndExplicitlyContinue() async throws {
        let source = """
        $slot = "周二 10:00"
        root = Col([Title("安排项目评审"), Form([SegmentedControl($slot, ["周二 10:00", "周三 14:00"]), Text($slot), Button("确认安排", @ToAssistant("按我的选择安排会议", {kind:"meeting"}))])])
        """
        let (runtime, transport) = try await makeRuntime(source: source, catalog: "nano-iui-1")
        await runtime.load()
        let (view, coordinator, window) = mount(runtime)
        defer { window.isHidden = true; view.configuration.userContentController.removeScriptMessageHandler(forName: "intelligentUI", contentWorld: .page); runtime.leave() }
        try await waitFor(view, "document.body.innerText.includes('确认安排')")
        _ = try await view.evaluateJavaScript("Array.from(document.querySelectorAll('button')).find(button => button.textContent === '周三 14:00').click()")
        try await waitFor(view, "document.querySelector('form').innerText.includes('周三 14:00')")
        for _ in 0..<100 where runtime.state["$slot"] != .string("周三 14:00") { try await Task.sleep(for: .milliseconds(20)) }
        XCTAssertEqual(runtime.state["$slot"], .string("周三 14:00"))
        XCTAssertEqual(runtime.chat.interactionSelections["card"]?.state["$slot"], .string("周三 14:00"))
        await runtime.flush()
        var sends = await transport.sends
        XCTAssertTrue(sends.isEmpty)
        _ = try await view.evaluateJavaScript("Array.from(document.querySelectorAll('button')).find(button => button.textContent === '确认安排').click()")
        for _ in 0..<200 where !runtime.submitted { try await Task.sleep(for: .milliseconds(20)) }
        XCTAssertTrue(runtime.submitted, runtime.error ?? "Not submitted")
        sends = await transport.sends
        XCTAssertEqual(sends.count, 1)
        XCTAssertEqual(sends.first?["interaction_reply"]["state"]["$slot"], .string("周三 14:00"))
        XCTAssertEqual(sends.first?["interaction_reply"]["event"]["message"], .string("按我的选择安排会议"))
        XCTAssertEqual(sends.first?["interaction_reply"]["event"]["label"], .string("确认安排"))
        XCTAssertNil(runtime.error)
        await runtime.load()
        XCTAssertEqual(runtime.state["$slot"], .string("周三 14:00"))
        do { _ = try await runtime.webRequest(.object(["type": .string("action")]), generation: coordinator.generation); XCTFail("Old page accepted after reload") } catch {}
        let generation = runtime.webID
        runtime.setReadOnly(true)
        do {
            _ = try await runtime.webRequest(.object(["type": .string("tool"), "name": .string("continue_conversation"), "args": .object(["message": .string("forbidden")])]), generation: generation)
            XCTFail("Read-only submission accepted")
        } catch {}
        _ = await runtime.client.session.signOut()
        do { _ = try await runtime.webRequest(.object(["type": .string("ready")]), generation: generation); XCTFail("Logged-out page accepted") } catch {}
    }

    private func mount(_ runtime: InteractiveRuntime) -> (WKWebView, InteractiveWebContent.Coordinator, UIWindow) {
        let coordinator = InteractiveWebContent.Coordinator(runtime: runtime, height: .constant(800))
        let view = coordinator.makeWebView()
        view.isOpaque = true; view.backgroundColor = .white
        let scene = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first!
        let window = UIWindow(windowScene: scene)
        window.frame = CGRect(x: 0, y: 0, width: 393, height: 852)
        let controller = UIViewController(); window.rootViewController = controller
        controller.view.backgroundColor = .white
        controller.view.addSubview(view); view.frame = CGRect(x: 0, y: 0, width: 393, height: 800)
        window.makeKeyAndVisible()
        return (view, coordinator, window)
    }

    func testIntelligentUIHtmlFrameCannotUseNativeAuthority() async throws {
        let html = """
        <p>Isolated content</p><script>addEventListener('message', async () => {
          try { await window.webkit.messageHandlers.intelligentUI.postMessage({type:'tool',name:'continue_conversation',args:{message:'forbidden'}}); parent.postMessage('unexpected', '*'); }
          catch { parent.postMessage('blocked', '*'); }
        });</script>
        """
        let source = "root = Col([HtmlView(\(JSONValue.string(html).prettyPrinted), 140)])"
        let (runtime, transport) = try await makeRuntime(source: source, catalog: "nano-iui-1")
        await runtime.load()
        let (view, coordinator, window) = mount(runtime)
        defer { window.isHidden = true; view.configuration.userContentController.removeScriptMessageHandler(forName: "intelligentUI", contentWorld: .page); runtime.leave(); _ = coordinator }
        try await waitFor(view, "document.querySelector('iframe') !== null")
        _ = try await view.evaluateJavaScript("window.addEventListener('message', event => {if (['blocked','unexpected'].includes(event.data)) window.frameResult = event.data}); const frame = document.querySelector('iframe'); frame.addEventListener('load', () => frame.contentWindow.postMessage('try', '*')); frame.contentWindow.postMessage('try', '*')")
        try await waitFor(view, "window.frameResult === 'blocked'")
        let sends = await transport.sends
        XCTAssertTrue(sends.isEmpty)
    }

    func testIntelligentUIConnectedToolsAndComposeStayInNativeSession() async throws {
        let (runtime, transport) = try await makeRuntime(source: "root = Col([Text(\"Tools\")])", catalog: "nano-iui-1")
        await runtime.load()
        let generation = runtime.webID
        let rows = try await runtime.webRequest(.object(["type": .string("tool"), "name": .string("conversation_messages"), "args": .object([:])]), generation: generation)
        XCTAssertEqual(rows, .array([]))
        _ = try await runtime.webRequest(.object(["type": .string("action"), "event": .object(["type": .string("ComposeMessage"), "params": .object(["target": .string("chat"), "text": .string("会议草稿")])])]), generation: generation)
        XCTAssertEqual(runtime.chat.drafts["chat"], "会议草稿")
        var sends = await transport.sends
        XCTAssertTrue(sends.isEmpty)
        _ = try await runtime.webRequest(.object(["type": .string("tool"), "name": .string("continue_conversation"), "args": .object(["message": .string("安排评审"), "context": .object(["kind": .string("meeting")])])]), generation: generation)
        sends = await transport.sends
        XCTAssertEqual(sends.count, 1)
        XCTAssertEqual(sends.first?["interaction_reply"]["event"]["context"], .object(["kind": .string("meeting")]))
        for path in ["https://outside.test/im/v1/intelligent-ui/api/wiki", "/im/v1/auth/refresh"] {
            do { _ = try await runtime.webRequest(.object(["type": .string("resource"), "path": .string(path)]), generation: generation); XCTFail("Unregistered resource accepted") } catch {}
        }
        runtime.leave()
    }

    func testIntelligentUIReloadDoesNotLatchTemporaryAgentUnavailability() async throws {
        let (runtime, transport) = try await makeRuntime(source: "root = Col([Text(\"Ready\")])", catalog: "nano-iui-1")
        await transport.setCanInteract(false)
        await runtime.load()
        XCTAssertFalse(runtime.readOnly, "Temporary Agent unavailability does not turn a card into history")
        await transport.setCanInteract(true)
        await runtime.load()
        XCTAssertFalse(runtime.readOnly)
        let oldCoordinator = InteractiveWebContent.Coordinator(runtime: runtime, height: .constant(100))
        let oldView = oldCoordinator.makeWebView()
        await runtime.load()
        oldCoordinator.webViewWebContentProcessDidTerminate(oldView)
        oldCoordinator.webView(oldView, didFailProvisionalNavigation: nil, withError: URLError(.cancelled))
        XCTAssertTrue(runtime.loaded)
        XCTAssertNil(runtime.error)
        oldView.configuration.userContentController.removeScriptMessageHandler(forName: "intelligentUI", contentWorld: .page)
        runtime.leave()
    }

    func testIntelligentUICardFitsNativeChatAndReceivesReadOnlyChanges() async throws {
        let source = """
        $slot = "周二 10:00"
        root = Col([Title("安排项目评审"), Text("请选择时间，确认后再交给助手安排。"), Form([SegmentedControl($slot, ["周二 10:00", "周三 14:00"]), Text($slot), Button("确认安排", @ToAssistant("安排会议"))])])
        """
        let (runtime, _) = try await makeRuntime(source: source, catalog: "nano-iui-1")
        var message = runtime.message; message.content = "请选择会议时间。"
        func content(_ readOnly: Bool) -> AnyView {
            AnyView(ScrollView { ChatMessageView(client: runtime.client, chat: runtime.chat, message: message,
                selfID: "viewer", readOnly: readOnly, refreshed: {}).padding(16) })
        }
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let window = UIWindow(windowScene: scene); window.frame = CGRect(x: 0, y: 0, width: 393, height: 852)
        let controller = UIHostingController(rootView: content(false)); window.rootViewController = controller
        controller.view.backgroundColor = .white; window.makeKeyAndVisible()
        defer { window.isHidden = true; window.rootViewController = nil }
        func webView(_ parent: UIView) -> WKWebView? {
            (parent as? WKWebView) ?? parent.subviews.lazy.compactMap { webView($0) }.first
        }
        for _ in 0..<100 where webView(controller.view) == nil { try await Task.sleep(for: .milliseconds(20)) }
        let view = try XCTUnwrap(webView(controller.view))
        try await waitFor(view, "document.body.innerText.includes('确认安排')")
        let measured = try await view.evaluateJavaScript("document.getElementById('root').getBoundingClientRect().height") as? Double
        let contentHeight = try XCTUnwrap(measured)
        for _ in 0..<100 where abs(view.bounds.height - contentHeight) > 2 { try await Task.sleep(for: .milliseconds(20)) }
        XCTAssertEqual(view.bounds.width, 361, accuracy: 1)
        XCTAssertEqual(view.bounds.height, contentHeight, accuracy: 2, "The whole card must fit the native scroll flow")
        // UIKit's CPU snapshot omits WebKit's separately composited surface.
        let image = try await view.takeSnapshot(configuration: nil)
        let attachment = XCTAttachment(image: try XCTUnwrap(image)); attachment.name = "iOS-native-chat-meeting-body"; attachment.lifetime = .keepAlways; add(attachment)
        controller.rootView = content(true)
        try await waitFor(view, "document.querySelector('fieldset').disabled")
    }

    private func waitFor(_ view: WKWebView, _ expression: String) async throws {
        for _ in 0..<300 {
            if (try? await view.evaluateJavaScript(expression)) as? Bool == true { return }
            try await Task.sleep(for: .milliseconds(50))
        }
        XCTFail("WebKit did not satisfy: \(expression)")
        throw NSError(domain: "InteractiveWebTest", code: 1)
    }

    private func find(_ kind: String, _ value: JSONValue) -> JSONValue? {
        if value["typeName"].stringValue == kind { return value }
        for child in value.arrayValue ?? Array(value.objectValue?.values ?? [:].values) {
            if let found = find(kind, child) { return found }
        }
        return nil
    }
    private func makeRuntime(readOnly: Bool = false, source override: String? = nil, catalog: String = "nano-1") async throws -> (InteractiveRuntime, InteractiveTestTransport) {
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
        message.interactive = MessageInteractive(format: "openui", catalog_version: catalog, source: override ?? source)
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
        } else if path.hasSuffix("/messages") {
            data = Data(#"{"items":[],"next_cursor":null}"#.utf8)
        } else if path.hasSuffix("/conversations/chat") {
            if !targetWritable { return (Data(#"{"detail":"No write permission"}"#.utf8), HTTPURLResponse(url: request.url!, statusCode: 403, httpVersion: nil, headerFields: nil)!) }
            data = Data(#"{"id":"chat","title":"Chat","participants":[],"participant_ids":["viewer"],"type":"direct","owner_id":"viewer","creator_id":"viewer","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now","can_write":true}"#.utf8)
        } else if path.contains("message-attempts") { status = 404 }
        return (data, HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!)
    }
}
