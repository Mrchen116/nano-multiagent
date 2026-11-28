import SwiftUI
import PhotosUI
import ImageIO
import UniformTypeIdentifiers

struct MeView: View {
    let client: IMClient
    let user: AuthUser
    let onAccountUpdated: @MainActor () -> Void
    var openChat: (String) -> Void
    let onSignOut: @MainActor () -> Void
    @State private var personal: NativePersonalAgentState?
    @State private var computers: [SettingsNode]?
    @State private var confirmSignOut = false
    @State private var applying = false
    @State private var membershipError: String?

    private var assistant: NativePersonalAgentState.Binding? {
        guard personal?.creation == nil, personal?.binding?.status == "active" else { return nil }
        return personal?.binding
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if user.accountEnabled {
                    NavigationLink { SettingsAccountView(client: client, onAccountUpdated: onAccountUpdated) } label: { identity }
                        .accessibilityHint(L("编辑个人资料与语言", "Edit profile and language"))
                    if let chatID = assistant?.conversation_id {
                        Button { openChat(chatID) } label: { assistantContact }
                    } else {
                        NavigationLink { PersonalAssistantSetup(client: client, user: user, openChat: openChat) } label: { assistantContact }
                    }
                    NavigationLink { SettingsNodesView(client: client, user: user, accountUpdated: onAccountUpdated) } label: {
                        computerShelf
                    }
                } else { identity }

                teamAccess
                if let membershipError { ErrorNotice(message: membershipError) }
            }.padding(.horizontal, 20).padding(.top, 4).padding(.bottom, 36)
        }
        .buttonStyle(.plain).background(NanoTheme.surface)
        .navigationTitle(L("我的", "Me")).navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                NavigationLink { preferences } label: { Image(systemName: "gearshape") }
                    .accessibilityLabel(L("设置", "Settings"))
            }
        }
        .task { await refreshSpace() }
        .refreshable { await refreshSpace() }
    }

    private var identity: some View {
        VStack(spacing: 10) {
            AvatarView(id: .userID(user.id), size: 76)
            VStack(spacing: 3) {
                Text(user.display_name).font(.system(.largeTitle, design: .rounded, weight: .bold)).foregroundStyle(NanoTheme.ink)
                Text("@" + user.username).font(.subheadline).foregroundStyle(NanoTheme.muted)
            }
            if user.accountEnabled {
                Label(L("编辑资料", "Edit profile"), systemImage: "pencil")
                    .font(.caption.weight(.semibold)).foregroundStyle(NanoTheme.ink)
                    .padding(.horizontal, 12).padding(.vertical, 6).background(NanoTheme.canvas, in: Capsule())
            }
        }.multilineTextAlignment(.center).frame(maxWidth: .infinity).padding(.vertical, 10)
            .contentShape(Rectangle()).accessibilityElement(children: .combine)
    }

    private var assistantContact: some View {
        HStack(spacing: 12) {
            if let assistant { AvatarView(id: .personal(assistant), size: 56) } else { PortraitPreview(size: 56) }
            VStack(alignment: .leading, spacing: 3) {
                Text(L("个人助手", "Personal assistant")).font(.caption.weight(.medium)).foregroundStyle(NanoTheme.muted)
                Text(assistant?.display_name ?? (personal?.creation != nil ? L("继续设置", "Continue setup") :
                      personal == nil ? L("查看助手", "View assistant") : L("创建助手", "Create assistant")))
                    .font(.headline).foregroundStyle(NanoTheme.ink)
            }
            Spacer(minLength: 2)
            Image(systemName: assistant?.conversation_id == nil ? "arrow.right" : "bubble.left.fill")
                .font(.body.weight(.medium)).foregroundStyle(NanoTheme.accent).frame(width: 44, height: 44)
                .background(NanoTheme.surface, in: Circle())
        }.padding(.horizontal, 14).padding(.vertical, 10)
            .background(NanoTheme.softAccent, in: RoundedRectangle(cornerRadius: 18))
            .accessibilityHint(assistant?.conversation_id == nil ? L("打开个人助手设置", "Open assistant setup") : L("打开聊天", "Open chat"))
    }

    private var computerShelf: some View {
        let count = computers?.count ?? user.owned_node_ids.count
        return VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Text(L("我的电脑", "My computers")).font(.headline)
                Spacer()
                Text(count, format: .number).font(.subheadline.monospacedDigit()).foregroundStyle(.secondary)
                Image(systemName: "chevron.right").font(.caption.bold()).foregroundStyle(.tertiary)
            }
            if let computer = computers?.first(where: { $0.id == user.default_entry_node_id }) ?? computers?.first(where: { $0.status == "online" }) ?? computers?.first {
                HStack(spacing: 14) {
                    Image(systemName: "desktopcomputer").font(.system(size: 31, weight: .regular)).foregroundStyle(NanoTheme.ink)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(computer.name).font(.subheadline.weight(.semibold))
                        HStack(spacing: 5) {
                            Circle().fill(computer.status == "online" ? Color.green : Color.secondary).frame(width: 7, height: 7)
                            Text(settingsStatus(computer.status)).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            } else if count == 0 {
                Label(L("连接电脑", "Connect a computer"), systemImage: "desktopcomputer.badge.plus")
                    .font(.subheadline).foregroundStyle(NanoTheme.accent)
            }
        }.foregroundStyle(NanoTheme.ink).padding(16).frame(maxWidth: .infinity, alignment: .leading)
            .background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 16))
            .contentShape(Rectangle()).accessibilityElement(children: .combine)
    }

    @ViewBuilder private var teamAccess: some View {
        if user.membership_status == "active" {
            NavigationLink {
                List {
                    if user.is_company_admin {
                        NavigationLink(L("团队成员", "Team members")) {
                            SettingsCompanyView(client: client, user: user, onAccountUpdated: onAccountUpdated)
                        }
                    }
                    NavigationLink(L("团队设置", "Team settings")) { SettingsPoliciesView(client: client, isAdmin: user.is_company_admin) }
                }.navigationTitle(L("我的团队", "My team")).toolbar(.hidden, for: .tabBar)
            } label: {
                CrewdenDestination(title: L("我的团队", "My team"), symbol: "person.2",
                    detail: user.is_company_admin ? L("管理员", "Admin") : L("成员", "Member"))
            }
        } else if user.membership_status == "none" {
            Button { Task { await applyToTeam() } } label: {
                CrewdenDestination(title: L("加入团队", "Join a team"), symbol: "person.2")
            }.disabled(applying)
        } else {
            Button { onAccountUpdated() } label: {
                CrewdenDestination(title: L("团队申请", "Team membership"), symbol: "person.2", detail: settingsStatus(user.membership_status))
            }.accessibilityHint(L("刷新状态", "Refresh status"))
        }
    }

    private func refreshSpace() async {
        guard user.accountEnabled else { return }
        async let binding: NativePersonalAgentState? = try? client.get("/im/v1/personal-agent")
        async let nodes = try? client.settingsNodes()
        let (next, devices) = await (binding, nodes)
        guard !Task.isCancelled else { return }
        personal = next
        computers = devices?.filter { $0.owner_id == user.owner_id }
    }

    private var preferences: some View {
        List {
            if user.accountEnabled {
                NavigationLink(L("个人资料与语言", "Profile and language")) { SettingsAccountView(client: client, onAccountUpdated: onAccountUpdated) }
                NavigationLink(L("模型服务", "Model services")) { ModelServicesNodesView(client: client, ownerID: user.owner_id) }
            }
            NavigationLink(L("提醒与安装", "Reminders and installation")) { SettingsHelpView() }
            Section { Button(L("退出登录", "Sign out"), role: .destructive) { confirmSignOut = true } }
        }.navigationTitle(L("设置", "Settings")).toolbar(.hidden, for: .tabBar)
        .confirmationDialog(L("退出当前账号？", "Sign out of this account?"), isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button(L("退出登录", "Sign out"), role: .destructive) { onSignOut() }
        } message: {
            Text(L("本机的会话和待发内容将清除。服务端聊天历史会保留。", "Local session and unsent content will be cleared. Server chat history is retained."))
        }
    }
    private func applyToTeam() async {
        guard !applying else { return }
        applying = true; defer { applying = false }
        do {
            let _: AuthUser = try await client.send("/im/v1/company/join", body: SettingsActionBody())
            membershipError = nil; onAccountUpdated()
        } catch { membershipError = settingsError(error) }
    }

}

struct SettingsAccountView: View {
    let client: IMClient
    let onAccountUpdated: @MainActor () -> Void
    @Environment(\.avatarImageStore) private var avatarImages
    @State private var profile: SettingsAccount?
    @State private var nodes: [SettingsNode] = []
    @State private var name = ""
    @State private var defaultNode = ""
    @State private var locale = "zh"
    @State private var error: String?
    @State private var success: String?
    @State private var busy = false
    @State private var avatarBusy = false
    @State private var pickedPhoto: PhotosPickerItem?
    @State private var cropCandidate: IdentifiableCropImage?

    private var dirty: Bool {
        guard let profile else { return false }
        return name != profile.display_name || defaultNode != (profile.default_entry_node_id ?? "") || locale != profile.locale
    }
    var body: some View {
        Form {
            if let profile {
                SettingsFeedback(error: error, success: success)
                Section(L("个人资料", "Profile")) {
                    HStack(spacing: 14) {
                        AvatarView(id: .account(profile), size: 64)
                            .environment(\.avatarDirectory, AvatarDirectory())
                        VStack(alignment: .leading, spacing: 3) {
                            Text(profile.display_name.isEmpty ? profile.username : profile.display_name)
                                .font(.headline)
                            Text("@" + profile.username)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                        Spacer(minLength: 8)
                        PhotosPicker(selection: $pickedPhoto, matching: .images) {
                            Text(profile.avatar_version != nil ? L("更换头像", "Change photo") : L("上传头像", "Upload photo"))
                                .font(.subheadline.weight(.semibold))
                        }
                        .buttonStyle(.bordered)
                        .disabled(busy || avatarBusy)
                    }
                    .padding(.vertical, 4)
                    if profile.avatar_version != nil {
                        Button(L("移除头像", "Remove photo"), role: .destructive) {
                            Task { await removeAvatar() }
                        }
                        .disabled(busy || avatarBusy)
                    }
                    LabeledContent(L("用户名", "Username"), value: profile.username)
                    VStack(alignment: .leading, spacing: 6) { Text(L("显示名称", "Display name")).font(.caption).foregroundStyle(NanoTheme.muted); TextField(L("显示名称", "Display name"), text: $name) }.padding(.vertical, 4)
                    DisclosureGroup(L("账号信息", "Account information")) {
                        LabeledContent(L("账号 ID", "Account ID"), value: profile.user_id).textSelection(.enabled)
                        LabeledContent(L("创建时间", "Created")) { NanoDateTime(value: profile.created_at) }
                    }
                }
                Section {
                    Picker(L("默认入口设备", "Default entry device"), selection: $defaultNode) {
                        Text(L("不指定", "None")).tag("")
                        ForEach(nodes.filter { profile.owned_node_ids.contains($0.node_id) }) { node in
                            Text(node.name + " · " + settingsStatus(node.status)).tag(node.node_id)
                        }
                        if let current = profile.default_entry_node_id, !nodes.contains(where: { $0.node_id == current }) {
                            Text(current).tag(current)
                        }
                    }
                    Picker(L("语言", "Language"), selection: $locale) {
                        Text("中文").tag(locale.hasPrefix("zh") ? locale : "zh")
                        Text("English").tag(locale.hasPrefix("en") ? locale : "en")
                    }
                } header: { Text(L("偏好", "Preferences")) } footer: {
                    Text(L("保存后，语言选择会同步到账号。", "Your language preference is saved to your account."))
                }
                if dirty { Section {
                    Button(L("放弃修改", "Discard changes")) { reset(profile); error = nil; success = nil }.disabled(busy)
                } }
            } else { SettingsLoading(retry: { Task { await load() } }, error: error) }
        }
        .navigationTitle(L("个人资料与语言", "Profile and language"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .nanoUnsavedChanges(dirty)
        .toolbar { ToolbarItem(placement: .confirmationAction) { Button(busy ? L("保存中…", "Saving…") : L("保存", "Save")) { Task { await save() } }.disabled(busy || avatarBusy || !dirty || name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) } }
        .onChange(of: pickedPhoto) { _, nextItem in
            guard let nextItem else { return }
            pickedPhoto = nil
            Task { await loadPickedPhoto(nextItem) }
        }
        .sheet(item: $cropCandidate) { candidate in
            AvatarCropSheet(
                image: candidate.image,
                saving: avatarBusy,
                onCancel: { if !avatarBusy { cropCandidate = nil } },
                onConfirm: { croppedData, mimeType in
                    Task { await uploadAvatar(croppedData, mimeType: mimeType) }
                }
            )
        }
        .task { await load() }
    }

    private func reset(_ value: SettingsAccount) {
        name = value.display_name
        defaultNode = value.default_entry_node_id ?? ""
        locale = value.locale
    }
    @MainActor private func loadPickedPhoto(_ item: PhotosPickerItem) async {
        error = nil; success = nil
        do {
            guard let rawData = try await item.loadTransferable(type: Data.self) else {
                error = AvatarImageProcessor.ValidationError.decodeFailed.localizedDescription
                return
            }
            let working = try AvatarImageProcessor.prepareWorkingImage(from: rawData)
            cropCandidate = IdentifiableCropImage(image: working)
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription ?? settingsError(error)
        }
    }
    @MainActor private func uploadAvatar(_ data: Data, mimeType: String) async {
        guard !avatarBusy else { return }
        avatarBusy = true; error = nil; success = nil
        defer { avatarBusy = false }
        do {
            let updated = try await client.uploadSettingsAvatar(data, mimeType: mimeType)
            try Task.checkCancellation()
            // Update only saved profile snapshot without touching unsaved form drafts!
            let uid = updated.user_id.isEmpty ? updated.id : updated.user_id
            avatarImages?.evict(userID: uid, keepingVersion: updated.avatar_version)
            profile = updated
            cropCandidate = nil
            success = L("个人头像已更新", "Profile photo updated")
            onAccountUpdated()
        } catch is CancellationError {} catch {
            cropCandidate = nil
            self.error = settingsError(error)
        }
    }
    @MainActor private func removeAvatar() async {
        guard !avatarBusy else { return }
        avatarBusy = true; error = nil; success = nil
        defer { avatarBusy = false }
        do {
            let updated = try await client.deleteSettingsAvatar()
            try Task.checkCancellation()
            let uid = updated.user_id.isEmpty ? updated.id : updated.user_id
            avatarImages?.evict(userID: uid, keepingVersion: nil)
            profile = updated
            success = L("已移除自定义头像", "Removed custom photo")
            onAccountUpdated()
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
    @MainActor private func load() async {
        error = nil
        do {
            async let account = client.settingsAccount()
            async let available = client.settingsNodes()
            let (loaded, list) = try await (account, available)
            try Task.checkCancellation()
            profile = loaded; nodes = list; reset(loaded)
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
    @MainActor private func save() async {
        busy = true; error = nil; success = nil
        defer { busy = false }
        do {
            let updated = try await client.saveSettingsAccount(SettingsAccountUpdate(
                display_name: name.trimmingCharacters(in: .whitespacesAndNewlines),
                default_entry_node_id: defaultNode.isEmpty ? nil : defaultNode, locale: locale))
            try Task.checkCancellation()
            profile = updated; reset(updated)
            UserDefaults.standard.set(updated.locale, forKey: "nano.locale")
            success = L("已保存", "Saved")
            onAccountUpdated()
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
}

struct SettingsHelpView: View {
    @AppStorage("nano.foregroundReminders") private var reminders = true
    var body: some View {
        Form {
            Section(L("版本", "Version")) {
                LabeledContent("Crewden", value: (Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "") + " (" + (Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "") + ")")
                if let revision = Bundle.main.object(forInfoDictionaryKey: "NanoIMBuildRevision") as? String { LabeledContent(L("代码版本", "Source revision"), value: revision).font(.caption).textSelection(.enabled) }
            }
            Section {
                Toggle(L("前台新消息提醒", "Foreground message reminders"), isOn: $reminders)
            } header: { Text(L("消息提醒", "Message reminders")) } footer: {
                Text(L("App 打开时，提示其他未静音聊天的新消息，不显示正文。后台或锁屏时暂不提供系统推送；重新打开后会同步消息。", "While the app is active, show reminders for new messages in other unmuted chats without message text. Chat works with reminders off. This version does not guarantee system notifications in the background, on the lock screen or after termination. Messages catch up when you return."))
            }
            Section(L("免费安装", "Free installation")) {
                Text(L("通过 AltStore 安装和管理 Crewden。首次安装时，在 Mac 上运行 AltServer，并用 USB 连接手机完成配对。Apple 账号和验证码请只在系统或 AltStore 中输入。", "Install and manage Crewden with AltStore. For first installation, run AltServer on your Mac and pair your iPhone over USB. Enter Apple credentials only in the system or AltStore."))
                Text(L("首次安装：USB 连接并信任 iPhone，在 Mini 的 AltServer 菜单选择 Install AltStore。按系统提示启用开发者模式，然后在 AltStore 的 My Apps 使用 + 选择本次构建的 IPA。", "First installation: connect and trust your iPhone over USB, then choose Install AltStore from Mini’s AltServer menu. Enable Developer Mode when prompted, then use + in AltStore → My Apps to select the built IPA."))
                Text(L("免费签名通常有效 7 天。请在 AltStore 的 My Apps 查看 Crewden 的实际到期时间和刷新结果。", "Free signing typically lasts 7 days. Check Crewden’s actual expiration and refresh result in AltStore → My Apps."))
            }
            Section(L("同一 Wi-Fi 下续签", "Refresh on the same Wi-Fi")) {
                Label(L("让 Mini 与 iPhone 连到同一局域网，并保持 AltServer 运行。", "Connect Mini and iPhone to the same local network and keep AltServer running."), systemImage: "1.circle")
                Label(L("先完成 USB 配对并开启 Wi-Fi 同步；在 AltStore 的 My Apps 手动刷新 Crewden。", "Pair over USB first and enable Wi-Fi sync. Refresh Crewden in AltStore → My Apps."), systemImage: "2.circle")
                Label(L("在 AltStore 检查新的到期时间，再打开 Crewden。自动刷新依赖系统调度，不保证每次成功。", "Check the new expiration in AltStore, then open Crewden. Automatic refresh depends on system scheduling and may not succeed every time."), systemImage: "3.circle")
            }
            Section(L("失败与过期恢复", "Failure and expiration recovery")) {
                Text(L("找不到 AltServer：检查同网连接、Mini 是否唤醒及 AltServer 是否运行；必要时重新通过 USB 连接并确认设备信任。账号或签名错误按 AltStore 提示在系统界面处理。", "If AltServer cannot be found, check the network, ensure Mini is awake and AltServer is running. Reconnect over USB and confirm device trust if needed. Resolve account or signing errors through the AltStore and system prompts."))
                Text(L("如果 Crewden 已无法打开，若 AltStore 也已过期，USB 连接后从 AltServer 菜单重新安装 AltStore，再以同一 Apple 账号和 App 标识重新签名安装。不要先删除 App；服务端历史仍保留，重新登录后可继续访问有权限的聊天。续签不需要删除聊天数据或重启 Mini 的 IM/Gateway。", "If Crewden can no longer open, if AltStore is also expired, reconnect over USB and reinstall AltStore from AltServer’s menu, then re-sign the app with the same Apple account and app identity. Do not delete the app first. Server history is retained and authorized chats remain accessible after signing in. Refreshing does not require deleting chat data or restarting Mini’s IM/Gateway."))
                Link(L("AltStore 官方帮助", "Official AltStore help"), destination: URL(string: "https://faq.altstore.io/altstore-classic/your-altstore")!)
            }
        }
        .navigationTitle(L("提醒与安装", "Reminders and installation"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
    }
}

private struct IdentifiableCropImage: Identifiable {
    let id = UUID()
    let image: UIImage
}

enum AvatarImageProcessor {
    static let maxUploadBytes = 5 * 1024 * 1024
    static let maxWorkingDimension = 2048

    enum ValidationError: LocalizedError, Equatable {
        case empty
        case tooLarge
        case unsupported
        case decodeFailed

        var errorDescription: String? {
            switch self {
            case .empty:
                L("所选图片文件为空。", "The selected image file is empty.")
            case .tooLarge:
                L("仅支持 5 MB 以内的静态图片，当前已生效头像保持不变。", "Only static images up to 5 MB are supported. Your current photo was kept.")
            case .unsupported:
                L("仅支持单帧静态照片（不支持 GIF 动图），当前已生效头像保持不变。", "Only single-frame static photos are supported (animated GIFs are not allowed).")
            case .decodeFailed:
                L("图片无法解码，请选择其他静态图片。", "Could not decode this image. Please choose another static photo.")
            }
        }
    }

    static func prepareWorkingImage(from data: Data) throws -> UIImage {
        guard !data.isEmpty else { throw ValidationError.empty }
        guard data.count <= maxUploadBytes else { throw ValidationError.tooLarge }
        if data.count >= 6 {
            let magic = String(decoding: data.prefix(6), as: UTF8.self)
            if magic == "GIF87a" || magic == "GIF89a" {
                throw ValidationError.unsupported
            }
        }
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else {
            throw ValidationError.decodeFailed
        }
        guard CGImageSourceGetCount(source) == 1 else {
            throw ValidationError.unsupported
        }
        if let typeIdentifier = CGImageSourceGetType(source) as String?,
           let utType = UTType(typeIdentifier),
           utType.conforms(to: .gif) || utType.conforms(to: .svg) {
            throw ValidationError.unsupported
        }
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceShouldCacheImmediately: true,
            kCGImageSourceThumbnailMaxPixelSize: maxWorkingDimension,
        ]
        guard let cgImage = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else {
            throw ValidationError.decodeFailed
        }
        return UIImage(cgImage: cgImage)
    }

    static func clampPan(_ pan: CGSize, imageSize: CGSize, zoom: CGFloat, ringDiameter: CGFloat) -> CGSize {
        guard imageSize.width > 0, imageSize.height > 0 else { return .zero }
        let scale = max(ringDiameter / imageSize.width, ringDiameter / imageSize.height) * zoom
        let maxX = max(0, (imageSize.width * scale - ringDiameter) / 2)
        let maxY = max(0, (imageSize.height * scale - ringDiameter) / 2)
        return CGSize(
            width: min(maxX, max(-maxX, pan.width)),
            height: min(maxY, max(-maxY, pan.height))
        )
    }

    static func exportCroppedAvatar(
        source: UIImage,
        zoom: CGFloat,
        pan: CGSize,
        ringDiameter: CGFloat = 240,
        outputSide: CGFloat = 512
    ) throws -> (Data, String) {
        let clamped = clampPan(pan, imageSize: source.size, zoom: zoom, ringDiameter: ringDiameter)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        let renderer = UIGraphicsImageRenderer(size: CGSize(width: outputSide, height: outputSide), format: format)
        let rendered = renderer.image { _ in
            let scale = max(outputSide / max(1, source.size.width), outputSide / max(1, source.size.height)) * zoom
            let drawW = source.size.width * scale
            let drawH = source.size.height * scale
            let ratio = outputSide / ringDiameter
            let drawX = (outputSide - drawW) / 2 + clamped.width * ratio
            let drawY = (outputSide - drawH) / 2 + clamped.height * ratio
            source.draw(in: CGRect(x: drawX, y: drawY, width: drawW, height: drawH))
        }
        if let png = rendered.pngData(), png.count <= maxUploadBytes {
            return (png, "image/png")
        }
        if let jpeg = rendered.jpegData(compressionQuality: 0.9), jpeg.count <= maxUploadBytes {
            return (jpeg, "image/jpeg")
        }
        throw ValidationError.tooLarge
    }
}

private struct AvatarCropSheet: View {
    let image: UIImage
    let saving: Bool
    let onCancel: () -> Void
    let onConfirm: (Data, String) -> Void

    @State private var zoom: CGFloat = 1.15
    @State private var committedPan: CGSize = .zero
    @State private var dragDelta: CGSize = .zero

    private let stageSize: CGFloat = 280
    private let ringDiameter: CGFloat = 240

    private var effectivePan: CGSize {
        AvatarImageProcessor.clampPan(
            CGSize(width: committedPan.width + dragDelta.width, height: committedPan.height + dragDelta.height),
            imageSize: image.size,
            zoom: zoom,
            ringDiameter: ringDiameter
        )
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Spacer(minLength: 8)
                ZStack {
                    Color(red: 0.11, green: 0.09, blue: 0.15)
                    let scale = max(ringDiameter / max(1, image.size.width), ringDiameter / max(1, image.size.height)) * zoom
                    Image(uiImage: image)
                        .resizable()
                        .frame(width: image.size.width * scale, height: image.size.height * scale)
                        .offset(effectivePan)
                    AvatarCircularCutoutOverlay(ringDiameter: ringDiameter)
                        .allowsHitTesting(false)
                }
                .frame(width: stageSize, height: stageSize)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .contentShape(Rectangle())
                .gesture(
                    DragGesture()
                        .onChanged { value in
                            guard !saving else { return }
                            dragDelta = value.translation
                        }
                        .onEnded { value in
                            committedPan = AvatarImageProcessor.clampPan(
                                CGSize(width: committedPan.width + value.translation.width, height: committedPan.height + value.translation.height),
                                imageSize: image.size,
                                zoom: zoom,
                                ringDiameter: ringDiameter
                            )
                            dragDelta = .zero
                        }
                )

                HStack(spacing: 12) {
                    Image(systemName: "minus")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                    Slider(value: Binding(
                        get: { zoom },
                        set: { next in
                            zoom = next
                            committedPan = AvatarImageProcessor.clampPan(committedPan, imageSize: image.size, zoom: next, ringDiameter: ringDiameter)
                        }
                    ), in: 1.0...2.8)
                    .disabled(saving)
                    Image(systemName: "plus")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: stageSize)

                Spacer()
            }
            .padding(.horizontal, 24)
            .background(NanoTheme.canvas)
            .navigationTitle(L("调整头像", "Adjust avatar"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(L("取消", "Cancel")) { onCancel() }
                        .disabled(saving)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(saving ? L("保存中…", "Saving…") : L("保存", "Save")) {
                        if let (data, mime) = try? AvatarImageProcessor.exportCroppedAvatar(
                            source: image,
                            zoom: zoom,
                            pan: effectivePan,
                            ringDiameter: ringDiameter
                        ) {
                            onConfirm(data, mime)
                        }
                    }
                    .fontWeight(.semibold)
                    .disabled(saving)
                }
            }
        }
        .interactiveDismissDisabled(saving)
    }
}

private struct AvatarCircularCutoutOverlay: View {
    let ringDiameter: CGFloat

    var body: some View {
        Canvas { ctx, size in
            var full = Path(CGRect(origin: .zero, size: size))
            let rect = CGRect(
                x: (size.width - ringDiameter) / 2,
                y: (size.height - ringDiameter) / 2,
                width: ringDiameter,
                height: ringDiameter
            )
            full.addEllipse(in: rect)
            ctx.fill(full, with: .color(.black.opacity(0.55)), style: FillStyle(eoFill: true))
            ctx.stroke(Path(ellipseIn: rect), with: .color(.white.opacity(0.9)), lineWidth: 1.5)
        }
    }
}
