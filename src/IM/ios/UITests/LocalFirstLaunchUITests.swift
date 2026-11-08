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
        defer { app.terminate() }
        let chat = app.staticTexts[title].firstMatch
        try requireFixture(chat.waitForExistence(timeout: 20), "The joined fixture group must be present before changing membership")
        chat.tap()
        try requireFixture(message(content).waitForExistence(timeout: 15), "The original complete fixture message must be visible")
        capture("membership-before-rename")

        // A second synthetic member changes the real server while this client remains open.
        // This exercises its WebSocket/access-check path, not a local store injection.
        try await fixtureChange("/im/v1/conversations/\(chatID)", method: "PATCH", body: ["title": renamed], status: 200)
        try requireFixture(app.navigationBars[renamed].waitForExistence(timeout: 15), "The renamed title must reach the visible conversation")
        try requireFixture(message(content).waitForExistence(timeout: 5), "A harmless membership change must retain the complete timeline")
        try requireFixture(!app.staticTexts["This conversation is no longer accessible."].exists, "A rename is not a revocation")
        capture("membership-after-rename")

        try await fixtureChange("/im/v1/conversations/\(chatID)/participants/\(userID)", method: "DELETE", status: 204)
        try requireFixture(app.staticTexts["This conversation is no longer accessible."].waitForExistence(timeout: 15), "Removal must report that access is revoked")
        let hidden = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: message(content))
        let hiddenResult = await XCTWaiter.fulfillment(of: [hidden], timeout: 5)
        try requireFixture(hiddenResult == .completed, "Revoked message content must stop being visible")
        try requireFixture(!app.staticTexts["A connection is needed to read this conversation"].exists, "A confirmed revocation must not suggest that reconnecting restores access")
        try requireFixture(!app.buttons["Retry"].exists, "Do not offer the missing-cache retry after access is revoked")
        capture("membership-revoked-timeline")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        try requireFixture(!app.staticTexts[renamed].exists, "The revoked group must also leave the list")
        capture("membership-revoked-list")
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

    func testSubmitUnconfirmedSendAfterOriginStops() async throws {
        let content = try required("NANO_UI_PENDING_CONTENT")
        app.launch()
        defer { app.terminate() }
        if ProcessInfo.processInfo.environment["NANO_UI_RESET_OWNED_SESSION"] == "1" {
            try resetOwnedSessionForLogin()
        }
        if ProcessInfo.processInfo.environment["NANO_UI_SIGN_IN"] == "1" {
            try signInFixture()
        }
        try openFixtureConversation()
        let composer = app.textViews["Message"]
        try requireFixture(composer.waitForExistence(timeout: 5), "Use the real editable message composer")
        try requireFixture(!app.staticTexts["Awaiting delivery confirmation"].exists, "Do not replace an existing pending attempt")
        composer.tap(); composer.typeText(content)
        try requireFixture(composer.value as? String == content, "Preserve the complete pending content")
        try requireFixture(app.buttons["Send"].isEnabled, "The user must explicitly submit the prepared content")
        capture("pending-ready-to-stop-origin")
        try await waitForOwnedOriginToStop()
        app.buttons["Send"].tap()
        try requireFixture(app.staticTexts["Awaiting delivery confirmation"].waitForExistence(timeout: 15), "The failed submission must remain visibly unconfirmed")
        try requireFixture(app.buttons["Retry"].exists, "Only an explicit retry may advance this attempt")
        try requireFixture(composer.value as? String == content, "The frozen content must remain visible in the composer")
        capture("pending-after-transport-failure")
    }

    func testUpgradeOfflineShowsPendingBeforeConversationRows() throws {
        app.launch()
        defer { app.terminate() }
        let notice = app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "1 unconfirmed sends")).firstMatch
        try requireFixture(notice.waitForExistence(timeout: 5), "A real legacy attempt must be imported before the first successful sync")
        try requireFixture(app.staticTexts["Checked once connected: sends in conversations you can still access stay visible, the rest are cleared."].exists, "Explain the pending-only state without inventing a conversation")
        try requireFixture(!app.textFields["Enter your username"].exists, "An unreachable service is not a sign-out")
        let title = try required("NANO_UI_CHAT_TITLE")
        try requireFixture(!app.staticTexts[title].exists, "A pending-only migration must not invent a placeholder conversation")
        capture("upgrade-offline-pending-count")
    }

    func testRecoveredPendingWaitsForExplicitRetry() throws {
        app.launch()
        defer { app.terminate() }
        try openFixtureConversation()
        try assertPendingFixture()
        capture("upgrade-online-pending-unchanged")
    }

    func testExplicitRetryCompletesTheRecoveredSend() throws {
        let content = try required("NANO_UI_PENDING_CONTENT")
        app.launch()
        defer { app.terminate() }
        try openFixtureConversation()
        try assertPendingFixture()
        app.buttons["Retry"].tap()
        try requireFixture(message(content).waitForExistence(timeout: 15), "Explicit retry must deliver the original complete content")
        try requireFixture(!app.staticTexts["Awaiting delivery confirmation"].exists, "A confirmed send must no longer be pending")
        try requireFixture(app.textViews["Message"].value as? String == "", "The confirmed frozen content must leave the composer")
        capture("upgrade-explicit-retry-confirmed")
    }

    private func signInFixture() throws {
        let username = app.textFields["Enter your username"]
        try requireFixture(username.waitForExistence(timeout: 10), "Begin with the dedicated fixture's sign-in form")
        username.tap(); username.typeText(try required("NANO_UI_USERNAME"))
        let password = app.secureTextFields["Enter your password"]
        password.tap(); password.typeText(try required("NANO_UI_PASSWORD"))
        app.buttons["Sign in"].tap()
    }

    private func openFixtureConversation() throws {
        let title = try required("NANO_UI_CHAT_TITLE")
        let chat = app.staticTexts[title].firstMatch
        try requireFixture(chat.waitForExistence(timeout: 20), "The real service must supply this fixture conversation")
        chat.tap()
        try requireFixture(app.navigationBars[title].waitForExistence(timeout: 5), "Open the intended conversation")
        let content = try required("NANO_UI_MESSAGE")
        try requireFixture(message(content).waitForExistence(timeout: 15), "Read the complete existing fixture message")
    }

    private func assertPendingFixture() throws {
        let content = try required("NANO_UI_PENDING_CONTENT")
        try requireFixture(app.staticTexts["Awaiting delivery confirmation"].waitForExistence(timeout: 10), "Recovery must not automatically resend an unconfirmed attempt")
        try requireFixture(app.buttons["Retry"].exists, "Preserve the explicit recovery action")
        try requireFixture(app.textViews["Message"].value as? String == content, "Recover the complete immutable content")
        try requireFixture(!app.buttons["Send"].isEnabled, "Do not offer a second ordinary send for a pending attempt")
        try requireFixture(!app.buttons["Remove attachment"].exists, "This text-only fixture must retain its empty attachment set")
    }

    private func waitForOwnedOriginToStop() async throws {
        let origin = try required("NANO_UI_ORIGIN")
        let url = try XCTUnwrap(URL(string: origin + "/health"))
        try requireFixture(url.scheme == "http" && url.host == "127.0.0.1" && url.port != nil, "Only coordinate an owned loopback fixture")
        var request = URLRequest(url: url)
        request.timeoutInterval = 1
        let (_, response) = try await URLSession.shared.data(for: request)
        try requireFixture((response as? HTTPURLResponse)?.statusCode == 200, "Confirm the same origin is healthy before requesting its stop")
        let run = try fixtureID("NANO_UI_STOP_RUN_ID")
        // A flushed, run-bound marker lets the host stop only its verified fixture process.
        // An attachment name alone is not a reliable real-time synchronization signal.
        FileHandle.standardOutput.write(Data("NANO_UI_READY_TO_STOP_OWNED_ORIGIN:\(run)\n".utf8))
        let deadline = Date().addingTimeInterval(30)
        while Date() < deadline {
            try Task.checkCancellation()
            do { _ = try await URLSession.shared.data(for: request) }
            catch let error as URLError where [.cannotConnectToHost, .networkConnectionLost].contains(error.code) { return }
            catch { if error is CancellationError { throw error } }
            try await Task.sleep(for: .milliseconds(200))
        }
        try requireFixture(false, "The owned origin must become transport-unreachable before Send is tapped")
    }

    private func fixtureID(_ name: String) throws -> String {
        let value = try required(name)
        try requireFixture(value.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "_") }, "Use only a dedicated fixture identifier")
        return value
    }

    private func fixtureChange(_ path: String, method: String, body: [String: String]? = nil, status: Int) async throws {
        let origin = try required("NANO_UI_ORIGIN")
        let url = try XCTUnwrap(URL(string: origin + path))
        try requireFixture(url.scheme == "http" && url.host == "127.0.0.1" && url.port != nil,
                           "Fixture mutations must only target a dedicated HTTP loopback port")
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 10
        request.setValue("Bearer " + (try required("NANO_UI_FIXTURE_OPERATOR_TOKEN")), forHTTPHeaderField: "Authorization")
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (_, response) = try await URLSession.shared.data(for: request)
        try requireFixture((response as? HTTPURLResponse)?.statusCode == status, "The real fixture operation must succeed before checking its UI consequence")
    }

    private func requireFixture(_ condition: @autoclosure () -> Bool, _ reason: String,
                                file: StaticString = #filePath, line: UInt = #line) throws {
        // XCTest's async failure recording can return to the method even with
        // continueAfterFailure=false. A thrown error also prevents later fixture writes.
        guard condition() else {
            XCTFail(reason, file: file, line: line)
            throw NSError(domain: "NanoIMUITests", code: 2, userInfo: [NSLocalizedDescriptionKey: reason])
        }
    }

    private func resetOwnedSessionForLogin() throws {
        // An interrupted prime can leave this dedicated fixture signed in. Use the
        // public sign-out flow, never erase a simulator or bypass genuine login.
        if app.textFields["Enter your username"].waitForExistence(timeout: 10) { return }
        let me = app.tabBars.buttons["Me"]
        try requireFixture(me.waitForExistence(timeout: 10), "Only reset the dedicated fixture's visible session")
        me.tap()
        let expected = try ProcessInfo.processInfo.environment["NANO_UI_RESET_USERNAME"] ?? required("NANO_UI_USERNAME")
        let identity = app.staticTexts["@" + expected]
        try requireFixture(identity.waitForExistence(timeout: 10), "Do not sign out an unexpected account")
        app.buttons["Sign out"].tap()
        let confirmation = app.sheets.buttons["Sign out"]
        try requireFixture(confirmation.waitForExistence(timeout: 5), "The normal sign-out confirmation must be visible")
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
