import XCTest
import Darwin

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

    func testTwoEditedCardsAreConsumedTogetherThenOnlyReeditedCardReturns() async throws {
        let labelA = try required("NANO_UI_CARD_A_LABEL"), labelB = try required("NANO_UI_CARD_B_LABEL")
        let cardA = try openMeetingCard(fieldLabel: labelA)
        let firstCount = try replaceCount(cardA, preferred: "7")
        let cardB = try revealCardField(labelB, towardLatest: true)
        let secondCount = try replaceCount(cardB, preferred: "8")
        let run = UUID().uuidString
        print("716_NATIVE_MULTI_RUN \(run) A=\(firstCount) B=\(secondCount)")
        capture("716-native-multi-both-edited")
        try await sendText("716-native-multi-first-\(run): Read both edited cards and confirm their counts only. Do not create anything.")
        try await sendText("716-native-multi-second-\(run): Reply received only. Do not reuse any card.")
        let revisited = try revealCardField(labelA)
        let thirdCount = try replaceCount(revisited, preferred: "9")
        print("716_NATIVE_MULTI_REEDIT \(run) A=\(thirdCount)")
        try await sendText("716-native-multi-third-\(run): Read only the newly edited card and confirm its count only. Do not create anything.")
        capture("716-native-multi-three-messages-sent")
    }

    func testNativeBudgetFailureRetainsAttachmentAndRecovers() async throws {
        try openConversation()
        app.buttons["Add attachment"].tap(); app.buttons["Photos"].tap()
        // Bind the synthetic blue photo by its observed picker AX label, not a sample-library index.
        let photos = app.images.matching(NSPredicate(format: "identifier == 'PXGGridLayout-Info' AND label == %@", try required("NANO_UI_OWNED_PHOTO_LABEL")))
        guard photos.firstMatch.waitForExistence(timeout: 5), photos.count == 1 else { XCTFail("The owned photo must be unique"); throw NSError(domain: "OneShotBackgroundUITests", code: 4) }
        // The Photos image's AX hit point is -1 despite the visible tile; use its observed centre.
        photos.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        let attachment = app.buttons["Remove attachment"]
        guard attachment.waitForExistence(timeout: 10) else { XCTFail("The real upload must finish before host preparation"); throw NSError(domain: "OneShotBackgroundUITests", code: 5) }
        let composer = app.textViews["Message"], run = UUID().uuidString
        let text = "716-native-budget-\(run): Keep this full message and my attachment. Confirm all three card counts only; do not create anything."
        composer.tap(); composer.typeText(text); XCTAssertEqual(composer.value as? String, text)
        capture("716-native-budget-before-send")
        let auth = try await request("/im/v1/auth/login", method: "POST", body: ["username": required("NANO_UI_USERNAME"), "password": required("NANO_UI_PASSWORD")])
        let token = try XCTUnwrap(auth["access_token"] as? String)
        let mid = try XCTUnwrap(fixture.cardIDs.last)
        print("716_BUDGET_READY run=\(run)"); fflush(stdout)
        try await waitForBudgetNote(mid, token: token, expanded: true)
        XCTAssertTrue(app.buttons["Send"].isEnabled); app.buttons["Send"].tap()
        let detail = "Card background is too large; the message was not sent. Reduce card content and retry, or leave this chat on the devices where you edited cards to clear their pending backgrounds. Your message and card edits are kept."
        let error = app.staticTexts.matching(NSPredicate(format: "label == %@", detail)).firstMatch
        guard error.waitForExistence(timeout: 10), composer.value as? String == text, attachment.exists else { XCTFail("Budget refusal must keep the full message and photo"); throw NSError(domain: "OneShotBackgroundUITests", code: 6) }
        capture("716-native-budget-rejected-retains-body-photo")
        let tree = XCTAttachment(string: app.debugDescription)
        tree.name = "716-native-budget-rejected-AX"; tree.lifetime = .keepAlways; add(tree)
        print("716_BUDGET_REJECTED run=\(run)"); fflush(stdout)
        try await waitForBudgetNote(mid, token: token, expanded: false)
        XCTAssertEqual(composer.value as? String, text); XCTAssertTrue(attachment.exists)
        try await sendText(text, alreadyComposed: true)
        XCTAssertFalse(attachment.exists)
        try await sendText("716-native-budget-next-\(run): Reply received only. Do not reuse any card.")
        capture("716-native-budget-recovered-and-next-sent")
    }

    private func waitForBudgetNote(_ mid: String, token: String, expanded: Bool) async throws {
        let path = "/im/v1/conversations/\(fixture.conversationID)/messages/\(mid)/interaction-state"
        let recovery = try required("NANO_UI_BUDGET_RECOVERY_NOTE"), expansion = try required("NANO_UI_BUDGET_EXPANSION_PREFIX")
        for _ in 0..<30 {
            let value = try await request(path, token: token), state = try XCTUnwrap(value["state"] as? [String: Any])
            let fields = try XCTUnwrap(value["fields"] as? [[String: Any]])
            let key = try XCTUnwrap(fields.first(where: { ($0["label"] as? String)?.hasSuffix("备注") == true })?["name"] as? String)
            let note = try XCTUnwrap(state[key] as? String)
            if expanded ? note.utf8.count == 12000 && note.hasPrefix(expansion) : note == recovery { return }
            try await Task.sleep(for: .milliseconds(250))
        }
        XCTFail("Owned host did not prepare the bound draft checkpoint"); throw NSError(domain: "OneShotBackgroundUITests", code: 3)
    }

    private func replaceCount(_ field: XCUIElement, preferred: String) throws -> String {
        field.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)).tap()
        let old = try XCTUnwrap(field.value as? String)
        let value = old == preferred ? String((Int(preferred) ?? 7) + 1) : preferred
        field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: old.count) + value)
        XCTAssertEqual(field.value as? String, value, "A real accessible edit must establish each pending background")
        return value
    }

    private func sendText(_ text: String, alreadyComposed: Bool = false) async throws {
        let composer = app.textViews["Message"]
        XCTAssertTrue(composer.waitForExistence(timeout: 5))
        if alreadyComposed { XCTAssertEqual(composer.value as? String, text) }
        else { composer.tap(); composer.typeText(text) }
        XCTAssertTrue(app.buttons["Send"].isEnabled)
        app.buttons["Send"].tap()
        let latest = app.buttons["Latest messages"]
        // XCTest's identifier subscript rejects strings longer than 128 characters.
        // Match the exact visible message label without weakening the receipt check.
        let sent = app.staticTexts.matching(NSPredicate(format: "label == %@", text)).firstMatch
        var jumpedToLatest = false
        let receipt = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            if sent.exists { return true }
            // The jump control can appear after the asynchronous Send returns.
            // Use it once within the original receipt wait, not just before it.
            if !jumpedToLatest && latest.exists && latest.isHittable {
                jumpedToLatest = true; latest.tap()
            }
            return sent.exists
        }, object: nil)
        let receiptResult = await XCTWaiter.fulfillment(of: [receipt], timeout: 20)
        capture("716-native-send-receipt")
        guard receiptResult == .completed else { XCTFail("The exact sent message receipt must appear"); throw NSError(domain: "OneShotBackgroundUITests", code: 7) }
        let empty = XCTNSPredicateExpectation(predicate: NSPredicate(format: "value == nil OR value == ''"), object: composer)
        await fulfillment(of: [empty], timeout: 10)
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
        let fieldLabel = try XCTUnwrap(fixture.cardLabels.first)
        let people = try openMeetingCard(fieldLabel: fieldLabel)
        let composer = app.textViews["Message"]
        let auth = try await request("/im/v1/auth/login", method: "POST", body: [
            "username": try required("NANO_UI_USERNAME"), "password": try required("NANO_UI_PASSWORD")
        ])
        let token = try XCTUnwrap(auth["access_token"] as? String)
        let cid = try required("NANO_UI_CONVERSATION_ID"), mid = try required("NANO_UI_CARD_ID")
        XCTAssertEqual(mid, fixture.cardIDs.first)
        let baseline = try await request("/im/v1/conversations/\(cid)/messages/\(mid)/interaction-state", token: token)
        let fields = try XCTUnwrap(baseline["fields"] as? [[String: Any]])
        let stateKey = try XCTUnwrap(fields.first(where: { $0["label"] as? String == fieldLabel })?["name"] as? String)
        XCTAssertNotNil((baseline["state"] as? [String: Any])?[stateKey] as? Int)
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
        XCTAssertEqual(savedState[stateKey] as? Int, Int(newCount))
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
        try openConversation()
        return try revealCardField(fieldLabel)
    }
    private func openConversation() throws {
        app.launch()
        let username = app.textFields["Enter your username"]
        if username.waitForExistence(timeout: 8) {
            username.tap(); username.typeText(try required("NANO_UI_USERNAME"))
            let password = app.secureTextFields["Enter your password"]
            password.tap(); password.typeText(try required("NANO_UI_PASSWORD"))
            app.buttons["Sign in"].tap()
        }
        let chat = app.staticTexts[try required("NANO_UI_CHAT_TITLE")].firstMatch
        let chatReadyDeadline = Date().addingTimeInterval(20)
        XCTAssertTrue(chat.waitForExistence(timeout: 20), "The real isolated service must supply the PA conversation")
        // A fresh simulator presents the password prompt after the authenticated list
        // loads. Checking before list readiness can finish before the sheet appears.
        let passwordSheet = app.sheets.matching(NSPredicate(format: "label IN %@", ["保存密码？", "Save Password?"])).firstMatch
        if passwordSheet.waitForExistence(timeout: 3) {
            let later = passwordSheet.buttons.matching(NSPredicate(format: "label IN %@", ["以后", "Not Now", "Later"])).firstMatch
            XCTAssertTrue(later.exists); later.tap()
        }
        // A system sheet may still be dismissing when tap returns. Wait for the
        // real entry condition using only the remainder of the original 20s budget.
        let entryReady = XCTNSPredicateExpectation(predicate: NSPredicate(format: "hittable == true"), object: chat)
        let entryResult = XCTWaiter.wait(for: [entryReady], timeout: max(0, chatReadyDeadline.timeIntervalSinceNow))
        capture("716-app-chat-list")
        XCTAssertEqual(entryResult, .completed, "A system prompt must not cover the authenticated conversation entry")
        chat.tap()
        XCTAssertTrue(app.textViews["Message"].waitForExistence(timeout: 5))
    }

    private func revealCardField(_ label: String, towardLatest: Bool = false) throws -> XCUIElement {
        XCTAssertTrue(fixture.cardLabels.contains(label), "Only accessible fields bound to the fixture may be edited")
        // WK accessibility can report an offscreen field as hittable while another
        // card owns the keyboard. Finish that edit and verify the actual viewport.
        let done = app.buttons["Done"]
        if done.exists && done.isHittable { done.tap() }
        let field = app.webViews.textFields[label].firstMatch
        for _ in 0..<8 {
            if isVisibleCardField(field) { break }
            let viewport = cardViewport()
            let top = app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: viewport.midX, dy: viewport.minY + viewport.height * 0.2))
            let bottom = app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: viewport.midX, dy: viewport.minY + viewport.height * 0.8))
            if towardLatest { bottom.press(forDuration: 0.05, thenDragTo: top) }
            else { top.press(forDuration: 0.05, thenDragTo: bottom) }
        }
        capture("716-app-card-probe")
        XCTAssertTrue(field.waitForExistence(timeout: 10), "WK field accessibility is a prerequisite, not an assumed journey pass")
        XCTAssertTrue(isVisibleCardField(field), "The card field must be inside the visible timeline, not under the keyboard or composer")
        return field
    }

    private func cardViewport() -> CGRect {
        let window = app.frame
        let top = app.navigationBars.firstMatch.frame.maxY
        let bottom = app.textViews["Message"].frame.minY
        return CGRect(x: window.minX, y: top, width: window.width, height: max(0, bottom - top))
    }

    private func isVisibleCardField(_ field: XCUIElement) -> Bool {
        guard field.exists && field.isHittable else { return false }
        let frame = field.frame
        return frame.width > 0 && frame.height > 0 && cardViewport().contains(frame)
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
