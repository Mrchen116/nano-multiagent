import SwiftUI

private struct PluginCatalog: Decodable, Sendable {
    struct Entry: Decodable, Sendable, Identifiable {
        struct Row: Decodable, Sendable, Identifiable { let id: String; let name: JSONValue }
        let name: String, display_name: JSONValue, description: JSONValue, version: String?
        let enabled: Bool, state: String, removable: Bool, diagnostics: [String], rows: [Row]
        var id: String { name }
    }
    struct Pending: Decodable, Sendable { let phase, target: String }
    let workspace: String, entries: [Entry], pending: Pending?, error: String?
}

private typealias PluginRead = AgentSettingsRead<PluginCatalog>

struct AgentPluginsView: View {
    let client: IMClient
    let agentID: String
    var onChanged: (() async -> Void)? = nil
    @Environment(\.scenePhase) private var scenePhase
    @State private var read: PluginRead?
    @State private var error: String?
    @State private var removing: PluginCatalog.Entry?
    @State private var busy = false
    @State private var hadPending = false
    private var writable: Bool { !busy && error == nil && read?.source == "current" && read?.data?.pending == nil }
    var body: some View {
        List {
            if let error { Section { ErrorNotice(message: error); Button(L("重新读取", "Refresh")) { Task { await refresh() } } } }
            if read == nil && error == nil { ProgressView() }
            if let read { AgentSettingsNotice(read: read) }
            if let catalog = read?.data {
                if let pending = catalog.pending {
                    Label(pending.target + " · " + (pending.phase == "waiting" ? L("等待电脑空闲", "Waiting for computer") : L("应用中", "Applying")), systemImage: "clock")
                }
                if let error = catalog.error { ErrorNotice(message: error) }
                if catalog.entries.isEmpty { Text(L("此工作区尚无插件", "No plugins in this workspace")).foregroundStyle(.secondary) }
                ForEach(catalog.entries) { plugin in
                    Section {
                        Toggle(isOn: Binding(get: { plugin.enabled }, set: { enabled in Task { await manage(plugin, enabled: enabled) } })) {
                            Text(local(plugin.display_name)).font(.headline)
                            if let version = plugin.version { Text(version).font(.caption).foregroundStyle(.secondary) }
                        }.disabled(!writable)
                        Text(local(plugin.description)).font(.subheadline)
                        if plugin.state == "failed" { Label(L("加载失败", "Failed to load"), systemImage: "exclamationmark.triangle") }
                        DisclosureGroup(L("插件详情", "Plugin details")) {
                            Text(plugin.name).font(.footnote.monospaced()).textSelection(.enabled)
                            ForEach(plugin.rows) { row in Text(local(row.name)) }
                            ForEach(plugin.diagnostics, id: \.self) { Text($0).font(.callout).textSelection(.enabled) }
                            if plugin.removable {
                                Button(L("卸载插件", "Uninstall plugin"), role: .destructive) { removing = plugin }.disabled(!writable)
                            }
                        }
                    }
                }
                Section(L("工作目录", "Workspace")) { Text(catalog.workspace).font(.footnote.monospaced()).textSelection(.enabled) }
            }
        }.navigationTitle(L("插件", "Plugins")).navigationBarTitleDisplayMode(.inline)
        .confirmationDialog(removing.map { L("卸载", "Uninstall") + " " + local($0.display_name) + "?" } ?? "", isPresented: Binding(get: { removing != nil }, set: { if !$0 { removing = nil } }), titleVisibility: .visible, presenting: removing) { plugin in
            Button(L("确认卸载", "Confirm uninstall"), role: .destructive) { Task { await manage(plugin, enabled: nil) } }
        }
        .refreshable { await refresh() }
        .task(id: scenePhase) {
            guard scenePhase == .active else { return }
            repeat {
                await refresh()
                do { try await Task.sleep(for: .seconds(read?.data?.pending == nil ? 5 : 1)) } catch { return }
            } while !Task.isCancelled
        }
    }
    private func local(_ text: JSONValue) -> String {
        if let string = text.stringValue { return string }
        let values = text.objectValue ?? [:]
        return values[L("zh", "en")]?.stringValue ?? values[L("zh-CN", "en-US")]?.stringValue ?? values["en"]?.stringValue ?? values.sorted { $0.key < $1.key }.first?.value.stringValue ?? ""
    }
    private func refresh() async {
        guard !busy else { return }
        busy = true; defer { busy = false }
        do {
            let result: PluginRead = try await client.get(agentPath(agentID) + "/settings/sections/plugins")
            try Task.checkCancellation()
            read = result; error = nil
            if result.data?.pending != nil {
                hadPending = true
            } else if hadPending && result.source == "current" {
                hadPending = false
                await onChanged?()
            }
        } catch {
            guard !Task.isCancelled else { return }
            if let api = error as? APIError, [401, 403, 404].contains(api.status) { read = nil }
            self.error = agentError(error)
        }
    }
    private func manage(_ plugin: PluginCatalog.Entry, enabled: Bool?) async {
        guard writable else { return }
        busy = true
        var body: [String: JSONValue] = ["action": .string(enabled == nil ? "remove_bundle" : "set_bundle"), "target": .string(plugin.name)]
        if let enabled { body["enabled"] = .bool(enabled) }
        var failure: String?
        var appliedImmediately = false
        do {
            let result: PluginCatalog = try await client.send(agentPath(agentID) + "/plugins", body: body)
            if result.pending != nil { hadPending = true } else { appliedImmediately = true }
        }
        catch { failure = agentError(error) }
        busy = false; await refresh()
        if appliedImmediately { await onChanged?() }
        if let failure { error = failure }
    }
}
