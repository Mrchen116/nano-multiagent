import SwiftUI

struct SettingsCompanyView: View {
    let client: IMClient
    let user: AuthUser
    let onAccountUpdated: @MainActor () -> Void
    @State private var members: [SettingsMember] = []
    @State private var cursor: String?
    @State private var loaded = false
    @State private var loading = false
    @State private var changing = false
    @State private var error: String?
    @State private var feedback: String?
    @State private var suspendTarget: SettingsMember?

    var body: some View {
        List {
            if !user.is_company_admin {
                ContentUnavailableView(L("仅公司管理员可管理成员", "Administrator access required"), systemImage: "person.crop.circle.badge.exclamationmark", description: Text(L("普通成员不能查看准入列表、批准或停用他人。", "Members cannot view admission records, approve or suspend other accounts.")))
            } else {
                SettingsFeedback(error: error, success: feedback)
                Section {
                    Text(L("批准后成员可使用公司功能。停用将立即撤销其客户端与名下设备接入，保留历史和配置。", "Approval grants company access. Suspension immediately revokes the member’s clients and devices while retaining history and settings.")).font(.footnote).foregroundStyle(.secondary)
                }
                if !loaded && loading { ProgressView(L("加载成员…", "Loading members…")) }
                if loaded && members.isEmpty { Text(L("没有成员", "No members")) }
                ForEach(members) { member in
                    Section {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(member.name + (member.id == user.id ? L("（你）", " (you)") : "")).font(.headline)
                            Text("@" + member.username).foregroundStyle(.secondary)
                            HStack {
                                Text(member.is_company_admin ? L("管理员", "Administrator") : L("成员", "Member"))
                                Text("·")
                                Text(settingsStatus(member.membership_status))
                            }.font(.subheadline)
                            Text(L("\(member.node_count) 台设备 · \(member.agent_count) 个 Agent", "\(member.node_count) devices · \(member.agent_count) agents")).font(.caption).foregroundStyle(.secondary)
                        }
                        if member.membership_status == "pending" {
                            Button(L("批准加入", "Approve membership")) { Task { await change(member, approve: true) } }.disabled(changing)
                        }
                        if member.membership_status == "active" {
                            Button(L("停用成员", "Suspend member"), role: .destructive) { error = nil; suspendTarget = member }.disabled(changing)
                        }
                    }
                }
                Section {
                    if cursor != nil { Button(L("加载更多", "Load more")) { Task { await load(more: true) } }.disabled(loading || changing) }
                    Button(loading ? L("刷新中…", "Refreshing…") : L("刷新成员", "Refresh members")) { Task { await load() } }.disabled(loading || changing)
                }
            }
        }
        .navigationTitle(L("公司成员", "Company members"))
        .toolbar(.hidden, for: .tabBar)
        .task { if user.is_company_admin { await load() } }
        .refreshable { if user.is_company_admin { await load() } }
        .confirmationDialog(L("停用成员？", "Suspend member?"), isPresented: Binding(get: { suspendTarget != nil }, set: { if !$0 { suspendTarget = nil } }), titleVisibility: .visible, presenting: suspendTarget) { target in
            Button(L("确认停用", "Confirm suspension"), role: .destructive) { Task { await change(target, approve: false) } }
            Button(L("取消", "Cancel"), role: .cancel) { suspendTarget = nil }
        } message: { target in
            Text(L("停用 \(target.name) 将撤销其登录与 \(target.node_count) 台设备、\(target.agent_count) 个 Agent 的接入。历史和配置会保留；设备不会关机或转交他人。", "Suspending \(target.name) revokes account access and access for \(target.node_count) devices and \(target.agent_count) agents. History and settings are retained. Devices are not shut down or transferred."))
        }
    }
    @MainActor private func load(more: Bool = false) async {
        guard user.is_company_admin, !loading else { return }
        loading = true; error = nil
        defer { loading = false }
        do {
            let result = try await client.settingsMembers(cursor: more ? (cursor ?? "") : "")
            try Task.checkCancellation()
            if more {
                let existing = Set(members.map(\.id))
                members += result.members.filter { !existing.contains($0.id) }
            } else { members = result.members }
            cursor = result.next_cursor; loaded = true
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
    @MainActor private func change(_ member: SettingsMember, approve: Bool) async {
        guard user.is_company_admin, !changing else { return }
        changing = true; error = nil; feedback = nil
        defer { changing = false }
        do {
            let updated = try await client.changeSettingsMember(member.id, approve: approve)
            try Task.checkCancellation()
            if let index = members.firstIndex(where: { $0.id == updated.id }) { members[index].membership_status = updated.membership_status }
            suspendTarget = nil
            feedback = approve ? L("已批准 \(member.name) 加入公司。", "Approved \(member.name)’s membership.") : L("已停用 \(member.name)。", "Suspended \(member.name).")
            if member.id == user.id { onAccountUpdated() }
        } catch is CancellationError {} catch { self.error = settingsError(error) }
    }
}
