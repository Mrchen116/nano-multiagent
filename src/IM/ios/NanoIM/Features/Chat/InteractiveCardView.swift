import SwiftUI

struct InteractiveCardView: View {
    @State private var runtime: InteractiveRuntime
    @State private var presentation: InteractiveCardPresentation?
    @State private var visible = false
    let readOnly: Bool
    var scroll: ChatScrollCoordinator?
    @Environment(\.openURL) private var openURL
    @Environment(\.scenePhase) private var scenePhase
    init(client: IMClient, message: ChatMessage, chat: ChatStore, readOnly: Bool,
         presentations: InteractiveCardPresentations? = nil, scroll: ChatScrollCoordinator? = nil) {
        let identity = InteractiveCardIdentity(message)
        let cached = presentations?.existing(identity)
        let draft = chat.interactionDrafts.runtime(message.conversation_id, messageID: message.id)
        let matchingDraft = draft.flatMap { InteractiveCardIdentity($0.message) == identity ? $0 : nil }
        let runtime = cached?.runtime ?? matchingDraft
            ?? InteractiveRuntime(client: client, message: message, chat: chat, readOnly: readOnly)
        _runtime = State(initialValue: runtime)
        _presentation = State(initialValue: runtime.usesWebRenderer ? presentations.map {
            cached ?? InteractiveCardPresentation(identity: identity, runtime: runtime, cache: $0)
        } : nil)
        self.readOnly = readOnly
        self.scroll = scroll
    }
    private var shouldActivate: Bool {
        visible && scenePhase == .active && scroll?.cardRenderingPaused != true && runtime.canPresent
    }

    var body: some View {
        let draftOwner = runtime.chat.interactionDrafts.runtime(runtime.message.conversation_id, messageID: runtime.message.id)
        let draftFailure = runtime.chat.interactionDrafts.failure(runtime.message.conversation_id, messageID: runtime.message.id)
        VStack(alignment: .leading, spacing: 12) {
            if let presentation {
                managedContent(presentation)
            } else if runtime.loaded {
                if runtime.usesWebRenderer {
                    InteractiveWebView(runtime: runtime).id(runtime.webID)
                } else {
                    InteractiveNodeView(node: runtime.root, runtime: runtime)
                        .disabled(runtime.busy || runtime.hasPending)
                }
            } else if runtime.error == nil { ProgressView(L("载入交互内容…", "Loading interaction…")) }
            if runtime.readOnly { Text(L("历史回复，仅供阅读", "Historical reply · read only")).font(.caption).foregroundStyle(.secondary) }
            if runtime.busy { ProgressView(runtime.composing ? L("正在采用…", "Preparing draft…") : L("正在发送…", "Sending…")) }
            else if runtime.submitted && !runtime.hasPending { Text(L("请求已发送，Agent 将在聊天中回复。", "Request sent. The Agent will reply in the conversation.")).font(.caption).foregroundStyle(NanoTheme.accent) }
            if let draftOwner, let draftFailure, draftOwner.conflict,
               runtime.chat.isGroupConversation(runtime.message.conversation_id) {
                DraftFailureNotice(runtime: draftOwner, failure: draftFailure)
            } else if let error = runtime.error {
                ErrorNotice(message: error)
                if !runtime.loaded { Button(L("读取最新", "Load latest")) { Task { await runtime.load() } } }
                else if !runtime.hasPending { Button(L("重试", "Retry")) { Task { await runtime.retryContent() } } }
            }
            if runtime.hasPending { Button(L("重试核对上次请求", "Check previous request")) { Task { await runtime.retry() } }.disabled(runtime.readOnly || runtime.busy) }
            if presentation == nil || (visible && presentation?.ready == true) {
                ForEach(runtime.fallbackAttachmentIndexes, id: \.self) { index in
                    AttachmentView(client: runtime.client, attachment: runtime.message.attachments[index])
                }
            }
        }
        .accessibilityElement(children: .contain)
        .task {
            let open = openURL
            runtime.openURL = { open($0) }
            if presentation == nil { await runtime.load() }
        }
        // Use the scroll view's own visibility lifecycle so first entry does not depend
        // on a separate geometry callback publishing the viewport before the card.
        .onScrollVisibilityChange(threshold: 0.01) { isVisible in
            guard let presentation else { return }
            visible = isVisible
            presentation.visible = isVisible
            if isVisible, scenePhase == .active, presentation.hasPage { presentation.activate() }
            if !isVisible { presentation.detach() }
        }
        .onChange(of: scenePhase) { _, phase in
            guard let presentation else { return }
            if phase == .background { presentation.suspend() }
            if phase == .active, visible, presentation.hasPage { presentation.activate() }
        }
        .task(id: shouldActivate) {
            guard shouldActivate, let presentation else { return }
            do { try await Task.sleep(for: .milliseconds(120)) } catch { return }
            presentation.activate(checkDraft: true)
        }
        .onChange(of: readOnly) { _, value in runtime.setReadOnly(value) }
        .onDisappear {
            visible = false
            if let presentation { presentation.detach() } else { runtime.leave() }
        }
        .sheet(isPresented: Binding(get: { runtime.attachmentPreview != nil }, set: { if !$0 { runtime.attachmentPreview = nil } })) {
            if let image = runtime.attachmentPreview { ImagePreview(image: image) }
        }
        .confirmationDialog(L("替换未发送的内容？", "Replace unsent content?"), isPresented: Binding(get: { runtime.pendingCompose != nil }, set: { if !$0 { runtime.pendingCompose = nil } }), titleVisibility: .visible) {
            Button(L("替换", "Replace"), role: .destructive) {
                if let request = runtime.pendingCompose { Task { await runtime.replaceCompose(request) } }
            }
            Button(L("取消", "Cancel"), role: .cancel) { runtime.pendingCompose = nil }
        }
    }

    private func managedContent(_ presentation: InteractiveCardPresentation) -> some View {
        let viewport = scroll?.viewport ?? .zero
        let cardHeight = presentation.height
        return ZStack {
            if !presentation.ready {
                RoundedRectangle(cornerRadius: 12).fill(NanoTheme.surface)
                if visible && runtime.error == nil {
                    ProgressView()
                        .accessibilityLabel(L("载入交互内容…", "Loading interaction…"))
                        .visualEffect { content, geometry in
                            let center = geometry.frame(in: .global).midY
                            let top = max(center - cardHeight / 2, viewport.minY)
                            let bottom = min(center + cardHeight / 2, viewport.maxY)
                            return content.offset(y: top < bottom ? (top + bottom) / 2 - center : 0)
                        }
                }
            }
            if presentation.admitted && runtime.loaded && ((visible && presentation.attached) || presentation.ready) {
                MountedInteractiveWebView(presentation: presentation, webID: runtime.webID,
                                          disabled: runtime.webDisabled, attached: presentation.attached)
                    .opacity(presentation.ready ? 1 : 0)
                    .accessibilityHidden(!presentation.ready)
                    .allowsHitTesting(presentation.ready)
            }
        }
        .frame(height: presentation.height)
        .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { _, width in
            presentation.updateWidth(width)
        }
    }
}
