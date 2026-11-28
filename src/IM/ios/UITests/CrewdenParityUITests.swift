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
    func testBrowseGroupDetailsAndPersonalSpace() throws {
        try launch()
        let group = try required("NANO_UI_CHAT_TITLE")
        let groupRow = app.staticTexts[group].firstMatch
        XCTAssertTrue(groupRow.waitForExistence(timeout: 20))
        groupRow.tap()
        app.buttons["聊天详情"].tap()
        XCTAssertTrue(app.switches["置顶聊天"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["移除"].exists)
        capture("crewden-group-details")
        app.buttons["更多聊天选项"].tap()
        app.buttons["修改名称"].tap()
        XCTAssertEqual(app.textFields["名称"].value as? String, group)
        app.buttons["取消"].tap()
        app.navigationBars.buttons.element(boundBy: 0).tap()
        app.navigationBars.buttons.element(boundBy: 0).tap()
        app.tabBars.buttons["我的"].tap()
        XCTAssertTrue(app.buttons.containing(NSPredicate(format: "label CONTAINS %@", "我的电脑")).firstMatch.waitForExistence(timeout: 10))
        capture("crewden-personal-space")
        app.buttons["设置"].tap()
        XCTAssertTrue(app.buttons["个人资料与语言"].exists)
        XCTAssertTrue(app.buttons["模型服务"].exists)
    }

    func testDailyNavigation() throws {
        try launch()
        let newChat = app.buttons["新建聊天"]
        XCTAssertTrue(newChat.waitForExistence(timeout: 20))
        capture("crewden-chat-list")
        newChat.tap()
        app.segmentedControls.buttons["群聊"].tap()
        XCTAssertTrue(app.textFields["群名称（可选）"].exists)
        app.segmentedControls.buttons["私聊"].tap()
        let person = app.buttons.containing(NSPredicate(format: "label CONTAINS %@", try required("NANO_UI_CONTACT_NAME"))).firstMatch
        XCTAssertTrue(person.waitForExistence(timeout: 15))
        capture("crewden-new-chat")
        person.tap()
        XCTAssertTrue(app.buttons["聊天详情"].waitForExistence(timeout: 15))
        app.navigationBars.buttons.element(boundBy: 0).tap()
        app.tabBars.buttons["任务"].tap()
        XCTAssertTrue(app.buttons["创建根任务"].waitForExistence(timeout: 10))
        capture("crewden-tasks")
        app.buttons["创建根任务"].tap()
        XCTAssertTrue(app.navigationBars["创建任务"].waitForExistence(timeout: 10))
        capture("crewden-task-editor")
        app.buttons["取消"].tap()
        app.tabBars.buttons["助手"].tap()
        let profile = app.buttons.containing(NSPredicate(format: "label CONTAINS %@", try required("NANO_UI_AGENT_NAME"))).firstMatch
        XCTAssertTrue(profile.waitForExistence(timeout: 15))
        capture("crewden-assistants")
        profile.tap()
        XCTAssertTrue(app.buttons["发消息"].waitForExistence(timeout: 10))
        capture("crewden-assistant-profile")
        app.buttons["工作记录"].tap()
        let delegation = app.buttons["派工关系"]
        XCTAssertTrue(delegation.waitForExistence(timeout: 15))
        XCTAssertTrue(app.scrollViews["work.records"].firstMatch.waitForExistence(timeout: 10))
        capture("crewden-work")
        delegation.tap()
        XCTAssertTrue(delegation.isSelected)
    }

    /// Checks that the Work preview really opens the chat message its text came from.
    func testReadLatestAssistantDelivery() throws {
        let env = ProcessInfo.processInfo.environment
        let title = try XCTUnwrap(env["NANO_UI_WORK_CHAT"])
        let excerpt = try XCTUnwrap(env["NANO_UI_LATEST_DELIVERY"])
        try launch()
        let assistant = app.buttons.containing(NSPredicate(format: "label CONTAINS %@", title)).firstMatch
        XCTAssertTrue(assistant.waitForExistence(timeout: 15))
        assistant.tap()
        let activity = app.navigationBars.buttons[title].firstMatch
        XCTAssertTrue(activity.waitForExistence(timeout: 10))
        capture("crewden-fitted-bubble")
        activity.tap()
        let records = app.buttons["查看工作记录"]
        XCTAssertTrue(records.waitForExistence(timeout: 10))
        capture("crewden-assistant-availability")
        records.tap()
        let original = app.buttons["查看原消息"]
        XCTAssertTrue(original.waitForExistence(timeout: 15))
        let note = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", excerpt)).firstMatch
        XCTAssertTrue(note.waitForExistence(timeout: 10))
        capture("crewden-work-history")
        original.tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", excerpt)).firstMatch.waitForExistence(timeout: 15))
    }

    func testRegisterAndFindFirstAssistant() throws {
        continueAfterFailure = false
        let origin = try required("NANO_UI_ORIGIN")
        XCTAssertEqual(URL(string: origin)?.host, "127.0.0.1")
        app.launchEnvironment["NANO_IM_BASE_URL"] = origin
        app.launchArguments = ["-nano.locale", "zh"]
        app.launch()
        let register = app.buttons["还没有账号？创建账号"]
        XCTAssertTrue(register.waitForExistence(timeout: 20))
        capture("crewden-login")
        app.buttons["登录"].tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 6))
        capture("crewden-login-keyboard")
        register.tap()
        capture("crewden-register")
        let username = app.textFields["输入用户名"]
        username.tap()
        username.typeText("first-" + UUID().uuidString.prefix(8))
        let displayName = app.textFields["其他人看到的名字"]
        displayName.tap()
        displayName.typeText("Mia")
        let password = app.secureTextFields["输入密码"]
        password.tap()
        let strongPassword = app.buttons["GenerateStrongPasswordButton"]
        if strongPassword.waitForExistence(timeout: 3) {
            app.buttons["xmark"].tap()
        }
        password.typeText("Crewden-" + UUID().uuidString.prefix(12))
        XCTAssertTrue(app.buttons["创建账号"].isEnabled)
        app.buttons["创建账号"].tap()
        let setup = app.buttons["assistant.setup.entry"]
        XCTAssertTrue(setup.waitForExistence(timeout: 25))
        capture("crewden-first-inbox")
        setup.tap()
        XCTAssertTrue(app.buttons["发送设置链接到电脑"].waitForExistence(timeout: 15))
        capture("crewden-first-setup")
        app.buttons["稍后"].tap()
        app.tabBars.buttons["我的"].tap()
        app.buttons["设置"].tap()
        app.buttons["退出登录"].tap()
        app.buttons["退出登录"].firstMatch.tap()
        XCTAssertTrue(register.waitForExistence(timeout: 15))
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
        app.tabBars.buttons["助手"].tap()
        let settings = app.buttons["personal-agent-settings"]
        XCTAssertTrue(settings.waitForExistence(timeout: 20))
        settings.tap()
        let disclosure = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "排除的聊天")).firstMatch
        XCTAssertTrue(disclosure.waitForExistence(timeout: 20))
        disclosure.tap()
        let toggle = app.switches["pa-exclude-" + chatID]
        XCTAssertTrue(toggle.waitForExistence(timeout: 5))
        for expected in ["0", "1"] {
            XCTAssertEqual(toggle.value as? String, expected)
            toggle.coordinate(withNormalizedOffset: CGVector(dx: 0.91, dy: 0.5)).tap()
            XCTAssertNotEqual(toggle.value as? String, expected)
            let save = app.buttons["保存排除范围"]
            XCTAssertTrue(save.waitForExistence(timeout: 5))
            if !save.isHittable { app.swipeUp() }
            save.tap()
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

        let activity = app.navigationBars.buttons[title].firstMatch.firstMatch
        XCTAssertTrue(activity.waitForExistence(timeout: 10))
        activity.tap()
        let records = app.buttons["查看工作记录"].firstMatch
        XCTAssertTrue(records.waitForExistence(timeout: 10))
        capture("crewden-agent-activity")
        if !records.isHittable { app.swipeUp() }
        records.tap()
        let delegation = app.buttons["派工关系"]
        XCTAssertTrue(delegation.waitForExistence(timeout: 10))
        delegation.tap()
        let sessionLink = app.descendants(matching: .any)["work.delegation." + child].firstMatch
        XCTAssertTrue(sessionLink.waitForExistence(timeout: 10))
        if !sessionLink.isHittable { app.swipeUp() }
        capture("crewden-delegation")
        sessionLink.tap()
        XCTAssertTrue(app.scrollViews["work.records"].firstMatch.waitForExistence(timeout: 10)
                      || app.staticTexts["执行信息与上下文"].firstMatch.exists)
        capture("crewden-child-execution")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertTrue(sessionLink.waitForExistence(timeout: 10))
    }

    func testInspectThreadNoticeAndReplyCount() throws {
        try launch()
        let title = try required("NANO_UI_CHAT_TITLE")
        let chat = app.staticTexts[title].firstMatch
        XCTAssertTrue(chat.waitForExistence(timeout: 20))
        chat.tap()
        let entry = app.buttons.containing(NSPredicate(format: "label CONTAINS %@", "条回复")).firstMatch
        XCTAssertTrue(entry.waitForExistence(timeout: 15))
        capture("crewden-chat-topic-entry")
        entry.tap()
        let notice = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "已取消关注此话题")).firstMatch
        XCTAssertTrue(notice.waitForExistence(timeout: 15))
        capture("crewden-thread-unfollowed")
    }

    func testManageHumanProfilePhotoAndVerifyTeamSurfaces() throws {
        continueAfterFailure = false
        let origin = try required("NANO_UI_ORIGIN")
        let url = try XCTUnwrap(URL(string: origin))
        XCTAssertEqual(url.host, "127.0.0.1")
        XCTAssertGreaterThan(try XCTUnwrap(url.port), 1024)
        app.launchEnvironment["NANO_IM_BASE_URL"] = origin
        app.launchArguments = ["-nano.locale", "zh"]
        app.launch()

        let username = app.textFields["输入用户名"]
        if username.waitForExistence(timeout: 10) {
            username.tap()
            username.typeText(try required("NANO_UI_USERNAME"))
            let password = app.secureTextFields["输入密码"]
            password.tap()
            password.typeText(try required("NANO_UI_PASSWORD"))
            app.buttons["登录"].tap()
        }

        let chatTitle = try required("NANO_UI_CHAT_TITLE")
        let chatRow = app.staticTexts[chatTitle].firstMatch
        XCTAssertTrue(chatRow.waitForExistence(timeout: 20))
        chatRow.tap()

        let quotedReply = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "核心指标已达标")).firstMatch
        XCTAssertTrue(quotedReply.waitForExistence(timeout: 15))
        Thread.sleep(forTimeInterval: 1.0)
        capture("ios-group-chat-avatars")

        app.navigationBars.buttons.element(boundBy: 0).tap()
        app.tabBars.buttons["我的"].tap()
        let myTeam = app.buttons.containing(NSPredicate(format: "label CONTAINS %@", "我的团队")).firstMatch
        XCTAssertTrue(myTeam.waitForExistence(timeout: 15))
        Thread.sleep(forTimeInterval: 0.8)
        capture("ios-me-space-avatar")

        myTeam.tap()
        let teamMembers = app.buttons["团队成员"]
        XCTAssertTrue(teamMembers.waitForExistence(timeout: 10))
        teamMembers.tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "周宁")).firstMatch.waitForExistence(timeout: 15))
        Thread.sleep(forTimeInterval: 1.0)
        capture("ios-company-members-avatars")

        app.navigationBars.buttons.element(boundBy: 0).tap()
        app.navigationBars.buttons.element(boundBy: 0).tap()
        app.buttons["设置"].tap()
        let profileNav = app.buttons["个人资料与语言"]
        XCTAssertTrue(profileNav.waitForExistence(timeout: 10))
        profileNav.tap()

        let changeBtn = app.buttons["更换头像"]
        XCTAssertTrue(changeBtn.waitForExistence(timeout: 15))
        XCTAssertTrue(app.buttons["移除头像"].exists)
        Thread.sleep(forTimeInterval: 0.8)
        capture("ios-account-with-avatar")

        let nameField = app.textFields["显示名称"]
        XCTAssertTrue(nameField.waitForExistence(timeout: 10))
        nameField.tap()
        nameField.typeText("（草稿保留）")
        if app.keyboards.buttons["Return"].exists {
            app.keyboards.buttons["Return"].tap()
        } else if app.keyboards.buttons["return"].exists {
            app.keyboards.buttons["return"].tap()
        }

        app.buttons["移除头像"].tap()
        XCTAssertTrue(app.staticTexts["已移除自定义头像"].waitForExistence(timeout: 15))
        XCTAssertTrue(app.buttons["上传头像"].exists)
        XCTAssertFalse(app.buttons["移除头像"].exists)
        XCTAssertEqual((nameField.value as? String)?.contains("草稿保留"), true)
        capture("ios-account-removed-keeps-draft")

        let discardBtn = app.buttons["放弃修改"]
        if !discardBtn.isHittable { app.swipeUp() }
        XCTAssertTrue(discardBtn.waitForExistence(timeout: 5))
        discardBtn.tap()
        app.swipeDown()
        Thread.sleep(forTimeInterval: 0.5)

        let uploadBtn = app.buttons["上传头像"]
        XCTAssertTrue(uploadBtn.waitForExistence(timeout: 5))
        uploadBtn.tap()

        let inAppPhoto = app.images.matching(NSPredicate(format: "label CONTAINS[c] %@ OR label CONTAINS %@", "Photo", "照片")).firstMatch
        XCTAssertTrue(inAppPhoto.waitForExistence(timeout: 10))
        // PHPicker's out-of-process Metal grid (PXGGridLayout-Info) reports hitPoint {-1,-1} to host XCUITest; tap its center coordinate directly.
        inAppPhoto.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()

        let cropNav = app.navigationBars["调整头像"]
        XCTAssertTrue(cropNav.waitForExistence(timeout: 15))
        let slider = app.sliders.firstMatch
        if slider.waitForExistence(timeout: 5) {
            slider.adjust(toNormalizedSliderPosition: 0.25)
        }
        capture("ios-avatar-crop-sheet")

        cropNav.buttons["保存"].tap()
        XCTAssertTrue(app.staticTexts["个人头像已更新"].waitForExistence(timeout: 15))
        XCTAssertTrue(app.buttons["更换头像"].exists)
        Thread.sleep(forTimeInterval: 0.8)
        capture("ios-account-reuploaded")

        app.terminate()
        app.launch()
        XCTAssertTrue(app.staticTexts[chatTitle].firstMatch.waitForExistence(timeout: 20))
        Thread.sleep(forTimeInterval: 1.0)
        capture("ios-cold-relaunch-inbox")
    }
}
