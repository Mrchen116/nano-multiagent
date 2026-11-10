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
    func makeCoordinator() -> Coordinator { Coordinator(runtime: runtime, height: $height) }
    func makeUIView(context: Context) -> WKWebView { context.coordinator.makeWebView() }
    func updateUIView(_ view: WKWebView, context: Context) {
        let disabled = runtime.webDisabled ? "true" : "false"
        view.evaluateJavaScript("window.nanoSetStatus?.({disabled:\(disabled)})", completionHandler: nil)
    }
    static func dismantleUIView(_ view: WKWebView, coordinator: Coordinator) {
        view.stopLoading()
        view.configuration.userContentController.removeScriptMessageHandler(forName: "intelligentUI", contentWorld: .page)
    }

    @MainActor final class Coordinator: NSObject, WKScriptMessageHandlerWithReply, WKNavigationDelegate, WKUIDelegate {
        let runtime: InteractiveRuntime
        let generation: UUID
        let height: Binding<CGFloat>
        private(set) var webView: WKWebView?
        private var indexURL: URL?
        init(runtime: InteractiveRuntime, height: Binding<CGFloat>) {
            self.runtime = runtime; self.height = height; generation = runtime.webID
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
            webView = view
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
            Task {
                var isAttachment = false
                do {
                    let request = try JSONValue(foundationObject: message.body)
                    isAttachment = request["type"].stringValue?.hasPrefix("attachment-") == true
                    if request["type"].stringValue == "height", generation == runtime.webID,
                       let value = request["height"].doubleValue, value.isFinite, value > 0 {
                        height.wrappedValue = CGFloat(value)
                        replyHandler(NSNull(), nil); return
                    }
                    let result = try await runtime.webRequest(request, generation: generation)
                    replyHandler(result.foundationObject, nil)
                } catch {
                    if !isAttachment, generation == runtime.webID { runtime.error = error.localizedDescription }
                    replyHandler(nil, error.localizedDescription)
                }
            }
        }
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if navigationAction.targetFrame?.isMainFrame == true {
                if navigationAction.request.url == indexURL { decisionHandler(.allow); return }
                if navigationAction.navigationType == .linkActivated, let url = navigationAction.request.url,
                   ["http", "https"].contains(url.scheme?.lowercased() ?? "") { runtime.openURL?(url) }
                decisionHandler(.cancel); return
            }
            // Sandboxed HtmlView / media frames have no native bridge authority.
            decisionHandler(.allow)
        }
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if navigationAction.sourceFrame.isMainFrame, let url = navigationAction.request.url,
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
