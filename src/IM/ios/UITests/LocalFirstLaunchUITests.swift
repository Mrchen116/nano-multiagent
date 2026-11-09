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

    func testReadExistingFixtureHistory() throws {
        app.launch()
        defer { app.terminate() }
        try openFixtureConversation()
        capture("existing-history-before-offline-revocation")
    }

    func testOfflineRevocationConvergesOnNextOnlineLaunch() async throws {
        let retained = try required("NANO_UI_CHAT_TITLE")
        let revoked = try required("NANO_UI_MEMBER_RENAMED_TITLE")
        let content = try required("NANO_UI_MEMBER_MESSAGE")
        app.launch()
        defer { app.terminate() }
        // The preceding offline phase read this exact group. The host removed access only
        // after that process terminated, so the cached seed cannot already know the change.
        try requireFixture(app.staticTexts[retained].firstMatch.waitForExistence(timeout: 5), "Keep the same account's other cached history visible")
        let absent = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: app.staticTexts[revoked].firstMatch)
        let result = await XCTWaiter.fulfillment(of: [absent], timeout: 15)
        try requireFixture(result == .completed, "The first online launch must converge after a revocation learned while offline")
        try requireFixture(app.staticTexts[retained].firstMatch.exists, "Keep unrelated cached history after the authoritative correction")
        try requireFixture(!app.textFields["Enter your username"].exists, "A group revocation must not sign out the account")
        try requireFixture(!app.staticTexts["No local cache this time"].exists, "Do not mistake degraded network-only mode for durable revocation")
        try requireFixture(!message(content).exists, "The revoked group's preview must not remain visible")
        capture("offline-revocation-converged-list")
    }

    func testCredentialRevocationClearsAnAlreadyVisibleConversation() async throws {
        app.launch()
        defer { app.terminate() }
        try openFixtureConversation()
        capture("credentials-before-server-revocation")
        try await waitForOwnedAccountCredentialsToBeRevoked()
        try requireFixture(app.state == .runningForeground, "The original process must survive the revocation handshake")
        XCUIDevice.shared.press(.home)
        let background = XCTNSPredicateExpectation(predicate: NSPredicate(format: "state == %@ OR state == %@",
            NSNumber(value: XCUIApplication.State.runningBackground.rawValue),
            NSNumber(value: XCUIApplication.State.runningBackgroundSuspended.rawValue)), object: app)
        let backgroundResult = await XCTWaiter.fulfillment(of: [background], timeout: 5)
        try requireFixture(backgroundResult == .completed, "The existing process must reach the background before reactivation")
        // activate() otherwise auto-launches a terminated App, which would silently replace
        // this active-401 journey with the separate cold-reopen case.
        try requireFixture(app.state == .runningBackground || app.state == .runningBackgroundSuspended, "Do not relaunch a process that stopped while backgrounded")
        app.activate()
        try assertRejectedCredentials()
    }

    func testRejectedCredentialsShowLoginWithoutCachedHistory() throws {
        app.launch()
        defer { app.terminate() }
        try assertRejectedCredentials()
    }

    private func assertRejectedCredentials() throws {
        let title = try required("NANO_UI_CHAT_TITLE")
        let content = try required("NANO_UI_MESSAGE")
        // The host revokes only this synthetic account on the owned server. No normal UI
        // sign-out participates: the actual refresh 401 must drive the credentials path.
        try requireFixture(app.textFields["Enter your username"].waitForExistence(timeout: 20), "Rejected credentials must return to the sign-in form")
        try requireFixture(app.secureTextFields["Enter your password"].exists, "Show login, not an account-admission screen")
        try requireFixture(!app.tabBars.buttons["Chats"].exists, "The old signed-in root must stop being displayed")
        try requireFixture(!app.staticTexts[title].exists, "Do not retain the previous account's cached conversation on screen")
        try requireFixture(!message(content).exists, "Do not retain the previous cached message on screen")
        capture("credentials-rejected-login")
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
        capture("pending-before-frozen-content-assertion")
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

    func testPrepareSeparateAccountDraft() throws {
        app.launch()
        defer { app.terminate() }
        try openFixtureConversation()
        let composer = app.textViews["Message"]
        try requireFixture(composer.waitForExistence(timeout: 5), "Use the previous account's real composer")
        let draft = try required("NANO_UI_DRAFT_CONTENT")
        composer.tap(); composer.typeText(draft)
        try requireFixture(composer.value as? String == draft, "Keep the complete separate draft before account switching")
        capture("account-a-separate-draft")
        app.navigationBars.buttons.element(boundBy: 0).tap()
    }

    func testSwitchAccountIsolatesPreviousContentAndPersistsNewMessages() async throws {
        app.launch()
        defer { app.terminate() }
        let previousTitle = try required("NANO_UI_PREVIOUS_CHAT_TITLE")
        let previousPending = try required("NANO_UI_PREVIOUS_PENDING_CONTENT")
        let previousDraftTitle = try required("NANO_UI_PREVIOUS_DRAFT_CHAT_TITLE")
        let previousDraft = try required("NANO_UI_PREVIOUS_DRAFT_CONTENT")
        let previousChat = app.staticTexts[previousTitle].firstMatch
        try requireFixture(previousChat.waitForExistence(timeout: 20), "First prove the previous account's pending conversation exists")
        previousChat.tap()
        try requireFixture(app.staticTexts["Awaiting delivery confirmation"].waitForExistence(timeout: 10), "Do not test isolation without a genuine previous pending attempt")
        try requireFixture(app.textViews["Message"].value as? String == previousPending, "Prove the complete previous frozen pending content")
        capture("account-a-pending-before-switch")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        let draftChat = app.staticTexts[previousDraftTitle].firstMatch
        try requireFixture(draftChat.waitForExistence(timeout: 5), "Keep the previous draft in its separate real conversation")
        draftChat.tap()
        try requireFixture(app.textViews["Message"].waitForExistence(timeout: 5), "Read the previous account's persisted composer")
        try requireFixture(app.textViews["Message"].value as? String == previousDraft, "Prove the previous draft survived process termination")
        capture("account-a-draft-before-switch")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        try resetOwnedSessionForLogin()
        try signInFixture()
        try requireFixture(app.staticTexts[try required("NANO_UI_CHAT_TITLE")].firstMatch.waitForExistence(timeout: 20), "The new account's own list must arrive before checking isolation")
        try assertPreviousAccountAbsent()
        capture("account-b-isolated-list")
        try openFixtureConversation()
        try assertPreviousAccountAbsent()
        let composer = app.textViews["Message"]
        try requireFixture(composer.waitForExistence(timeout: 5), "The new account must have its own composer")
        try requireFixture(composer.value as? String == "", "Do not inherit the previous account's draft or frozen content")
        let sent = try required("NANO_UI_SENT_MESSAGE")
        composer.tap(); composer.typeText(sent)
        try requireFixture(composer.value as? String == sent && app.buttons["Send"].isEnabled, "Send the complete new account message through the public composer")
        app.buttons["Send"].tap()
        try requireFixture(message(sent).waitForExistence(timeout: 15), "The new account's explicit Send must produce its complete message")
        let received = try required("NANO_UI_RECEIVED_MESSAGE")
        let peer = try fixtureID("NANO_UI_FIXTURE_PEER_USER_ID")
        let chatID = try fixtureID("NANO_UI_CHAT_ID")
        try await fixtureChange("/im/v1/conversations/\(chatID)/messages", method: "POST", body: [
            "sender": ["type": "user", "id": peer], "content": received,
            "attachments": [], "client_msg_id": UUID().uuidString,
        ], status: 201)
        try requireFixture(message(received).waitForExistence(timeout: 15), "Receive the peer's complete real message during this login session")
        try requireFixture(!app.staticTexts["Awaiting delivery confirmation"].exists, "A confirmed new-account send must not inherit the previous pending state")
        capture("account-b-new-send-and-receive")
    }

    func testNewAccountOfflineRelaunchKeepsOnlyItsOwnMessages() throws {
        app.launch()
        defer { app.terminate() }
        let title = try required("NANO_UI_CHAT_TITLE")
        let chat = app.staticTexts[title].firstMatch
        try requireFixture(chat.waitForExistence(timeout: 5), "The new account's cached list must load with its origin stopped")
        try assertPreviousAccountAbsent()
        capture("account-b-offline-list")
        chat.tap()
        try requireFixture(message(try required("NANO_UI_SENT_MESSAGE")).waitForExistence(timeout: 5), "Keep the complete message sent in the new account session")
        try requireFixture(message(try required("NANO_UI_RECEIVED_MESSAGE")).waitForExistence(timeout: 5), "Keep the complete message received in the new account session")
        try requireFixture(!app.textFields["Enter your username"].exists, "An offline origin must not sign out the new account")
        try requireFixture(app.textViews["Message"].value as? String == "", "Do not restore either previous composer value offline")
        try assertPreviousAccountAbsent()
        capture("account-b-offline-full-messages")
    }

    func testSwitchServiceThroughConnectionSettings() throws {
        app.launch()
        defer { app.terminate() }
        let oldTitle = try required("NANO_UI_CHAT_TITLE")
        try requireFixture(app.staticTexts[oldTitle].firstMatch.waitForExistence(timeout: 20), "Begin with the known primary service account")
        try resetOwnedSessionForLogin()
        let settings = app.buttons["Connection settings"]
        try requireFixture(settings.waitForExistence(timeout: 5), "Switch the server through the real authentication settings")
        settings.tap()
        let server = app.textFields["Server URL"]
        try requireFixture(server.waitForExistence(timeout: 5), "Use the editable server URL field")
        let current = server.value as? String ?? ""
        try requireFixture(current == (try required("NANO_UI_ORIGIN")) || current == (try required("NANO_UI_ORIGIN")) + "/", "Only replace this matrix's known primary origin")
        // Tap past the visible short loopback URL so deletion begins at its end,
        // rather than guessing where a center tap positions the insertion point.
        server.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)).tap()
        server.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: current.count))
        server.typeText(try required("NANO_UI_SECOND_ORIGIN"))
        try requireFixture(server.value as? String == (try required("NANO_UI_SECOND_ORIGIN")), "Preserve the complete isolated second origin")
        try signInFixture()
        try requireFixture(app.staticTexts[try required("NANO_UI_SECOND_CHAT_TITLE")].firstMatch.waitForExistence(timeout: 20), "The second service must authenticate this same username and supply its own list")
        try assertSecondServiceContent()
        capture("same-username-second-service")
    }

    func testPersistedSecondServiceSurvivesOfflineReopen() throws {
        // The previous test saved this value through AuthView. Remove only the Debug
        // override; setting the second origin here would hide a broken saved preference.
        app.launchEnvironment.removeValue(forKey: "NANO_IM_BASE_URL")
        app.launch()
        defer { app.terminate() }
        try assertSecondServiceContent()
        capture("persisted-second-service-offline-reopen")
    }

    private func assertPreviousAccountAbsent() throws {
        for key in ["NANO_UI_PREVIOUS_CHAT_TITLE", "NANO_UI_PREVIOUS_DRAFT_CHAT_TITLE", "NANO_UI_PREVIOUS_MESSAGE", "NANO_UI_PREVIOUS_PENDING_CONTENT", "NANO_UI_PREVIOUS_DRAFT_CONTENT"] {
            try requireFixture(!message(try required(key)).exists, "Do not expose previous-account content: \(key)")
        }
        try requireFixture(!app.staticTexts["Awaiting delivery confirmation"].exists, "Do not expose a previous-account pending state")
        try requireFixture(!app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "unconfirmed sends")).firstMatch.exists, "Do not inherit any previous pending-only count")
    }

    private func assertSecondServiceContent() throws {
        let title = try required("NANO_UI_SECOND_CHAT_TITLE")
        let chat = app.staticTexts[title].firstMatch
        try requireFixture(chat.waitForExistence(timeout: 5), "The saved second service must provide its own cached conversation")
        try requireFixture(!app.staticTexts[try required("NANO_UI_CHAT_TITLE")].exists, "The primary service's conversation must not appear on the second service")
        try assertPreviousAccountAbsent()
        chat.tap()
        try requireFixture(message(try required("NANO_UI_SECOND_MESSAGE")).waitForExistence(timeout: 5), "Read the complete content belonging only to the second service")
        try requireFixture(!message(try required("NANO_UI_SENT_MESSAGE")).exists && !message(try required("NANO_UI_RECEIVED_MESSAGE")).exists, "The same username must not merge content across services")
        try requireFixture(app.textViews["Message"].value as? String == "", "Do not import a composer across services")
    }

    func testPrimeRealExecutionForPermanentCleanup() throws {
        app.launch()
        defer { app.terminate() }
        try signInFixture()
        try openFixtureConversation()
        let composer = app.textViews["Message"]
        composer.tap(); composer.typeText(try required("NANO_UI_CLEANUP_TASK"))
        app.buttons["Send"].tap()
        let reply = message(try required("NANO_UI_CLEANUP_REPLY"))
        try requireFixture(reply.waitForExistence(timeout: 150), "The synthetic Sol agent must actually read the owned fixture and reply")
        let process = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Process (")).firstMatch
        try requireFixture(process.waitForExistence(timeout: 15), "Prime real execution details, not merely synthetic ordinary text")
        process.tap()
        capture("cleanup-real-execution-before")
        // This phase ends the process; it does not assert preservation of a reading anchor.
    }

    func testPermanentCleanupWhileCandidateConversationRemainsOpen() async throws {
        let agent = try fixtureID("NANO_UI_CLEANUP_AGENT_ID")
        let displayName = try required("NANO_UI_CLEANUP_AGENT_NAME")
        app.launch()
        defer { app.terminate() }
        let candidateTitle = try required("NANO_UI_CANDIDATE_CHAT_TITLE")
        let candidate = app.staticTexts[candidateTitle].firstMatch
        try requireFixture(candidate.waitForExistence(timeout: 15), "The separate candidate conversation must be available")
        candidate.tap()
        let composer = app.textViews["Message"]
        // Completion tokens cannot contain whitespace; the immutable Agent ID is a valid unique query.
        let mentionQuery = "@" + agent
        composer.tap(); composer.typeText(mentionQuery)
        try requireFixture(composer.value as? String == mentionQuery, "Use the fixture's exact Agent ID as the mention query")
        try requireFixture(app.staticTexts[displayName].firstMatch.waitForExistence(timeout: 5), "The soon-to-be-deleted member must positively exist as a mention candidate")
        capture("cleanup-candidate-before")

        let lifecycle = try await fixtureJSON("/im/v1/agents/\(agent)/lifecycle")
        let revision = try XCTUnwrap(lifecycle["revision"] as? Int)
        try await fixtureChange("/im/v1/agents/\(agent)/lifecycle", method: "PUT",
                                body: ["request_id": "cleanup714-stop", "enabled": false, "expected_revision": revision], status: 202)
        var stopped = false
        let stopDeadline = Date().addingTimeInterval(40)
        while Date() < stopDeadline {
            let state = try await fixtureJSON("/im/v1/agents/\(agent)/lifecycle")
            if state["desired"] as? String == "disabled", state["observed"] as? String == "disabled",
               state["applied_revision"] as? Int == state["revision"] as? Int { stopped = true; break }
            try await Task.sleep(for: .milliseconds(250))
        }
        try requireFixture(stopped, "The real owning Node must confirm stop before deletion")
        let scope = try await fixtureJSON("/im/v1/agents/\(agent)/deletion")
        try requireFixture(scope["eligible"] as? Bool == true, "Only the owned synthetic Agent is eligible")
        try await fixtureChange("/im/v1/agents/\(agent)/deletion", method: "POST", body: [
            "request_id": "cleanup714-delete", "expected_revision": try XCTUnwrap(scope["revision"] as? Int),
            "expected_profile_version": try XCTUnwrap(scope["profile_version"] as? Int)
        ], status: 202)
        var deleted = false
        let deleteDeadline = Date().addingTimeInterval(60)
        while Date() < deleteDeadline {
            let state = try await fixtureJSON("/im/v1/agents/\(agent)/deletion")
            if (state["operation"] as? [String: Any])?["state"] as? String == "deleted" { deleted = true; break }
            try await Task.sleep(for: .milliseconds(250))
        }
        try requireFixture(deleted, "Actual Node cleanup must complete; a submitted request is not success")
        try requireFixture(app.staticTexts["No matching members"].waitForExistence(timeout: 20), "An already open conversation must stop offering the deleted Agent")
        capture("cleanup-candidate-after")
        // This fixture proves mention removal, not command removal without a loaded-command positive control.
        composer.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: mentionQuery.count))
        app.navigationBars.buttons.element(boundBy: 0).tap()
        let chat = app.staticTexts[try required("NANO_UI_CHAT_TITLE")].firstMatch
        try requireFixture(chat.waitForExistence(timeout: 10), "Cleanup preserves access and conversation identity")
        chat.tap()
        try assertExecutionCleaned()
        capture("cleanup-online-timeline-after")
    }

    func testOfflineRelaunchCannotReviveDeletedExecution() throws {
        app.launch()
        defer { app.terminate() }
        let chat = app.staticTexts[try required("NANO_UI_CHAT_TITLE")].firstMatch
        try requireFixture(chat.waitForExistence(timeout: 5), "The cleaned conversation remains available from disk")
        try requireFixture(!app.textFields["Enter your username"].exists, "Offline cleanup is not an account sign-out")
        capture("cleanup-offline-list")
        chat.tap()
        try assertExecutionCleaned()
        capture("cleanup-offline-timeline")
    }

    private func assertExecutionCleaned() throws {
        let reply = message(try required("NANO_UI_CLEANUP_REPLY"))
        for _ in 0..<6 {
            if reply.exists && reply.isHittable { break }
            app.scrollViews.firstMatch.swipeUp()
        }
        try requireFixture(reply.waitForExistence(timeout: 10) && reply.isHittable, "Retain the full ordinary Agent reply visibly after execution cleanup")
        try requireFixture(!app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Process (")).firstMatch.exists,
                           "Old thinking and tool process must not reappear beside the retained reply")
        let ordinary = message(try required("NANO_UI_MESSAGE"))
        for _ in 0..<10 {
            if ordinary.exists && ordinary.isHittable { break }
            app.scrollViews.firstMatch.swipeDown()
        }
        try requireFixture(ordinary.exists && ordinary.isHittable, "Keep earlier ordinary chat history visibly readable as well as the latest reply")
    }

    private func fixtureJSON(_ path: String) async throws -> [String: Any] {
        let origin = try required("NANO_UI_ORIGIN")
        let url = try XCTUnwrap(URL(string: origin + path))
        try requireFixture(url.scheme == "http" && url.host == "127.0.0.1" && url.port != nil, "Only query the owned loopback fixture")
        var request = URLRequest(url: url)
        request.timeoutInterval = 15
        request.setValue("Bearer " + (try required("NANO_UI_FIXTURE_OPERATOR_TOKEN")), forHTTPHeaderField: "Authorization")
        let (data, response) = try await URLSession.shared.data(for: request)
        try requireFixture((response as? HTTPURLResponse)?.statusCode == 200, "Read the real fixture's business status")
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
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

    private func waitForOwnedAccountCredentialsToBeRevoked() async throws {
        let origin = try required("NANO_UI_ORIGIN")
        let url = try XCTUnwrap(URL(string: origin + "/im/v1/auth/me"))
        try requireFixture(url.scheme == "http" && url.host == "127.0.0.1" && url.port != nil, "Only coordinate an owned loopback account")
        var request = URLRequest(url: url)
        request.timeoutInterval = 2
        request.setValue("Bearer " + (try required("NANO_UI_FIXTURE_ACCOUNT_ACCESS_TOKEN")), forHTTPHeaderField: "Authorization")
        let (_, initial) = try await URLSession.shared.data(for: request)
        try requireFixture((initial as? HTTPURLResponse)?.statusCode == 200, "Confirm the synthetic account is valid before requesting revocation")
        let run = try fixtureID("NANO_UI_REVOKE_RUN_ID")
        FileHandle.standardOutput.write(Data("NANO_UI_READY_TO_REVOKE_OWNED_ACCOUNT:\(run)\n".utf8))
        let deadline = Date().addingTimeInterval(30)
        while Date() < deadline {
            try Task.checkCancellation()
            let (_, response) = try await URLSession.shared.data(for: request)
            let status = (response as? HTTPURLResponse)?.statusCode
            if status == 401 { return }
            try requireFixture(status == 200, "Only an actual credential rejection is the revocation handshake")
            try await Task.sleep(for: .milliseconds(200))
        }
        try requireFixture(false, "The host must revoke the owned account before testing the App's refresh path")
    }

    private func fixtureID(_ name: String) throws -> String {
        let value = try required(name)
        try requireFixture(value.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "_") }, "Use only a dedicated fixture identifier")
        return value
    }

    private func fixtureChange(_ path: String, method: String, body: [String: Any]? = nil, status: Int) async throws {
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

    private func requireFixture(_ condition: @autoclosure () throws -> Bool, _ reason: String,
                                file: StaticString = #filePath, line: UInt = #line) throws {
        // XCTest's async failure recording can return to the method even with
        // continueAfterFailure=false. A thrown error also prevents later fixture writes.
        guard try condition() else {
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
