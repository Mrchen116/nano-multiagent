import SwiftUI
import Observation
import UIKit
import WebKit

/// Conversation-local display cache. A web page belongs to one message and is never
/// rebound to a different card. Draft writes continue to belong to InteractiveRuntime.
@MainActor
final class InteractiveCardPresentations {
    private static let pageLimit = 4
    private static let heightLimit = 40
    private var entries: [InteractiveCardPresentation] = []
    private var sizes: [InteractiveCardIdentity: CGSize] = [:]
    private var heightOrder: [InteractiveCardIdentity] = []

    func existing(_ identity: InteractiveCardIdentity) -> InteractiveCardPresentation? {
        entries.first { $0.identity == identity }
    }

    func size(_ identity: InteractiveCardIdentity) -> CGSize? { sizes[identity] }
    func admit(_ entry: InteractiveCardPresentation, explicit: Bool) -> Bool {
        if let index = entries.firstIndex(where: { $0 === entry }) {
            entries.remove(at: index)
        } else if entries.count >= Self.pageLimit {
            guard let index = entries.firstIndex(where: { !$0.visible })
                    ?? (explicit ? entries.firstIndex(where: { !$0.runtime.busy }) : nil) else { return false }
            entries.remove(at: index).evict()
        }
        entries.append(entry)
        entry.admitted = true
        return true
    }

    func record(_ size: CGSize, for identity: InteractiveCardIdentity) {
        sizes[identity] = size
        heightOrder.removeAll { $0 == identity }
        heightOrder.append(identity)
        if heightOrder.count > Self.heightLimit { sizes[heightOrder.removeFirst()] = nil }
    }

    func prune(_ identities: Set<InteractiveCardIdentity>) {
        entries.filter { !identities.contains($0.identity) }.forEach { $0.evict() }
        entries.removeAll { !identities.contains($0.identity) }
        sizes = sizes.filter { identities.contains($0.key) }
        heightOrder.removeAll { !identities.contains($0) }
    }

    func releaseOffscreen() {
        entries.filter { !$0.visible }.forEach { $0.evict() }
        entries.removeAll { !$0.visible }
    }

    func clear() { prune([]) }
}

struct InteractiveCardIdentity: Hashable {
    let messageID: String
    let source: String
    let attachments: [String]
    let format: String?
    let catalog: String?
    let readOnly: Bool
    let supersededBy: String?

    init(_ message: ChatMessage) {
        messageID = message.id
        source = message.interactive?.source ?? ""
        attachments = message.attachments.map { $0.url + "|" + ($0.content_type ?? "") }
        format = message.interactive?.format
        catalog = message.interactive?.catalog_version
        readOnly = message.interactive?.read_only == true
        supersededBy = message.interactive?.superseded_by
    }
}

@MainActor @Observable
final class InteractiveCardPresentation {
    let identity: InteractiveCardIdentity
    let runtime: InteractiveRuntime
    private weak var cache: InteractiveCardPresentations?
    var admitted = false
    var visible = false
    private(set) var height: CGFloat
    private var readyGeneration: UUID?
    var ready: Bool { runtime.loaded && readyGeneration == runtime.webID }
    var hasPage: Bool { page != nil }
    private var measuredWidth: CGFloat?
    private var width: CGFloat = 0
    private var needsDraftLoad = true
    private var lastDraftCheck: ContinuousClock.Instant?
    @ObservationIgnored private var page: WKWebView?
    @ObservationIgnored private var coordinator: InteractiveWebContent.Coordinator?
    @ObservationIgnored private var loadTask: Task<Void, Never>?
    @ObservationIgnored private var loadOwner: UUID?

    init(identity: InteractiveCardIdentity, runtime: InteractiveRuntime, cache: InteractiveCardPresentations) {
        self.identity = identity
        self.runtime = runtime
        self.cache = cache
        let measured = cache.size(identity)
        height = measured?.height ?? 120
        measuredWidth = measured?.width
    }

    func activate(explicit: Bool = false, checkDraft: Bool = false) {
        guard visible, runtime.canPresent, cache?.admit(self, explicit: explicit) == true else { return }
        let wasAttached = runtime.presentationLease != nil
        if !wasAttached, let coordinator, coordinator.interruptedImageLoad || coordinator.pendingImageLoads > 0 {
            releasePage()
            runtime.retireWebPage()
        }
        runtime.setPresentationAttached(true)
        if !wasAttached, let page, ready {
            // The bridge stops while detached. Catch layout changes delivered during that gap.
            let lease = runtime.presentationLease
            page.evaluateJavaScript("Math.ceil(document.getElementById('root')?.getBoundingClientRect().height ?? 0)") { [weak self, weak page] value, _ in
                guard let self, self.page === page, self.runtime.presentationLease == lease,
                      let height = value as? Double, height > 0 else { return }
                self.measured(CGFloat(height))
            }
        }
        guard loadTask == nil else { return }
        let initial = needsDraftLoad
        if !initial {
            guard checkDraft, let lastDraftCheck, lastDraftCheck.duration(to: .now) >= .seconds(30) else { return }
        }
        lastDraftCheck = .now
        let owner = UUID()
        loadOwner = owner
        loadTask = Task { [weak self] in
            guard let self else { return }
            if initial { await runtime.load() }
            else { await runtime.refreshPresentationDraft() }
            if loadOwner == owner {
                needsDraftLoad = !runtime.loaded
                loadTask = nil
                loadOwner = nil
            }
        }
    }

    func detach() {
        visible = false
        suspend()
    }

    func suspend() {
        runtime.setPresentationAttached(false)
        cancelLoad()
        if page != nil && (!ready || (coordinator?.pendingImageLoads ?? 0) > 0) {
            // A rejected one-shot bootstrap or initial image reply is not reusable.
            releasePage()
            runtime.retireWebPage()
        }
    }

    func evict() {
        runtime.setPresentationAttached(false)
        admitted = false
        cancelLoad()
        releasePage()
        runtime.leave()
    }

    private func cancelLoad() {
        loadTask?.cancel()
        loadTask = nil
        loadOwner = nil
    }

    private func releasePage() {
        if let page { InteractiveWebContent.stop(page) }
        page?.removeFromSuperview()
        page = nil
        coordinator = nil
        readyGeneration = nil
    }

    func webView() -> WKWebView? {
        guard admitted, runtime.canPresent else { return nil }
        if let page, coordinator?.generation == runtime.webID { return page }
        if let page { InteractiveWebContent.stop(page); page.removeFromSuperview() }
        let coordinator = InteractiveWebContent.Coordinator(runtime: runtime) { [weak self] height in
            self?.measured(height)
        }
        self.coordinator = coordinator
        let view = coordinator.makeWebView()
        page = view
        return view
    }

    func updateWidth(_ width: CGFloat) {
        guard width > 0, abs(width - self.width) >= 1 else { return }
        self.width = width
        if page == nil, let measuredWidth, abs(width - measuredWidth) >= 1 { height = 120 }
    }

    private func measured(_ value: CGFloat) {
        guard visible, admitted, value.isFinite, value > 0 else { return }
        if abs(height - value) >= 1 { height = value }
        if width > 0 {
            measuredWidth = width
            cache?.record(CGSize(width: width, height: value), for: identity)
        }
        readyGeneration = runtime.webID
    }

    func updateStatus(_ view: WKWebView, disabled: Bool) { coordinator?.updateStatus(view, disabled: disabled) }
}

struct MountedInteractiveWebView: UIViewRepresentable {
    let presentation: InteractiveCardPresentation
    let webID: UUID
    let disabled: Bool

    func makeUIView(context: Context) -> UIView { UIView() }

    func updateUIView(_ host: UIView, context: Context) {
        guard presentation.runtime.webID == webID, let page = presentation.webView() else { return }
        if page.superview !== host {
            page.removeFromSuperview()
            host.subviews.forEach { $0.removeFromSuperview() }
            page.frame = host.bounds
            page.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            host.addSubview(page)
        }
        presentation.updateStatus(page, disabled: disabled)
    }

    static func dismantleUIView(_ host: UIView, coordinator: ()) {
        host.subviews.forEach { $0.removeFromSuperview() }
    }
}
