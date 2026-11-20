import SwiftUI

struct ComputerUpdate: Codable, Sendable, Equatable {
    struct Current: Codable, Sendable, Equatable { let version: String }
    struct Target: Codable, Sendable, Equatable { let version, sha256: String; let release_notes: String? }
    struct Operation: Codable, Sendable, Equatable {
        let id, state: String
        let cancel_requested, relay_gated: Bool
        var cancellable: Bool { ["requested", "downloading", "installing", "waiting"].contains(state) }
        var switching: Bool { ["switching", "verifying", "rolling_back"].contains(state) }
        var active: Bool { cancellable || switching }
    }
    let installation, reason, install_command: String
    let current: Current?, target: Target?, available: Bool, operation: Operation?

    var status: String {
        guard let op = operation else { return reason }
        if op.active { return op.state }
        if op.relay_gated { return "recovery_required" }
        if reason == "available" && op.state != "succeeded" { return op.state }
        return reason == "current" && op.state == "succeeded" ? op.state : reason
    }
    var canStart: Bool { available && target != nil && operation?.active != true && status != "recovery_required" }
    var canCancel: Bool { operation?.cancellable == true && operation?.cancel_requested == false }
}

struct ComputerUpdateSection: View {
    let client: IMClient, nodeID: String, update: ComputerUpdate
    let canManage: Bool
    let refresh: () async -> Void
    @State private var requestID: String?
    @State private var targetHash: String?
    @State private var working = false
    @State private var error: String?

    var body: some View {
        Section(L("电脑端更新", "Computer updates")) {
            LabeledContent(L("更新状态", "Update status"), value: label(update.status))
            if let target = update.target {
                LabeledContent(L("发行版本", "Release version"), value: target.version)
                if let notes = target.release_notes, !notes.isEmpty { Text(notes).font(.callout) }
            }
            if let error { ErrorNotice(message: error) }
            if update.operation?.cancellable == true {
                Button(update.operation?.cancel_requested == true ? L("正在取消", "Cancelling") : L("取消更新", "Cancel update")) { Task { await submit(cancel: true) } }
                    .disabled(!canManage || !update.canCancel || working)
            } else if update.canStart {
                Button(L("更新电脑端", "Update computer")) { Task { await submit(cancel: false) } }.disabled(!canManage || working)
            }
            if !update.install_command.isEmpty {
                NavigationLink(L("安装与恢复说明", "Installation and recovery")) { ComputerInstallView(client: client, recoveryCommand: update.install_command) }
            }
        }
    }
    private func label(_ value: String) -> String {
        switch value {
        case "requested": L("已请求", "Requested")
        case "downloading": L("正在下载", "Downloading")
        case "installing": L("正在安装", "Installing")
        case "waiting": L("等待电脑空闲", "Waiting for computer to become idle")
        case "switching": L("正在切换版本", "Switching versions")
        case "verifying": L("正在验证", "Verifying")
        case "rolling_back": L("正在回退", "Rolling back")
        case "rolled_back": L("已回退", "Rolled back")
        case "recovery_required": L("需要在电脑上恢复", "Recovery needed on computer")
        case "legacy": L("需要在电脑上升级", "Upgrade on computer")
        case "incompatible": L("当前设备不兼容", "Incompatible")
        case "offline": L("电脑离线", "Computer offline")
        case "source": L("源码安装", "Source installation")
        case "unpublished": L("暂无发行版本", "No release published")
        case "available": L("有更新", "Update available")
        case "current": L("已经是最新版", "Up to date")
        case "succeeded": L("已更新", "Updated")
        case "cancelled": L("已取消", "Cancelled")
        case "interrupted": L("更新中断", "Interrupted")
        case "failed": L("更新失败", "Update failed")
        default: value
        }
    }
    private func submit(cancel: Bool) async {
        guard !working, canManage else { return }
        working = true; defer { working = false }
        error = nil
        let path = "/im/v1/nodes/" + agentSegment(nodeID) + "/update"
        do {
            if cancel, let op = update.operation, update.canCancel {
                let _: EmptyResponse = try await client.send(path + "/cancel", body: ["operation_id": op.id])
            } else if !cancel, let target = update.target, update.canStart {
                if targetHash != target.sha256 || requestID == nil { requestID = UUID().uuidString; targetHash = target.sha256 }
                let _: EmptyResponse = try await client.send(path, body: ["request_id": requestID!, "version": target.version, "sha256": target.sha256])
                requestID = nil
            }
        } catch { self.error = settingsError(error) }
        await refresh()
    }
}

struct ComputerInstallView: View {
    let client: IMClient
    var recoveryCommand: String? = nil
    @State private var command = ""
    @State private var loaded = false
    @State private var error: String?
    @State private var copied = false
    @State private var manual = false
    private var content: String {
        if manual { return command }
        let instruction = recoveryCommand == nil
        ? L("请在这台电脑安装 Crewden，运行下面的安装命令，然后把设备绑定链接发给我。", "Install Crewden on this computer with the command below and give me the device binding link.")
        : L("请在这台电脑运行以下 Crewden 安装命令，保留现有配置，确认设备重新在线。", "Run the Crewden installation command below on this computer, preserve its configuration, and verify it reconnects.")
        return instruction + "\n\n" + command
    }
    var body: some View {
        Form {
            if let error { ErrorNotice(message: error); Button(L("重试", "Retry")) { Task { await load() } } }
            if !loaded && error == nil { ProgressView() }
            else if loaded && command.isEmpty { Text(L("当前服务暂无安装包。", "This service has no installer available.")) }
            if !command.isEmpty {
                Section {
                    Picker(L("安装方式", "Install method"), selection: $manual) {
                        Text(L("交给电脑上的助手", "Ask an assistant")).tag(false)
                        Text(L("在终端执行", "Use Terminal")).tag(true)
                    }.pickerStyle(.segmented)
                    Text(content).font(.system(.callout, design: .monospaced)).textSelection(.enabled)
                    Button { UIPasteboard.general.string = content; copied = true } label: {
                        Label(copied ? L("已复制", "Copied") : L("复制到电脑", "Copy instructions"), systemImage: copied ? "checkmark" : "doc.on.doc")
                    }
                } footer: {
                    Text(recoveryCommand == nil ? L("在要连接的电脑上完成安装，再用绑定链接确认。", "Finish installation on the computer and confirm its binding link.") : L("完成后返回设备详情查看实际上报的版本。", "Return to the computer details to see the reported version."))
                }
            }
        }.navigationTitle(L("连接电脑", "Connect computer")).navigationBarTitleDisplayMode(.inline)
        .task { await load() }.onChange(of: manual) { _, _ in copied = false }
    }
    private func load() async {
        if let recoveryCommand { command = recoveryCommand; loaded = true; return }
        do {
            let state: AssistantOnboarding = try await client.get("/im/v1/onboarding")
            command = state.install.available ? state.install.command : ""; loaded = true; error = nil
        } catch { self.error = settingsError(error) }
    }
}
