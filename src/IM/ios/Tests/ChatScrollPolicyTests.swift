import XCTest
import SwiftUI
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
        coordinator.contentChanged(validIDs: ["A", "B"])
        coordinator.viewportChanged(CGRect(x: 0, y: 0, width: 400, height: 600))
        coordinator.geometryChanged(geometry(offset: 600))
        coordinator.rowChanged("A", frame: CGRect(x: 0, y: -20, width: 400, height: 200))
        coordinator.rowChanged("B", frame: CGRect(x: 0, y: 210, width: 400, height: 200))
        coordinator.phaseChanged(.tracking, geometry: geometry(offset: 600))
        coordinator.phaseChanged(.interacting, geometry: geometry(offset: 600))
        coordinator.geometryChanged(geometry(offset: 580))
        coordinator.phaseChanged(.idle, geometry: geometry(offset: 580))
        XCTAssertEqual(coordinator.policy.anchor?.id, "A")
        coordinator.rowDisappeared("A")
        coordinator.rowChanged("B", frame: CGRect(x: 0, y: 0, width: 400, height: 200))
        await eventually { coordinator.position.viewID(type: String.self) == "A" }
        XCTAssertEqual(coordinator.policy.anchor?.id, "A", "Lazy recycling is not authoritative deletion")
        coordinator.rowChanged("A", frame: CGRect(x: 0, y: 0, width: 400, height: 200))
        await eventually { coordinator.position.y == 600 }
        XCTAssertEqual(coordinator.policy.anchor?.viewportY, -20)
        // These assertions observe adapter requests only; real tail/anchor frames are tested natively.
        coordinator.disappeared()
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
