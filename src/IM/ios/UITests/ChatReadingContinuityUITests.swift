import XCTest
import UIKit

/// Real-layout acceptance of navigation lifetime, reading ownership and viewport changes.
/// The host binds the same frozen rendering fixture used for the native performance samples.
@MainActor
final class ChatReadingContinuityUITests: XCTestCase {
    private var driver: NativeChatDriver!
    override func setUpWithError() throws {
        continueAfterFailure = false
        driver = try NativeChatDriver(test: self)
    }
    override func tearDownWithError() throws { driver?.app.terminate() }

    func testCacheReentryDetailsAndForegroundPreserveTheRightIntent() throws {
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == "tall-card" })
        try driver.launchAndLogin()
        try driver.open(conversation)
        try driver.require(driver.stableTail(conversation.tail), "Fresh entry must reveal the real tall-card tail")
        driver.capture("candidate-fresh-mixed-true-tail", tree: true)

        for _ in 0..<6 { driver.swipe(history: true) }
        let anchor = try visibleHistoryAnchor()
        let originalY = try anchor.element.snapshot().frame.minY
        driver.capture("candidate-reading-before-details", tree: true)
        driver.app.buttons["Conversation details"].tap()
        driver.capture("candidate-conversation-details")
        driver.app.navigationBars.buttons.element(boundBy: 0).tap()
        try driver.require(anchor.element.waitForExistence(timeout: 5), "Details return retains the same reading context")
        driver.pause(0.3)
        let detailsY = try anchor.element.snapshot().frame.minY
        try driver.require(abs(detailsY - originalY) <= 4,
                           "Details return must not jump a history anchor")
        driver.capture("candidate-reading-after-details")

        XCUIDevice.shared.press(.home)
        driver.app.activate()
        try driver.require(anchor.element.waitForExistence(timeout: 5), "Foreground retains the same reading context")
        driver.pause(0.3)
        let foregroundY = try anchor.element.snapshot().frame.minY
        try driver.require(abs(foregroundY - originalY) <= 4,
                           "Foreground must not turn history reading into follow-latest")
        driver.capture("candidate-reading-after-foreground")

        // A new navigation instance is deliberately different from returning through details.
        try driver.backToChats()
        try driver.open(conversation)
        try driver.require(driver.stableTail(conversation.tail), "Chats reentry must follow latest even when cached item count is unchanged")
        driver.capture("candidate-cached-reentry-true-tail", tree: true)
    }

    func testKeyboardAndComposerResizeKeepFollowingActualCardTail() throws {
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == "tall-card" })
        try driver.launchAndLogin()
        try driver.open(conversation)
        try driver.require(driver.stableTail(conversation.tail), "Begin keyboard journey at the rendered tail")
        let composer = driver.app.textViews["Message"]
        composer.tap()
        try driver.require(driver.app.keyboards.firstMatch.waitForExistence(timeout: 5), "Exercise a genuine software keyboard, not a simulated inset")
        try clearLocalDraft(composer)
        try driver.require(driver.stableTail(conversation.tail), "Keyboard appearance keeps the actual card tail above the composer")
        driver.capture("candidate-keyboard-follow-tail", tree: true)
        let draft = "line one\nline two\nline three"
        composer.typeText(draft)
        try requireComposerValue(draft, composer: composer)
        try driver.require(driver.stableTail(conversation.tail), "Growing multiline composer must also keep following")
        driver.capture("candidate-multiline-composer-follow-tail")
        // Only this isolated user's unsent local draft is changed, through the system editor.
        try clearLocalDraft(composer)
        try driver.backToChats()
        try driver.open(conversation)
        try requireComposerValue("", composer: driver.app.textViews["Message"])
        try driver.require(driver.stableTail(conversation.tail), "Keyboard removal/navigation settles at the true latest tail")
        driver.capture("candidate-keyboard-removed-tail")
    }

    func testEarlierCompletionCannotReclaimLatest() throws {
        let title = try NativeChatFixture.required("NANO_UI_EARLIER_RACE_TITLE")
        let tail = try NativeChatFixture.required("NANO_UI_PAGINATION_TAIL")
        try driver.launchAndLogin()
        let row = driver.app.staticTexts.matching(NSPredicate(format: "label == %@", title)).firstMatch
        try driver.require(row.waitForExistence(timeout: 8), "The fresh pagination-race conversation must exist")
        row.tap()
        try driver.require(driver.stableTail(tail, timeout: 10), "Begin at the actual latest message")
        driver.app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 80, dy: 30)).tap()
        driver.pause(1)
        try driver.seekEarlier(maxSwipes: 12)
        driver.app.buttons["Earlier messages"].tap()
        let latest = driver.app.buttons["Latest messages"]
        try driver.require(latest.waitForExistence(timeout: 5), "History offers a real Latest action")
        let latestStart = Date().timeIntervalSince1970
        latest.tap()
        driver.record("earlier-race-latest-tap", ["unixSeconds": latestStart])
        try driver.require(driver.stableTail(tail), "Latest owns the final geometry after Earlier")
        // Let the fixture's held response arrive, then observe its resulting layout.
        driver.pause(4.5)
        try driver.require(driver.stableTail(tail), "Late page/layout updates cannot reclaim the old reading anchor")
        driver.capture("candidate-earlier-then-latest-still-tail", tree: true)
    }

    /// Bounded functional diagnosis of the same first history gestures, not a performance sample.
    func testNativeMarkdownTwelveGestureDiagnostic() throws {
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == "markdown" })
        try driver.launchAndLogin()
        try driver.open(conversation)
        for _ in 0..<6 { driver.swipe(history: true) }
        try driver.require(driver.app.textViews["Message"].exists, "Native Markdown remains responsive after six history gestures")
        driver.capture("diagnostic-markdown-after-six-history", tree: true)
        for _ in 0..<6 { driver.swipe(history: false) }
        try driver.require(driver.app.textViews["Message"].exists, "Native Markdown remains responsive after six return gestures")
        driver.capture("diagnostic-markdown-after-six-return", tree: true)
    }

    /// Reading ownership and an explicit Latest command are separate from return gestures.
    func testNativeMarkdownReadingAndExplicitLatest() throws {
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == "markdown" })
        try driver.launchAndLogin()
        try driver.open(conversation)
        // Do not repair fresh entry with Latest or a setup scroll before this assertion.
        try driver.require(driver.stableTail(conversation.tail), "Untouched Markdown entry must show the actual stable tail")
        driver.capture("markdown-reading-fresh-true-tail", tree: true)

        for _ in 0..<6 { driver.swipe(history: true) }
        driver.pause(0.5)
        let anchor = try requireReadingHistory(conversation, name: "markdown-reading-after-six-history")
        driver.pause(0.8)
        try requireReadingHistoryUnchanged(conversation, anchor: anchor, name: "markdown-reading-not-reclaimed")

        driver.app.buttons["Latest messages"].tap()
        try driver.require(driver.stableTail(conversation.tail), "Explicit Latest must complete at the actual Markdown tail, not merely issue a scroll")
        try requireLatestAbsent()
        driver.capture("markdown-reading-explicit-latest-true-tail", tree: true)
    }

    func testStatusBarScrollToTopKeepsUserReading() throws {
        let conversation = try XCTUnwrap(driver.fixture.conversations.first { $0.kind == "markdown" })
        try driver.launchAndLogin()
        try driver.open(conversation)
        try driver.require(driver.stableTail(conversation.tail), "Begin native scroll-to-top at the untouched actual tail")
        driver.capture("markdown-status-bar-before-clock", tree: true)

        // Exercise native scroll-to-top itself. No seekHistoryStart/swipe fallback is allowed.
        driver.app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 80, dy: 30)).tap()
        driver.pause(1)
        let earlierVisible = driver.fullyVisible(driver.app.buttons["Earlier messages"])
        let firstVisible = driver.fullyVisible(driver.text("H763-001"))
        driver.record("markdown-status-bar-top-result", ["earlierVisible": earlierVisible,
                                                       "firstMarkerVisible": firstVisible, "fallbackSwipes": 0])
        driver.capture("markdown-status-bar-top-result", tree: true)
        try driver.require(earlierVisible || firstVisible, "The clock tap alone must reveal Earlier or the actual H763-001 history top")
        let anchor = try requireReadingHistory(conversation, name: "markdown-status-bar-reading")
        driver.pause(0.8)
        try requireReadingHistoryUnchanged(conversation, anchor: anchor, name: "markdown-status-bar-not-reclaimed")

        driver.app.buttons["Latest messages"].tap()
        try driver.require(driver.stableTail(conversation.tail), "Latest after native scroll-to-top must return to the actual stable tail")
        try requireLatestAbsent()
        driver.capture("markdown-status-bar-latest-true-tail", tree: true)
    }

    /// One fresh D run: 61...120, an actual Earlier prepend, then independent 001 proof.
    func testEarlierPrependRestoresTheSameFirstVisibleHistoryMessageY() throws {
        let title = try NativeChatFixture.required("NANO_UI_PAGINATION_TITLE")
        let tail = try NativeChatFixture.required("NANO_UI_PAGINATION_TAIL")
        let oldHead = try NativeChatFixture.required("NANO_UI_PAGINATION_OLD_HEAD")
        let newHead = try NativeChatFixture.required("NANO_UI_PAGINATION_NEW_HEAD")
        try driver.launchAndLogin()
        let row = driver.app.staticTexts.matching(NSPredicate(format: "label == %@", title)).firstMatch
        try driver.require(row.waitForExistence(timeout: 8), "The dedicated fresh D conversation must exist")
        row.tap()
        try driver.require(driver.app.textViews["Message"].waitForExistence(timeout: 10), "D composer must load normally")
        try driver.require(driver.stableTail(tail), "Untouched D entry must show the actual tail without repair")
        var ready = false
        for _ in 0..<180 {
            let sample = try paginationSample(oldHead: oldHead, newHead: newHead, tail: tail)
            try driver.require(!sample.newVisible, "BLOCKED: D already exposes 001; this case needs a new 60-message cache window, never a database reset")
            if sample.earlierVisible && sample.headVisible && sample.firstVisibleHeader == oldHead && sample.reading { ready = true; break }
            driver.swipe(history: true)
        }
        driver.capture("D-earlier-before-prepend", tree: true)
        try driver.require(ready, "BLOCKED: fresh D must expose Earlier and its first old header 061 together; a cached 120-message window is not a valid start")
        var before: [PaginationSample] = []
        for _ in 0..<3 {
            before.append(try paginationSample(oldHead: oldHead, newHead: newHead, tail: tail))
            driver.pause(0.2)
        }
        let reference = before[0]
        try driver.require(before.allSatisfy { $0.headVisible && $0.earlierVisible && $0.firstVisibleHeader == oldHead && $0.reading && abs($0.head.minY - reference.head.minY) <= 4 },
                           "The actual first old header must be stable before Earlier")
        try driver.require(reference.head.minY - reference.area.minY > 4 && driver.app.buttons["Earlier messages"].isHittable && driver.app.buttons["Latest messages"].isHittable,
                           "Preserve a nonzero original viewport offset, not a Reader.top-only target")
        // D timestamps are 360s apart: prepending cannot remove 061's in-row timestamp.
        driver.record("D-pagination-reference", ["title": title, "oldHead": oldHead, "newHead": newHead,
                      "tail": tail, "before": before.map(\.evidence), "timestampSpacingSeconds": 360])
        driver.app.buttons["Earlier messages"].tap()
        var after: [PaginationSample] = [], consecutive = 0
        let deadline = ProcessInfo.processInfo.systemUptime + 15
        repeat {
            let sample = try paginationSample(oldHead: oldHead, newHead: newHead, tail: tail)
            after.append(sample)
            driver.record("D-pagination-live-sample", sample.evidence)
            consecutive = sample.restored(to: reference) ? consecutive + 1 : 0
            if consecutive >= 3 {
                let ys = after.suffix(3).map { $0.head.minY } + [reference.head.minY]
                if (ys.max() ?? 0) - (ys.min() ?? 0) <= 4 { break }
            }
            driver.pause(0.2)
        } while ProcessInfo.processInfo.systemUptime < deadline
        // Retain realization transients, but never replace the pre-click reference with them.
        driver.capture("D-pagination-restoration-outcome", tree: true)
        try driver.require(consecutive >= 3 && after.suffix(3).allSatisfy { $0.restored(to: reference) },
                           "Earlier must restore the same 061 header to its original y within 4pt for three real AX frames")
        for _ in 0..<4 {
            driver.pause(0.2)
            after.append(try paginationSample(oldHead: oldHead, newHead: newHead, tail: tail))
        }
        let settledY = after.suffix(7).map { $0.head.minY } + [reference.head.minY]
        driver.record("D-pagination-restoration-result", ["originalReference": reference.evidence,
                      "allAfterSamples": after.map(\.evidence), "gesturesAfterEarlier": 0, "LatestTaps": 0,
                      "coverage": "External restoration only; correlate normal R6 trace before claiming Reader and UIKit-y branches"])
        try driver.require(after.allSatisfy(\.reading), "Latest must remain present and the actual tail outside the viewport throughout pagination")
        try driver.require(after.suffix(7).allSatisfy { $0.restored(to: reference) } && (settledY.max() ?? 0) - (settledY.min() ?? 0) <= 4,
                           "The original 061 y must remain restored through the subsequent observation window")
        try driver.require(driver.app.buttons["Latest messages"].isHittable, "Restored history keeps Latest operable")
        driver.capture("D-pagination-restored-original-y", tree: true)

        // Only after restoration passes, a NEW user input reveals the inserted page.
        driver.app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 80, dy: 30)).tap()
        let topDeadline = ProcessInfo.processInfo.systemUptime + 5
        var top = try paginationSample(oldHead: oldHead, newHead: newHead, tail: tail)
        while !top.newVisible && ProcessInfo.processInfo.systemUptime < topDeadline {
            driver.pause(0.2)
            top = try paginationSample(oldHead: oldHead, newHead: newHead, tail: tail)
        }
        driver.record("D-pagination-inserted-page-proof", ["sample": top.evidence, "clockTaps": 1,
                      "fallbackSwipes": 0, "proofOccursAfterRestorationAssertions": true])
        driver.capture("D-pagination-clock-reveals-001", tree: true)
        try driver.require(top.newVisible && top.reading, "The clock alone must reveal actual new header 001; a no-op Earlier must not pass")
    }

    private struct PaginationSample {
        let head: CGRect
        let area: CGRect
        let headCount: Int
        let latestCount: Int
        let earlierCount: Int
        let earlierVisible: Bool
        let firstVisibleHeader: String
        let newVisible: Bool
        let tailIntersects: Bool
        let loading: Bool
        let uptime: TimeInterval
        var headVisible: Bool { headCount == 1 && head.width > 0 && head.height > 0 && area.contains(head) }
        var reading: Bool { latestCount == 1 && !tailIntersects }
        func restored(to reference: Self) -> Bool {
            headVisible && reading && !loading && earlierCount == 0 && abs(head.minY - reference.head.minY) <= 4 && abs(area.minY - reference.area.minY) <= 1
        }
        var evidence: [String: Any] {
            ["uptime": uptime, "oldHeadCount": headCount, "oldHeadY": headCount == 1 ? head.minY as Any : NSNull(),
             "oldHeadHeight": head.height, "oldHeadVisible": headVisible, "newHeadVisible": newVisible,
             "navMaxY": area.minY, "effectiveComposerMinY": area.maxY, "LatestCount": latestCount,
             "EarlierCount": earlierCount, "earlierVisible": earlierVisible, "firstVisibleHeader": firstVisibleHeader, "loading": loading,
             "actualTailIntersectsViewport": tailIntersects, "reading": reading]
        }
    }

    private func paginationSample(oldHead: String, newHead: String, tail: String) throws -> PaginationSample {
        // A single public AX generation supplies all message/button/viewport observations.
        let root = try driver.app.snapshot()
        func nativeNodes(_ node: any XCUIElementSnapshot) -> [any XCUIElementSnapshot] {
            node.elementType == .webView ? [] : [node] + node.children.flatMap { nativeNodes($0) }
        }
        let nodes = nativeNodes(root)
        let nav = try XCTUnwrap(nodes.first { $0.elementType == .navigationBar })
        let composer = try XCTUnwrap(nodes.first { $0.elementType == .textView && $0.label == "Message" })
        let area = CGRect(x: root.frame.minX, y: nav.frame.maxY, width: root.frame.width,
                          height: max(0, composer.frame.minY - 10 - nav.frame.maxY))
        let old = nodes.filter { $0.elementType == .staticText && $0.label == oldHead }
        let new = nodes.filter { $0.elementType == .staticText && $0.label == newHead }
        let earlier = nodes.filter { $0.elementType == .button && $0.label == "Earlier messages" }
        let latest = nodes.filter { $0.elementType == .button && $0.label == "Latest messages" }
        func visible(_ frames: [CGRect]) -> Bool { frames.count == 1 && frames[0].width > 0 && frames[0].height > 0 && area.contains(frames[0]) }
        let tailIntersects = nodes.contains { $0.elementType == .staticText && $0.label.contains(tail) && $0.frame.width > 0 && $0.frame.height > 0 && area.intersects($0.frame) }
        let firstHeader = nodes.filter { $0.elementType == .staticText && $0.label.hasPrefix("D763-") && $0.frame.width > 0 && $0.frame.height > 0 && area.intersects($0.frame) }.min { $0.frame.minY < $1.frame.minY }?.label ?? ""
        return PaginationSample(head: old.count == 1 ? old[0].frame : .zero, area: area, headCount: old.count,
                                latestCount: latest.count, earlierCount: earlier.count, earlierVisible: visible(earlier.map(\.frame)),
                                firstVisibleHeader: firstHeader, newVisible: visible(new.map(\.frame)), tailIntersects: tailIntersects,
                                loading: nodes.contains { $0.label == "Loading history…" }, uptime: ProcessInfo.processInfo.systemUptime)
    }

    private func requireReadingHistory(_ conversation: NativeChatFixture.Conversation,
                                       name: String) throws -> (element: XCUIElement, marker: String, y: CGFloat) {
        let latest = driver.app.buttons["Latest messages"]
        try driver.require(latest.exists && latest.isHittable, "History reading must expose an operable Latest action")
        let anchor = try visibleHistoryAnchor()
        let frame = try anchor.element.snapshot().frame
        let area = driver.viewport
        let tailElement = driver.text(conversation.tail)
        let tailFrame: CGRect?
        if tailElement.exists { tailFrame = try tailElement.snapshot().frame } else { tailFrame = nil }
        let tailIntersects = tailFrame.map { $0.width > 0 && $0.height > 0 && area.intersects($0) } ?? false
        driver.record(name, ["visibleHistoryMarker": anchor.marker, "anchorY": frame.minY,
                             "tailInAX": tailFrame != nil, "tailIntersectsViewport": tailIntersects,
                             "navMaxY": area.minY, "composerMinY": area.maxY,
                             "latestHittable": latest.isHittable])
        driver.capture(name, tree: true)
        try driver.require(!tailIntersects, "The actual tail must be outside the effective viewport while reading history")
        return (anchor.element, anchor.marker, frame.minY)
    }

    private func requireReadingHistoryUnchanged(_ conversation: NativeChatFixture.Conversation,
                                                anchor: (element: XCUIElement, marker: String, y: CGFloat),
                                                name: String) throws {
        _ = try requireReadingHistory(conversation, name: name)
        try driver.require(driver.fullyVisible(anchor.element), "A short observation window must retain the same visible history marker")
        let y = try anchor.element.snapshot().frame.minY
        driver.record(name + "-anchor", ["marker": anchor.marker, "beforeY": anchor.y, "afterY": y])
        try driver.require(abs(y - anchor.y) <= 4, "History must not be automatically reclaimed after native scrolling")
    }

    private func requireLatestAbsent() throws {
        let deadline = Date().addingTimeInterval(2)
        while driver.app.buttons["Latest messages"].exists && Date() < deadline { driver.pause(0.1) }
        try driver.require(!driver.app.buttons["Latest messages"].exists, "Latest must disappear after the actual tail completion")
    }

    private func composerValue(_ composer: XCUIElement) throws -> String? {
        let snapshot = try composer.snapshot()
        if let value = snapshot.value { return try XCTUnwrap(value as? String) }
        // UIKit can omit an empty text view's AX value. Cross-check the actual
        // composer placeholder and send action before treating that as empty.
        let placeholder = driver.app.staticTexts.matching(
            NSPredicate(format: "label IN %@", ["Message…", "Message, @ to mention"])
        ).firstMatch
        let send = driver.app.buttons["Send"]
        return placeholder.exists && send.exists && !send.isEnabled ? "" : nil
    }

    private func requireComposerValue(_ expected: String, composer: XCUIElement) throws {
        let deadline = Date().addingTimeInterval(3)
        repeat {
            if try composerValue(composer) == expected { return }
            driver.pause(0.1)
        } while Date() < deadline
        driver.capture("composer-value-mismatch", tree: true)
        try driver.require(false, "The real composer must exactly match the expected local draft")
    }

    private func clearLocalDraft(_ composer: XCUIElement) throws {
        let initial = try XCTUnwrap(composerValue(composer), "The composer must expose its draft or its empty state")
        guard !initial.isEmpty else { return }
        let label = NSPredicate(format: "label IN %@", ["Select All", "全选"])
        for attempt in 0..<2 {
            if attempt > 0 { composer.tap() }
            composer.press(forDuration: 1)
            let menuItems = driver.app.menuItems.matching(label).allElementsBoundByIndex.filter(\.isHittable)
            let buttons = driver.app.buttons.matching(label).allElementsBoundByIndex.filter(\.isHittable)
            let choices = menuItems.isEmpty ? buttons : menuItems
            if choices.count == 1 {
                choices[0].tap()
                composer.typeText(XCUIKeyboardKey.delete.rawValue)
                try requireComposerValue("", composer: composer)
                let confirmedEmpty = try composerValue(composer)
                try driver.require(confirmedEmpty == "", "Deleted local draft remains empty on a second observation")
                return
            }
        }
        driver.capture("composer-select-all-unavailable", tree: true)
        try driver.require(false, "A unique public Select All action must be available; counted backspace is not a cleanup substitute")
    }

    private func visibleHistoryAnchor() throws -> (element: XCUIElement, marker: String) {
        let viewport = driver.viewport
        // A tall Markdown message can fill the viewport with its numbered body
        // while its header is offscreen.
        let pattern = #"(H763-(?!300)[0-9]{3} · .*|引用块 (?!300)[0-9]{3}：.*|fixture_763_(?!300)[0-9]{3})"#
        let markers = driver.app.staticTexts.matching(NSPredicate(format: "label MATCHES %@", pattern))
        for element in markers.allElementsBoundByIndex {
            guard let snapshot = try? element.snapshot(), !snapshot.frame.isEmpty,
                  viewport.contains(snapshot.frame) else { continue }
            let anchor = driver.app.staticTexts.matching(NSPredicate(format: "label == %@", snapshot.label)).firstMatch
            return (anchor, snapshot.label)
        }
        driver.capture("candidate-no-visible-history-anchor", tree: true)
        throw NSError(domain: "ChatReadingContinuity", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "No fully visible history message marker after real swipes"])
    }
}
