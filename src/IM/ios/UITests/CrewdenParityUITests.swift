import XCTest

/// Exercises the installed app against the dedicated, loopback IM prepared by the test host.
@MainActor
final class CrewdenParityUITests: XCTestCase {
    private let app = XCUIApplication()
    private func required(_ name: String) throws -> String {
        try XCTUnwrap(ProcessInfo.processInfo.environment[name], "Missing isolated fixture \(name)")
    }
    private func launch() throws {
        continueAfterFailure = false
        let origin = try required("NANO_UI_ORIGIN")
        let url = try XCTUnwrap(URL(string: origin))
        XCTAssertEqual(url.host, "127.0.0.1")
        XCTAssertGreaterThan(try XCTUnwrap(url.port), 1024)
        app.launchEnvironment["NANO_IM_BASE_URL"] = origin
        app.launchArguments = ["-nano.locale", "zh"]
        app.launch()
        let username = app.textFields["输入用户名"]
        if username.waitForExistence(timeout: 3) {
            capture("crewden-sign-in")
            username.tap(); username.typeText(try required("NANO_UI_USERNAME"))
            let password = app.secureTextFields["输入密码"]
            password.tap(); password.typeText(try required("NANO_UI_PASSWORD"))
            app.buttons["登录"].tap()
        }
    }
    private func capture(_ name: String) {
        let a = XCTAttachment(screenshot: app.screenshot()); a.name = name; a.lifetime = .keepAlways; add(a)
    }
    func testCreateAssistantAndEditFirstDraft() throws {
        try launch()
        let setup = app.buttons["assistant.setup.entry"]
        XCTAssertTrue(setup.waitForExistence(timeout: 15))
        setup.tap()
        let submit = app.buttons["assistant.setup.submit"]
        XCTAssertTrue(submit.waitForExistence(timeout: 30))
        capture("crewden-create-pa")
        submit.tap()
        let suggestion = app.buttons["找到第一步"]
        XCTAssertTrue(suggestion.waitForExistence(timeout: 60))
        capture("crewden-first-chat")
        suggestion.tap()
        XCTAssertTrue((app.textViews.firstMatch.value as? String)?.contains("第一步") == true)
        XCTAssertTrue(app.buttons["发送"].isEnabled)
    }
    func testFindAndQuoteHistoricalMessage() throws {
        try launch()
        let title = try required("NANO_UI_CHAT_TITLE")
        XCTAssertTrue(app.staticTexts[title].firstMatch.waitForExistence(timeout: 20))
        capture("crewden-inbox")
        let query = try required("NANO_UI_SEARCH_QUERY")
        let field = app.textFields["搜索聊天"]
        field.tap(); field.typeText(query)
        let result = app.buttons.containing(NSPredicate(format: "label CONTAINS %@", query)).matching(NSPredicate(format: "label CONTAINS %@", title)).firstMatch
        XCTAssertTrue(result.waitForExistence(timeout: 15))
        result.tap()
        let message = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", query)).firstMatch
        XCTAssertTrue(message.waitForExistence(timeout: 15))
        capture("crewden-group-chat")
        message.press(forDuration: 0.8)
        let quote = app.buttons["引用"]
        XCTAssertTrue(quote.waitForExistence(timeout: 5))
        capture("crewden-message-actions")
        quote.tap()
        XCTAssertTrue(app.buttons["取消引用"].waitForExistence(timeout: 5))
        let editor = app.textViews.firstMatch
        editor.tap(); editor.typeText(try required("NANO_UI_REPLY_TEXT"))
        capture("crewden-quote-composer")
        app.buttons["发送"].tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", try required("NANO_UI_REPLY_TEXT"))).firstMatch.waitForExistence(timeout: 10))
    }
    func testManagePersonalAssistantExclusions() throws {
        try launch()
        let chatID = try required("NANO_UI_POLICY_CHAT")
        app.tabBars.buttons["智能体"].tap()
        let settings = app.buttons["personal-agent-settings"]
        XCTAssertTrue(settings.waitForExistence(timeout: 20))
        settings.tap()
        let disclosure = app.buttons["pa-exclusions"]
        XCTAssertTrue(disclosure.waitForExistence(timeout: 20))
        disclosure.tap()
        let toggle = app.switches["pa-exclude-" + chatID]
        XCTAssertTrue(toggle.waitForExistence(timeout: 5))
        for expected in ["0", "1"] {
            XCTAssertEqual(toggle.value as? String, expected)
            toggle.tap()
            app.buttons["保存排除范围"].tap()
            XCTAssertTrue(app.staticTexts["已保存"].waitForExistence(timeout: 12))
            capture("crewden-pa-exclusion-" + expected)
            app.navigationBars.buttons.element(boundBy: 0).tap()
            XCTAssertTrue(settings.waitForExistence(timeout: 10))
            settings.tap()
            XCTAssertTrue(disclosure.waitForExistence(timeout: 12))
            disclosure.tap()
        }
        XCTAssertEqual(toggle.value as? String, "0")
    }
}

extension CrewdenParityUITests {
    /// The host resolves these IDs from two real deliveries and a reported child in this stack.
    func testInspectActivityAndTraceAnEarlierDelivery() throws {
        try launch()
        let title = try required("NANO_UI_WORK_CHAT")
        let reply = try required("NANO_UI_WORK_REPLY")
        let session = try required("NANO_UI_WORK_SESSION")
        let turn = try required("NANO_UI_WORK_TURN")
        let child = try required("NANO_UI_WORK_CHILD")
        let chat = app.staticTexts[title].firstMatch
        XCTAssertTrue(chat.waitForExistence(timeout: 20))
        chat.tap()

        let message = app.staticTexts[reply].firstMatch
        XCTAssertTrue(message.waitForExistence(timeout: 15))
        message.press(forDuration: 0.8)
        let openWork = app.buttons["查看这条回复的工作记录"]
        XCTAssertTrue(openWork.waitForExistence(timeout: 5))
        openWork.tap()
        let target = app.descendants(matching: .any)["work.turn." + session + ":" + turn].firstMatch
        XCTAssertTrue(target.waitForExistence(timeout: 15))
        XCTAssertTrue(target.isHittable)
        capture("crewden-focused-delivery")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertTrue(message.waitForExistence(timeout: 10))

        let activity = app.buttons["查看" + title + "的活动"].firstMatch
        XCTAssertTrue(activity.waitForExistence(timeout: 10))
        activity.tap()
        let records = app.buttons["查看工作记录"].firstMatch
        XCTAssertTrue(records.waitForExistence(timeout: 10))
        capture("crewden-agent-activity")
        if !records.isHittable { app.swipeUp() }
        records.tap()
        let delegation = app.segmentedControls.buttons["派工关系"]
        XCTAssertTrue(delegation.waitForExistence(timeout: 10))
        delegation.tap()
        let sessionLink = app.descendants(matching: .any)["work.delegation." + child].firstMatch
        XCTAssertTrue(sessionLink.waitForExistence(timeout: 10))
        if !sessionLink.isHittable { app.swipeUp() }
        capture("crewden-delegation")
        sessionLink.tap()
        XCTAssertTrue(app.staticTexts["执行轮次 · 最新在前"].firstMatch.waitForExistence(timeout: 10)
                      || app.staticTexts["执行信息与上下文"].firstMatch.exists)
        capture("crewden-child-execution")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertTrue(sessionLink.waitForExistence(timeout: 10))
    }
}
