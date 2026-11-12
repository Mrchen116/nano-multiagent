import SwiftUI

/// The only ScrollPosition writer. Per-pixel geometry stays outside Observation so moving the
/// viewport does not reparse the entire timeline or rebuild every message's Markdown body.
@MainActor @Observable
final class ChatScrollCoordinator {
    var position = ScrollPosition(idType: String.self, edge: .bottom)
    private(set) var showLatest = false
    private(set) var viewport = CGRect.zero
    @ObservationIgnored private(set) var policy = ChatScrollPolicy()
    @ObservationIgnored var invalidateRestoration: (() -> Void)?
    @ObservationIgnored var readingAnchorChanged: ((String?) -> Void)?
    @ObservationIgnored private var geometry: ScrollGeometry?
    @ObservationIgnored private var containerFrame = CGRect.zero
    @ObservationIgnored private var rows: [String: CGRect] = [:]
    @ObservationIgnored private var validIDs = Set<String>()
    @ObservationIgnored private var tail = CGRect.zero
    @ObservationIgnored private var correction: Task<Void, Never>?
    @ObservationIgnored private var lastCorrection: CorrectionKey?
    @ObservationIgnored private var active = true
    @ObservationIgnored private var hasAppeared = false
    @ObservationIgnored private let timing = ChatScrollTiming()

    private struct CorrectionKey: Equatable {
        let revision: Int
        let offset: CGFloat
        let height: CGFloat
        let viewport: CGRect
        let tail: CGRect
        let anchorY: CGFloat?
    }

    var readingHistory: Bool { policy.intent == .history }
    private var atBottom: Bool {
        guard let geometry else { return false }
        // Check both the estimated extent and actual final row; neither a scroll command nor
        // an estimated lazy content height proves that the real last content is in the viewport.
        let extentVisible = geometry.contentOffset.y + geometry.containerSize.height - geometry.contentInsets.bottom >= geometry.contentSize.height - 2
        return extentVisible && !tail.isEmpty && tail.maxY <= viewport.maxY + 2 && tail.minY >= viewport.minY - 2
    }

    func appeared() {
        active = true
        if !hasAppeared {
            hasAppeared = true
            invalidateRestoration?()
            readingAnchorChanged?(nil)
        }
        scheduleCorrection()
    }
    func disappeared() { active = false; correction?.cancel(); correction = nil }

    func latest() {
        correction?.cancel(); correction = nil
        policy.latest()
        timing.beganLatest()
        lastCorrection = nil
        invalidateRestoration?()
        readingAnchorChanged?(nil)
        // Immediate ownership and first jump do not wait for layout or network.
        position.scrollTo(edge: .bottom)
        scheduleCorrection()
    }

    func viewportChanged(_ frame: CGRect) {
        guard containerFrame != frame else { return }
        containerFrame = frame
        updateViewport()
        scheduleCorrection()
    }

    private func updateViewport() {
        let top = geometry?.contentInsets.top ?? 0
        let bottom = geometry?.contentInsets.bottom ?? 0
        let effective = CGRect(x: containerFrame.minX, y: containerFrame.minY + top,
                               width: containerFrame.width, height: max(0, containerFrame.height - top - bottom))
        if viewport != effective { viewport = effective }
    }

    func geometryChanged(_ value: ScrollGeometry) {
        geometry = value
        updateViewport()
        recognizeMovement(offset: value.contentOffset.y)
        updateButton()
        scheduleCorrection()
    }

    func phaseChanged(_ phase: ScrollPhase, geometry: ScrollGeometry) {
        let mapped: ChatScrollPolicy.Phase
        switch phase {
        case .idle: mapped = .idle
        case .tracking: mapped = .tracking
        case .interacting: mapped = .interacting
        case .decelerating: mapped = .decelerating
        case .animating: mapped = .animating
        }
        self.geometry = geometry
        updateViewport()
        // SwiftUI need not deliver phase and geometry notifications in a particular order.
        // Check the last movement both before leaving a gesture and after entering one.
        recognizeMovement(offset: geometry.contentOffset.y)
        let userMovementEnded = policy.changePhase(mapped, offset: geometry.contentOffset.y, atBottom: atBottom)
        recognizeMovement(offset: geometry.contentOffset.y)
        if phase == .idle {
            if policy.intent == .latest { readingAnchorChanged?(nil) }
            else if userMovementEnded || policy.anchor == nil { captureAnchor() }
            scheduleCorrection()
        } else {
            correction?.cancel(); correction = nil
        }
        updateButton()
    }

    func rowChanged(_ id: String, frame: CGRect) {
        rows[id] = frame
        scheduleCorrection()
    }

    func rowDisappeared(_ id: String) { rows[id] = nil }

    func tailChanged(_ frame: CGRect) {
        tail = frame
        updateButton()
        scheduleCorrection()
    }

    func tailDisappeared() {
        tail = .zero
        updateButton()
        scheduleCorrection()
    }

    func contentChanged(validIDs: Set<String>) {
        self.validIDs = validIDs
        rows = rows.filter { validIDs.contains($0.key) }
        // Cleanup can briefly empty the projection while authoritative pages are bridged.
        // Keep only the target offset, never old message content, through that empty phase.
        if !validIDs.isEmpty, let anchor = policy.anchor, !validIDs.contains(anchor.id) { captureAnchor() }
        scheduleCorrection()
    }

    func paginationStarted() -> Int {
        captureAnchor()
        return policy.revision
    }

    func paginationFinished(revision: Int) {
        guard policy.admitsRestore(revision: revision) else { return }
        scheduleCorrection()
    }

    func restore(_ id: String) {
        guard policy.intent == .history, !policy.pausesCorrection else { return }
        let targetY = policy.anchor?.viewportY ?? 0
        policy.remember(.init(id: id, viewportY: targetY))
        lastCorrection = nil
        position.scrollTo(id: id, anchor: .top)
        scheduleCorrection()
    }

    private func recognizeMovement(offset: CGFloat) {
        guard policy.moved(to: offset) else { return }
        correction?.cancel(); correction = nil
        invalidateRestoration?()
        timing.cancel()
        lastCorrection = nil
    }

    private func updateButton() {
        if atBottom { timing.reachedTail() }
        let visible = !atBottom
        if showLatest != visible { showLatest = visible }
    }

    private func captureAnchor() {
        guard policy.intent == .history, !policy.pausesCorrection, !viewport.isEmpty else { return }
        let top = rows.filter { $0.value.maxY > viewport.minY && $0.value.minY < viewport.maxY }
            .min { $0.value.minY < $1.value.minY }
        policy.remember(top.map { .init(id: $0.key, viewportY: $0.value.minY - viewport.minY) })
        readingAnchorChanged?(top?.key)
    }

    private func scheduleCorrection() {
        guard active, correction == nil, !policy.pausesCorrection else { return }
        let revision = policy.revision
        correction = Task { [weak self] in
            // Coalesce the current layout pass; there is no fixed rendering-completion delay.
            await Task.yield()
            // A cancelled older task must not clear a newer task's coalescing handle.
            guard let self, !Task.isCancelled else { return }
            self.correction = nil
            guard self.active, self.policy.revision == revision,
                  !self.policy.pausesCorrection else { return }
            self.correctLayout()
        }
    }

    private func correctLayout() {
        guard let geometry, !viewport.isEmpty else { return }
        let key = CorrectionKey(revision: policy.revision, offset: geometry.contentOffset.y,
                                height: geometry.contentSize.height, viewport: viewport, tail: tail,
                                anchorY: policy.anchor.flatMap { rows[$0.id]?.minY })
        guard key != lastCorrection else { return }
        if policy.intent == .latest {
            guard !atBottom else { return }
            lastCorrection = key
            position.scrollTo(edge: .bottom)
        } else if let anchor = policy.anchor {
            if let frame = rows[anchor.id] {
                let delta = frame.minY - viewport.minY - anchor.viewportY
                guard abs(delta) > 1 else { return }
                lastCorrection = key
                position.scrollTo(y: geometry.contentOffset.y + delta)
            } else if validIDs.contains(anchor.id) {
                // A large prepend/height change can unrealize a still-authoritative row.
                // Realize that same identity first; its next frame restores the saved offset.
                lastCorrection = key
                position.scrollTo(id: anchor.id, anchor: .top)
            }
        } else {
            captureAnchor()
        }
    }
}
