import XCTest

/// App-targeted D5 measurements. XCTest invokes each measure block once discarded and
/// five times measured; resets, app restart, entry and tail preparation are excluded.
@MainActor
final class ChatContinuityPerformanceTests: XCTestCase {
    private var driver: NativeChatDriver!
    override func setUpWithError() throws {
        continueAfterFailure = true
        executionTimeAllowance = 2400
        driver = try NativeChatDriver(test: self)
        guard ProcessInfo.processInfo.environment["NANO_UI_300_PRIMED"] == "1" else {
            throw XCTSkip("First prove four Earlier taps and visible H763-001 for both conversations; host must verify the same 300-row SQLite windows")
        }
    }
    override func tearDownWithError() throws { driver?.app.terminate() }
    func testMarkdownColdScroll() throws { try scrolling(kind: "markdown", cold: true) }
    func testMarkdownWarmScroll() throws { try scrolling(kind: "markdown", cold: false) }
    func testMixedColdScroll() throws { try scrolling(kind: "tall-card", cold: true) }
    func testMixedWarmScroll() throws { try scrolling(kind: "tall-card", cold: false) }

    private func scrolling(kind: String, cold: Bool) throws {
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == kind })
        if !cold { try driver.launchAndLogin(); try driver.open(conversation) }
        let options = XCTMeasureOptions()
        options.iterationCount = 5
        options.invocationOptions = [.manuallyStart, .manuallyStop]
        let metrics: [XCTMetric] = [XCTHitchMetric(application: driver.app),
                                   XCTOSSignpostMetric.scrollingAndDecelerationMetric,
                                   XCTCPUMetric(application: driver.app), XCTMemoryMetric(application: driver.app)]
        var iteration = 0
        measure(metrics: metrics, options: options) {
            iteration += 1
            do {
                if cold {
                    driver.app.terminate()
                    try driver.launchAndLogin(); try driver.open(conversation)
                } else if iteration > 1 {
                    try driver.backToChats(); try driver.open(conversation)
                }
                try driver.reachTailForSetup(conversation)
                driver.record("scroll-sample-start", ["kind": kind, "cold": cold, "iteration": iteration,
                                                      "discardedWarmup": iteration == 1,
                                                      "corpusSHA256": driver.fixture.frozen_dataset.sha256])
                startMeasuring()
                let scrollStart = Date()
                for _ in 0..<6 { driver.swipe(history: true) }
                for _ in 0..<6 { driver.swipe(history: false) }
                let scrollEnd = Date()
                stopMeasuring()
                driver.record("scroll-sample-interval", ["kind": kind, "cold": cold, "iteration": iteration,
                    "startUnixSeconds": scrollStart.timeIntervalSince1970,
                    "endUnixSeconds": scrollEnd.timeIntervalSince1970])
                driver.capture("\(kind)-\(cold ? "cold" : "warm")-sample-\(iteration)")
            } catch {
                // A failed load/tail precondition remains a failed sample; never replace
                // it with a smaller load or fabricate a zero-valued native metric.
                XCTFail("D5 sample \(iteration) failed: \(error.localizedDescription)")
            }
        }
    }

    func testMarkdownColdLatest() throws { try latest(kind: "markdown", cold: true) }
    func testMarkdownWarmLatest() throws { try latest(kind: "markdown", cold: false) }
    func testMixedColdLatest() throws { try latest(kind: "tall-card", cold: true) }
    func testMixedWarmLatest() throws { try latest(kind: "tall-card", cold: false) }

    private func latest(kind: String, cold: Bool) throws {
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == kind })
        if !cold { try driver.launchAndLogin(); try driver.open(conversation) }
        let signpost = ProcessInfo.processInfo.environment["NANO_CHAT_SIGNPOST"] == "true"
        // Clock is deliberately automation wall time, not handler latency or App hitches.
        var metrics: [XCTMetric] = [XCTClockMetric()]
        if signpost {
            metrics.append(XCTOSSignpostMetric(subsystem: "com.nano.im.chat", category: "Scroll", name: "LatestToTail"))
        }
        let options = XCTMeasureOptions(); options.iterationCount = 5
        options.invocationOptions = [.manuallyStart, .manuallyStop]
        var iteration = 0
        var failedTailIterations: [Int] = []
        measure(metrics: metrics, options: options) {
            iteration += 1
            do {
                if cold {
                    driver.app.terminate()
                    try driver.launchAndLogin(); try driver.open(conversation)
                } else if iteration > 1 {
                    try driver.backToChats(); try driver.open(conversation)
                }
                try driver.reachTailForSetup(conversation)
                try driver.seekHistoryStart()
                let latest = driver.app.buttons["Latest messages"]
                try driver.require(latest.exists && latest.isHittable, "The actual Latest button must follow visible H763-001")
                startMeasuring()
                let start = ProcessInfo.processInfo.systemUptime
                latest.tap()
                let stable = driver.stableTail(conversation.tail)
                let end = ProcessInfo.processInfo.systemUptime
                let stableWall: Any
                if let completedAt = driver.lastTailCompletionUptime { stableWall = completedAt - start }
                else { stableWall = NSNull() }
                stopMeasuring()
                driver.record("Latest-sample-outcome", ["kind": kind, "cold": cold, "iteration": iteration,
                    "discardedWarmup": iteration == 1, "historyAnchor": "H763-001", "stable": stable,
                    "commandToStableSeconds": stableWall, "commandToOutcomeSeconds": end - start,
                    "includesAutomationSynchronization": true, "handlerSignpostAvailable": signpost,
                    "corpusSHA256": driver.fixture.frozen_dataset.sha256])
                driver.capture("\(kind)-\(cold ? "cold" : "warm")-Latest-sample-\(iteration)")
                // Defer XCTest failure recording until all native metrics are collected;
                // an assertion inside measure can abort later iterations on some runners.
                // A clock value is not a completed-tail latency when stable is false.
                if !stable { failedTailIterations.append(iteration) }
            } catch {
                driver.record("Latest-sample-precondition-failed", ["kind": kind, "cold": cold,
                    "iteration": iteration, "discardedWarmup": iteration == 1, "validMeasurement": false])
                XCTFail("Latest sample \(iteration) precondition failed: \(error.localizedDescription)")
            }
        }
        XCTAssertEqual(iteration, 6, "Keep one discarded warmup and all five measured Latest invocations")
        XCTAssertTrue(failedTailIterations.isEmpty, "Latest did not reach three stable tail frames in invocations \(failedTailIterations)")
    }
}
