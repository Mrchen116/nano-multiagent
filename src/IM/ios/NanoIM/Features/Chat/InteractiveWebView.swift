import SwiftUI
import WebKit

/// Only the answer body uses WebKit; chat navigation, authority and delivery stay native.
struct InteractiveWebView: View {
    let runtime: InteractiveRuntime
    @State private var height: CGFloat = 120
    var body: some View {
        InteractiveWebContent(runtime: runtime, height: $height)
            .frame(height: height)
    }
}

struct InteractiveWebContent: UIViewRepresentable {
    let runtime: InteractiveRuntime
    @Binding var height: CGFloat
    func makeCoordinator() -> Coordinator {
        let height = $height
        return Coordinator(runtime: runtime) { height.wrappedValue = $0 }
    }
    func makeUIView(context: Context) -> WKWebView { context.coordinator.makeWebView() }
    func updateUIView(_ view: WKWebView, context: Context) { context.coordinator.updateStatus(view, disabled: runtime.webDisabled) }
    static func dismantleUIView(_ view: WKWebView, coordinator: Coordinator) { stop(view) }
    static func stop(_ view: WKWebView) {
        view.stopLoading()
        view.navigationDelegate = nil
        view.uiDelegate = nil
        view.configuration.userContentController.removeScriptMessageHandler(forName: "intelligentUI", contentWorld: .page)
    }

    @MainActor final class Coordinator: NSObject, WKScriptMessageHandlerWithReply, WKNavigationDelegate, WKUIDelegate {
        let runtime: InteractiveRuntime
        let generation: UUID
        private let heightChanged: (CGFloat) -> Void
        private var lastDisabled: Bool?
        private var sentMountedStatus = false
        private(set) var pendingImageLoads = 0
        private(set) var interruptedImageLoad = false
        private var indexURL: URL?
        init(runtime: InteractiveRuntime, heightChanged: @escaping (CGFloat) -> Void) {
            self.runtime = runtime; self.heightChanged = heightChanged; generation = runtime.webID
        }

        func updateStatus(_ view: WKWebView, disabled: Bool) {
            guard lastDisabled != disabled else { return }
            lastDisabled = disabled
            view.evaluateJavaScript("window.nanoSetStatus?.({disabled:\(disabled)})", completionHandler: nil)
        }
        func makeWebView() -> WKWebView {
            let config = WKWebViewConfiguration()
            // No shared browser cookies, storage or IM credentials enter the rendering surface.
            config.websiteDataStore = .nonPersistent()
            config.userContentController.addScriptMessageHandler(self, contentWorld: .page, name: "intelligentUI")
            let view = WKWebView(frame: .zero, configuration: config)
            view.isOpaque = false; view.backgroundColor = .clear
            view.scrollView.isScrollEnabled = false
            view.scrollView.contentInsetAdjustmentBehavior = .never
            view.navigationDelegate = self; view.uiDelegate = self
            guard let index = Bundle.main.url(forResource: "index", withExtension: "html", subdirectory: "IntelligentUI") else {
                runtime.error = L("缺少交互组件资源，请重新构建客户端。", "Interactive assets are missing. Rebuild the client.")
                return view
            }
            indexURL = index
            view.loadFileURL(index, allowingReadAccessTo: index.deletingLastPathComponent())
            return view
        }
        func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage,
                                   replyHandler: @escaping @MainActor @Sendable (Any?, String?) -> Void) {
            guard message.frameInfo.isMainFrame, message.frameInfo.request.url == indexURL else {
                replyHandler(nil, "This frame cannot access Nano"); return
            }
            let lease = runtime.presentationLease
            let imageLoad = (message.body as? [String: Any])?["type"] as? String == "attachment-image"
            if imageLoad { pendingImageLoads += 1 }
            Task {
                defer { if imageLoad { pendingImageLoads -= 1 } }
                var isAttachment = false
                do {
                    guard runtime.acceptsPresentation(generation), runtime.presentationLease == lease else {
                        if imageLoad { interruptedImageLoad = true }
                        replyHandler(nil, "This card is no longer active"); return
                    }
                    let request = try JSONValue(foundationObject: message.body)
                    isAttachment = request["type"].stringValue?.hasPrefix("attachment-") == true
                    if request["type"].stringValue == "height", generation == runtime.webID,
                       let value = request["height"].doubleValue, value.isFinite, value > 0 {
                        heightChanged(CGFloat(value))
                        if !sentMountedStatus, let page = message.webView {
                            sentMountedStatus = true
                            lastDisabled = nil
                            updateStatus(page, disabled: runtime.webDisabled)
                        }
                        replyHandler(NSNull(), nil); return
                    }
                    let result = try await runtime.webRequest(request, generation: generation)
                    guard runtime.acceptsPresentation(generation), runtime.presentationLease == lease else {
                        if imageLoad { interruptedImageLoad = true }
                        replyHandler(nil, "This card is no longer active"); return
                    }
                    replyHandler(result.foundationObject, nil)
                } catch {
                    if imageLoad, runtime.presentationLease != lease { interruptedImageLoad = true }
                    if !isAttachment, runtime.acceptsPresentation(generation), runtime.presentationLease == lease { runtime.error = error.localizedDescription }
                    replyHandler(nil, error.localizedDescription)
                }
            }
        }
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if navigationAction.targetFrame?.isMainFrame == true {
                if navigationAction.request.url == indexURL { decisionHandler(.allow); return }
                if runtime.acceptsPresentation(generation), navigationAction.navigationType == .linkActivated, let url = navigationAction.request.url,
                   ["http", "https"].contains(url.scheme?.lowercased() ?? "") { runtime.openURL?(url) }
                decisionHandler(.cancel); return
            }
            // Sandboxed HtmlView / media frames have no native bridge authority.
            decisionHandler(.allow)
        }
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if runtime.acceptsPresentation(generation), navigationAction.sourceFrame.isMainFrame, let url = navigationAction.request.url,
               ["http", "https"].contains(url.scheme?.lowercased() ?? "") { runtime.openURL?(url) }
            return nil
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            guard generation == runtime.webID else { return }
            runtime.resetAttachmentPresentation()
            runtime.error = error.localizedDescription
        }
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            guard generation == runtime.webID else { return }
            runtime.resetAttachmentPresentation()
            runtime.error = L("交互内容已停止，请读取最新内容。", "Interactive content stopped. Load the latest content.")
            runtime.loaded = false
        }
    }
}
