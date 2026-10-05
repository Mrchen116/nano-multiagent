import SwiftUI

struct SettingsBindingView: View {
    let client: IMClient
    let user: AuthUser
    let onAccountUpdated: @MainActor () -> Void
    @Environment(\.scenePhase) private var scenePhase
    @State private var link = ""
    @State private var token = ""
    @State private var binding: SettingsBinding?
    @State private var error: String?
    @State private var busy = false
    @State private var cancelled = false
    @State private var visible = false
    @State private var confirmDecline = false
    @State private var acceptanceUncertain = false
    private var waiting: Bool { binding?.state == "awaiting_local_confirmation" }
    private var committed: Bool { binding?.state == "committed" }

    var body: some View {
        Form {
            Section {
                LabeledContent(L("接收账号", "Receiving account"), value: user.display_name)
                Text("@" + user.username).foregroundStyle(.secondary)
            } footer: {
                Text(L("确认账号无误后再接受。若要切换账号，请返回“我的”退出登录。", "Check the receiving account before accepting. To use another account, return to Me and sign out."))
            }
            if binding == nil && !cancelled {
                Section {
                    SecureField(L("粘贴完整绑定链接", "Paste the full binding link"), text: $link)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                        .privacySensitive()
                    Button(busy ? L("检查中…", "Checking…") : L("检查设备", "Inspect device")) { Task { await inspectLink() } }
                        .disabled(busy || link.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                } footer: { Text(L("在设备上发起绑定后，主动粘贴它提供的链接。链接只在本次页面内存中使用，不要发到聊天。", "Start binding on the device, then paste its link here. The link stays only in this page’s memory; do not send it in chat.")) }
            }
            SettingsFeedback(error: error)
            if let binding {
                Section(L("确认设备", "Confirm device")) {
                    LabeledContent(L("设备", "Device"), value: binding.node_name)
                    LabeledContent(L("设备 ID", "Device ID"), value: binding.node_id).textSelection(.enabled)
                    if binding.agents.isEmpty { Text(L("尚无 Agent", "No agents")) }
                    ForEach(binding.agents, id: \.self) { Text($0).font(.body.monospaced()) }
                }
                Section {
                    if committed {
                        Label(L("设备绑定已完成", "Device binding completed"), systemImage: "checkmark.circle.fill").foregroundStyle(.green)
                    } else if waiting {
                        Label(L("已接受，等待设备端确认", "Accepted, waiting for device confirmation"), systemImage: "clock")
                        Text(L("请回到发起绑定的设备完成确认。此步骤完成前，设备尚未转交给当前账号。", "Complete confirmation on the device where binding started. Ownership has not transferred yet."))
                    } else if binding.state == "awaiting_account" {
                        Button(busy ? L("提交中…", "Submitting…") : L("接受绑定", "Accept binding")) { Task { await accept() } }.disabled(busy || acceptanceUncertain)
                    } else { Text(L("当前绑定状态：", "Current binding state: ") + binding.state) }
                    if !committed {
                        Button(L("刷新状态", "Refresh status")) { Task { await inspectToken() } }.disabled(busy)
                        Button(L("拒绝绑定", "Decline binding"), role: .destructive) { confirmDecline = true }.disabled(busy)
                    }
                }
            }
            if cancelled { Section { Label(L("已拒绝绑定，设备归属未改变。", "Binding declined. Device ownership is unchanged."), systemImage: "xmark.circle") } }
            if cancelled || committed {
                Button(L("绑定另一台设备", "Bind another device")) { clearFlow() }
            }
        }
        .navigationTitle(L("绑定设备", "Bind a device"))
        .navigationBarTitleDisplayMode(.inline).toolbar(.hidden, for: .tabBar)
        .onAppear { visible = true }
        .onDisappear { visible = false; link = ""; token = ""; binding = nil }
        .task(id: waiting && visible && scenePhase == .active) {
            guard waiting && visible && scenePhase == .active else { return }
            repeat {
                do { try await Task.sleep(for: .seconds(2)) } catch { return }
                await inspectToken()
            } while waiting && !Task.isCancelled && error == nil
        }
        .confirmationDialog(L("拒绝这次设备绑定？", "Decline this device binding?"), isPresented: $confirmDecline, titleVisibility: .visible) {
            Button(L("拒绝绑定", "Decline binding"), role: .destructive) { Task { await decline() } }
            Button(L("取消", "Cancel"), role: .cancel) {}
        }
    }
    private func clearFlow() { link = ""; token = ""; binding = nil; cancelled = false; error = nil; acceptanceUncertain = false }
    @MainActor private func inspectLink() async {
        error = nil
        do {
            token = try SettingsBindingLink.token(from: link, server: await client.serverURL())
            link = ""
            await inspectToken()
        } catch {
            // Never expose parser input or token-bearing URLs in errors.
            self.error = L("请输入当前 IM 服务提供的完整绑定链接（/bind/confirm#token=…）。", "Enter the complete binding link from this IM service (/bind/confirm#token=…).")
        }
    }
    @MainActor private func inspectToken() async {
        guard !token.isEmpty, !busy else { return }
        busy = true; error = nil
        defer { busy = false }
        do {
            let result = try await client.inspectSettingsBinding(token: token)
            try Task.checkCancellation()
            guard visible, !token.isEmpty else { return }
            binding = result; acceptanceUncertain = false
            if result.state == "committed" { token = ""; onAccountUpdated() }
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
    @MainActor private func accept() async {
        guard !token.isEmpty, !busy else { return }
        busy = true; error = nil
        defer { busy = false }
        do {
            let result = try await client.acceptSettingsBinding(token: token)
            guard visible, !token.isEmpty else { return }
            binding = result; acceptanceUncertain = false
            if result.state == "committed" { token = ""; onAccountUpdated() }
        } catch is CancellationError {} catch {
            acceptanceUncertain = true
            self.error = L("接受结果尚未确认。请刷新状态后再决定下一步。", "Acceptance is not confirmed. Refresh the status before taking another action.") + " " + settingsError(error)
        }
    }
    @MainActor private func decline() async {
        guard !token.isEmpty, !busy else { return }
        busy = true; error = nil
        defer { busy = false }
        do {
            let result = try await client.declineSettingsBinding(token: token)
            guard visible else { return }
            if result.state == "cancelled" { clearFlow(); cancelled = true }
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
}
