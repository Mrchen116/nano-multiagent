import Foundation

/// Position ownership is independent of layout: a taller row is never a reading gesture.
struct ChatScrollPolicy {
    enum Intent: Equatable { case latest, history }
    enum Phase { case idle, tracking, interacting, decelerating, animating }
    struct Anchor: Equatable {
        let id: String
        let viewportY: CGFloat
    }
    private(set) var intent: Intent = .latest
    private(set) var revision = 0
    private(set) var phase: Phase = .idle
    private(set) var anchor: Anchor?
    private var gestureOrigin: CGFloat?
    private var gestureMoved = false
    var pausesCorrection: Bool { phase != .idle }

    mutating func latest() {
        revision += 1
        intent = .latest
        anchor = nil
        gestureOrigin = nil
        gestureMoved = false
    }

    @discardableResult
    mutating func changePhase(_ phase: Phase, offset: CGFloat, atBottom: Bool) -> Bool {
        let userMovementEnded = phase == .idle && gestureMoved
        self.phase = phase
        if phase == .tracking {
            gestureOrigin = offset
            gestureMoved = false
        } else if phase == .interacting, gestureOrigin == nil {
            // Accessibility/indirect input can start interaction without a touch-tracking phase.
            gestureOrigin = offset
            gestureMoved = false
        } else if phase == .idle {
            if gestureMoved { intent = atBottom ? .latest : .history }
            gestureOrigin = nil
            gestureMoved = false
            if intent == .latest { anchor = nil }
        }
        return userMovementEnded
    }

    /// Returns true only once per actual user gesture, so stale async restores lose ownership.
    mutating func moved(to offset: CGFloat) -> Bool {
        guard phase == .interacting || phase == .decelerating,
              !gestureMoved, let origin = gestureOrigin, abs(offset - origin) > 1 else { return false }
        gestureMoved = true
        revision += 1
        intent = .history
        anchor = nil
        return true
    }

    mutating func remember(_ anchor: Anchor?) {
        guard intent == .history, phase == .idle else { return }
        self.anchor = anchor
    }

    func admitsRestore(revision: Int) -> Bool {
        self.revision == revision && intent == .history && !pausesCorrection
    }
}
