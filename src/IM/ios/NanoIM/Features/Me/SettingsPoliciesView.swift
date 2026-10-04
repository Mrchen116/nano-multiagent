import SwiftUI

struct SettingsPoliciesView: View {
    let client: IMClient
    let isAdmin: Bool
    @State private var saved: SettingsPolicy?
    @State private var draft: SettingsPolicy?
    @State private var capacity: SettingsCapacity?
    @State private var error: String?
    @State private var capacityError: String?
    @State private var success: String?
    @State private var saving = false
    @State private var capacityLoading = false

    var body: some View {
        Form {
            if let draft {
                SettingsFeedback(error: error, success: success)
                if !isAdmin { Section { Label(L("仅管理员可修改，当前为只读。", "Only administrators can edit. These settings are read-only."), systemImage: "lock") } }
                Section(L("模型与审计", "Model and audit")) {
                    TextField(L("默认模型", "Default model"), text: field(\.default_model)).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Picker(L("审计级别", "Audit level"), selection: field(\.audit_level)) {
                        Text(L("关闭", "Off")).tag("off")
                        Text(L("基本", "Basic")).tag("basic")
                        Text(L("严格", "Strict")).tag("strict")
                    }
                }.disabled(!isAdmin || saving)
                Section {
                    integerField(L("每轮最大步数", "Maximum turns per run"), keyPath: \.max_turn_per_run)
                    integerField(L("每分钟请求限制", "Requests per minute"), keyPath: \.rate_limit_per_min)
                    integerField(L("单附件大小上限（MB）", "Attachment size limit (MB)"), keyPath: \.max_attachment_size_mb)
                    integerField(L("保留天数", "Retention days"), keyPath: \.retention_days)
                } header: { Text(L("运行与存储限制", "Runtime and storage limits")) } footer: { Text(L("所有数值必须为大于零的整数。", "All numeric values must be positive integers.")) }
                    .disabled(!isAdmin || saving)
                if isAdmin {
                    Section {
                        Button(saving ? L("保存中…", "Saving…") : L("保存策略", "Save policies")) { Task { await save() } }
                            .disabled(saving || draft == saved || !draft.valid)
                        Button(L("放弃修改", "Discard changes")) { self.draft = saved; error = nil; success = nil }.disabled(saving || draft == saved)
                    }
                }
            } else { SettingsLoading(retry: { Task { await load() } }, error: error) }
            if isAdmin {
                Section {
                    if let capacityError { ErrorNotice(message: capacityError) }
                    if capacityLoading && capacity == nil { ProgressView(L("加载容量…", "Loading capacity…")) }
                    if let capacity {
                        capacityRow(capacity.service, name: L("整个服务", "Entire service"))
                        ForEach(capacity.owners, id: \.owner_id) { usage in
                            capacityRow(usage, name: usage.display_name ?? usage.username ?? usage.owner_id ?? L("未知账号", "Unknown account"))
                        }
                    }
                    Button(L("刷新容量", "Refresh capacity")) { Task { await loadCapacity() } }.disabled(capacityLoading)
                } header: { Text(L("附件容量", "Attachment capacity")) } footer: {
                    Text(L("已用与预留均计入容量限制。预留代表进行中的上传。", "Stored and reserved bytes both count toward capacity. Reserved space represents uploads in progress."))
                }
            }
        }
        .navigationTitle(L("系统策略", "System policies"))
        .toolbar(.hidden, for: .tabBar)
        .task { await load() }
        .task { if isAdmin { await loadCapacity() } }
    }
    private func field<Value>(_ keyPath: WritableKeyPath<SettingsPolicy, Value>) -> Binding<Value> {
        Binding(get: { draft![keyPath: keyPath] }, set: { draft?[keyPath: keyPath] = $0; success = nil })
    }
    private func integerField(_ label: String, keyPath: WritableKeyPath<SettingsPolicy, Int>) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label).font(.subheadline)
            TextField(label, value: field(keyPath), format: .number.grouping(.never))
                .keyboardType(.numberPad).accessibilityLabel(label)
        }
    }
    private func capacityRow(_ value: SettingsCapacity.Usage, name: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(name).font(.headline)
            if let username = value.username { Text("@" + username).font(.caption).foregroundStyle(.secondary) }
            Text(L("已用 \(bytes(value.used_bytes)) · 预留 \(bytes(value.reserved_bytes))", "Used \(bytes(value.used_bytes)) · Reserved \(bytes(value.reserved_bytes))")).font(.subheadline)
            Text(L("上限 \(bytes(value.limit_bytes))", "Limit \(bytes(value.limit_bytes))")).font(.subheadline).foregroundStyle(.secondary)
            if value.full { Label(L("容量已满", "Capacity full"), systemImage: "exclamationmark.triangle").foregroundStyle(.orange) }
        }.padding(.vertical, 4)
    }
    private func bytes(_ count: Int64) -> String { String(format: "%.1f MiB", Double(count) / 1_048_576) }
    @MainActor private func load() async {
        error = nil
        do {
            let value = try await client.settingsPolicies()
            try Task.checkCancellation()
            saved = value; draft = value
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
    @MainActor private func loadCapacity() async {
        guard isAdmin, !capacityLoading else { return }
        capacityLoading = true; capacityError = nil
        defer { capacityLoading = false }
        do {
            let value = try await client.settingsCapacity()
            try Task.checkCancellation()
            capacity = value
        } catch is CancellationError {} catch {
            capacity = nil
            capacityError = settingsError(error)
        }
    }
    @MainActor private func save() async {
        guard isAdmin, let draft, draft.valid, !saving else { return }
        saving = true; error = nil; success = nil
        defer { saving = false }
        do {
            let value = try await client.saveSettingsPolicies(draft)
            try Task.checkCancellation()
            saved = value; self.draft = value; success = L("策略已保存", "Policies saved")
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
}
