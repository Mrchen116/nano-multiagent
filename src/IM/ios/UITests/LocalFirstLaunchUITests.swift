import XCTest

/// Cross-process coverage: genuine login, server DTO decoding, process termination and a
/// subsequent launch from disk. Run against an isolated IM instance, never production.
/// The two phases are separate so the harness can make that origin unreachable in between.
@MainActor
final class LocalFirstLaunchUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchEnvironment["NANO_IM_BASE_URL"] = try required("NANO_UI_ORIGIN")
        app.launchArguments = ["-nano.locale", "en"]
    }

    func testPrimeFromRealServer() throws {
        let title = try required("NANO_UI_CHAT_TITLE")
        let content = try required("NANO_UI_MESSAGE")
        app.launch()
        if ProcessInfo.processInfo.environment["NANO_UI_RESET_OWNED_SESSION"] == "1" {
            try resetOwnedSessionForLogin()
        }
        let username = app.textFields["Enter your username"]
        XCTAssertTrue(username.waitForExistence(timeout: 10), "Use a dedicated simulator with no existing session")
        username.tap(); username.typeText(try required("NANO_UI_USERNAME"))
        let password = app.secureTextFields["Enter your password"]
        password.tap(); password.typeText(try required("NANO_UI_PASSWORD"))
        app.buttons["Sign in"].tap()
        let chat = app.staticTexts[title].firstMatch
        XCTAssertTrue(chat.waitForExistence(timeout: 20), "The real server must supply the seeded conversation")
        capture("online-list")
        chat.tap()
        XCTAssertTrue(message(content).waitForExistence(timeout: 15), "The real message endpoint must decode and render")
        capture("online-timeline")
        app.terminate()
    }

    func testOfflineRelaunchReadsListAndTimeline() throws {
        let title = try required("NANO_UI_CHAT_TITLE")
        let content = try required("NANO_UI_MESSAGE")
        // The harness has stopped only this test origin after priming. No test-only cache
        // injection or in-process store method participates in this launch.
        app.launch()
        let chat = app.staticTexts[title].firstMatch
        XCTAssertTrue(chat.waitForExistence(timeout: 5), "An unreachable origin must not gate the cached list")
        XCTAssertFalse(app.textFields["Enter your username"].exists, "Network failure is not a sign-out")
        capture("offline-list")
        chat.tap()
        XCTAssertTrue(message(content).waitForExistence(timeout: 5), "Cached history must appear before network timeouts")
        capture("offline-timeline")
        app.terminate()
    }

    func testSuccessfulEmptyConversationStopsLoading() throws {
        let title = try required("NANO_UI_EMPTY_CHAT_TITLE")
        app.launch()
        let chat = app.staticTexts[title].firstMatch
        XCTAssertTrue(chat.waitForExistence(timeout: 20), "The real server must supply the dedicated empty conversation")
        chat.tap()
        XCTAssertTrue(app.staticTexts["conversation.empty"].waitForExistence(timeout: 15), "A successful empty message page must finish loading")
        XCTAssertTrue(app.navigationBars[title].exists, "Verify the empty state belongs to the target conversation")
        XCTAssertFalse(app.progressIndicators["Loading conversation…"].exists, "A successful empty result is not a request still in flight")
        capture("online-empty-timeline")
        app.terminate()
    }

    func testMembershipRenameThenRemovalUpdatesVisibleConversation() async throws {
        let title = try required("NANO_UI_MEMBER_CHAT_TITLE")
        let renamed = try required("NANO_UI_MEMBER_RENAMED_TITLE")
        let content = try required("NANO_UI_MEMBER_MESSAGE")
        let chatID = try fixtureID("NANO_UI_MEMBER_CHAT_ID")
        let userID = try fixtureID("NANO_UI_MEMBER_USER_ID")
        app.launch()
        let chat = app.staticTexts[title].firstMatch
        XCTAssertTrue(chat.waitForExistence(timeout: 20), "The joined fixture group must be present before changing membership")
        chat.tap()
        XCTAssertTrue(message(content).waitForExistence(timeout: 15))
        capture("membership-before-rename")

        // A second synthetic member changes the real server while this client remains open.
        // This exercises its WebSocket/access-check path, not a local store injection.
        try await fixtureChange("/im/v1/conversations/\(chatID)", method: "PATCH", body: ["title": renamed], status: 200)
        XCTAssertTrue(app.navigationBars[renamed].waitForExistence(timeout: 15))
        XCTAssertTrue(message(content).waitForExistence(timeout: 5), "A harmless membership change must retain the complete timeline")
        XCTAssertFalse(app.staticTexts["This conversation is no longer accessible."].exists)
        capture("membership-after-rename")

        try await fixtureChange("/im/v1/conversations/\(chatID)/participants/\(userID)", method: "DELETE", status: 204)
        XCTAssertTrue(app.staticTexts["This conversation is no longer accessible."].waitForExistence(timeout: 15))
        let hidden = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: message(content))
        await fulfillment(of: [hidden], timeout: 5)
        capture("membership-revoked-timeline")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertFalse(app.staticTexts[renamed].exists, "The revoked group must also leave the list")
        capture("membership-revoked-list")
        app.terminate()
    }

    func testRevokedConversationStaysAbsentOnOfflineRelaunch() throws {
        let retained = try required("NANO_UI_CHAT_TITLE")
        let revoked = try required("NANO_UI_MEMBER_RENAMED_TITLE")
        app.launch()
        XCTAssertTrue(app.staticTexts[retained].firstMatch.waitForExistence(timeout: 5), "The same user's other cached group must still load offline")
        XCTAssertFalse(app.textFields["Enter your username"].exists)
        XCTAssertFalse(app.staticTexts[revoked].exists, "A known revoked group must not return from disk")
        XCTAssertFalse(message(try required("NANO_UI_MEMBER_MESSAGE")).exists)
        capture("membership-revoked-offline-list")
        app.terminate()
    }

    private func fixtureID(_ name: String) throws -> String {
        let value = try required(name)
        XCTAssertTrue(value.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "_") }, "Use only a dedicated fixture identifier")
        return value
    }

    private func fixtureChange(_ path: String, method: String, body: [String: String]? = nil, status: Int) async throws {
        let origin = try required("NANO_UI_ORIGIN")
        let url = try XCTUnwrap(URL(string: origin + path))
        XCTAssertEqual(url.scheme, "http")
        XCTAssertEqual(url.host, "127.0.0.1", "Fixture mutations must never target a public or production service")
        XCTAssertNotNil(url.port)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 10
        request.setValue("Bearer " + (try required("NANO_UI_FIXTURE_OPERATOR_TOKEN")), forHTTPHeaderField: "Authorization")
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (_, response) = try await URLSession.shared.data(for: request)
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, status, "The real fixture operation must succeed before checking its UI consequence")
    }

    private func resetOwnedSessionForLogin() throws {
        // An interrupted prime can leave this dedicated fixture signed in. Use the
        // public sign-out flow, never erase a simulator or bypass genuine login.
        if app.textFields["Enter your username"].waitForExistence(timeout: 10) { return }
        let me = app.tabBars.buttons["Me"]
        XCTAssertTrue(me.waitForExistence(timeout: 10), "Only reset the dedicated fixture's visible session")
        me.tap()
        let identity = app.staticTexts["@" + (try required("NANO_UI_USERNAME"))]
        XCTAssertTrue(identity.waitForExistence(timeout: 10), "Do not sign out an unexpected account")
        app.buttons["Sign out"].tap()
        let confirmation = app.sheets.buttons["Sign out"]
        XCTAssertTrue(confirmation.waitForExistence(timeout: 5), "The normal sign-out confirmation must be visible")
        confirmation.tap()
    }

    private func message(_ content: String) -> XCUIElement {
        app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", content)).firstMatch
    }

    private func required(_ name: String) throws -> String {
        guard let value = ProcessInfo.processInfo.environment[name], !value.isEmpty else {
            XCTFail("Missing isolated native journey input: \(name)")
            throw NSError(domain: "NanoIMUITests", code: 1)
        }
        return value
    }

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
