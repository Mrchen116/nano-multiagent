import XCTest
import SwiftUI
import UIKit
@testable import NanoIM

final class ChatScrollPolicyTests: XCTestCase {
    func testFreshEntryAlwaysFollowsLatestWithoutWaitingForItemCount() {
        let policy = ChatScrollPolicy()
        XCTAssertEqual(policy.intent, .latest)
        XCTAssertNil(policy.anchor)
    }

    func testTouchWithoutMovementDoesNotLoseFollowing() {
        var policy = ChatScrollPolicy()
        policy.changePhase(.tracking, offset: 100, atBottom: true)
        XCTAssertTrue(policy.pausesCorrection)
        policy.changePhase(.idle, offset: 100, atBottom: false)
        XCTAssertEqual(policy.intent, .latest, "A resize during a card tap is not user scrolling")
        XCTAssertEqual(policy.revision, 0)
        XCTAssertFalse(policy.pausesCorrection)
    }

    func testDetachingDuringDecelerationKeepsReadingIntentAndReleasesCorrection() {
        var policy = ChatScrollPolicy()
        policy.changePhase(.interacting, offset: 800, atBottom: true)
        XCTAssertTrue(policy.moved(to: 700))
        policy.changePhase(.decelerating, offset: 700, atBottom: false)
        let revision = policy.revision
        XCTAssertTrue(policy.pausesCorrection)
        policy.endScrollSurface()
        XCTAssertEqual(policy.intent, .history)
        XCTAssertEqual(policy.revision, revision)
        XCTAssertFalse(policy.pausesCorrection)
    }

    func testOnlyActualGestureMovementInvalidatesEarlierRestore() {
        var policy = ChatScrollPolicy()
        policy.changePhase(.tracking, offset: 800, atBottom: true)
        policy.changePhase(.interacting, offset: 800, atBottom: true)
        XCTAssertFalse(policy.moved(to: 800))
        XCTAssertTrue(policy.moved(to: 780))
        XCTAssertEqual(policy.intent, .history)
        let revision = policy.revision
        XCTAssertFalse(policy.moved(to: 700), "Each gesture advances once, not once per pixel")
        policy.changePhase(.decelerating, offset: 700, atBottom: false)
        XCTAssertTrue(policy.pausesCorrection)
        policy.changePhase(.idle, offset: 500, atBottom: false)
        policy.remember(.init(id: "message", viewportY: -20))
        XCTAssertTrue(policy.admitsRestore(revision: revision))
        policy.latest()
        XCTAssertFalse(policy.admitsRestore(revision: revision))
        XCTAssertNil(policy.anchor)
        XCTAssertEqual(policy.intent, .latest)
        // Returning to history is a new operation, not permission for an old page restore.
        policy.changePhase(.tracking, offset: 1000, atBottom: true)
        policy.changePhase(.interacting, offset: 1000, atBottom: true)
        XCTAssertTrue(policy.moved(to: 900))
        policy.changePhase(.idle, offset: 900, atBottom: false)
        XCTAssertEqual(policy.intent, .history)
        XCTAssertFalse(policy.admitsRestore(revision: revision))
    }

    func testLayoutMovementAndProgrammaticScrollAreNotUserIntent() {
        var policy = ChatScrollPolicy()
        XCTAssertFalse(policy.moved(to: 2000))
        policy.changePhase(.animating, offset: 2000, atBottom: false)
        XCTAssertFalse(policy.moved(to: 3000))
        policy.changePhase(.idle, offset: 3000, atBottom: true)
        XCTAssertEqual(policy.intent, .latest)
        XCTAssertEqual(policy.revision, 0)
    }

    func testUserReturningToActualBottomResumesFollowing() {
        var policy = ChatScrollPolicy()
        policy.changePhase(.tracking, offset: 0, atBottom: false)
        policy.changePhase(.interacting, offset: 0, atBottom: false)
        XCTAssertTrue(policy.moved(to: 200))
        policy.changePhase(.idle, offset: 200, atBottom: true)
        XCTAssertEqual(policy.intent, .latest)
        XCTAssertNil(policy.anchor)
    }

    @MainActor
    func testGeometryNotificationBeforeInteractingPhaseStillCommitsUserReading() {
        let coordinator = ChatScrollCoordinator()
        var invalidations = 0
        coordinator.invalidateRestoration = { invalidations += 1 }
        coordinator.geometryChanged(geometry(offset: 1400))
        coordinator.phaseChanged(.tracking, geometry: geometry(offset: 1400))
        // The final offset can arrive while the policy still sees tracking.
        coordinator.geometryChanged(geometry(offset: 1200))
        coordinator.phaseChanged(.interacting, geometry: geometry(offset: 1200))
        coordinator.phaseChanged(.idle, geometry: geometry(offset: 1200))
        XCTAssertTrue(coordinator.readingHistory)
        XCTAssertEqual(invalidations, 1, "The actual gesture invalidates pending restoration once")
        coordinator.disappeared()
    }

    @MainActor
    func testUnrealizedAuthoritativeAnchorIsRealizedBeforeOffsetRestoration() async {
        let coordinator = ChatScrollCoordinator()
        let surface = ScrollSurface(adapter: coordinator.physicalGeometry)
        surface.addRow("A", y: 580)
        surface.addRow("B", y: 1210)
        var requests: [(String, UnitPoint)] = []
        coordinator.attachMessageScroller { requests.append(($0, $1)) }
        beginHistory(coordinator)
        XCTAssertEqual(coordinator.policy.anchor?.id, "A")
        surface.removeRow("A")
        coordinator.rowDisappeared("A")
        await eventually { requests.last?.0 == "A" && requests.last?.1 == .top }
        XCTAssertEqual(coordinator.policy.anchor?.id, "A", "Lazy recycling is not authoritative deletion")
        // Model Reader realization in a changed native layout. SwiftUI's cached offset remains
        // old; only the coherent live row+offset may determine the resulting native position.
        surface.scroll.contentOffset.y = 1190
        surface.addRow("A", y: 1190)
        await eventually { surface.scroll.contentOffset.y == 1210 }
        XCTAssertEqual(coordinator.policy.anchor?.viewportY, -20)
        XCTAssertEqual(surface.rows["A"]!.convert(surface.rows["A"]!.bounds, to: surface.window).minY, -20)
        coordinator.disappeared()
    }

    @MainActor
    func testNativeEffectiveViewportDoesNotApplySystemInsetsTwice() {
        let coordinator = ChatScrollCoordinator()
        // Captured native frames: the ScrollView's global frame already excludes navigation,
        // composer and keyboard. ScrollGeometry also reports the system insets separately.
        let visible = CGRect(x: 0, y: 116, width: 402, height: 361.66666666666663)
        coordinator.viewportChanged(visible)
        coordinator.geometryChanged(ScrollGeometry(
            contentOffset: CGPoint(x: 0, y: 118565.33333333333),
            contentSize: CGSize(width: 402, height: 119043),
            contentInsets: EdgeInsets(top: 116, leading: 0, bottom: 396.3333333333333, trailing: 0),
            containerSize: visible.size))
        XCTAssertEqual(coordinator.viewport, visible, "Keyboard insets must not collapse a real 361pt viewport to zero")
        coordinator.disappeared()
    }

    @MainActor
    func testActualVisibleTailDoesNotRemainLatestBecauseOfEstimatedExtent() {
        let coordinator = ChatScrollCoordinator()
        let visible = CGRect(x: 0, y: 116, width: 402, height: 663.6666666666666)
        coordinator.viewportChanged(visible)
        coordinator.geometryChanged(ScrollGeometry(
            contentOffset: CGPoint(x: 0, y: 113565.33333333333),
            contentSize: CGSize(width: 402, height: 114345),
            contentInsets: EdgeInsets(top: 116, leading: 0, bottom: 94.33333333333337, trailing: 0),
            containerSize: visible.size))
        coordinator.contentChanged(orderedMessageIDs: ["final"])
        coordinator.rowChanged("final", frame: CGRect(x: 16, y: 648, width: 370, height: 114.0926424352656))
        XCTAssertFalse(coordinator.showLatest, "An actual native final tail inside the effective viewport is not offscreen")
        coordinator.rowChanged("final", frame: CGRect(x: 16, y: 1386, width: 370, height: 114))
        XCTAssertTrue(coordinator.showLatest, "A genuinely offscreen tail must still offer Latest")
        coordinator.disappeared()
    }

    @MainActor
    func testExpandingViewportRealignsAnAlreadyVisibleTail() async {
        let coordinator = ChatScrollCoordinator()
        let surface = ScrollSurface(adapter: coordinator.physicalGeometry)
        surface.addRow("last", y: 1771)
        surface.viewport.frame.size.height = 300
        surface.scroll.contentInset.bottom = 300
        surface.scroll.contentOffset.y = 1700
        coordinator.attachMessageScroller { _, _ in XCTFail("The visible tail can be aligned directly") }
        defer { coordinator.disappeared() }
        coordinator.viewportChanged(surface.viewport.frame)
        coordinator.geometryChanged(geometry(offset: 1700))
        coordinator.contentChanged(orderedMessageIDs: ["last"])
        XCTAssertFalse(coordinator.showLatest)

        // The viewport and inset have settled, but the scroll offset still reflects
        // the keyboard layout. The final row remains visible 329pt above the bottom.
        surface.viewport.frame.size.height = 600
        surface.scroll.contentInset.bottom = 0
        surface.scroll.contentOffset.y = 1700
        coordinator.viewportChanged(surface.viewport.frame)
        coordinator.geometryChanged(geometry(offset: 1700))
        XCTAssertFalse(coordinator.showLatest, "The tail is visible throughout the expansion")
        await eventually { surface.scroll.contentOffset.y == 1400 }
        XCTAssertEqual(surface.rows["last"]!.convert(surface.rows["last"]!.bounds, to: surface.window).maxY, 571)
    }

    @MainActor
    func testFinalMessageBottomIsAuthoritativeEvenForTallRows() {
        let coordinator = ChatScrollCoordinator()
        coordinator.viewportChanged(CGRect(x: 0, y: 116, width: 402, height: 664))
        coordinator.contentChanged(orderedMessageIDs: ["earlier", "last"])
        coordinator.rowChanged("earlier", frame: CGRect(x: 16, y: 200, width: 370, height: 100))
        XCTAssertTrue(coordinator.showLatest, "An earlier visible row cannot stand in for the final message")
        coordinator.rowChanged("last", frame: CGRect(x: 16, y: -500, width: 370, height: 1264))
        XCTAssertFalse(coordinator.showLatest, "A tall final row need not be entirely visible at its bottom")
        coordinator.rowChanged("last", frame: CGRect(x: 16, y: -500, width: 370, height: 1500))
        XCTAssertTrue(coordinator.showLatest, "A dynamic height change immediately exposes the offscreen tail")
        coordinator.disappeared()
    }

    @MainActor
    func testLatestIdentityChangesInvalidateOldCompletionAndEmptyHasNoTarget() async {
        let coordinator = ChatScrollCoordinator()
        var requests: [(String, UnitPoint)] = []
        coordinator.attachMessageScroller { requests.append(($0, $1)) }
        coordinator.viewportChanged(CGRect(x: 0, y: 0, width: 400, height: 600))
        coordinator.geometryChanged(geometry(offset: 1400))
        coordinator.contentChanged(orderedMessageIDs: ["A"])
        coordinator.rowChanged("A", frame: CGRect(x: 16, y: 400, width: 368, height: 180))
        XCTAssertFalse(coordinator.showLatest)
        coordinator.contentChanged(orderedMessageIDs: ["A", "B"])
        XCTAssertTrue(coordinator.showLatest, "A newly authoritative final row must obtain its own frame")
        coordinator.latest()
        XCTAssertEqual(requests.last?.0, "B", "Positioning and completion share the same final identity")
        XCTAssertEqual(requests.last?.1, .bottom)
        coordinator.rowChanged("B", frame: CGRect(x: 16, y: 400, width: 368, height: 180))
        XCTAssertFalse(coordinator.showLatest)
        coordinator.rowDisappeared("B")
        XCTAssertTrue(coordinator.showLatest, "Recycling cannot keep stale completion")
        coordinator.contentChanged(orderedMessageIDs: [])
        XCTAssertFalse(coordinator.showLatest, "An empty conversation has no jump-to-latest target")
        coordinator.disappeared()
    }

    @MainActor
    func testPendingLatestSurvivesMissingAdapterAndStaleDetach() async {
        let coordinator = ChatScrollCoordinator()
        coordinator.viewportChanged(CGRect(x: 0, y: 0, width: 400, height: 600))
        coordinator.geometryChanged(geometry(offset: 1400))
        coordinator.contentChanged(orderedMessageIDs: ["last"])
        coordinator.latest()
        // The target remains pending even if initial layout arrives before Reader installation.
        for _ in 0..<5 { await Task.yield() }
        var oldRequests: [String] = []
        let old = coordinator.attachMessageScroller { id, _ in oldRequests.append(id) }
        await eventually { oldRequests.last == "last" }
        var currentRequests: [String] = []
        let current = coordinator.attachMessageScroller { id, _ in currentRequests.append(id) }
        coordinator.detachMessageScroller(old)
        coordinator.latest()
        XCTAssertEqual(currentRequests.last, "last", "Old disappearance must not deactivate the current View")
        coordinator.detachMessageScroller(current)
        let count = currentRequests.count
        coordinator.latest()
        XCTAssertEqual(currentRequests.count, count, "A detached View cannot receive requests")
    }

    @MainActor
    func testHistoryIDJumpWaitsForOneCoherentNativeGeometryInsteadOfMixedCallbacks() async {
        let coordinator = ChatScrollCoordinator()
        let surface = ScrollSurface(adapter: coordinator.physicalGeometry)
        surface.addRow("A", y: 580)
        surface.addRow("B", y: 1210)
        var requests: [String] = []
        coordinator.attachMessageScroller { id, _ in requests.append(id) }
        beginHistory(coordinator)
        surface.removeRow("B")
        coordinator.restore("B")
        XCTAssertEqual(requests.last, "B")
        // Reproduce both mixed-cache orders from CODE-763-L1 without changing the live tree.
        coordinator.geometryChanged(geometry(offset: 1190))
        for _ in 0..<5 { await Task.yield() }
        XCTAssertEqual(surface.scroll.contentOffset.y, 600, "New cached offset + old row cannot issue y")
        coordinator.rowChanged("B", frame: CGRect(x: 0, y: 0, width: 400, height: 200))
        for _ in 0..<5 { await Task.yield() }
        XCTAssertEqual(surface.scroll.contentOffset.y, 600, "Independent cached row still is not a live snapshot")
        surface.scroll.contentOffset.y = 1190
        surface.addRow("B", y: 1190)
        coordinator.physicalGeometry.markersChanged()
        await eventually { surface.scroll.contentOffset.y == 1210 }
        // A new genuine gesture invalidates the pending operation and suppresses correction.
        coordinator.phaseChanged(.tracking, geometry: geometry(offset: 1210))
        coordinator.phaseChanged(.interacting, geometry: geometry(offset: 1210))
        surface.scroll.contentOffset.y = 500
        coordinator.geometryChanged(geometry(offset: 500))
        coordinator.physicalGeometry.markersChanged()
        for _ in 0..<5 { await Task.yield() }
        XCTAssertEqual(surface.scroll.contentOffset.y, 500, "No native correction may run during active user scrolling")
        coordinator.disappeared()
    }

    @MainActor
    func testAlreadyRealizedHistoryRestoreDoesNotWaitForANoopReaderJump() async {
        let coordinator = ChatScrollCoordinator()
        let surface = ScrollSurface(adapter: coordinator.physicalGeometry)
        surface.addRow("A", y: 580); surface.addRow("B", y: 1210)
        var requests: [String] = []
        coordinator.attachMessageScroller { id, _ in requests.append(id) }
        beginHistory(coordinator)
        XCTAssertEqual(coordinator.policy.anchor?.viewportY, -20)
        // The target is already at Reader's .top, but not at the saved relative Y.
        // Reader may legitimately do nothing, without any later layout notification.
        surface.rows["A"]!.frame.origin.y = 600
        coordinator.restore("A")
        await eventually { surface.scroll.contentOffset.y == 620 }
        XCTAssertEqual(surface.rows["A"]!.convert(surface.rows["A"]!.bounds, to: surface.window).minY, -20)
        XCTAssertTrue(requests.isEmpty, "A live target needs coherent Y correction, not realization")
        coordinator.disappeared()
    }

    @MainActor
    func testNativeTopCompletionUsesLiveMarkersInsteadOfStaleSwiftUICaches() async throws {
        for cachedTailY: CGFloat in [400, 610] {
            let coordinator = ChatScrollCoordinator()
            let surface = ScrollSurface(adapter: coordinator.physicalGeometry)
            surface.addRow("A", y: 0); surface.addRow("B", y: 1210)
            coordinator.viewportChanged(surface.viewport.frame)
            coordinator.contentChanged(orderedMessageIDs: ["A", "B"])
            coordinator.geometryChanged(geometry(offset: 600))
            coordinator.rowChanged("A", frame: CGRect(x: 16, y: -20, width: 368, height: 200))
            coordinator.rowChanged("B", frame: CGRect(x: 16, y: cachedTailY, width: 368, height: 200))
            coordinator.attachMessageScroller { _, _ in }
            let proxy = try XCTUnwrap(surface.scroll.delegate as? ChatScrollDelegateObserver)
            XCTAssertTrue(proxy.scrollViewShouldScrollToTop(surface.scroll))
            // UIKit finishes first. Deliberately deliver no matching SwiftUI row/offset callbacks.
            surface.scroll.contentOffset.y = 0
            proxy.scrollViewDidScrollToTop(surface.scroll)
            XCTAssertTrue(coordinator.readingHistory, "A cached visible tail must not reclaim Latest")
            XCTAssertEqual(coordinator.policy.anchor?.id, "A")
            XCTAssertEqual(coordinator.policy.anchor?.viewportY, 0)
            XCTAssertTrue(coordinator.showLatest)
            for _ in 0..<5 { await Task.yield() }
            XCTAssertEqual(surface.scroll.contentOffset.y, 0, "Completion must not restore the old cached relative Y")
            coordinator.disappeared()
        }
    }

    @MainActor
    private func beginHistory(_ coordinator: ChatScrollCoordinator) {
        coordinator.viewportChanged(CGRect(x: 0, y: 0, width: 400, height: 600))
        coordinator.contentChanged(orderedMessageIDs: ["A", "B"])
        coordinator.geometryChanged(geometry(offset: 620))
        coordinator.rowChanged("A", frame: CGRect(x: 0, y: -20, width: 400, height: 200))
        coordinator.rowChanged("B", frame: CGRect(x: 0, y: 610, width: 400, height: 200))
        coordinator.phaseChanged(.tracking, geometry: geometry(offset: 620))
        coordinator.phaseChanged(.interacting, geometry: geometry(offset: 620))
        coordinator.geometryChanged(geometry(offset: 600))
        coordinator.phaseChanged(.idle, geometry: geometry(offset: 600))
    }

    @MainActor
    private final class ScrollSurface {
        let window = UIWindow(frame: CGRect(x: 0, y: 0, width: 400, height: 600))
        let scroll = UIScrollView(frame: CGRect(x: 0, y: 0, width: 400, height: 600))
        let content = UIView(frame: CGRect(x: 0, y: 0, width: 400, height: 2000))
        let viewport = UIView(frame: CGRect(x: 0, y: 0, width: 400, height: 600))
        let marker = UIView(frame: CGRect(x: 0, y: 0, width: 400, height: 2000))
        let adapter: ChatScrollGeometryAdapter
        var rows: [String: UIView] = [:]
        init(adapter: ChatScrollGeometryAdapter) {
            self.adapter = adapter
            window.addSubview(scroll); window.addSubview(viewport)
            scroll.contentInsetAdjustmentBehavior = .never
            scroll.contentSize = content.bounds.size
            scroll.addSubview(content); content.addSubview(marker)
            scroll.contentOffset.y = 600
            adapter.register(marker, as: .content)
            adapter.register(viewport, as: .viewport)
        }
        func addRow(_ id: String, y: CGFloat) {
            let row = UIView(frame: CGRect(x: 16, y: y, width: 368, height: 200))
            content.addSubview(row); rows[id] = row
            adapter.register(row, as: .row(id))
        }
        func removeRow(_ id: String) {
            guard let row = rows.removeValue(forKey: id) else { return }
            adapter.unregister(row, as: .row(id)); row.removeFromSuperview()
        }
    }

    @MainActor
    func testNativeHistoryRestoreKeepsHorizontalOffsetClampsAndRejectsForeignRows() throws {
        let adapter = ChatScrollGeometryAdapter()
        let surface = ScrollSurface(adapter: adapter)
        surface.addRow("A", y: 580)
        surface.scroll.contentOffset.x = -16
        adapter.activate()
        let snapshot = try XCTUnwrap(adapter.snapshot(for: "A"))
        XCTAssertTrue(adapter.restore(snapshot, id: "A", viewportY: -10000))
        XCTAssertEqual(surface.scroll.contentOffset.y, 1400)
        XCTAssertEqual(surface.scroll.contentOffset.x, -16)
        let other = UIScrollView(frame: surface.scroll.frame)
        let foreign = UIView(frame: CGRect(x: 0, y: 0, width: 100, height: 100))
        surface.window.addSubview(other); other.addSubview(foreign)
        adapter.register(foreign, as: .row("A"))
        XCTAssertNil(adapter.snapshot(for: "A"), "Same window does not authorize a different nested scroll")
        XCTAssertFalse(adapter.restore(snapshot, id: "A", viewportY: 0))
        XCTAssertEqual(surface.scroll.contentOffset.y, 1400)
        adapter.deactivate()
    }

    @MainActor
    func testNativeTopRespectsOriginalDecisionAndCannotReclaimNewLatest() throws {
        let coordinator = ChatScrollCoordinator()
        let surface = ScrollSurface(adapter: coordinator.physicalGeometry)
        surface.addRow("A", y: 580); surface.addRow("B", y: 1210)
        let original = RecordingScrollDelegate()
        surface.scroll.delegate = original
        coordinator.viewportChanged(surface.viewport.frame)
        coordinator.contentChanged(orderedMessageIDs: ["A", "B"])
        coordinator.geometryChanged(geometry(offset: 600))
        coordinator.attachMessageScroller { _, _ in }
        let proxy = try XCTUnwrap(surface.scroll.delegate as? ChatScrollDelegateObserver)
        original.allowTop = false
        XCTAssertFalse(proxy.scrollViewShouldScrollToTop(surface.scroll))
        XCTAssertFalse(coordinator.readingHistory)
        XCTAssertEqual(coordinator.policy.revision, 0)
        original.allowTop = true
        XCTAssertTrue(proxy.scrollViewShouldScrollToTop(surface.scroll))
        XCTAssertTrue(coordinator.readingHistory)
        XCTAssertTrue(coordinator.policy.pausesCorrection)
        let revision = coordinator.policy.revision
        coordinator.latest()
        proxy.scrollViewDidScrollToTop(surface.scroll)
        XCTAssertEqual(coordinator.policy.intent, .latest, "A late native completion cannot take ownership back")
        XCTAssertGreaterThan(coordinator.policy.revision, revision)
        XCTAssertFalse(coordinator.policy.pausesCorrection)
        let forwarding: any UIScrollViewDelegate = proxy
        forwarding.scrollViewDidScroll?(surface.scroll)
        XCTAssertTrue(original.receivedScroll, "Unimplemented optional methods must reach SwiftUI's delegate")
        coordinator.disappeared()
        XCTAssertTrue(surface.scroll.delegate === original)
    }

    @MainActor
    func testNativeTopNoopAndDelegateReplacementDoNotLeaveAnOwnedPause() throws {
        let coordinator = ChatScrollCoordinator()
        let surface = ScrollSurface(adapter: coordinator.physicalGeometry)
        let original = RecordingScrollDelegate()
        surface.scroll.delegate = original
        coordinator.attachMessageScroller { _, _ in }
        let old = try XCTUnwrap(surface.scroll.delegate as? ChatScrollDelegateObserver)
        surface.scroll.contentOffset.y = 0
        XCTAssertTrue(old.scrollViewShouldScrollToTop(surface.scroll))
        XCTAssertEqual(coordinator.policy.revision, 0, "Already-top must not require a didTop callback")
        XCTAssertFalse(coordinator.policy.pausesCorrection)
        surface.scroll.contentOffset.y = 600
        XCTAssertTrue(old.scrollViewShouldScrollToTop(surface.scroll))
        XCTAssertTrue(coordinator.policy.pausesCorrection)
        let replacement = RecordingScrollDelegate()
        surface.scroll.delegate = replacement
        coordinator.physicalGeometry.markersChanged()
        let current = try XCTUnwrap(surface.scroll.delegate as? ChatScrollDelegateObserver)
        XCTAssertTrue(current.original === replacement)
        XCTAssertFalse(coordinator.policy.pausesCorrection, "Replacing a native binding cancels its old pending top")
        coordinator.latest()
        old.scrollViewDidScrollToTop(surface.scroll)
        XCTAssertFalse(coordinator.readingHistory)
        coordinator.disappeared()
        XCTAssertTrue(surface.scroll.delegate === replacement, "Detach restores only the delegate we actually wrapped")
    }

    @MainActor
    private final class RecordingScrollDelegate: NSObject, UIScrollViewDelegate {
        var allowTop = true
        var receivedScroll = false
        func scrollViewShouldScrollToTop(_ scrollView: UIScrollView) -> Bool { allowTop }
        func scrollViewDidScroll(_ scrollView: UIScrollView) { receivedScroll = true }
    }

    private func geometry(offset: CGFloat) -> ScrollGeometry {
        ScrollGeometry(contentOffset: CGPoint(x: 0, y: offset), contentSize: CGSize(width: 400, height: 2000),
                       contentInsets: EdgeInsets(), containerSize: CGSize(width: 400, height: 600))
    }

    @MainActor
    private func eventually(_ condition: @MainActor () -> Bool, file: StaticString = #filePath, line: UInt = #line) async {
        let deadline = Date().addingTimeInterval(1)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
        XCTAssertTrue(condition(), file: file, line: line)
    }

    func testHistoryAnchorOnlyChangesWhileIdleReading() {
        var policy = ChatScrollPolicy()
        policy.remember(.init(id: "wrong", viewportY: 0))
        XCTAssertNil(policy.anchor)
        policy.changePhase(.tracking, offset: 100, atBottom: false)
        policy.changePhase(.interacting, offset: 100, atBottom: false)
        XCTAssertTrue(policy.moved(to: 50))
        policy.remember(.init(id: "moving", viewportY: 2))
        XCTAssertNil(policy.anchor)
        policy.changePhase(.idle, offset: 50, atBottom: false)
        let anchor = ChatScrollPolicy.Anchor(id: "stable", viewportY: -15)
        policy.remember(anchor)
        XCTAssertEqual(policy.anchor, anchor)
    }
}
