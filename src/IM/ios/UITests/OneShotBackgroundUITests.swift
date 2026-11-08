import XCTest

/// Genuine cross-process App entry. Inputs must name this unit's isolated synthetic service.
@MainActor
final class OneShotBackgroundUITests: XCTestCase {
    private var app: XCUIApplication!
    private var fixture: JourneyFixture!

    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 120
        // A locally verified fresh-runtime manifest is mandatory. Loopback alone could
        // still be the existing preview or another task's service.
        fixture = try JSONDecoder().decode(JourneyFixture.self, from: Data(required("NANO_UI_FIXTURE_JSON").utf8))
        let origin = try required("NANO_UI_ORIGIN")
        let url = try XCTUnwrap(URL(string: origin)), port = try XCTUnwrap(url.port)
        XCTAssertNotNil(UUID(uuidString: fixture.runID))
        XCTAssertEqual(url.scheme, "http"); XCTAssertEqual(url.host, "127.0.0.1")
        XCTAssertGreaterThanOrEqual(port, 49152); XCTAssertNotEqual(port, 62814)
        XCTAssertEqual(origin, fixture.origin)
        XCTAssertEqual(try required("NANO_UI_USERNAME"), fixture.username)
        XCTAssertEqual(try required("NANO_UI_CONVERSATION_ID"), fixture.conversationID)
        XCTAssertEqual(try required("NANO_UI_CHAT_TITLE"), fixture.chatTitle)
        app = XCUIApplication()
        app.launchEnvironment["NANO_IM_BASE_URL"] = origin
        app.launchArguments = ["-nano.locale", "en"]
    }
    override func tearDownWithError() throws { app?.terminate() }

    func testProbeRealCardFieldsThroughAppEntry() throws {
        let people = try openMeetingCard()
        people.tap()
        capture("716-app-field-focused")
    }

    func testEditedCardSendsOnceThroughRealComposer() throws {
        let people = try openMeetingCard()
        // A trailing-edge tap places the caret after the existing one-digit fixture value.
        people.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)).tap()
        let old = try XCTUnwrap(people.value as? String)
        let newCount = old == "7" ? "6" : "7"
        people.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: old.count) + newCount)
        XCTAssertEqual(people.value as? String, newCount, "Only a real accessible field edit establishes the first-send precondition")
        let run = UUID().uuidString
        print("716_NATIVE_RUN \(run) editedCount=\(newCount)")
        let first = "716-native-first-\(run): Confirm the edited participant count only. Do not create anything."
        let second = "716-native-second-\(run): Reply received only; do not reuse the card."
        let composer = app.textViews["Message"]
        XCTAssertTrue(composer.waitForExistence(timeout: 5))
        composer.tap(); composer.typeText(first)
        capture("716-native-edited-before-send")
        app.buttons["Send"].tap()
        // Sending while reading an older card intentionally preserves that reading position.
        // Use the actual existing jump control before asserting a new offscreen message.
        let latest = app.buttons["Latest messages"]
        if latest.exists { latest.tap() }
        XCTAssertTrue(app.staticTexts[first].firstMatch.waitForExistence(timeout: 20))
        let empty = NSPredicate(format: "value == nil OR value == ''")
        expectation(for: empty, evaluatedWith: composer)
        waitForExpectations(timeout: 10)
        composer.tap(); composer.typeText(second)
        app.buttons["Send"].tap()
        XCTAssertTrue(app.staticTexts[second].firstMatch.waitForExistence(timeout: 20))
        capture("716-native-two-messages-sent")
    }

    func testTwoEditedCardsAreConsumedTogetherThenOnlyReeditedCardReturns() throws {
        let labelA = try required("NANO_UI_CARD_A_LABEL"), labelB = try required("NANO_UI_CARD_B_LABEL")
        let cardA = try openMeetingCard(fieldLabel: labelA)
        let firstCount = try replaceCount(cardA, preferred: "7")
        let cardB = try revealCardField(labelB, towardLatest: true)
        let secondCount = try replaceCount(cardB, preferred: "8")
        let run = UUID().uuidString
        print("716_NATIVE_MULTI_RUN \(run) A=\(firstCount) B=\(secondCount)")
        capture("716-native-multi-both-edited")
        try sendText("716-native-multi-first-\(run): Read both edited cards and confirm their counts only. Do not create anything.")
        try sendText("716-native-multi-second-\(run): Reply received only. Do not reuse any card.")
        let revisited = try revealCardField(labelA)
        let thirdCount = try replaceCount(revisited, preferred: "9")
        print("716_NATIVE_MULTI_REEDIT \(run) A=\(thirdCount)")
        try sendText("716-native-multi-third-\(run): Read only the newly edited card and confirm its count only. Do not create anything.")
        capture("716-native-multi-three-messages-sent")
    }

    private func replaceCount(_ field: XCUIElement, preferred: String) throws -> String {
        field.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)).tap()
        let old = try XCTUnwrap(field.value as? String)
        let value = old == preferred ? String((Int(preferred) ?? 7) + 1) : preferred
        field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: old.count) + value)
        XCTAssertEqual(field.value as? String, value, "A real accessible edit must establish each pending background")
        return value
    }

    private func sendText(_ text: String) throws {
        let composer = app.textViews["Message"]
        XCTAssertTrue(composer.waitForExistence(timeout: 5))
        composer.tap(); composer.typeText(text)
        XCTAssertTrue(app.buttons["Send"].isEnabled)
        app.buttons["Send"].tap()
        let latest = app.buttons["Latest messages"]
        if latest.exists { latest.tap() }
        XCTAssertTrue(app.staticTexts[text].firstMatch.waitForExistence(timeout: 20))
        expectation(for: NSPredicate(format: "value == nil OR value == ''"), evaluatedWith: composer)
        waitForExpectations(timeout: 10)
    }

    func testNativeConflictComparisonAndExplicitAdoption() async throws {
        let text = "716-native-conflict: Keep my message until I decide."
        let people = try openMeetingCard()
        let composer = app.textViews["Message"]
        // A separate authenticated device advances the real server revision, after this
        // App has loaded its draft. This is ordinary API use, not a product test hook.
        let tokenPair = try await request("/im/v1/auth/login", method: "POST", body: [
            "username": try required("NANO_UI_USERNAME"), "password": try required("NANO_UI_PASSWORD")
        ])
        let token = try XCTUnwrap(tokenPair["access_token"] as? String)
        let cid = try required("NANO_UI_CONVERSATION_ID"), mid = try required("NANO_UI_CARD_ID")
        let path = "/im/v1/conversations/\(cid)/messages/\(mid)/interaction-state"
        let remote = try await request(path, token: token)
        var state = try XCTUnwrap(remote["state"] as? [String: Any])
        let remoteCount = (state["$participants"] as? Int) == 9 ? 10 : 9
        state["$participants"] = remoteCount
        _ = try await request(path, method: "PUT", token: token, body: [
            "expected_draft_revision": try XCTUnwrap(remote["draft_revision"]), "state": state
        ])
        people.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)).tap()
        let old = try XCTUnwrap(people.value as? String)
        people.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: old.count) + "8")
        // The 409 notice can move this lazy card outside the viewport immediately.
        // Assert the actual local 8 later in the comparison rather than querying a recycled WK node.
        let comparisons = app.buttons.matching(identifier: "View latest changes")
        XCTAssertTrue(comparisons.firstMatch.waitForExistence(timeout: 10))
        // The offscreen card also offers the same action. Query order is not screen
        // order: choose the visible native notice instead of guessing a matching index.
        let compare = try XCTUnwrap(comparisons.allElementsBoundByIndex.first(where: { $0.isHittable }))
        XCTAssertFalse(app.buttons["Send"].isEnabled)
        // Wait for the failure notice before typing; otherwise its arrival can move
        // the UIKit composer between XCTest's tap and key dispatch.
        composer.tap(); composer.typeText(text)
        XCTAssertEqual(composer.value as? String, text)
        capture("716-native-conflict-blocks-conversation")
        compare.tap()
        let adoptions = app.buttons.matching(identifier: "Use latest draft (discards these local edits)")
        XCTAssertTrue(adoptions.firstMatch.waitForExistence(timeout: 10))
        let adopt = try XCTUnwrap(adoptions.allElementsBoundByIndex.first(where: { $0.isHittable }))
        XCTAssertTrue(app.staticTexts["Other device"].exists)
        XCTAssertTrue(app.staticTexts["This device"].exists)
        XCTAssertTrue(app.staticTexts[String(remoteCount)].firstMatch.exists)
        XCTAssertTrue(app.staticTexts["8"].firstMatch.exists)
        // The notice may move the original card outside the lazy viewport. The local
        // column still shows 8, so inspection has not silently replaced it with the remote value.
        XCTAssertEqual(composer.value as? String, text)
        capture("716-native-conflict-three-columns")
        adopt.tap()
        let resolved = expectation(for: NSPredicate(format: "exists == false"), evaluatedWith: compare)
        await fulfillment(of: [resolved], timeout: 10)
        XCTAssertTrue(app.buttons["Send"].isEnabled)
        XCTAssertEqual(composer.value as? String, text)
        let adoptedField = app.webViews.textFields["参会人数"].firstMatch
        let restored = expectation(for: NSPredicate(format: "value == %@", String(remoteCount)), evaluatedWith: adoptedField)
        await fulfillment(of: [restored], timeout: 15)
        capture("716-native-conflict-adopted")
    }

    func testNativeTransientSaveBlocksAndRecovers() async throws {
        guard try required("NANO_UI_OUTAGE_EXPECTED") == "1" else { throw XCTSkip("Requires a dedicated owned IM outage, never the preview") }
        let text = "716-native-transient: Keep this message while saving recovers."
        let people = try openMeetingCard()
        let composer = app.textViews["Message"]
        let auth = try await request("/im/v1/auth/login", method: "POST", body: [
            "username": try required("NANO_UI_USERNAME"), "password": try required("NANO_UI_PASSWORD")
        ])
        let token = try XCTUnwrap(auth["access_token"] as? String)
        let cid = try required("NANO_UI_CONVERSATION_ID"), mid = try required("NANO_UI_CARD_ID")
        print("716_OUTAGE_READY")
        try await waitForService(available: false)
        people.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)).tap()
        let old = try XCTUnwrap(people.value as? String), newCount = old == "5" ? "6" : "5"
        people.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: old.count) + newCount)
        let retryButtons = app.buttons.matching(identifier: "Retry saving")
        XCTAssertTrue(retryButtons.firstMatch.waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["Send"].isEnabled)
        composer.tap(); composer.typeText(text)
        XCTAssertEqual(composer.value as? String, text)
        capture("716-native-transient-blocks-conversation")
        print("716_OUTAGE_RECOVER")
        try await waitForService(available: true)
        try XCTUnwrap(retryButtons.allElementsBoundByIndex.first(where: { $0.isHittable })).tap()
        let recovered = expectation(for: NSPredicate(format: "enabled == true"), evaluatedWith: app.buttons["Send"])
        await fulfillment(of: [recovered], timeout: 15)
        XCTAssertEqual(composer.value as? String, text)
        let saved = try await request("/im/v1/conversations/\(cid)/messages/\(mid)/interaction-state", token: token)
        let savedState = try XCTUnwrap(saved["state"] as? [String: Any])
        XCTAssertEqual(savedState["$participants"] as? Int, Int(newCount))
        capture("716-native-transient-recovered")
    }

    private func waitForService(available: Bool) async throws {
        let url = try XCTUnwrap(URL(string: required("NANO_UI_ORIGIN") + "/health"))
        for _ in 0..<30 {
            var request = URLRequest(url: url); request.timeoutInterval = 1
            let isAvailable: Bool
            do { let (_, response) = try await URLSession.shared.data(for: request); isAvailable = (response as? HTTPURLResponse)?.statusCode == 200 }
            catch { isAvailable = false }
            if isAvailable == available { return }
            try await Task.sleep(for: .milliseconds(250))
        }
        XCTFail("The owned outage harness did not reach available=\(available)")
        throw NSError(domain: "OneShotBackgroundUITests", code: 2)
    }

    private func request(_ path: String, method: String = "GET", token: String? = nil, body: [String: Any]? = nil) async throws -> [String: Any] {
        let origin = try required("NANO_UI_ORIGIN")
        let url = try XCTUnwrap(URL(string: origin + path))
        XCTAssertEqual(origin, fixture.origin)
        if path != "/im/v1/auth/login" {
            let allowed = fixture.cardIDs.map { "/im/v1/conversations/\(fixture.conversationID)/messages/\($0)/interaction-state" }
            XCTAssertTrue(allowed.contains(path), "Only card objects bound to this fresh fixture may be read or updated")
        }
        XCTAssertEqual(url.host, "127.0.0.1", "Only this unit's isolated loopback service is allowed")
        var request = URLRequest(url: url); request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body { request.httpBody = try JSONSerialization.data(withJSONObject: body) }
        let (data, response) = try await URLSession.shared.data(for: request)
        let status = try XCTUnwrap(response as? HTTPURLResponse).statusCode
        XCTAssertTrue((200..<300).contains(status), "Synthetic device API \(method) \(path) returned \(status)")
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    private func openMeetingCard(fieldLabel: String = "参会人数") throws -> XCUIElement {
        app.launch()
        let username = app.textFields["Enter your username"]
        if username.waitForExistence(timeout: 8) {
            username.tap(); username.typeText(try required("NANO_UI_USERNAME"))
            let password = app.secureTextFields["Enter your password"]
            password.tap(); password.typeText(try required("NANO_UI_PASSWORD"))
            app.buttons["Sign in"].tap()
        }
        // iOS may offer to store the synthetic password after login. Decline in the
        // simulator instead of letting an invisible interruption swallow the chat tap.
        let passwordSheet = app.sheets.matching(NSPredicate(format: "label IN %@", ["保存密码？", "Save Password?"])).firstMatch
        if passwordSheet.waitForExistence(timeout: 3) {
            let later = passwordSheet.buttons.matching(NSPredicate(format: "label IN %@", ["以后", "Not Now", "Later"])).firstMatch
            XCTAssertTrue(later.exists); later.tap()
        }
        let chat = app.staticTexts[try required("NANO_UI_CHAT_TITLE")].firstMatch
        XCTAssertTrue(chat.waitForExistence(timeout: 20), "The real isolated service must supply the PA conversation")
        capture("716-app-chat-list")
        chat.tap()
        return try revealCardField(fieldLabel)
    }

    private func revealCardField(_ label: String, towardLatest: Bool = false) throws -> XCUIElement {
        XCTAssertTrue(fixture.cardLabels.contains(label), "Only accessible fields bound to the fixture may be edited")
        // Move through the actual native timeline, not the App runtime or JS.
        let field = app.webViews.textFields[label].firstMatch
        for _ in 0..<8 {
            if field.exists && field.isHittable { break }
            if towardLatest { app.scrollViews.firstMatch.swipeUp() }
            else { app.scrollViews.firstMatch.swipeDown() }
        }
        capture("716-app-card-probe")
        XCTAssertTrue(field.waitForExistence(timeout: 10), "WK field accessibility is a prerequisite, not an assumed journey pass")
        XCTAssertTrue(field.isHittable, "The visible card field must be directly tappable")
        return field
    }
    private func required(_ name: String) throws -> String {
        guard let value = ProcessInfo.processInfo.environment[name], !value.isEmpty else {
            XCTFail("Missing isolated native journey input: \(name)")
            throw NSError(domain: "OneShotBackgroundUITests", code: 1)
        }
        return value
    }
    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways
        add(attachment)
    }
}

/// Produced only after the host runner checks the owned process and read-only fixture DB.
private struct JourneyFixture: Decodable {
    let runID: String
    let origin: String
    let username: String
    let conversationID: String
    let chatTitle: String
    let cardIDs: [String]
    let cardLabels: [String]
}
