import SwiftUI

private struct AgentRoleDocument: Decodable, Sendable {
    let content: String
    let version: String?
}

struct AgentRoleEditor: View {
    let client: IMClient
    let agentID: String
    let online: Bool
    @Binding var hasUnsavedChanges: Bool
    @Environment(\.scenePhase) private var scenePhase
    @State private var current: AgentRoleDocument?
    @State private var draft: AgentRoleDocument?
    @State private var loading = false
    @State private var saving = false
    @State private var confirmed = false
    @State private var denied = false
    @State private var reloadRevision = 0
    @State private var message: Message?

    private enum Message: Equatable { case saved, conflict, unconfirmed, tooLong }
    private struct ReadRequest: Equatable {
        let online: Bool
        let revision: Int
        let saving: Bool
    }

    private var path: String { agentPath(agentID) + "/role" }
    private var content: String { draft?.content ?? current?.content ?? "" }
    private var dirty: Bool { draft.map { $0.content != current?.content } ?? false }
    private var editable: Bool { online && confirmed && !loading && !saving }
    private var tooLong: Bool { content.utf16.count > 2000 }
    private var changed: Bool {
        guard let current, let draft else { return false }
        return dirty && current.version != draft.version
    }
    private var unset: String { L("尚未设置角色约定。Agent 会主动询问。", "No role agreement saved. The Agent will ask you to define one.") }
    private var status: String? {
        if tooLong || message == .tooLong { return L("最多使用 2,000 个 UTF-16 代码单元。", "Use at most 2,000 UTF-16 code units.") }
        if message == .saved { return L("角色约定已保存。", "Role agreement saved.") }
        if message == .unconfirmed { return L("保存结果未确认，草稿仍保留。", "The save could not be confirmed. Your draft is still here.") }
        if changed || message == .conflict {
            return L("编辑期间角色约定已更新。请核对当前约定，再决定是否保存草稿。", "The role changed while you were editing. Review the current agreement before saving your draft.")
        }
        return nil
    }

    var body: some View {
        let request = ReadRequest(online: online && scenePhase == .active, revision: reloadRevision, saving: saving)
        Section(L("角色约定", "Role agreement")) {
            Text(L("记录长期职责、目标和分工。后续 Agent 请求及 Dreaming 整理采用已保存的约定。", "Long-term responsibilities, goals, and who does what. Future Agent requests and Dreaming batches use the saved agreement."))
                .font(.caption).foregroundStyle(.secondary)
            if current != nil && !denied {
                if current?.content.isEmpty == true && !dirty { Text(unset).font(.caption).foregroundStyle(.secondary) }
                TextEditor(text: Binding(get: { content }, set: { edit($0) }))
                    .frame(minHeight: 120)
                    .accessibilityLabel(L("角色约定", "Role agreement"))
                    .accessibilityIdentifier("agent-role-content")
                    .disabled(!editable)
                Button(L("保存角色约定", "Save role agreement")) { Task { await save() } }
                    .disabled(!editable || !dirty || tooLong)
                    .accessibilityIdentifier("agent-role-save")
            }
            if loading || saving {
                ProgressView()
            } else if !online || !confirmed {
                Text(L("暂时无法读取当前角色约定。", "The current role agreement is unavailable.")).font(.caption).foregroundStyle(.secondary)
                if online && !denied {
                    Button(L("重试", "Retry")) { reloadRevision += 1 }
                }
            }
            if let status { Text(status).font(.caption).foregroundStyle(.secondary) }
            if let current, !denied && dirty && (!editable || changed || message == .conflict || message == .unconfirmed) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(editable ? L("当前已保存的约定", "Current saved agreement") : L("上次读取的约定", "Last read agreement"))
                        .font(.caption.weight(.semibold))
                    Text(current.content.isEmpty ? unset : current.content).font(.caption).textSelection(.enabled)
                }
            }
        }
        .task(id: request) {
            if !request.saving { await read(online: request.online) }
        }
        .onChange(of: dirty || saving) { _, value in hasUnsavedChanges = value }
    }

    private func edit(_ value: String) {
        guard let current, editable else { return }
        draft = value == current.content ? nil : AgentRoleDocument(content: value, version: draft.map { $0.version } ?? current.version)
        if value == current.content || message == .saved || message == .tooLong { message = nil }
    }

    private func read(online: Bool) async {
        confirmed = false
        loading = online
        guard online else { return }
        defer { if !Task.isCancelled { loading = false } }
        do {
            let document: AgentRoleDocument = try await client.get(path)
            try Task.checkCancellation()
            current = document
            denied = false
            confirmed = true
        } catch {
            if !Task.isCancelled, let failure = error as? APIError {
                denied = [401, 403, 404].contains(failure.status)
            }
        }
    }

    private func save() async {
        guard let current, editable, dirty, !tooLong else { return }
        let payload: [String: JSONValue] = ["content": .string(content), "version": current.version.map(JSONValue.string) ?? .null]
        saving = true
        message = nil
        defer { saving = false }
        do {
            self.current = try await client.send(path, method: "PUT", body: payload)
            draft = nil
            message = .saved
        } catch {
            let code = (error as? APIError)?.code
            if code == "role_too_long" { message = .tooLong; return }
            message = code == "role_conflict" ? .conflict : .unconfirmed
            confirmed = false
            reloadRevision += 1
        }
    }
}
