import os

/// Native performance measurement only; the scroll coordinator owns completion semantics.
@MainActor
final class ChatScrollTiming {
    private let signposter = OSSignposter(subsystem: "com.nano.im.chat", category: "Scroll")
    private var latest: OSSignpostIntervalState?

    func beganLatest() {
        cancel()
        latest = signposter.beginInterval("LatestToTail")
    }

    func reachedTail() {
        guard let latest else { return }
        signposter.endInterval("LatestToTail", latest)
        self.latest = nil
    }

    func cancel() {
        guard let latest else { return }
        // Keep interrupted samples distinguishable in traces; they are not successful jumps.
        signposter.emitEvent("LatestInterrupted")
        signposter.endInterval("LatestToTail", latest, "interrupted")
        self.latest = nil
    }
}
