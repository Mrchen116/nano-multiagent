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
