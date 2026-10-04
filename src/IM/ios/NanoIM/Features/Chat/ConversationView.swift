import SwiftUI
import PhotosUI
import UniformTypeIdentifiers

struct ConversationView: View {
    @Bindable var store: ChatStore
    let conversationID: String
    let openChat: (String) -> Void
    @State private var photo: PhotosPickerItem?
    @State private var importing = false
    @State private var uploading = false
    @State private var commands: [ChatCommandSet] = []
    @State private var bottomVisible = true
    @State private var firstLoaded = false
    @State private var confirmFork: ChatMessage?
    @State private var operationError: String?
    private var conversation: Conversation? { store.conversations.first { $0.id == conversationID } }
    private var items: [TimelineItem] { store.timelines[conversationID] ?? [] }
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
                                Task { await store.loadChat(conversationID, older: true); if let anchor { scroll.scrollTo(anchor, anchor: .top) } }
                            }.frame(maxWidth: .infinity)
                        }
                        ForEach(items) { item in
                            if let message = item.message {
                                ChatMessageView(client: store.client, message: message, selfID: store.user.id, participants: conversation?.participants ?? [], refreshed: { Task { await store.loadChat(conversationID) } })
                                    .id(item.id).contextMenu {
                                        Button(L("复制正文", "Copy message"), systemImage: "doc.on.doc") { UIPasteboard.general.string = message.content }
                                        if conversation?.category == "agent", message.sender.type == "agent", message.kernel_message_id != nil, message.delivery_status == "completed" {
                                            Button(L("从这里分支", "Fork from here"), systemImage: "arrow.triangle.branch") { confirmFork = message }
                                        }
                                    }
                                    .onAppear { Task { await store.markRead(conversationID, messageID: message.id) } }
                            } else {
                                Label(L("Agent 配置已更新", "Agent configuration updated"), systemImage: "slider.horizontal.3").font(.caption).foregroundStyle(.secondary).id(item.id)
                            }
                        }
                        Color.clear.frame(height: 1).id("bottom")
                            .onAppear { bottomVisible = true }
                            .onDisappear { bottomVisible = false }
                    }.padding()
                }
                .overlay(alignment: .bottomTrailing) {
                    if !bottomVisible { Button { withAnimation { scroll.scrollTo("bottom", anchor: .bottom) } } label: { Image(systemName: "arrow.down").padding(12).background(.regularMaterial, in: Circle()) }.padding().accessibilityLabel(L("最新消息", "Latest messages")) }
                }
                .onChange(of: items.count) { _, _ in
                    if bottomVisible || !firstLoaded { scroll.scrollTo("bottom", anchor: .bottom); firstLoaded = true }
                }
                .onChange(of: items.last?.message?.content) { _, _ in if bottomVisible { scroll.scrollTo("bottom", anchor: .bottom) } }
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) { composer.disabled(conversation == nil) }
        .background(Color(.systemGroupedBackground))
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
                    HStack { Image(systemName: "paperclip"); Text(item.file_name ?? L("附件", "Attachment")).lineLimit(1); Button { store.attachments[conversationID]?.removeAll { $0.id == item.id } } label: { Image(systemName: "xmark.circle.fill") } }.font(.caption).padding(8).background(.quaternary, in: Capsule())
                } } }.disabled(store.pending[conversationID] != nil)
            }
            HStack(alignment: .bottom, spacing: 8) {
                Menu {
                    PhotosPicker(selection: $photo, matching: .images) { Label(L("照片", "Photos"), systemImage: "photo") }
                    Button(L("文件", "Files"), systemImage: "doc") { importing = true }
                    if conversation?.type == "group" {
                        Menu(L("提及 Agent", "Mention agent")) { ForEach(conversation?.participants.filter { $0.type == "agent" } ?? [], id: \.id) { actor in
                            Button(actor.display_name ?? actor.id) { draft.wrappedValue += "@\(actor.id) " }
                        } }
                    }
                    Menu(L("命令", "Commands")) { ForEach(commands) { group in
                        Section(group.display_name) {
                            ForEach(group.commands) { command in Button("/" + command.name) { draft.wrappedValue = ChatText.command(command.name, agentID: conversation?.type == "group" ? group.agent_id : nil) } }
                            ForEach(group.skills) { skill in Button("/skill:" + skill.name) { draft.wrappedValue = ChatText.skill(skill.name) } }
                        }
                    } }
                } label: { Image(systemName: uploading ? "hourglass" : "plus.circle").font(.title2).padding(.vertical, 7) }
                    .disabled(uploading || store.pending[conversationID] != nil).accessibilityLabel(L("附件、提及和命令", "Attachments, mentions and commands"))
                ComposerTextView(text: draft, enabled: store.pending[conversationID] == nil, pastedImage: { image in Task { await uploadImage(image) } })
                    .frame(minHeight: 40, maxHeight: 130).padding(.horizontal, 6).background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 12))
                Button { Task { await store.send(conversationID) } } label: {
                    if store.sending.contains(conversationID) { ProgressView() } else { Image(systemName: "arrow.up.circle.fill").font(.largeTitle) }
                }.disabled(uploading || store.pending[conversationID] != nil || ((store.drafts[conversationID] ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && (store.attachments[conversationID] ?? []).isEmpty))
                    .accessibilityLabel(L("发送", "Send"))
            }
            if uploading { ProgressView(L("正在上传…", "Uploading…")) }
        }.padding(.horizontal, 12).padding(.vertical, 8).background(.bar)
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
                let values = try url.resourceValues(forKeys: [.contentTypeKey, .fileSizeKey])
                guard (values.fileSize ?? 0) <= 10 * 1024 * 1024 else { operationError = L("单个文件不能超过 10 MB。", "Each file must be no larger than 10 MB."); continue }
                await upload(try Data(contentsOf: url), name: url.lastPathComponent, type: values.contentType?.preferredMIMEType ?? "application/octet-stream")
            }
        } catch { operationError = error.localizedDescription }
    }
    private func upload(_ data: Data, name: String, type: String) async {
        uploading = true; operationError = nil; defer { uploading = false }
        do {
            let attachment = try await store.client.upload(data, fileName: name, contentType: type, conversationID: conversationID)
            guard store.conversations.contains(where: { $0.id == conversationID }) else { return }
            store.attachments[conversationID, default: []].append(attachment)
        } catch { operationError = error.localizedDescription }
    }
    private func fork(_ message: ChatMessage) async {
        do {
            let chat: Conversation = try await store.client.send("/im/v1/conversations/\(conversationID.pathComponent)/fork", body: ["fork_message_id": message.id])
            confirmFork = nil; await store.loadConversations(); openChat(chat.id)
        } catch { operationError = error.localizedDescription }
    }
}

struct ComposerTextView: UIViewRepresentable {
    @Binding var text: String
    let enabled: Bool
    let pastedImage: (UIImage) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> PasteTextView {
        let view = PasteTextView(); view.delegate = context.coordinator
        view.font = .preferredFont(forTextStyle: .body); view.adjustsFontForContentSizeCategory = true
        view.backgroundColor = .clear; view.textContainerInset = UIEdgeInsets(top: 9, left: 0, bottom: 9, right: 0)
        view.accessibilityLabel = L("消息", "Message"); view.imagePasted = pastedImage
        return view
    }
    func updateUIView(_ view: PasteTextView, context: Context) {
        context.coordinator.parent = self; view.isEditable = enabled; view.imagePasted = pastedImage
        if view.markedTextRange == nil && view.text != text { view.text = text }
    }
    func sizeThatFits(_ proposal: ProposedViewSize, uiView: PasteTextView, context: Context) -> CGSize? {
        guard let width = proposal.width else { return nil }
        let height = min(130, max(40, uiView.sizeThatFits(CGSize(width: width, height: .greatestFiniteMagnitude)).height))
        return CGSize(width: width, height: height)
    }
    final class Coordinator: NSObject, UITextViewDelegate {
        var parent: ComposerTextView
        init(_ parent: ComposerTextView) { self.parent = parent }
        func textViewDidChange(_ textView: UITextView) { parent.text = textView.text }
    }
    final class PasteTextView: UITextView {
        var imagePasted: ((UIImage) -> Void)?
        override func paste(_ sender: Any?) {
            if isEditable, let image = UIPasteboard.general.image { imagePasted?(image) }
            else { super.paste(sender) }
        }
    }
}
