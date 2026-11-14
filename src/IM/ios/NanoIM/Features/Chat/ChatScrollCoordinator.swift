import SwiftUI
import os

/// The only scroll-request owner. Per-pixel geometry stays outside Observation so moving the
/// viewport does not reparse the entire timeline or rebuild every message's Markdown body.
@MainActor @Observable
final class ChatScrollCoordinator {
    @ObservationIgnored let physicalGeometry = ChatScrollGeometryAdapter()
    private(set) var showLatest = false
    private(set) var viewport = CGRect.zero
    @ObservationIgnored private(set) var policy = ChatScrollPolicy()
    @ObservationIgnored var invalidateRestoration: (() -> Void)?
    @ObservationIgnored var readingAnchorChanged: ((String?) -> Void)?
    @ObservationIgnored private var geometry: ScrollGeometry?
    @ObservationIgnored private var containerFrame = CGRect.zero
    @ObservationIgnored private var rows: [String: CGRect] = [:]
    @ObservationIgnored private var validIDs = Set<String>()
    @ObservationIgnored private var latestID: String?
    private var tail: CGRect { latestID.flatMap { rows[$0] } ?? .zero }
    @ObservationIgnored private var correction: Task<Void, Never>?
    @ObservationIgnored private var lastCorrection: CorrectionKey?
    @ObservationIgnored private var active = true
    @ObservationIgnored private var hasAppeared = false
    @ObservationIgnored private let timing = ChatScrollTiming()
    @ObservationIgnored private var messageScroller: MessageScroller?
    @ObservationIgnored private var pendingMessageGeometry: PendingMessageGeometry?
    @ObservationIgnored private var nativeTopRevision: Int?

    init() {
        physicalGeometry.invalidated = { [weak self] in self?.scheduleCorrection() }
        physicalGeometry.topRequested = { [weak self] in self?.nativeTopRequested() }
        physicalGeometry.topCompleted = { [weak self] in self?.nativeTopCompleted() }
        physicalGeometry.topCancelled = { [weak self] in self?.nativeTopCancelled() }
    }

    private struct MessageScroller {
        let generation: UUID
        let scroll: (String, UnitPoint) -> Void
    }

    private struct PendingMessageGeometry {
        let id: String
        let revision: Int
        let generation: UUID
        let snapshot: ChatScrollGeometryAdapter.Snapshot?
    }

    @discardableResult
    func attachMessageScroller(_ scroll: @escaping (String, UnitPoint) -> Void) -> UUID {
        correction?.cancel(); correction = nil
        lastCorrection = nil
        pendingMessageGeometry = nil
        let generation = UUID()
        messageScroller = MessageScroller(generation: generation, scroll: scroll)
        appeared()
        return generation
    }

    func detachMessageScroller(_ generation: UUID) {
        guard messageScroller?.generation == generation else { return }
        disappeared()
    }

    private func requestMessage(_ id: String, anchor: UnitPoint) -> Bool {
        guard active, let messageScroller else { return false }
        // Only a coherent post-jump tuple may refine this identity request. There is no
        // retained ScrollPosition point/ID that can outlive a gesture or fight the Reader.
        pendingMessageGeometry = PendingMessageGeometry(
            id: id, revision: policy.revision, generation: messageScroller.generation,
            snapshot: physicalGeometry.snapshot(for: id))
        trace("request-message-" + id, extra: [
            "adapterGeneration": messageScroller.generation.uuidString,
            "nativeBeforeOffset": pendingMessageGeometry?.snapshot.map { $0.offset.y as Any } ?? NSNull(),
            "nativeBeforeRowTop": pendingMessageGeometry?.snapshot.map { $0.row.minY as Any } ?? NSNull()
        ])
        messageScroller.scroll(id, anchor)
        return true
    }

    // Temporary local diagnosis; remove before the delivery tree is frozen.
    private func trace(_ event: String, extra: [String: Any] = [:]) {
        #if DEBUG
        guard ProcessInfo.processInfo.environment["NANO_CHAT_SCROLL_TRACE"] == "1" else { return }
        var values: [String: Any] = [
            "event": event, "uptime": ProcessInfo.processInfo.systemUptime,
            "phase": String(describing: policy.phase), "intent": String(describing: policy.intent),
            "revision": policy.revision, "nativeTop": policy.nativeTop, "nativeGeometryBound": physicalGeometry.isBound,
            "offset": geometry?.contentOffset.y ?? 0, "height": geometry?.contentSize.height ?? 0,
            "offsetX": geometry?.contentOffset.x ?? 0, "contentWidth": geometry?.contentSize.width ?? 0,
            "containerHeight": geometry?.containerSize.height ?? 0,
            "containerWidth": geometry?.containerSize.width ?? 0,
            "insetTop": geometry?.contentInsets.top ?? 0, "insetBottom": geometry?.contentInsets.bottom ?? 0,
            "insetLeading": geometry?.contentInsets.leading ?? 0, "insetTrailing": geometry?.contentInsets.trailing ?? 0,
            "viewportLeft": viewport.minX, "viewportRight": viewport.maxX,
            "viewportTop": viewport.minY, "viewportBottom": viewport.maxY,
            "tailLeft": tail.minX, "tailRight": tail.maxX,
            "tailTop": tail.minY, "tailBottom": tail.maxY, "rows": rows.count, "latestID": latestID ?? "",
            "rowFrames": rows.mapValues { ["x": $0.minX, "y": $0.minY, "width": $0.width, "height": $0.height, "maxY": $0.maxY] },
            "atBottom": atBottom, "active": active
        ]
        values.merge(extra) { _, new in new }
        if let data = try? JSONSerialization.data(withJSONObject: values, options: [.sortedKeys]),
           let text = String(data: data, encoding: .utf8) {
            Logger(subsystem: "com.nano.im.chat", category: "ScrollTrace").notice("763_SCROLL \(text, privacy: .public)")
        }
        #endif
    }

    private struct CorrectionKey: Equatable {
        let revision: Int
        let offset: CGFloat
        let height: CGFloat
        let viewport: CGRect
        let latestID: String?
        let tail: CGRect
        let anchorGeometry: ChatScrollGeometryAdapter.Snapshot?
    }

    var readingHistory: Bool { policy.intent == .history }
    private var atBottom: Bool {
        // Use the same actual final message for positioning and completion. Lazy extent
        // and a separate transparent sentinel can disagree with its rendered bottom edge.
        if physicalGeometry.isBound {
            guard let latestID, let live = physicalGeometry.snapshot(for: latestID) else { return false }
            return live.row.maxY <= live.viewport.maxY + 2 && live.row.maxY >= live.viewport.minY - 2
        }
        return !tail.isEmpty && !viewport.isEmpty && tail.maxY <= viewport.maxY + 2 && tail.maxY >= viewport.minY - 2
    }

    func appeared() {
        active = true
        physicalGeometry.activate()
        if !hasAppeared {
            hasAppeared = true
            invalidateRestoration?()
            readingAnchorChanged?(nil)
        }
        scheduleCorrection()
    }
    func disappeared() {
        active = false
        physicalGeometry.deactivate()
        nativeTopRevision = nil
        policy.endScrollSurface()
        correction?.cancel(); correction = nil
        messageScroller = nil
        pendingMessageGeometry = nil
        lastCorrection = nil
    }

    func latest() {
        trace("latest-handler")
        correction?.cancel(); correction = nil
        policy.latest()
        nativeTopRevision = nil
        pendingMessageGeometry = nil
        timing.beganLatest()
        lastCorrection = nil
        invalidateRestoration?()
        readingAnchorChanged?(nil)
        // Immediate ownership and first jump do not wait for layout or network.
        if let latestID { _ = requestMessage(latestID, anchor: .bottom) }
        scheduleCorrection()
    }

    private func nativeTopRequested() {
        guard active else { return }
        correction?.cancel(); correction = nil
        policy.beginNativeTop()
        nativeTopRevision = policy.revision
        pendingMessageGeometry = nil
        lastCorrection = nil
        timing.cancel()
        invalidateRestoration?()
        readingAnchorChanged?(nil)
        trace("native-top-began")
    }

    private func nativeTopCompleted() {
        guard active, nativeTopRevision == policy.revision else { return }
        nativeTopRevision = nil
        policy.endNativeTop(atBottom: atBottom)
        captureAnchor()
        trace("native-top-completed")
        updateButton()
        scheduleCorrection()
    }

    private func nativeTopCancelled() {
        guard nativeTopRevision != nil else { return }
        nativeTopRevision = nil
        policy.cancelNativeTop()
        lastCorrection = nil
        trace("native-top-cancelled")
        scheduleCorrection()
    }

    func viewportChanged(_ frame: CGRect) {
        guard containerFrame != frame else { return }
        containerFrame = frame
        updateViewport()
        scheduleCorrection()
    }

    private func updateViewport() {
        // This frame is measured after safe-area navigation, composer and keyboard layout.
        // ScrollGeometry.contentInsets already describe that layout; applying them again
        // shrinks the visible region twice (to zero with the software keyboard).
        if viewport != containerFrame { viewport = containerFrame }
    }

    func geometryChanged(_ value: ScrollGeometry) {
        geometry = value
        updateViewport()
        recognizeMovement(offset: value.contentOffset.y)
        updateButton()
        trace("geometry")
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
        trace("phase-before-\(phase)")
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
        if id == latestID { updateButton() }
        trace("row-" + id)
        scheduleCorrection()
    }

    func rowDisappeared(_ id: String) {
        rows[id] = nil
        if id == latestID { updateButton() }
        scheduleCorrection()
    }

    func contentChanged(orderedMessageIDs: [String]) {
        let validIDs = Set(orderedMessageIDs)
        self.validIDs = validIDs
        physicalGeometry.prune(validIDs: validIDs)
        latestID = orderedMessageIDs.last
        rows = rows.filter { validIDs.contains($0.key) }
        // Cleanup can briefly empty the projection while authoritative pages are bridged.
        // Keep only the target offset, never old message content, through that empty phase.
        if !validIDs.isEmpty, let anchor = policy.anchor, !validIDs.contains(anchor.id) { captureAnchor() }
        updateButton()
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
        pendingMessageGeometry = nil
        // Already-realized rows need only one coherent native Y correction. Reader/top may
        // legally be a no-op, so waiting for a changed post-ID tuple would deadlock restoration.
        if physicalGeometry.snapshot(for: id) == nil { _ = requestMessage(id, anchor: .top) }
        scheduleCorrection()
    }

    private func recognizeMovement(offset: CGFloat) {
        guard policy.moved(to: offset) else { return }
        pendingMessageGeometry = nil
        correction?.cancel(); correction = nil
        invalidateRestoration?()
        timing.cancel()
        lastCorrection = nil
    }

    private func updateButton() {
        if atBottom { timing.reachedTail() }
        let visible = latestID != nil && !atBottom
        if showLatest != visible { showLatest = visible }
    }

    private func captureAnchor() {
        guard policy.intent == .history, !policy.pausesCorrection, !viewport.isEmpty else { return }
        if physicalGeometry.isBound {
            // didScrollToTop can precede SwiftUI's final geometry notifications. An installed
            // native binding must never capture the previous animation frame as the new intent.
            let top = physicalGeometry.rowSnapshots().filter {
                validIDs.contains($0.key) && $0.value.row.maxY > $0.value.viewport.minY
                    && $0.value.row.minY < $0.value.viewport.maxY
            }.min { $0.value.row.minY < $1.value.row.minY }
            policy.remember(top.map { .init(id: $0.key, viewportY: $0.value.row.minY - $0.value.viewport.minY) })
            readingAnchorChanged?(top?.key)
        } else {
            let top = rows.filter { $0.value.maxY > viewport.minY && $0.value.minY < viewport.maxY }
                .min { $0.value.minY < $1.value.minY }
            policy.remember(top.map { .init(id: $0.key, viewportY: $0.value.minY - viewport.minY) })
            readingAnchorChanged?(top?.key)
        }
    }

    private func scheduleCorrection() {
        guard active, correction == nil, !policy.pausesCorrection else { return }
        let revision = policy.revision
        let generation = messageScroller?.generation
        correction = Task { [weak self] in
            // Coalesce the current layout pass; there is no fixed rendering-completion delay.
            await Task.yield()
            // A cancelled older task must not clear a newer task's coalescing handle.
            guard let self, !Task.isCancelled else { return }
            self.correction = nil
            guard self.active, self.policy.revision == revision,
                  self.messageScroller?.generation == generation,
                  !self.policy.pausesCorrection else { return }
            self.correctLayout()
        }
    }

    private func correctLayout() {
        guard messageScroller != nil, let geometry, !viewport.isEmpty else { return }
        updateButton()
        let anchorGeometry = policy.anchor.flatMap { physicalGeometry.snapshot(for: $0.id) }
        let key = CorrectionKey(revision: policy.revision, offset: geometry.contentOffset.y,
                                height: geometry.contentSize.height, viewport: viewport, latestID: latestID, tail: tail,
                                anchorGeometry: anchorGeometry)
        guard key != lastCorrection else { return }
        if policy.intent == .latest {
            guard let latestID, !atBottom else { return }
            trace("correct-final-message")
            if requestMessage(latestID, anchor: .bottom) { lastCorrection = key }
        } else if let anchor = policy.anchor {
            if let snapshot = anchorGeometry {
                guard abs(snapshot.delta(to: anchor.viewportY)) > 1 else { pendingMessageGeometry = nil; return }
                if let pending = pendingMessageGeometry,
                   pending.id == anchor.id, pending.revision == policy.revision,
                   pending.generation == messageScroller?.generation {
                    // The whole live tuple must advance, not one independent cached callback.
                    guard pending.snapshot != snapshot else { return }
                }
                pendingMessageGeometry = nil
                trace("correct-history-y", extra: ["anchorID": anchor.id,
                    "nativeOffsetY": snapshot.offset.y, "nativeOffsetX": snapshot.offset.x,
                    "nativeRowTop": snapshot.row.minY, "nativeViewportTop": snapshot.viewport.minY,
                    "savedViewportY": anchor.viewportY, "nativeDelta": snapshot.delta(to: anchor.viewportY)])
                if physicalGeometry.restore(snapshot, id: anchor.id, viewportY: anchor.viewportY) {
                    lastCorrection = key
                    if let after = physicalGeometry.snapshot(for: anchor.id) {
                        trace("history-y-applied", extra: ["anchorID": anchor.id,
                            "nativeOffsetY": after.offset.y, "nativeOffsetX": after.offset.x,
                            "nativeRowTop": after.row.minY, "nativeViewportTop": after.viewport.minY])
                    }
                }
            } else if validIDs.contains(anchor.id) {
                // A large prepend/height change can unrealize a still-authoritative row.
                // Realize that same identity first; its next frame restores the saved offset.
                if requestMessage(anchor.id, anchor: .top) { lastCorrection = key }
            }
        } else {
            captureAnchor()
        }
    }
}
