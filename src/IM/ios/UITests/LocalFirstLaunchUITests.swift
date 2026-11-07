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
