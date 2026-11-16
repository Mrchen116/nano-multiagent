import SwiftUI
import UIKit

/// A fixed physical endpoint avoids asking the lazy layout to solve a complex final row.
/// Completion still belongs to the coordinator's actual final-message geometry.
enum ChatScrollEndpoint: Hashable { case latest }

/// Reads one live UIKit coordinate tree rather than combining independently delivered frames.
/// The persistent content marker identifies only this timeline's nearest scroll ancestor.
@MainActor
final class ChatScrollGeometryAdapter {
    enum Role: Hashable { case content, viewport, row(String) }
    struct Snapshot: Equatable {
        let scrollID: ObjectIdentifier
        let row: CGRect
        let viewport: CGRect
        let offset: CGPoint
        let contentSize: CGSize
        let bounds: CGRect
        let insets: UIEdgeInsets

        var topLimit: CGFloat { -insets.top }
        var bottomLimit: CGFloat { max(topLimit, contentSize.height - bounds.height + insets.bottom) }
        func delta(to viewportY: CGFloat) -> CGFloat { row.minY - viewport.minY - viewportY }
    }
    private final class WeakView {
        weak var view: UIView?
        init(_ view: UIView) { self.view = view }
    }
    private struct Binding {
        weak var scroll: UIScrollView?
        let generation: UUID
        let observer: ChatScrollDelegateObserver
    }
    private var markers: [Role: WeakView] = [:]
    private var binding: Binding?
    private var active = false
    var invalidated: (() -> Void)?
    var topRequested: (() -> Void)?
    var topCompleted: (() -> Void)?
    var topCancelled: (() -> Void)?
    var isBound: Bool {
        guard let binding, let scroll = binding.scroll else { return false }
        return scroll.delegate === binding.observer
    }

    func activate() { active = true; markersChanged() }
    func deactivate() { active = false; unbind() }

    func register(_ view: UIView, as role: Role) {
        guard markers[role]?.view !== view else { return }
        markers[role] = WeakView(view)
        markersChanged()
    }
    func unregister(_ view: UIView, as role: Role) {
        guard markers[role]?.view === view else { return }
        markers[role] = nil
        markersChanged()
    }
    func prune(validIDs: Set<String>) {
        markers = markers.filter { role, view in
            guard view.view != nil else { return false }
            if case .row(let id) = role { return validIDs.contains(id) }
            return true
        }
    }
    func markersChanged() {
        updateBinding()
        invalidated?()
    }

    func snapshot(for id: String) -> Snapshot? {
        guard active, let row = markers[.row(id)]?.view,
              let viewport = markers[.viewport]?.view,
              let window = viewport.window, row.window === window,
              let scroll = resolvedScroll(),
              nearestScroll(to: row) === scroll else { return nil }
        let rowFrame = row.convert(row.bounds, to: window)
        let viewportFrame = viewport.convert(viewport.bounds, to: window)
        guard usable(rowFrame), usable(viewportFrame), scroll.contentOffset.y.isFinite,
              scroll.contentSize.height.isFinite else { return nil }
        return Snapshot(scrollID: ObjectIdentifier(scroll), row: rowFrame, viewport: viewportFrame,
                        offset: scroll.contentOffset, contentSize: scroll.contentSize,
                        bounds: scroll.bounds, insets: scroll.adjustedContentInset)
    }

    /// Read all available rows in this MainActor turn, without independently cached frames.
    func rowSnapshots() -> [String: Snapshot] {
        var result: [String: Snapshot] = [:]
        for role in markers.keys {
            if case .row(let id) = role, let snapshot = snapshot(for: id) { result[id] = snapshot }
        }
        return result
    }

    /// The caller reads and applies synchronously on MainActor. Revalidate before writing so a
    /// stale or foreign marker can never move a different scroll view; horizontal offset is kept.
    @discardableResult
    func restore(_ snapshot: Snapshot, id: String, viewportY: CGFloat) -> Bool {
        guard self.snapshot(for: id) == snapshot, let scroll = resolvedScroll(),
              !scroll.isTracking, !scroll.isDragging, !scroll.isDecelerating else { return false }
        let y = min(snapshot.bottomLimit, max(snapshot.topLimit,
                    snapshot.offset.y + snapshot.delta(to: viewportY)))
        guard y.isFinite else { return false }
        if abs(y - snapshot.offset.y) > 1 {
            scroll.setContentOffset(CGPoint(x: snapshot.offset.x, y: y), animated: false)
        }
        return true
    }

    private func usable(_ frame: CGRect) -> Bool {
        !frame.isEmpty && !frame.isInfinite && !frame.isNull
        && frame.minX.isFinite && frame.minY.isFinite && frame.width.isFinite && frame.height.isFinite
    }
    private func nearestScroll(to view: UIView) -> UIScrollView? {
        var ancestor = view.superview
        while let current = ancestor {
            if let scroll = current as? UIScrollView { return scroll }
            ancestor = current.superview
        }
        return nil
    }
    private func resolvedScroll() -> UIScrollView? {
        guard let content = markers[.content]?.view, let viewport = markers[.viewport]?.view,
              let window = content.window, viewport.window === window,
              let scroll = nearestScroll(to: content), scroll.window === window else { return nil }
        let viewportFrame = viewport.convert(viewport.bounds, to: window)
        let scrollFrame = scroll.convert(scroll.bounds, to: window)
        guard usable(viewportFrame), usable(scrollFrame),
              scrollFrame.insetBy(dx: -1, dy: -1).contains(viewportFrame) else { return nil }
        return scroll
    }
    private func updateBinding() {
        guard active, let scroll = resolvedScroll() else { unbind(); return }
        if let binding, binding.scroll === scroll, scroll.delegate === binding.observer { return }
        unbind()
        // Another timeline's observer is never adopted as our forward target.
        guard !(scroll.delegate is ChatScrollDelegateObserver) else { return }
        let generation = UUID()
        let observer = ChatScrollDelegateObserver(original: scroll.delegate)
        observer.topRequested = { [weak self, weak scroll] in
            guard let self, let scroll, self.owns(scroll, generation: generation) else { return }
            self.topRequested?()
        }
        observer.topCompleted = { [weak self, weak scroll] in
            guard let self, let scroll, self.owns(scroll, generation: generation) else { return }
            self.topCompleted?()
        }
        observer.dragBegan = { [weak self, weak scroll] in
            guard let self, let scroll, self.owns(scroll, generation: generation) else { return }
            self.topCancelled?()
        }
        binding = Binding(scroll: scroll, generation: generation, observer: observer)
        scroll.delegate = observer
    }
    private func owns(_ scroll: UIScrollView, generation: UUID) -> Bool {
        active && binding?.generation == generation && binding?.scroll === scroll
        && scroll.delegate === binding?.observer
    }
    private func unbind() {
        guard let old = binding else { return }
        binding = nil
        if let scroll = old.scroll, scroll.delegate === old.observer {
            scroll.delegate = old.observer.original
        }
        topCancelled?()
    }
}

/// Observe only the public native top request; never infer user intent from animation flags.
/// Optional delegate methods we do not implement are forwarded to the original SwiftUI owner.
@MainActor
final class ChatScrollDelegateObserver: NSObject, UIScrollViewDelegate {
    weak var original: (any UIScrollViewDelegate)?
    var topRequested: (() -> Void)?
    var topCompleted: (() -> Void)?
    var dragBegan: (() -> Void)?

    init(original: (any UIScrollViewDelegate)?) { self.original = original }
    override func responds(to selector: Selector!) -> Bool {
        super.responds(to: selector) || original?.responds(to: selector) == true
    }
    override func forwardingTarget(for selector: Selector!) -> Any? {
        if let original, original.responds(to: selector) { return original }
        return super.forwardingTarget(for: selector)
    }
    func scrollViewShouldScrollToTop(_ scrollView: UIScrollView) -> Bool {
        let allowed = original?.scrollViewShouldScrollToTop?(scrollView) ?? true
        let top = -scrollView.adjustedContentInset.top
        let bottom = max(top, scrollView.contentSize.height - scrollView.bounds.height + scrollView.adjustedContentInset.bottom)
        // UIKit need not send a completion for an already-top or non-scrollable no-op.
        if allowed, scrollView.contentOffset.y > top + 1, bottom - top > 1 { topRequested?() }
        return allowed
    }
    func scrollViewDidScrollToTop(_ scrollView: UIScrollView) {
        original?.scrollViewDidScrollToTop?(scrollView)
        topCompleted?()
    }
    func scrollViewWillBeginDragging(_ scrollView: UIScrollView) {
        original?.scrollViewWillBeginDragging?(scrollView)
        dragBegan?()
    }
}

/// Background markers do not participate in sizing, accessibility or event handling.
struct ChatScrollGeometryMarker: UIViewRepresentable {
    let adapter: ChatScrollGeometryAdapter
    let role: ChatScrollGeometryAdapter.Role
    func makeUIView(context: Context) -> ChatScrollMarkerView {
        let view = ChatScrollMarkerView()
        view.isUserInteractionEnabled = false
        view.isAccessibilityElement = false
        view.configure(adapter: adapter, role: role)
        return view
    }
    func updateUIView(_ view: ChatScrollMarkerView, context: Context) {
        view.configure(adapter: adapter, role: role)
        adapter.markersChanged()
    }
    static func dismantleUIView(_ view: ChatScrollMarkerView, coordinator: ()) { view.unbind() }
}

final class ChatScrollMarkerView: UIView {
    private weak var adapter: ChatScrollGeometryAdapter?
    private var role: ChatScrollGeometryAdapter.Role?
    func configure(adapter: ChatScrollGeometryAdapter, role: ChatScrollGeometryAdapter.Role) {
        if self.adapter !== adapter || self.role != role { unbind() }
        self.adapter = adapter; self.role = role
        adapter.register(self, as: role)
    }
    func unbind() {
        if let role { adapter?.unregister(self, as: role) }
        adapter = nil; role = nil
    }
    override func layoutSubviews() { super.layoutSubviews(); adapter?.markersChanged() }
    override func didMoveToWindow() { super.didMoveToWindow(); adapter?.markersChanged() }
    override func didMoveToSuperview() { super.didMoveToSuperview(); adapter?.markersChanged() }
}
