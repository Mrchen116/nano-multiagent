import XCTest

/// Temporary observation only: no performance/acceptance pass is inferred from this run.
@MainActor
final class ChatScrollGeometryDiagnosticUITests: XCTestCase {
    func testObserveStatusBarAndKeyboardGeometryWithoutTransportFaults() throws {
        continueAfterFailure = false
        let driver = try NativeChatDriver(test: self)
        defer { driver.app.terminate() }
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == "tall-card" })
        try driver.launchAndLogin()
        try driver.open(conversation)
        try driver.reachTailForSetup(conversation)
        driver.capture("diagnostic-true-tail-before-system-scroll", tree: true)
        driver.record("diagnostic-statusbar-action", ["uptime": ProcessInfo.processInfo.systemUptime])
        driver.app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 80, dy: 30)).tap()
        driver.pause(2)
        driver.capture("diagnostic-after-statusbar-scroll", tree: true)
        try driver.reachTailForSetup(conversation)
        driver.record("diagnostic-keyboard-action", ["uptime": ProcessInfo.processInfo.systemUptime])
        driver.app.textViews["Message"].tap()
        try driver.require(driver.app.keyboards.firstMatch.waitForExistence(timeout: 5), "Observe a genuine software keyboard")
        driver.pause(4)
        driver.capture("diagnostic-keyboard-after-four-seconds", tree: true)
        driver.record("diagnostic-tail-observed-not-acceptance", ["stable": driver.stableTail(conversation.tail)])
        let latest = driver.app.buttons["Latest messages"]
        if latest.exists && latest.isHittable {
            driver.record("diagnostic-manual-latest-with-keyboard", ["uptime": ProcessInfo.processInfo.systemUptime])
            latest.tap()
            driver.pause(2)
            driver.capture("diagnostic-keyboard-after-manual-latest", tree: true)
        }
    }
}
