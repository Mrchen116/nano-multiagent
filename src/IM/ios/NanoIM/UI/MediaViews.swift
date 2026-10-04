import SwiftUI
import QuickLook

struct ProtectedImageView: View {
    let client: IMClient
    let source: String
    var label: String = ""
    @State private var image: UIImage?
    @State private var error: String?
    @State private var preview = false
    var body: some View {
        Group {
            if let image {
                Button { preview = true } label: { Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 320).clipShape(RoundedRectangle(cornerRadius: 10)) }
                    .accessibilityLabel(label.isEmpty ? L("查看图片", "View image") : label)
            } else if let error { ErrorNotice(message: error) }
            else { ProgressView().frame(minHeight: 70) }
        }.task(id: source) { await load() }
            .sheet(isPresented: $preview) { NavigationStack { ScrollView([.horizontal, .vertical]) { if let image { Image(uiImage: image).resizable().scaledToFit().padding() } }.navigationTitle(L("图片", "Image")).toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("完成", "Done")) { preview = false } } } } }
    }
    private func load() async {
        do {
            let data: Data
            if let url = URL(string: source, relativeTo: client.baseURL)?.absoluteURL, !ServerOrigin.same(url, client.baseURL) {
                guard ["https", "http"].contains(url.scheme ?? "") else { throw URLError(.unsupportedURL) }
                // External images never use the authenticated client.
                data = try await URLSession.shared.data(from: url).0
            } else { data = try await client.protectedResource(source).0 }
            try Task.checkCancellation()
            guard let decoded = UIImage(data: data) else { throw URLError(.cannotDecodeContentData) }
            image = decoded
        } catch is CancellationError {} catch { self.error = error.localizedDescription }
    }
}
struct AttachmentView: View {
    let client: IMClient
    let attachment: ChatAttachment
    @State private var local: URL?
    @State private var preview: URL?
    @State private var error: String?
    @State private var loading = false
    @State private var download: Task<Void, Never>?
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if attachment.content_type?.hasPrefix("image/") == true { ProtectedImageView(client: client, source: attachment.url, label: attachment.file_name ?? "") }
            HStack {
                Button { download = Task { await prepare() } } label: { Label(attachment.file_name ?? L("附件", "Attachment"), systemImage: "paperclip").lineLimit(2) }.disabled(loading)
                if loading { ProgressView() }
                if let local { ShareLink(item: local) { Image(systemName: "square.and.arrow.up").accessibilityLabel(L("分享或保存", "Share or save")) } }
            }
            if let error { ErrorNotice(message: error) }
        }.quickLookPreview($preview)
            .onDisappear { download?.cancel(); download = nil; if let local { try? FileManager.default.removeItem(at: local.deletingLastPathComponent()) }; local = nil; preview = nil }
    }
    private func prepare() async {
        loading = true; error = nil; defer { loading = false }
        do {
            let (data, _) = try await client.protectedResource(attachment.url)
            try Task.checkCancellation()
            let folder = FileManager.default.temporaryDirectory.appendingPathComponent("nano-media-\(UUID().uuidString)", isDirectory: true)
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            let name = (attachment.file_name ?? "attachment").split(separator: "/").last.map(String.init) ?? "attachment"
            let file = folder.appendingPathComponent(name)
            try data.write(to: file, options: .atomic)
            if let local { try? FileManager.default.removeItem(at: local.deletingLastPathComponent()) }
            local = file; preview = file
        } catch is CancellationError {} catch { self.error = error.localizedDescription }
    }
}
