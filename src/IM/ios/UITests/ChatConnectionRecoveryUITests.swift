import XCTest
import UIKit

/// One-shot, host-coordinated outages of this run's exclusively owned real IM listener.
/// No test endpoint, client interception or production connection participates.
@MainActor
final class ChatConnectionRecoveryUITests: XCTestCase {
    private var driver: NativeChatDriver!
    override func setUpWithError() throws {
        continueAfterFailure = false
        driver = try NativeChatDriver(test: self)
    }
    override func tearDownWithError() throws { driver?.app.terminate() }

    func testThreeSecondChatsOutageIsSilentAndDoesNotMoveRows() throws {
        guard ProcessInfo.processInfo.environment["NANO_UI_OUTAGE_KIND"] == "short" else {
            throw XCTSkip("Requires the separately coordinated one-shot 3-second owned-listener outage")
        }
        try driver.launchAndLogin()
        let conversation = driver.fixture.conversations[1]
        // Populate B's real local cache and establish a conversation-specific baseline before
        // releasing the host. No Latest/history repair is allowed, including during setup.
        try driver.open(conversation)
        try driver.require(driver.stableTail(conversation.tail, timeout: 10), "Short recovery requires B's actual rendered tail before the fault")
        let chatBaseline = try shortSnapshot(surface: "chat", conversation: conversation)
        try requireShortChat(chatBaseline, baseline: chatBaseline)
        driver.record("short-outage-chat-baseline", chatBaseline.evidence)
        driver.capture("short-outage-chat-before", tree: true)
        try driver.backToChats()
        let row = driver.app.staticTexts[conversation.title].firstMatch
        let chatsBaseline = try shortSnapshot(surface: "Chats", conversation: conversation)
        try requireShortChats(chatsBaseline, baseline: chatsBaseline)
        driver.record("short-outage-Chats-baseline", chatsBaseline.evidence)
        driver.capture("short-outage-Chats-before", tree: true)

        let readyAt = ProcessInfo.processInfo.systemUptime
        let deadline = readyAt + 10
        var observations: [[String: Any]] = []
        var navigation: [[String: Any]] = []
        var chatSamples = 0
        // Preserve partial evidence even if an assertion fails. Only the host can correlate
        // these intervals with the verified listener's actual fault/restore receipts.
        defer {
            driver.record("short-outage-both-surfaces-observations", [
                "readyUptime": readyAt, "deadlineUptime": deadline, "samples": observations,
                "navigation": navigation, "chatSampleCount": chatSamples,
                "faultCoverage": "inconclusive-until-host-cross-correlates-actual-fault-receipts",
                "coverageRule": "Both surfaces require a complete sample interval inside the actual same 3-second fault; otherwise inconclusive"
            ])
        }
        // The host consumes exactly this one ready event; this test never starts a fault.
        driver.record("owned-outage-short-ready", ["ready": true, "uptime": readyAt])
        // Keep the two Chats observations minimal so ordinary navigation has a chance to
        // reach cached B during the SAME three-second outage, without extending that fault.
        for _ in 0..<2 {
            let sample = try shortSnapshot(surface: "Chats", conversation: conversation)
            observations.append(sample.evidence)
            try requireShortChats(sample, baseline: chatsBaseline)
        }
        navigation.append(["event": "B-row-tap-start", "surface": "Chats", "uptime": ProcessInfo.processInfo.systemUptime])
        row.tap()
        navigation.append(["event": "B-row-tap-returned", "surface": "chat", "uptime": ProcessInfo.processInfo.systemUptime])
        // Continue beyond the five-second quiet deadline to catch any delayed retry flash.
        // Use only chat's own pre-fault baseline after leaving Chats, never its stale row.
        while ProcessInfo.processInfo.systemUptime < deadline {
            let sample = try shortSnapshot(surface: "chat", conversation: conversation)
            observations.append(sample.evidence)
            chatSamples += 1
            try requireShortChat(sample, baseline: chatBaseline)
            driver.pause(max(0, 0.2 - (ProcessInfo.processInfo.systemUptime - sample.startedAt)))
        }
        try driver.require(chatSamples > 0, "The bounded short observation must include cached B; fault overlap still needs host correlation")
        driver.capture("short-outage-chat-after", tree: true)
    }

    func testLongOutageFeedbackIsStableAcrossBothSurfaces() throws {
        guard ProcessInfo.processInfo.environment["NANO_UI_OUTAGE_KIND"] == "long" else {
            throw XCTSkip("Requires the separately coordinated one-shot 12-second owned-listener outage")
        }
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == "tall-card" })
        try driver.launchAndLogin()
        try driver.open(conversation)
        try driver.require(driver.stableTail(conversation.tail, timeout: 10), "Long recovery starts from a real rendered tall-card tail")
        for _ in 0..<3 { driver.swipe(history: true) }
        let anchor = try historyAnchor()
        let beforeY = try anchor.snapshot().frame.minY
        let beforeNav = driver.app.navigationBars.firstMatch.frame
        let beforeComposer = driver.app.textViews["Message"].frame
        try driver.require(!feedbackButton.exists,
                           "Healthy fixture must be recovered before attributing feedback to the one-shot outage")
        driver.capture("long-outage-reading-before", tree: true)
        driver.record("owned-outage-long-ready", ["ready": true])
        let feedback = feedbackButton
        try driver.require(feedback.waitForExistence(timeout: 10), "Continuous unavailability must eventually have one honest navigation feedback")
        driver.capture("long-outage-conversation-feedback")
        let duringY = try anchor.snapshot().frame.minY
        try driver.require(abs(duringY - beforeY) <= 4, "Sustained failure feedback must not move the history anchor")
        try driver.require(driver.app.navigationBars.firstMatch.frame == beforeNav, "Fault feedback must not resize the navigation area")
        try driver.require(driver.app.textViews["Message"].frame == beforeComposer, "Fault feedback must not resize the composer or viewport")
        try driver.require(driver.app.buttons["Conversation details"].isHittable, "The long title must leave the details action reachable")
        try driver.require(visibleFeedbackButtons.count == 1,
                           "There is one connection feedback, never duplicated content rows")
        try driver.backToChats()
        try driver.require(feedbackButton.exists,
                           "The same sustained outage also has one stable Chats feedback")
        driver.capture("long-outage-Chats-feedback")
        feedbackButton.tap()
        try driver.require(driver.app.navigationBars["Connection and updates"].waitForExistence(timeout: 3), "Feedback opens truthful details and a real retry action")
        driver.capture("long-outage-connection-details", tree: true)
        driver.app.buttons["Done"].tap()
        // The one listener is restored by the host/runner; wait for actual transport recovery.
        let cleared = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: feedbackButton)
        try driver.require(XCTWaiter.wait(for: [cleared], timeout: 30) == .completed,
                           "Complete sync plus confirmed realtime recovery clears the auxiliary feedback")
        driver.capture("long-outage-Chats-recovered", tree: true)
        try driver.open(conversation)
        try driver.require(driver.stableTail(conversation.tail), "A fresh Chats navigation after recovery still follows latest")
        driver.capture("long-outage-recovered-tail")
    }

    private struct ShortSnapshot {
        let surface: String
        let startedAt: TimeInterval
        let endedAt: TimeInterval
        let navigation: CGRect?
        let composer: CGRect?
        let row: CGRect?
        let tail: CGRect?
        let tailVisible: Bool
        let feedbackCount: Int
        let legacyCount: Int

        var evidence: [String: Any] {
            var result: [String: Any] = ["surface": surface, "sampleStartUptime": startedAt,
                                       "uptime": endedAt, "sampleEndUptime": endedAt,
                                       "feedback": feedbackCount > 0, "legacyStatusCount": legacyCount,
                                       "tailVisible": tailVisible]
            for (name, frame) in [("navigation", navigation), ("composer", composer), ("row", row), ("tail", tail)] {
                if let frame {
                    result[name] = ["x": frame.minX, "y": frame.minY, "width": frame.width, "height": frame.height]
                }
            }
            return result
        }
    }

    private var visibleFeedbackButtons: XCUIElementQuery {
        driver.app.buttons.matching(identifier: "chat.connectionFeedback")
            .matching(NSPredicate(format: "label MATCHES %@", ".*\\S.*"))
    }

    private var feedbackButton: XCUIElement { visibleFeedbackButtons.firstMatch }

    /// One public AX generation supplies both feedback and geometry, avoiding a series of
    /// live queries that could consume the entire short fault before navigating to B.
    private func shortSnapshot(surface: String, conversation: NativeChatFixture.Conversation) throws -> ShortSnapshot {
        let startedAt = ProcessInfo.processInfo.systemUptime
        let root = try driver.app.snapshot()
        let endedAt = ProcessInfo.processInfo.systemUptime
        let nodes = shortNodes(root)
        let navigation = nodes.first { $0.elementType == .navigationBar }?.frame
        let composer = nodes.first { $0.elementType == .textView && $0.label == "Message" }?.frame
        let row = surface == "Chats" ? nodes.first { $0.elementType == .staticText && $0.label == conversation.title }?.frame : nil
        let leaves = shortTailLeaves(root, marker: conversation.tail)
        let exact = leaves.filter { $0.label.trimmingCharacters(in: .whitespacesAndNewlines) == conversation.tail }
        // Match the driver's true-tail rule: the final Text leaf, never a tall WK aggregate
        // or an earlier Title leaf carrying the same marker.
        let tail = (exact.isEmpty ? leaves : exact).last?.frame
        var tailVisible = false
        if let tail, let navigation, let composer {
            let viewport = CGRect(x: root.frame.minX, y: navigation.maxY, width: root.frame.width,
                                  height: max(0, composer.minY - 10 - navigation.maxY))
            tailVisible = tail.width > 0 && tail.height > 0 && viewport.contains(tail)
        }
        let feedback = nodes.filter {
            $0.elementType == .button && $0.identifier == "chat.connectionFeedback"
            && !$0.label.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }.count
        let legacy = nodes.filter {
            $0.elementType == .staticText && ($0.label.hasPrefix("Connecting") || $0.label.hasPrefix("Offline. Retrying") || $0.label.hasPrefix("Service unavailable. Retrying"))
        }.count
        return ShortSnapshot(surface: surface, startedAt: startedAt, endedAt: endedAt, navigation: navigation,
                             composer: composer, row: row, tail: tail, tailVisible: tailVisible,
                             feedbackCount: feedback, legacyCount: legacy)
    }

    private func shortNodes(_ root: any XCUIElementSnapshot) -> [any XCUIElementSnapshot] {
        [root] + root.children.flatMap { shortNodes($0) }
    }

    private func shortTailLeaves(_ root: any XCUIElementSnapshot, marker: String) -> [any XCUIElementSnapshot] {
        let children = root.children.flatMap { shortTailLeaves($0, marker: marker) }
        if !children.isEmpty { return children }
        return root.elementType == .staticText && root.label.contains(marker) ? [root] : []
    }

    private func requireShortChats(_ sample: ShortSnapshot, baseline: ShortSnapshot) throws {
        try driver.require(sample.feedbackCount == 0 && sample.legacyCount == 0, "Short Chats recovery remains silent")
        let navigation = try XCTUnwrap(sample.navigation)
        let baselineNavigation = try XCTUnwrap(baseline.navigation)
        let row = try XCTUnwrap(sample.row)
        let baselineRow = try XCTUnwrap(baseline.row)
        try driver.require(navigation.width > 0 && row.width > 0 && row.height > 0, "Chats has a meaningful pre-fault content baseline")
        try driver.require(navigation == baselineNavigation, "Short recovery keeps Chats navigation geometry")
        try driver.require(abs(row.minY - baselineRow.minY) <= 1, "Short reconnect must not insert a Chats row or move content")
    }

    private func requireShortChat(_ sample: ShortSnapshot, baseline: ShortSnapshot) throws {
        try driver.require(sample.feedbackCount == 0 && sample.legacyCount == 0, "Short conversation recovery remains silent")
        let navigation = try XCTUnwrap(sample.navigation)
        let baselineNavigation = try XCTUnwrap(baseline.navigation)
        let composer = try XCTUnwrap(sample.composer)
        let baselineComposer = try XCTUnwrap(baseline.composer)
        let tail = try XCTUnwrap(sample.tail)
        let baselineTail = try XCTUnwrap(baseline.tail)
        try driver.require(navigation.width > 0 && composer.width > 0 && composer.height > 0,
                           "Conversation has meaningful navigation and composer baselines")
        try driver.require(sample.tailVisible, "Short recovery keeps B's actual cached tail visible without Latest/history repair")
        try driver.require(navigation == baselineNavigation, "Short recovery keeps conversation navigation geometry")
        try driver.require(composer == baselineComposer, "Short recovery keeps the conversation composer and viewport fixed")
        try driver.require(abs(tail.minY - baselineTail.minY) <= 4 && abs(tail.maxY - baselineTail.maxY) <= 4,
                           "Short recovery must not move B's cached tail content")
    }

    private func historyAnchor() throws -> XCUIElement {
        let viewport = driver.viewport
        let marker = #"(H763-[0-9]{3} · .*|引用块 [0-9]{3}：.*|fixture_763_[0-9]{3})"#
        let candidates = driver.app.staticTexts.matching(NSPredicate(format: "label MATCHES %@", marker))
        for element in candidates.allElementsBoundByIndex {
            guard let snapshot = try? element.snapshot(), !snapshot.frame.isEmpty,
                  viewport.contains(snapshot.frame) else { continue }
            return driver.app.staticTexts.matching(NSPredicate(format: "label == %@", snapshot.label)).firstMatch
        }
        driver.capture("long-outage-no-history-anchor", tree: true)
        throw NSError(domain: "ChatConnectionRecovery", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "No complete history anchor is visible"])
    }
}
