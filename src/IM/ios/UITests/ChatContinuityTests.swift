import XCTest

/// Native, read-only journeys for the frozen bugfix-763 corpus. No transport faults here:
/// the fixture's one-shot faults belong to the candidate's explicitly coordinated run.
@MainActor
final class ChatContinuityTests: XCTestCase {
    private var driver: NativeChatDriver!
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 1800
        driver = try NativeChatDriver(test: self)
    }
    override func tearDownWithError() throws { driver?.app.terminate() }

    func testPrimeActualNativeScreenshot() throws {
        try driver.launchAndLogin()
        driver.capture("763-baseline-real-login-Chats", tree: true)
        try driver.open(driver.fixture.conversations[0])
        try driver.require(driver.text("H763-").waitForExistence(timeout: 15), "The genuine message DTO must render")
        driver.capture("763-baseline-real-timeline", tree: true)
    }
    func testDenseCardsFastRoundTripReturnsToRenderedTail() throws {
        let title = try NativeChatFixture.required("NANO_UI_INTERACTIVE_TITLE")
        let tail = try NativeChatFixture.required("NANO_UI_INTERACTIVE_TAIL")
        try driver.launchAndLogin()
        let row = driver.app.staticTexts.matching(NSPredicate(format: "label == %@", title)).firstMatch
        try driver.require(row.waitForExistence(timeout: 8), "The dense card conversation must exist")
        let control = driver.app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@ OR label BEGINSWITH %@", "展开 10", "收起 10")).firstMatch
        driver.record("dense-card-window-start", ["unixSeconds": Date().timeIntervalSince1970])
        row.tap()
        try driver.require(control.waitForExistence(timeout: 12),
                           "Wait for the final live card to render before the scroll")
        driver.capture("dense-cards-initial-rendered")
        driver.record("dense-card-scroll-start", ["unixSeconds": Date().timeIntervalSince1970])
        for _ in 0..<3 { driver.swipe(history: true) }
        for _ in 0..<3 { driver.swipe(history: false) }
        let latest = driver.app.buttons["Latest messages"]
        if latest.exists && latest.isHittable { latest.tap() }
        try driver.require(driver.stableTail(tail, timeout: 8), "Return to the actual final message")
        try driver.require(control.waitForExistence(timeout: 8),
                           "The final card must be interactive, not a preview")
        driver.record("dense-card-window-end", ["unixSeconds": Date().timeIntervalSince1970])
        driver.capture("dense-cards-return-rendered")
    }

    func testLoadMarkdown300ThroughFourEarlierPages() throws { try prime300(kind: "markdown") }
    func testLoadMixed300ThroughFourEarlierPages() throws { try prime300(kind: "tall-card") }
    private func prime300(kind: String) throws {
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == kind })
        try driver.launchAndLogin()
        try driver.open(conversation)
        driver.capture("\(kind)-initial-page")
        try driver.loadAll300(conversation)
    }

    func testFarLatestMarkdownHasActualStableTail() throws { try farLatest(kind: "markdown") }
    func testFarLatestMixedHasActualStableTail() throws { try farLatest(kind: "tall-card") }
    private func farLatest(kind: String) throws {
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == kind })
        try driver.launchAndLogin()
        try driver.open(conversation)
        // Use the same literal first-history marker in both versions, never a swipe count
        // that silently changes the distance when a card's layout changes.
        try driver.reachTailForSetup(conversation)
        try driver.seekHistoryStart()
        driver.capture("\(kind)-far-Latest-before", tree: true)
        let latest = driver.app.buttons["Latest messages"]
        try driver.require(latest.exists && latest.isHittable, "The real Latest control must be available")
        let start = ProcessInfo.processInfo.systemUptime
        latest.tap()
        let stable = driver.stableTail(conversation.tail, timeout: 3, captureFrames: true)
        driver.record("far-Latest-command-wall", ["kind": kind, "seconds": ProcessInfo.processInfo.systemUptime - start,
                                                 "stable": stable, "includesAutomationSynchronization": true,
                                                 "handlerSignpost": "not available in uninstrumented baseline"])
        driver.capture("\(kind)-far-Latest-after")
        try driver.require(stable, "Latest must reveal the final tail, not merely issue scrollTo")
    }
}
