import SwiftUI

/// Renders live, authoritative task-graph node cards embedded inside a chat message bubble.
struct TaskEmbeddedCardsView: View {
    let client: IMClient
    let chat: ChatStore
    let refs: [TaskCardRef]
    var readOnly = false

    @Environment(\.openURL) private var openURL
    @State private var summaries: [String: TaskCardNodeSummary] = [:]
    @State private var hasLoadedLive = false
    @State private var busyKeys: Set<String> = []
    @State private var actionError: String?
    @State private var inspectedRef: TaskCardRef?

    private var refIdentity: String {
        refs.map(\.cardKey).joined(separator: ",")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(refs) { ref in
                if let summary = summaries[ref.cardKey] {
                    cardRow(ref: ref, summary: summary)
                } else if hasLoadedLive {
                    unavailableRow
                } else {
                    offlinePlaceholderRow
                }
            }
            if let actionError {
                ErrorNotice(message: actionError)
            }
        }
        .padding(.top, 2)
        .task(id: "\(refIdentity)-\(chat.taskCardsRevision)") {
            await loadCards()
        }
        .onChange(of: chat.connection == .online) { _, isOnline in
            if isOnline {
                Task { await loadCards() }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .nanoTaskGraphChanged)) { note in
            guard (note.object as? IMClient) === client || note.object == nil else { return }
            Task { await loadCards() }
        }
        .sheet(item: $inspectedRef, onDismiss: { Task { await loadCards() } }) { target in
            NavigationStack {
                TaskDetailLoader(
                    client: client,
                    graphID: target.graph_id,
                    nodeID: target.node_id,
                    onReference: { chatID, text in
                        inspectedRef = nil
                        if !text.isEmpty {
                            chat.setDraft(chatID, [chat.drafts[chatID] ?? "", text].filter { !$0.isEmpty }.joined(separator: "\n\n"))
                        }
                        openURL(client.baseURL.appending(path: "chat").appending(component: chatID))
                    },
                    onOpenGraph: { graphID, scopeID in
                        inspectedRef = nil
                        var comps = URLComponents(url: client.baseURL.appending(path: "tasks").appending(component: graphID), resolvingAgainstBaseURL: false)
                        if let scopeID { comps?.queryItems = [.init(name: "scope", value: scopeID)] }
                        if let url = comps?.url { openURL(url) }
                    }
                )
            }
        }
    }

    private func cardRow(ref: TaskCardRef, summary: TaskCardNodeSummary) -> some View {
        let isBusy = busyKeys.contains(ref.cardKey)
        let isOnline = chat.connection == .online
        let canAct = !readOnly && isOnline && summary.can_edit != false && summary.conversation?.can_write != false
        let isSubnode = summary.node_id != summary.root_node_id
        let crumb: String = if isSubnode || summary.mode != "none", let rootTitle = summary.root_title, !rootTitle.isEmpty {
            L("所属目标：", "Goal: ") + rootTitle
        } else if let chatTitle = summary.conversation?.title, !chatTitle.isEmpty {
            L("单卡 · ", "Single · ") + chatTitle
        } else {
            L("任务卡片", "Task card")
        }

        return VStack(alignment: .leading, spacing: 7) {
            Button { inspectedRef = ref } label: {
                VStack(alignment: .leading, spacing: 5) {
                    HStack(spacing: 8) {
                        TaskCrumbPill(text: crumb, highlight: isSubnode || summary.mode != "none")
                        Spacer(minLength: 4)
                        TaskStatusBadge(status: summary.status)
                    }
                    Text(summary.title)
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(NanoTheme.ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if let rationale = summary.proposal?.rationale, !rationale.isEmpty {
                        Text(rationale)
                            .font(.caption)
                            .foregroundStyle(NanoTheme.muted)
                            .lineLimit(3)
                    } else if summary.status == "waiting", let reason = summary.wait?.reason, !reason.isEmpty {
                        Text(reason)
                            .font(.caption)
                            .foregroundStyle(Color(red: 0.60, green: 0.38, blue: 0.09))
                            .lineLimit(2)
                    } else if let desc = summary.description, !desc.isEmpty {
                        Text(desc)
                            .font(.caption)
                            .foregroundStyle(NanoTheme.muted)
                            .lineLimit(2)
                    }
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if summary.status == "proposed" {
                if canAct {
                    HStack(spacing: 8) {
                        Button {
                            Task { await approve(ref: ref, summary: summary) }
                        } label: {
                            Text(summary.isPrereqBlocked ? L("批准立项", "Approve to queue") : L("批准开工", "Approve & start"))
                                .font(.caption.weight(.bold))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 11)
                                .padding(.vertical, 5)
                                .background(NanoTheme.accent, in: Capsule())
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)

                        Button {
                            Task { await updateStatus(ref: ref, summary: summary, status: "backlog") }
                        } label: {
                            Text(L("先存着", "Stash"))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(NanoTheme.ink)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 5)
                                .background(NanoTheme.surface, in: Capsule())
                                .overlay { Capsule().stroke(NanoTheme.border, lineWidth: 1) }
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)

                        Button {
                            Task { await updateStatus(ref: ref, summary: summary, status: "closed") }
                        } label: {
                            Text(L("关闭", "Close"))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(NanoTheme.muted)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 5)
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)
                    }
                } else if !isOnline {
                    Text(L("离线只读 · 连接后可操作", "Offline read-only · Connect to update"))
                        .font(.caption2)
                        .foregroundStyle(NanoTheme.muted)
                }
            } else {
                HStack {
                    Text(statusHint(for: summary))
                        .font(.caption2)
                        .foregroundStyle(summary.status == "doing" ? Color(red: 0.14, green: 0.42, blue: 0.27) : NanoTheme.muted)
                    Spacer()
                    Button { inspectedRef = ref } label: {
                        Text(L("查看任务 ›", "Open task ›"))
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(NanoTheme.accent)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 10))
        .overlay {
            RoundedRectangle(cornerRadius: 10)
                .stroke(summary.status == "proposed" ? Color(red: 0.87, green: 0.66, blue: 0.16).opacity(0.65) : NanoTheme.border, lineWidth: 1)
        }
    }

    private func statusHint(for summary: TaskCardNodeSummary) -> String {
        switch summary.status {
        case "backlog":
            return L("已收进「先存着」，平时免催促", "Saved in Stashed without reminders")
        case "doing":
            return L("已批准开工，正在推进", "Approved and advancing")
        case "todo":
            return summary.isPrereqBlocked ? L("已批准立项，等待前置完成", "Approved; waiting on prerequisites") : L("已在待办日程中", "In To do")
        case "done":
            return L("该事项已完成", "Completed")
        case "closed":
            return L("该事项已关闭", "Closed")
        default:
            return L("负责人：", "Assignee: ") + (summary.assignee?.taskName ?? L("未分配", "Unassigned"))
        }
    }

    private var unavailableRow: some View {
        Label(L("该任务不可用或无权查看", "Task unavailable or inaccessible"), systemImage: "eye.slash")
            .font(.caption)
            .foregroundStyle(NanoTheme.muted)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(10)
            .background(NanoTheme.surface.opacity(0.75), in: RoundedRectangle(cornerRadius: 10))
            .overlay { RoundedRectangle(cornerRadius: 10).stroke(NanoTheme.border, lineWidth: 1) }
    }

    private var offlinePlaceholderRow: some View {
        Label(L("任务卡片 · 连接后同步状态", "Task card · Connect to sync"), systemImage: "checklist")
            .font(.caption)
            .foregroundStyle(NanoTheme.muted)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(10)
            .background(NanoTheme.surface.opacity(0.75), in: RoundedRectangle(cornerRadius: 10))
            .overlay { RoundedRectangle(cornerRadius: 10).stroke(NanoTheme.border, lineWidth: 1) }
    }

    private func loadCards() async {
        if let repository = chat.repository,
           let cached = try? await repository.cachedTaskCards(refs),
           !cached.isEmpty, summaries.isEmpty {
            summaries = cached
        }
        do {
            let items = try await client.taskNodes(refs)
            guard !Task.isCancelled else { return }
            summaries = Dictionary(uniqueKeysWithValues: items.map { ($0.cardKey, $0) })
            hasLoadedLive = true
            actionError = nil
            if let repository = chat.repository, !items.isEmpty {
                try? await repository.cacheTaskCards(items)
            }
        } catch {
            // Keep locally cached summaries readable while offline.
        }
    }

    private func approve(ref: TaskCardRef, summary: TaskCardNodeSummary) async {
        busyKeys.insert(ref.cardKey)
        defer { busyKeys.remove(ref.cardKey) }
        do {
            try await client.approveTask(graphID: ref.graph_id, revision: summary.revision, nodeID: ref.node_id)
            await loadCards()
        } catch {
            actionError = error.localizedDescription
        }
    }

    private func updateStatus(ref: TaskCardRef, summary: TaskCardNodeSummary, status: String) async {
        busyKeys.insert(ref.cardKey)
        defer { busyKeys.remove(ref.cardKey) }
        do {
            try await client.applyTaskOperations(
                graphID: ref.graph_id,
                revision: summary.revision,
                operations: [TaskOperations.setStatus(nodeID: ref.node_id, status: status)]
            )
            await loadCards()
        } catch {
            actionError = error.localizedDescription
        }
    }
}
