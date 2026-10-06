import SwiftUI
import PhotosUI
import UniformTypeIdentifiers

struct ConversationView: View {
    @Bindable var store: ChatStore
    let conversationID: String
    let openChat: (String) -> Void
    @State private var photo: PhotosPickerItem?
    @State private var pickingPhoto = false
    @State private var importing = false
    @State private var commands: [ChatCommandSet] = []
    @State private var bottomVisible = true
    @State private var firstLoaded = false
    @State private var confirmFork: ChatMessage?
    @State private var operationError: String?
    @State private var selection = NSRange(location: 0, length: 0)
    @State private var editing = false
    @State private var composing = false
    @State private var focusRequest: ComposerFocusRequest?
    @State private var dismissedCompletion = false
    @State private var copied = false
    @State private var loadingHistory = false
    @State private var viewport = CGRect.zero
    @ScaledMetric(relativeTo: .body) private var mentionRowHeight = 48.0
    @ScaledMetric(relativeTo: .body) private var commandRowHeight = 80.0
    private var conversation: Conversation? { store.conversations.first { $0.id == conversationID } }
    private var items: [TimelineItem] {
        let timeline = store.timelines[conversationID] ?? []
        let messageIDs = Set(timeline.compactMap { $0.message?.id })
        return timeline.filter { $0.message != nil || messageIDs.contains($0.before_message_id ?? "") }
    }
    private var uploads: [AttachmentUpload] { store.uploadDrafts[conversationID] ?? [] }
    private var uploading: Bool { uploads.contains(where: \.uploading) }
    private var draft: Binding<String> { Binding(get: { store.drafts[conversationID] ?? "" }, set: { store.drafts[conversationID] = $0 }) }
    var body: some View {
        VStack(spacing: 0) {
            if !store.connectionText.isEmpty { Text(store.connectionText).font(.caption).foregroundStyle(.secondary).padding(6) }
            if let error = store.errors[conversationID] ?? operationError { ErrorNotice(message: error).padding(10) }
            ScrollViewReader { scroll in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 18) {
                        if store.before[conversationID] != nil {
                            Button(L("更早的消息", "Earlier messages")) {
                                let anchor = items.first?.id
                                loadingHistory = true
                                Task { await store.loadChat(conversationID, older: true); if let anchor { scroll.scrollTo(anchor, anchor: .top) }; loadingHistory = false }
                            }.disabled(loadingHistory).frame(maxWidth: .infinity)
                            if loadingHistory { ProgressView(L("正在加载历史…", "Loading history…")).frame(maxWidth: .infinity) }
                        }
                        ForEach(items) { item in
                            if let message = item.message {
                                ChatMessageView(client: store.client, message: message, selfID: store.user.id, participants: conversation?.participants ?? [], refreshed: { Task { await store.loadChat(conversationID) } })
                                    .id(item.id).contextMenu {
                                        Button(L("复制正文", "Copy message"), systemImage: "doc.on.doc") {
                                            UIPasteboard.general.string = MarkdownContent.copy(ChatText.display(message.content, participants: conversation?.participants ?? []))
                                            copied = true
                                        }
                                        if conversation?.category == "agent", message.sender.type == "agent", message.kernel_message_id != nil, message.delivery_status == "completed" {
                                            Button(L("从这里分支", "Fork from here"), systemImage: "arrow.triangle.branch") { confirmFork = message }
                                        }
                                    }
                                    .onGeometryChange(for: Bool.self) { geometry in
                                        let frame = geometry.frame(in: .global)
                                        return frame.intersection(viewport).height >= min(44, frame.height) && !viewport.isEmpty
                                    } action: { _, visible in
                                        if visible { Task { await store.markRead(conversationID, messageID: message.id) } }
                                    }
                            } else {
                                Label(L("Agent 配置已更新", "Agent configuration updated"), systemImage: "slider.horizontal.3").font(.caption).foregroundStyle(.secondary).id(item.id)
                            }
                        }
                        Color.clear.frame(height: 1).id("bottom")
                    }.padding()
                }
                .onGeometryChange(for: CGRect.self) { $0.frame(in: .global) } action: { _, frame in viewport = frame }
                // Lazy row recycling is not viewport visibility, especially while the composer resizes.
                .onScrollGeometryChange(for: Bool.self) { geometry in
                    geometry.visibleRect.maxY >= geometry.contentSize.height - 24
                } action: { _, visible in
                    bottomVisible = visible
                }
                .overlay(alignment: .bottomTrailing) {
                    if !bottomVisible { Button { scroll.scrollTo("bottom", anchor: .bottom) } label: { Image(systemName: "arrow.down").padding(12).background(.regularMaterial, in: Circle()) }.padding().accessibilityLabel(L("最新消息", "Latest messages")) }
                }
                .onChange(of: items.count) { _, _ in
                    if bottomVisible || !firstLoaded { scroll.scrollTo("bottom", anchor: .bottom); firstLoaded = true }
                }
                .onChange(of: items.last?.message?.content) { _, _ in if bottomVisible { scroll.scrollTo("bottom", anchor: .bottom) } }
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            if store.checkingAccess.contains(conversationID) {
                VStack { ProgressView(L("正在确认聊天权限…", "Checking conversation access…")); Button(L("重试", "Retry")) { Task { await store.loadConversations(); await store.loadChat(conversationID) } } }.padding().frame(maxWidth: .infinity).background(.bar)
            } else { composer.disabled(conversation == nil) }
        }
        .background(NanoTheme.canvas)
        .overlay(alignment: .top) { if copied { Label(L("已复制正文", "Message copied"), systemImage: "checkmark.circle.fill").font(.callout).padding(12).background(.regularMaterial, in: Capsule()).padding(.top, 8) } }
        .task(id: copied) { if copied { try? await Task.sleep(for: .seconds(2)); if !Task.isCancelled { copied = false } } }
        .navigationTitle(conversation?.title ?? L("聊天", "Conversation"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .toolbar { ToolbarItem(placement: .topBarTrailing) { NavigationLink {
            ChatInfoView(store: store, conversationID: conversationID, openChat: openChat)
        } label: { Image(systemName: "ellipsis.circle") }.accessibilityLabel(L("聊天详情", "Conversation details")) } }
        .task(id: conversationID) {
            store.selectedID = conversationID
            await store.loadChat(conversationID)
            do { let result: ItemsPage<ChatCommandSet> = try await store.client.get("/im/v1/conversations/\(conversationID.pathComponent)/commands"); commands = result.items }
            catch { /* Commands are optional when a target device is offline; message sending remains available. */ }
        }
        .onDisappear { if store.selectedID == conversationID { store.selectedID = nil } }
        .onChange(of: photo) { _, selected in Task { await uploadPhoto(selected) } }
        .onChange(of: draft.wrappedValue) { _, _ in dismissedCompletion = false }
        .photosPicker(isPresented: $pickingPhoto, selection: $photo, matching: .images)
        .fileImporter(isPresented: $importing, allowedContentTypes: [.item], allowsMultipleSelection: true) { result in Task { await uploadFiles(result) } }
        .confirmationDialog(L("从这条回复创建新分支？", "Create a new branch from this reply?"), isPresented: Binding(get: { confirmFork != nil }, set: { if !$0 { confirmFork = nil } }), titleVisibility: .visible) {
            Button(L("创建分支", "Create branch")) { if let message = confirmFork { Task { await fork(message) } } }
        }
    }
    private var composer: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let pending = store.pending[conversationID], !store.sending.contains(conversationID) {
                HStack { Text(L("等待核对发送结果", "Awaiting delivery confirmation")).font(.caption); Spacer(); Button(L("重试核对", "Retry")) { Task { await store.send(conversationID, retry: true) } } }
                    .accessibilityLabel(pending.content)
            }
            if !(store.attachments[conversationID] ?? []).isEmpty {
                ScrollView(.horizontal) { HStack { ForEach(store.attachments[conversationID] ?? []) { item in
                    HStack {
                        if item.content_type?.hasPrefix("image/") == true { ProtectedImageView(client: store.client, source: item.url, label: item.file_name ?? L("待发图片", "Image to send")).frame(width: 64, height: 64) }
                        else { Image(systemName: "paperclip"); Text(item.file_name ?? L("附件", "Attachment")).lineLimit(1) }
                        Button { store.attachments[conversationID]?.removeAll { $0.id == item.id } } label: { Image(systemName: "xmark.circle.fill") }.accessibilityLabel(L("移除附件", "Remove attachment"))
                    }.font(.caption).padding(8).background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 12))
                } } }.disabled(store.pending[conversationID] != nil)
            }
            if !uploads.isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(uploads) { item in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(item.fileName).lineLimit(1)
                                    if item.contentType.hasPrefix("image/"), let data = item.data, let image = UIImage(data: data) { Image(uiImage: image).resizable().scaledToFit().frame(width: 44, height: 44) }
                                    Spacer()
                                    if item.uploading { ProgressView() }
                                    else {
                                        Button(L("移除", "Remove")) { store.removeUpload(conversationID, uploadID: item.id) }
                                        if item.retryable {
                                            TimelineView(.periodic(from: .now, by: 1)) { context in
                                                let seconds = max(0, Int(ceil((item.retryAt ?? .distantPast).timeIntervalSince(context.date))))
                                                Button(seconds > 0 ? L("等待 \(seconds) 秒", "Wait \(seconds)s") : L("重试", "Retry")) {
                                                    Task { await store.retryUpload(conversationID, uploadID: item.id) }
                                                }.disabled(seconds > 0)
                                            }
                                        }
                                    }
                                }
                                if let error = item.error { Text(error).foregroundStyle(.red) }
                            }.font(.caption).padding(8).background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 8))
                        }
                    }
                }.frame(maxHeight: 140).disabled(store.pending[conversationID] != nil)
                Button(L("仅发送文字，保留附件", "Send text only; keep attachments")) {
                    Task { await store.send(conversationID, textOnly: true) }
                }.font(.caption).disabled(uploading || store.pending[conversationID] != nil || draft.wrappedValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            if let completion { completionPanel(completion) }
            HStack(alignment: .bottom, spacing: 8) {
                Menu {
                    Button(L("照片", "Photos"), systemImage: "photo") { pickingPhoto = true }
                    Button(L("文件", "Files"), systemImage: "doc") { importing = true }
                } label: { Image(systemName: uploading ? "hourglass" : "plus.circle").font(.title2).padding(.vertical, 7) }
                    .disabled(uploading || store.pending[conversationID] != nil).accessibilityLabel(L("添加附件", "Add attachment"))
                ComposerTextView(text: draft, selection: $selection, editing: $editing, composing: $composing, focusRequest: focusRequest, enabled: store.pending[conversationID] == nil, pastedImage: { image in Task { await uploadImage(image) } })
                    .fixedSize(horizontal: false, vertical: true).padding(.horizontal, 8).background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 13))
                    .overlay(RoundedRectangle(cornerRadius: 13).stroke(NanoTheme.border))
                    .overlay(alignment: .topLeading) {
                        if draft.wrappedValue.isEmpty { Text(conversation?.type == "group" ? L("消息，@ 提及成员", "Message, @ to mention") : L("输入消息…", "Message…")).foregroundStyle(NanoTheme.muted).padding(.leading, 13).padding(.top, 9).allowsHitTesting(false) }
                    }
                Button { Task { await store.send(conversationID) } } label: {
                    if store.sending.contains(conversationID) { ProgressView() } else { Image(systemName: "arrow.up.circle.fill").font(.largeTitle) }
                }.disabled(!uploads.isEmpty || store.pending[conversationID] != nil || ((store.drafts[conversationID] ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && (store.attachments[conversationID] ?? []).isEmpty))
                    .accessibilityLabel(L("发送", "Send"))
            }
        }.padding(.horizontal, 16).padding(.vertical, 10).background(NanoTheme.surface)
            .overlay(alignment: .top) { Rectangle().fill(NanoTheme.border).frame(height: 0.5) }
    }
    private var completion: ChatText.Completion? {
        guard editing, !composing, !dismissedCompletion, store.pending[conversationID] == nil else { return nil }
        return ChatText.completion(draft.wrappedValue, selection: selection, mentions: conversation?.type == "group")
    }
    private struct CommandChoice: Identifiable {
        let id: String
        let label: String
        let source: String
        let description: String
        let insertion: String
    }
    private func commandChoices(_ query: String) -> [CommandChoice] {
        commands.flatMap { group in
            group.commands.map { command in
                CommandChoice(id: "\(group.agent_id)/\(command.name)", label: "/" + command.name, source: group.display_name, description: command.description, insertion: ChatText.command(command.name, agentID: conversation?.type == "group" ? group.agent_id : nil).trimmingCharacters(in: .whitespaces))
            } + group.skills.map { skill in
                CommandChoice(id: "\(group.agent_id)/skill:\(skill.skill_key)", label: "/skill:" + skill.name, source: group.display_name, description: skill.description, insertion: ChatText.skill(skill.name).trimmingCharacters(in: .whitespaces))
            }
        }.filter { query.isEmpty || $0.label.dropFirst().lowercased().hasPrefix(query.lowercased()) }
    }
    private func selectCompletion(_ completion: ChatText.Completion, value: String) {
        let result = ChatText.replacing(draft.wrappedValue, completion: completion, with: value)
        draft.wrappedValue = result.text; selection = result.selection
        focusRequest = ComposerFocusRequest(selection: result.selection)
    }
    private func completionPanel(_ completion: ChatText.Completion) -> some View {
        let members = (conversation?.participants ?? []).filter {
            ($0.user_id ?? $0.id) != store.user.id && (completion.query.isEmpty || ($0.display_name ?? $0.id).localizedCaseInsensitiveContains(completion.query) || $0.id.localizedCaseInsensitiveContains(completion.query))
        }
        let choices = commandChoices(completion.query)
        let height = min(220, max(1, Double(completion.kind == .mention ? members.count : choices.count)) * (completion.kind == .mention ? mentionRowHeight : commandRowHeight))
        return VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(completion.kind == .mention ? L("提及成员", "Mention a member") : L("命令", "Commands")).font(.caption.weight(.semibold)).foregroundStyle(NanoTheme.muted)
                Spacer()
                Button { dismissedCompletion = true } label: { Image(systemName: "xmark").padding(10) }.accessibilityLabel(L("关闭候选", "Dismiss suggestions"))
            }.padding(.leading, 12)
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    if completion.kind == .mention {
                        ForEach(members, id: \.id) { actor in
                            Button { selectCompletion(completion, value: ChatText.mention(actor, participants: conversation?.participants ?? [])) } label: {
                                HStack(spacing: 10) {
                                    AvatarView(name: actor.display_name ?? actor.id, kind: actor.type == "agent" ? "agent" : "person", size: 32)
                                    Text(actor.display_name ?? actor.id).foregroundStyle(NanoTheme.ink)
                                    Spacer()
                                    Text(actor.type == "agent" ? "Agent" : L("真人", "Person")).font(.caption).foregroundStyle(NanoTheme.muted)
                                }.padding(.horizontal, 12).padding(.vertical, 8).frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                            }.buttonStyle(.plain)
                        }
                        if members.isEmpty { Text(L("没有匹配的成员", "No matching members")).font(.callout).foregroundStyle(NanoTheme.muted).padding(12) }
                    } else {
                        ForEach(choices) { choice in
                            Button { selectCompletion(completion, value: choice.insertion) } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack { Text(choice.label).font(.body.weight(.medium)).foregroundStyle(NanoTheme.ink); Spacer(); Text(choice.source).font(.caption).foregroundStyle(NanoTheme.muted) }
                                    if !choice.description.isEmpty { Text(choice.description).font(.caption).foregroundStyle(NanoTheme.muted).lineLimit(2) }
                                }.padding(.horizontal, 12).padding(.vertical, 10).frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                            }.buttonStyle(.plain)
                        }
                        if choices.isEmpty { Text(L("暂无匹配的命令", "No matching commands")).font(.callout).foregroundStyle(NanoTheme.muted).padding(12) }
                    }
                }
            }.frame(height: height)
        }.background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(NanoTheme.border))
    }
    private func uploadPhoto(_ selected: PhotosPickerItem?) async {
        guard let selected else { return }; photo = nil
        do { if let data = try await selected.loadTransferable(type: Data.self), let image = UIImage(data: data) { await uploadImage(image) } }
        catch { operationError = error.localizedDescription }
    }
    private func uploadImage(_ image: UIImage) async {
        guard let data = image.jpegData(compressionQuality: 0.9) else { return }
        await upload(data, name: "photo-\(UUID().uuidString.prefix(8)).jpg", type: "image/jpeg")
    }
    private func uploadFiles(_ result: Result<[URL], Error>) async {
        do {
            for url in try result.get() {
                let access = url.startAccessingSecurityScopedResource(); defer { if access { url.stopAccessingSecurityScopedResource() } }
                let type = (try? url.resourceValues(forKeys: [.contentTypeKey]))?.contentType?.preferredMIMEType ?? "application/octet-stream"
                do { await upload(try Data(contentsOf: url), name: url.lastPathComponent, type: type) }
                catch { await store.addUpload(conversationID, data: nil, name: url.lastPathComponent, type: type, error: L("无法读取此文件，请重新选择。", "This file could not be read. Please select it again.")) }
            }
        } catch { operationError = error.localizedDescription }
    }
    private func upload(_ data: Data, name: String, type: String) async {
        operationError = nil
        await store.addUpload(conversationID, data: data, name: name, type: type)
    }
    private func fork(_ message: ChatMessage) async {
        do {
            let chat: Conversation = try await store.client.send("/im/v1/conversations/\(conversationID.pathComponent)/fork", body: ["fork_message_id": message.id])
            confirmFork = nil; await store.loadConversations(); openChat(chat.id)
        } catch { operationError = error.localizedDescription }
    }
}

struct ComposerFocusRequest {
    let id = UUID()
    let selection: NSRange
}

struct ComposerTextView: UIViewRepresentable {
    @Binding var text: String
    @Binding var selection: NSRange
    @Binding var editing: Bool
    @Binding var composing: Bool
    let focusRequest: ComposerFocusRequest?
    let enabled: Bool
    let pastedImage: (UIImage) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> PasteTextView {
        let view = PasteTextView(); view.delegate = context.coordinator
        view.font = .preferredFont(forTextStyle: .body); view.adjustsFontForContentSizeCategory = true
        view.backgroundColor = .clear; view.textColor = UIColor(named: "Ink"); view.textContainerInset = UIEdgeInsets(top: 9, left: 0, bottom: 9, right: 0)
        view.accessibilityLabel = L("消息", "Message"); view.imagePasted = pastedImage
        return view
    }
    func updateUIView(_ view: PasteTextView, context: Context) {
        context.coordinator.parent = self; view.isEditable = enabled; view.imagePasted = pastedImage
        context.coordinator.updating = true
        defer { context.coordinator.updating = false }
        if view.markedTextRange == nil && view.text != text { view.text = text }
        if let request = focusRequest, context.coordinator.lastFocusRequest != request.id {
            context.coordinator.lastFocusRequest = request.id
            view.selectedRange = request.selection
            view.becomeFirstResponder()
        }
    }
    func sizeThatFits(_ proposal: ProposedViewSize, uiView: PasteTextView, context: Context) -> CGSize? {
        guard let width = proposal.width else { return nil }
        let height = min(130, max(40, uiView.sizeThatFits(CGSize(width: width, height: .greatestFiniteMagnitude)).height))
        return CGSize(width: width, height: height)
    }
    final class Coordinator: NSObject, UITextViewDelegate {
        var parent: ComposerTextView
        var updating = false
        var lastFocusRequest: UUID?
        init(_ parent: ComposerTextView) { self.parent = parent }
        func textViewDidChange(_ textView: UITextView) {
            guard !updating else { return }
            parent.text = textView.text; updateSelection(textView)
        }
        func textViewDidChangeSelection(_ textView: UITextView) { if !updating { updateSelection(textView) } }
        func textViewDidBeginEditing(_ textView: UITextView) { if !updating { parent.editing = true; updateSelection(textView) } }
        func textViewDidEndEditing(_ textView: UITextView) { if !updating { parent.editing = false } }
        private func updateSelection(_ textView: UITextView) { parent.selection = textView.selectedRange; parent.composing = textView.markedTextRange != nil }
    }
    final class PasteTextView: UITextView {
        var imagePasted: ((UIImage) -> Void)?
        override func paste(_ sender: Any?) {
            if isEditable, let image = UIPasteboard.general.image { imagePasted?(image) }
            else { super.paste(sender) }
        }
    }
}
