import SwiftUI

extension EnvironmentValues {
    @Entry var openTaskOverview: (() -> Void)? = nil
}

struct TasksView: View {
    enum Lens: String, CaseIterable {
        case actions, goals
    }
    enum CandidateTab: String, CaseIterable {
        case proposed, stashed
    }

    let client: IMClient
    let onReference: (String, String) -> Void

    @State private var lens: Lens = .actions
    @State private var candidateTab: CandidateTab = .proposed
    @State private var scope = "mine"
    @State private var ownerKey = ""
    @State private var choosingOwner = false
    @State private var filterConversationID = ""
    @State private var query = ""
    @State private var searching = false
    @FocusState private var searchFocused: Bool

    @State private var focus: TaskFocusResponse?
    @State private var loading = false
    @State private var loaded = false
    @State private var error: String?

    @State private var quickTitle = ""
    @State private var captureConversationID = ""
    @State private var quickSaving = false
    @State private var conversations: [Conversation] = []
    @State private var contacts: [Contact] = []

    @State private var completedExpanded = false
    @State private var completedItems: [TaskSummary] = []
    @State private var completedCursor: String?
    @State private var loadingCompleted = false

    @State private var selected: TaskSummary?
    @State private var pushedGraph: GoalRoute?
    @State private var creatingRoot = false
    @State private var creatingGoal = false
    @State private var showingHelp = false
    @State private var busyTaskIDs: Set<String> = []
    @State private var toastText: String?
    @State private var toastToken = UUID()
    @State private var visible = true
    @Environment(\.scenePhase) private var phase

    private struct GoalRoute: Identifiable, Hashable {
        let graphID: String
        let scopeID: String?
        var id: String { "\(graphID):\(scopeID ?? "")" }
    }

    private var writableConversations: [Conversation] {
        conversations.filter { $0.can_write == true && $0.dissolved_at == nil }
    }

    private var selectedCaptureChat: Conversation? {
        writableConversations.first { $0.id == captureConversationID } ?? writableConversations.first
    }

    private var ownerActors: [ActorRef] {
        contacts.map { contact in
            var actor = contact.actor
            actor.display_name = contact.display_name
            return actor
        }
    }

    private var selectedOwnerActor: ActorRef? {
        ownerActors.first { $0.taskKey == ownerKey }
    }

    private var actionCount: Int {
        guard let focus else { return 0 }
        return focus.counts.needs_you + focus.counts.active
    }

    private var goalCount: Int {
        focus?.counts.goals ?? 0
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                headerControls
                if searching {
                    NanoSearchField(text: $query, prompt: L("搜索事项或目标…", "Search tasks or goals…"))
                        .focused($searchFocused)
                        .onAppear { searchFocused = true }
                }
                if !writableConversations.isEmpty {
                    quickCaptureBar
                }
                if scope == "assignee" {
                    Button { choosingOwner = true } label: {
                        TaskPropertyRow(title: L("负责人", "Assignee")) {
                            if let actor = selectedOwnerActor {
                                TaskActorLabel(actor: actor)
                            } else {
                                Text(L("请选择负责人", "Select assignee")).foregroundStyle(NanoTheme.accent)
                            }
                        }
                    }
                    .buttonStyle(.plain)
                    .padding(.horizontal, 12)
                    .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 12))
                }
                if let error {
                    ErrorNotice(message: error)
                    Button(L("重试", "Retry")) { Task { await load() } }.buttonStyle(.bordered)
                }
                if !loaded && error == nil {
                    ProgressView().frame(maxWidth: .infinity).padding(.vertical, 24)
                }
                if scope == "assignee" && ownerKey.isEmpty {
                    Text(L("先选择一位成员或数字员工，查看其负责的当前行动或长线目标。",
                           "Choose a person or assistant to inspect their actions or goals."))
                        .font(.subheadline).foregroundStyle(NanoTheme.muted)
                        .padding(.vertical, 16)
                } else if loaded, let focus {
                    if lens == .actions {
                        actionsLensView(focus)
                    } else {
                        goalsLensView(focus)
                    }
                }
            }
            .padding(14)
            .padding(.bottom, 32)
        }
        .background(NanoTheme.canvas)
        .nanoRootTitle(L("任务", "Tasks"))
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button { showingHelp = true } label: {
                    Image(systemName: "questionmark.circle")
                }
                .accessibilityLabel(L("状态说明", "Status guide"))
                Button { creatingRoot = true } label: {
                    Image(systemName: "plus")
                }
                .accessibilityLabel(L("创建根任务", "Create root task"))
            }
        }
        .overlay(alignment: .bottom) {
            if let toastText {
                Text(toastText)
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 9)
                    .background(Color.black.opacity(0.84), in: Capsule())
                    .padding(.horizontal, 16)
                    .padding(.bottom, 12)
                    .allowsHitTesting(false)
                    .transition(.opacity)
            }
        }
        .navigationDestination(item: $pushedGraph) { route in
            TaskGraphView(client: client, graphID: route.graphID, scopeID: route.scopeID, onReference: onReference)
        }
        .refreshable { await load() }
        .onSubmit {
            if searching { Task { await load() } }
        }
        .onChange(of: scope) { _, _ in
            completedItems = []; completedCursor = nil
            Task {
                await load()
                if completedExpanded { await loadCompleted(more: false) }
            }
        }
        .onChange(of: ownerKey) { _, _ in
            completedItems = []; completedCursor = nil
            Task {
                await load()
                if completedExpanded { await loadCompleted(more: false) }
            }
        }
        .onChange(of: filterConversationID) { _, _ in
            completedItems = []; completedCursor = nil
            Task {
                await load()
                if completedExpanded { await loadCompleted(more: false) }
            }
        }
        .onChange(of: query) { _, value in
            if value.isEmpty { Task { await load() } }
        }
        .onChange(of: completedExpanded) { _, expanded in
            if expanded && completedItems.isEmpty {
                Task { await loadCompleted(more: false) }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .nanoTaskGraphChanged)) { note in
            guard (note.object as? IMClient) === client || note.object == nil else { return }
            Task {
                await load()
                if completedExpanded { await loadCompleted(more: false) }
            }
        }
        .task {
            await loadMetadata()
        }
        .task(id: "\(phase == .active)-\(visible)") {
            guard phase == .active, visible else { return }
            while !Task.isCancelled {
                await load()
                try? await Task.sleep(for: .seconds(3))
            }
        }
        .onAppear { visible = true }
        .onDisappear { visible = false }
        .sheet(item: $selected, onDismiss: { Task { await load() } }) { item in
            NavigationStack {
                TaskDetailLoader(client: client, graphID: item.graph_id, nodeID: item.effectiveNodeID,
                                 onReference: { id, text in selected = nil; onReference(id, text) },
                                 onOpenGraph: { gid, sid in
                                     selected = nil
                                     pushedGraph = GoalRoute(graphID: gid, scopeID: sid)
                                 })
            }
        }
        .sheet(isPresented: $choosingOwner) {
            TaskActorPicker(actors: ownerActors, selectedKey: ownerKey, allowUnassigned: false,
                            context: L("跨目标汇总该主体负责的事项", "Filter tasks owned by this member or agent")) {
                ownerKey = $0?.taskKey ?? ""
            }
        }
        .sheet(isPresented: $creatingRoot) {
            NavigationStack {
                TaskEditorView(client: client, graph: nil, node: nil, parentID: nil,
                               conversationID: selectedCaptureChat?.id, initialMode: "none") {
                    creatingRoot = false
                    Task { await load() }
                }
            }
        }
        .sheet(isPresented: $creatingGoal) {
            NavigationStack {
                TaskEditorView(client: client, graph: nil, node: nil, parentID: nil,
                               conversationID: selectedCaptureChat?.id, initialMode: "dag") {
                    creatingGoal = false
                    Task { await load() }
                }
            }
        }
        .sheet(isPresented: $showingHelp) {
            TaskStatusHelpSheet()
        }
    }

    // MARK: - Top Controls & Quick Capture

    private var headerControls: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                lensTabs
                Spacer(minLength: 4)
                Button {
                    searching.toggle()
                    if !searching && !query.isEmpty { query = "" }
                } label: {
                    Image(systemName: searching ? "xmark" : "magnifyingglass")
                        .font(.subheadline.weight(.semibold))
                        .frame(width: 34, height: 34)
                        .background(NanoTheme.surface, in: Circle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(searching ? L("收起搜索", "Hide search") : L("搜索任务", "Search tasks"))
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    Menu {
                        Button {
                            scope = "mine"
                        } label: {
                            Label(L("与我有关", "Relevant to me"), systemImage: scope == "mine" ? "checkmark" : "person.crop.circle")
                        }
                        Button {
                            scope = "assignee"
                            if ownerKey.isEmpty { choosingOwner = true }
                        } label: {
                            Label(L("按负责人", "By assignee"), systemImage: scope == "assignee" ? "checkmark" : "person.2")
                        }
                        Button {
                            scope = "all"
                        } label: {
                            Label(L("团队全部", "All team"), systemImage: scope == "all" ? "checkmark" : "square.grid.2x2")
                        }
                    } label: {
                        HStack(spacing: 5) {
                            Circle().fill(NanoTheme.accent).frame(width: 7, height: 7)
                            Text(scopeTitle)
                            Image(systemName: "chevron.down").font(.caption2)
                        }
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(NanoTheme.ink)
                        .padding(.horizontal, 11)
                        .padding(.vertical, 7)
                        .background(NanoTheme.surface, in: Capsule())
                        .overlay { Capsule().stroke(NanoTheme.border, lineWidth: 1) }
                    }

                    if !conversations.isEmpty {
                        Menu {
                            Button {
                                filterConversationID = ""
                            } label: {
                                Label(L("全部会话", "All conversations"), systemImage: filterConversationID.isEmpty ? "checkmark" : "tray.full")
                            }
                            Divider()
                            ForEach(conversations) { chat in
                                Button {
                                    filterConversationID = chat.id
                                } label: {
                                    Label(chat.title, systemImage: filterConversationID == chat.id ? "checkmark" : "bubble.left")
                                }
                            }
                        } label: {
                            HStack(spacing: 5) {
                                Image(systemName: "bubble.left")
                                Text(conversations.first { $0.id == filterConversationID }?.title ?? L("全部会话", "All chats"))
                                    .lineLimit(1)
                                Image(systemName: "chevron.down").font(.caption2)
                            }
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(filterConversationID.isEmpty ? NanoTheme.muted : NanoTheme.accent)
                            .padding(.horizontal, 11)
                            .padding(.vertical, 7)
                            .background(NanoTheme.surface, in: Capsule())
                            .overlay { Capsule().stroke(NanoTheme.border, lineWidth: 1) }
                        }
                    }

                    Button { creatingGoal = true } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "point.3.connected.trianglepath.dotted")
                            Text(L("拆多步目标", "Multi-step goal"))
                        }
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(NanoTheme.accent)
                        .padding(.horizontal, 11)
                        .padding(.vertical, 7)
                        .background(NanoTheme.softAccent, in: Capsule())
                    }
                    .buttonStyle(.plain)

                    Button { showingHelp = true } label: {
                        HStack(spacing: 4) {
                            Text("?").font(.caption.bold())
                            Text(L("状态说明", "Statuses"))
                        }
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(NanoTheme.muted)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .background(NanoTheme.surface, in: Capsule())
                        .overlay { Capsule().stroke(NanoTheme.border, lineWidth: 1) }
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var lensTabs: some View {
        HStack(spacing: 4) {
            lensTab(.actions, title: L("当前行动", "Current actions"), count: actionCount)
            lensTab(.goals, title: L("长线目标", "Goals"), count: goalCount)
        }
        .padding(4)
        .background(NanoTheme.surface.opacity(0.85), in: Capsule())
        .overlay { Capsule().stroke(NanoTheme.border, lineWidth: 1) }
    }

    private func lensTab(_ target: Lens, title: String, count: Int) -> some View {
        let active = lens == target
        return Button {
            lens = target
        } label: {
            HStack(spacing: 5) {
                Text(title)
                Text("\(count)")
                    .font(.caption2.weight(.bold))
                    .monospacedDigit()
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(active ? NanoTheme.softAccent : NanoTheme.canvas, in: Capsule())
            }
            .font(.caption.weight(active ? .bold : .semibold))
            .foregroundStyle(active ? NanoTheme.accent : NanoTheme.muted)
            .padding(.horizontal, 11)
            .padding(.vertical, 6)
            .background(active ? NanoTheme.surface : Color.clear, in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(active ? .isSelected : [])
    }

    private var scopeTitle: String {
        switch scope {
        case "assignee": return L("按负责人", "By assignee")
        case "all": return L("团队全部", "All team")
        default: return L("与我有关", "Relevant to me")
        }
    }

    private var quickCaptureBar: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                if let chat = selectedCaptureChat {
                    let isPA = chat.category == "agent"
                    Menu {
                        ForEach(writableConversations) { option in
                            Button {
                                captureConversationID = option.id
                            } label: {
                                Label(option.title, systemImage: option.id == chat.id ? "checkmark" : (option.category == "agent" ? "sparkles" : "person.2"))
                            }
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: isPA ? "sparkles" : "person.2")
                            Text(chat.title).lineLimit(1)
                            Image(systemName: "chevron.down").font(.caption2)
                        }
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(isPA ? Color(red: 0.39, green: 0.29, blue: 0.03) : NanoTheme.accent)
                        .padding(.horizontal, 9)
                        .padding(.vertical, 5)
                        .background(isPA ? Color("Butter") : NanoTheme.softAccent, in: Capsule())
                    }
                }

                TextField(L("随手记件小事…", "Jot down a quick task…"), text: $quickTitle)
                    .font(.subheadline)
                    .submitLabel(.done)
                    .onSubmit { Task { await submitQuickCapture() } }
                    .disabled(quickSaving)

                Button {
                    Task { await submitQuickCapture() }
                } label: {
                    if quickSaving {
                        ProgressView().controlSize(.small)
                    } else {
                        Text(L("＋ 记下来", "＋ Add"))
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 11)
                            .padding(.vertical, 7)
                            .background(NanoTheme.accent, in: Capsule())
                    }
                }
                .buttonStyle(.plain)
                .disabled(quickSaving || quickTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || selectedCaptureChat == nil)
            }
        }
        .padding(10)
        .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 16))
        .overlay { RoundedRectangle(cornerRadius: 16).stroke(NanoTheme.border, lineWidth: 1) }
    }

    // MARK: - Actions Lens

    @ViewBuilder
    private func actionsLensView(_ focus: TaskFocusResponse) -> some View {
        if scope == "mine" || !focus.needs_you.isEmpty || !focus.stashed.isEmpty {
            candidateSwitcherSection(focus)
        }
        activeSection(focus)
        completedSection(focus)
    }

    private func candidateSwitcherSection(_ focus: TaskFocusResponse) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                HStack(spacing: 4) {
                    candidateTabButton(.proposed, title: L("待你拍板", "Needs decision"), count: focus.counts.needs_you, butter: focus.counts.needs_you > 0)
                    candidateTabButton(.stashed, title: L("先存着", "Stashed"), count: focus.counts.stashed, butter: false)
                }
                .padding(3.5)
                .background(NanoTheme.surface.opacity(0.85), in: Capsule())
                .overlay { Capsule().stroke(NanoTheme.border, lineWidth: 1) }
                Spacer()
            }

            if candidateTab == .proposed {
                if focus.needs_you.isEmpty {
                    calmZeroCard(L("当前没有待你拍板的事项，可以切到旁边「先存着 (\(focus.counts.stashed))」看看备选点子。",
                                   "Nothing waiting for your decision right now. Switch to Stashed (\(focus.counts.stashed)) to browse saved ideas."))
                } else {
                    VStack(spacing: 9) {
                        ForEach(focus.needs_you) { item in
                            needsYouCard(item)
                        }
                    }
                    if let next = focus.next_cursors.needs_you {
                        Button(L("加载更多待拍板事项", "Load more")) {
                            Task { await loadMoreFocus(section: "needs_you", cursor: next) }
                        }
                        .font(.caption.weight(.semibold))
                    }
                }
            } else {
                if focus.stashed.isEmpty {
                    calmZeroCard(L("还没有「先存着」的点子；遇到暂不急做的提议点「先存着」就会收在这里。",
                                   "No stashed ideas yet. Tap Stash on any proposal to keep it here without reminders."))
                } else {
                    VStack(spacing: 9) {
                        ForEach(focus.stashed) { item in
                            stashedCard(item)
                        }
                    }
                    if let next = focus.next_cursors.stashed {
                        Button(L("加载更多暂存事项", "Load more")) {
                            Task { await loadMoreFocus(section: "stashed", cursor: next) }
                        }
                        .font(.caption.weight(.semibold))
                    }
                }
            }
        }
    }

    private func candidateTabButton(_ tab: CandidateTab, title: String, count: Int, butter: Bool) -> some View {
        let active = candidateTab == tab
        return Button {
            candidateTab = tab
        } label: {
            HStack(spacing: 5) {
                Text(title)
                Text("\(count)")
                    .font(.caption2.weight(.bold))
                    .monospacedDigit()
                    .foregroundStyle(butter ? Color(red: 0.37, green: 0.28, blue: 0.06) : (active ? NanoTheme.accent : NanoTheme.muted))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(butter ? Color("Butter") : (active ? NanoTheme.softAccent : NanoTheme.canvas), in: Capsule())
            }
            .font(.caption.weight(active ? .bold : .semibold))
            .foregroundStyle(active ? NanoTheme.accent : NanoTheme.muted)
            .padding(.horizontal, 11)
            .padding(.vertical, 6)
            .background(active ? NanoTheme.surface : Color.clear, in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(active ? .isSelected : [])
    }

    private func needsYouCard(_ item: TaskSummary) -> some View {
        let isBusy = busyTaskIDs.contains(item.id)
        let canWrite = item.conversation.can_write && item.can_edit != false
        return VStack(alignment: .leading, spacing: 8) {
            crumbView(for: item)
            Button { selected = item } label: {
                VStack(alignment: .leading, spacing: 5) {
                    Text(item.title)
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(NanoTheme.ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if item.status == "waiting", let reason = item.wait?.reason, !reason.isEmpty {
                        Text(reason)
                            .font(.caption)
                            .foregroundStyle(NanoTheme.muted)
                            .lineLimit(3)
                    } else if ["in_review", "done"].contains(item.status), let res = item.result, !res.isEmpty {
                        Text(res)
                            .font(.caption)
                            .foregroundStyle(NanoTheme.muted)
                            .lineLimit(2)
                    } else if let desc = item.description, !desc.isEmpty {
                        Text(desc)
                            .font(.caption)
                            .foregroundStyle(NanoTheme.muted)
                            .lineLimit(2)
                    }
                    metadataRow(item)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if canWrite {
                HStack(spacing: 8) {
                    if item.status == "proposed" {
                        Button {
                            Task { await approve(item) }
                        } label: {
                            Text(item.isPrereqBlocked ? L("批准立项", "Approve to queue") : L("批准开工", "Approve & start"))
                                .font(.caption.weight(.bold))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(NanoTheme.accent, in: Capsule())
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)

                        Button {
                            Task { await updateStatus(item, status: "backlog", toast: L("已收进「先存着」：\(item.title)", "Stashed: \(item.title)")) }
                        } label: {
                            Text(L("先存着", "Stash"))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(Color(red: 0.36, green: 0.32, blue: 0.21))
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(Color("Butter").opacity(0.55), in: Capsule())
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)

                        Button {
                            Task { await updateStatus(item, status: "closed", toast: L("已关闭：\(item.title)", "Closed: \(item.title)")) }
                        } label: {
                            Text(L("关闭", "Close"))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(NanoTheme.muted)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)
                    } else if item.status == "in_review" {
                        Button {
                            Task { await updateStatus(item, status: "done", toast: L("已确认完成：\(item.title)", "Completed: \(item.title)")) }
                        } label: {
                            Text(L("确认完成", "Confirm done"))
                                .font(.caption.weight(.bold))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(NanoTheme.accent, in: Capsule())
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)

                        Button { selected = item } label: {
                            Text(L("查看交付", "Review"))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(NanoTheme.accent)
                                .padding(.horizontal, 11)
                                .padding(.vertical, 6)
                                .background(NanoTheme.softAccent, in: Capsule())
                        }
                        .buttonStyle(.plain)
                    } else if item.status == "waiting" {
                        Button { onReference(item.conversation.id, "") } label: {
                            Text(L("回聊天回复", "Reply in chat"))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(NanoTheme.accent)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(NanoTheme.softAccent, in: Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 13))
        .overlay {
            RoundedRectangle(cornerRadius: 13)
                .stroke(item.status == "proposed" ? Color(red: 0.87, green: 0.66, blue: 0.16).opacity(0.65) : NanoTheme.border, lineWidth: item.status == "proposed" ? 1.4 : 1)
        }
    }

    private func stashedCard(_ item: TaskSummary) -> some View {
        let isBusy = busyTaskIDs.contains(item.id)
        let canWrite = item.conversation.can_write && item.can_edit != false
        return VStack(alignment: .leading, spacing: 8) {
            crumbView(for: item)
            Button { selected = item } label: {
                VStack(alignment: .leading, spacing: 5) {
                    Text(item.title)
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(NanoTheme.ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if let desc = item.description, !desc.isEmpty {
                        Text(desc)
                            .font(.caption)
                            .foregroundStyle(NanoTheme.muted)
                            .lineLimit(2)
                    }
                    metadataRow(item)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if canWrite {
                HStack(spacing: 8) {
                    Button {
                        Task { await updateStatus(item, status: "todo", toast: L("已提上日程：\(item.title)", "Scheduled: \(item.title)")) }
                    } label: {
                        Text(L("↑ 提上日程", "↑ Schedule"))
                            .font(.caption.weight(.bold))
                            .foregroundStyle(NanoTheme.accent)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(NanoTheme.softAccent, in: Capsule())
                    }
                    .buttonStyle(.plain)
                    .disabled(isBusy)

                    Button {
                        Task { await expandToGoal(item) }
                    } label: {
                        Text(L("展开成目标图", "Expand to goal"))
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(NanoTheme.ink)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(NanoTheme.canvas, in: Capsule())
                    }
                    .buttonStyle(.plain)
                    .disabled(isBusy)

                    Button {
                        Task { await updateStatus(item, status: "closed", toast: L("已关闭：\(item.title)", "Closed: \(item.title)")) }
                    } label: {
                        Text(L("关闭", "Close"))
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(NanoTheme.muted)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 6)
                    }
                    .buttonStyle(.plain)
                    .disabled(isBusy)
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(NanoTheme.surface.opacity(0.92), in: RoundedRectangle(cornerRadius: 13))
        .overlay {
            RoundedRectangle(cornerRadius: 13)
                .strokeBorder(NanoTheme.border, style: StrokeStyle(lineWidth: 1, dash: [5, 4]))
        }
    }

    private func activeSection(_ focus: TaskFocusResponse) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 7) {
                Text(L("进行中", "In progress")).font(.subheadline.bold())
                Text("\(focus.counts.active)")
                    .font(.caption2.weight(.bold))
                    .monospacedDigit()
                    .foregroundStyle(NanoTheme.muted)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 2)
                    .background(NanoTheme.surface, in: Capsule())
                Spacer()
            }

            if focus.active.isEmpty {
                calmZeroCard(query.isEmpty
                             ? L("当前没有进行中的事项；可在上方速记栏随手记一件小事。", "No active items right now. Use the quick-capture bar above to add one.")
                             : L("没有找到匹配的进行中事项。", "No matching active tasks."))
            } else {
                VStack(spacing: 9) {
                    ForEach(focus.active) { item in
                        activeCard(item)
                    }
                }
                if let next = focus.next_cursors.active {
                    Button(L("加载更多进行中事项", "Load more")) {
                        Task { await loadMoreFocus(section: "active", cursor: next) }
                    }
                    .font(.caption.weight(.semibold))
                }
            }
        }
        .padding(.top, 4)
    }

    private func activeCard(_ item: TaskSummary) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            crumbView(for: item)
            Button { selected = item } label: {
                VStack(alignment: .leading, spacing: 6) {
                    Text(item.title)
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(NanoTheme.ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if let desc = item.description, !desc.isEmpty {
                        Text(desc)
                            .font(.caption)
                            .foregroundStyle(NanoTheme.muted)
                            .lineLimit(2)
                    } else if let result = item.result, !result.isEmpty {
                        Text(result)
                            .font(.caption)
                            .foregroundStyle(NanoTheme.muted)
                            .lineLimit(2)
                    }
                    metadataRow(item)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 13))
        .overlay { RoundedRectangle(cornerRadius: 13).stroke(NanoTheme.border, lineWidth: 1) }
    }

    private func completedSection(_ focus: TaskFocusResponse) -> some View {
        DisclosureGroup(isExpanded: $completedExpanded) {
            VStack(alignment: .leading, spacing: 8) {
                if loadingCompleted && completedItems.isEmpty {
                    ProgressView().padding(.vertical, 8)
                } else if completedItems.isEmpty {
                    Text(L("暂无已完结记录", "No completed items"))
                        .font(.caption).foregroundStyle(NanoTheme.muted).padding(.vertical, 4)
                } else {
                    ForEach(completedItems) { item in
                        Button { selected = item } label: {
                            VStack(alignment: .leading, spacing: 5) {
                                crumbView(for: item, interactive: false)
                                Text(item.title)
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(NanoTheme.ink)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                metadataRow(item)
                            }
                            .padding(10)
                            .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 10))
                        }
                        .buttonStyle(.plain)
                    }
                    if completedCursor != nil {
                        Button(L("加载更多已完结记录", "Load more")) {
                            Task { await loadCompleted(more: true) }
                        }
                        .font(.caption.weight(.semibold))
                        .disabled(loadingCompleted)
                    }
                }
            }
            .padding(.top, 8)
        } label: {
            Text(L("查看已完结记录 (\(focus.completed_count))", "Completed history (\(focus.completed_count))"))
                .font(.caption.weight(.semibold))
                .foregroundStyle(NanoTheme.muted)
        }
        .padding(.top, 6)
    }

    // MARK: - Goals Lens

    private func goalsLensView(_ focus: TaskFocusResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(L("正在推进与跟进的长线目标", "Multi-stage goals"))
                    .font(.subheadline.bold())
                Text("\(focus.counts.goals)")
                    .font(.caption2.weight(.bold))
                    .monospacedDigit()
                    .foregroundStyle(NanoTheme.muted)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 2)
                    .background(NanoTheme.surface, in: Capsule())
                Spacer()
            }

            if focus.goals.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "point.3.connected.trianglepath.dotted")
                        .font(.title).foregroundStyle(NanoTheme.accent)
                    Text(query.isEmpty ? L("还没有多阶段长线目标", "No multi-step goals yet") : L("没有找到匹配的长线目标", "No matching goals"))
                        .font(.subheadline.weight(.semibold))
                    if query.isEmpty {
                        Button(L("拆一个多步目标", "Create multi-step goal")) { creatingGoal = true }
                            .buttonStyle(.bordered)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 28)
                .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 14))
            } else {
                ForEach(focus.goals) { goal in
                    NavigationLink {
                        TaskGraphView(client: client, graphID: goal.graph_id, scopeID: goal.root_node_id, onReference: onReference)
                    } label: {
                        goalCard(goal)
                    }
                    .buttonStyle(.plain)
                }
                if let next = focus.next_cursors.goals {
                    Button(L("加载更多长线目标", "Load more")) {
                        Task { await loadMoreFocus(section: "goals", cursor: next) }
                    }
                    .font(.caption.weight(.semibold))
                }
            }
        }
    }

    private func goalCard(_ goal: TaskSummary) -> some View {
        let done = goal.progress?.done ?? goal.direct_counts?.done ?? 0
        let total = max(1, goal.progress?.total ?? goal.direct_counts?.total ?? 1)
        let goalSummary = (goal.root_goal_summary ?? goal.description ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                TaskStatusBadge(status: goal.status)
                Text(L("归属：", "In: ") + goal.conversation.title)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(NanoTheme.muted)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 2)
                    .background(NanoTheme.canvas, in: Capsule())
                Spacer()
                HStack(spacing: 3) {
                    Text(L("阶段全景", "Stages"))
                    Image(systemName: "chevron.right").font(.caption2)
                }
                .font(.caption.weight(.bold))
                .foregroundStyle(NanoTheme.accent)
            }

            Text(goal.title)
                .font(.headline)
                .foregroundStyle(NanoTheme.ink)
                .frame(maxWidth: .infinity, alignment: .leading)

            if !goalSummary.isEmpty {
                Text(L("目标说明：", "Goal description: ") + goalSummary)
                    .font(.caption)
                    .foregroundStyle(NanoTheme.muted)
                    .lineLimit(3)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            VStack(alignment: .leading, spacing: 4) {
                ProgressView(value: Double(min(done, total)), total: Double(total))
                    .tint(NanoTheme.accent)
                Text(L("阶段进度：已完成 \(done) / 共 \(total)", "Progress: \(done) / \(total) stages done"))
                    .font(.caption2)
                    .foregroundStyle(NanoTheme.muted)
            }

            if let stages = goal.stage_nodes, !stages.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(Array(stages.enumerated()), id: \.element.id) { index, stage in
                            if index > 0 {
                                Text("→").font(.caption2).foregroundStyle(NanoTheme.muted)
                            }
                            let mark = stage.status == "done" ? "✓ " : (stage.status == "doing" ? "● " : "◌ ")
                            Text(mark + stage.title)
                                .font(.caption2.weight(stage.status == "doing" ? .bold : .medium))
                                .foregroundStyle(stage.status == "doing" ? NanoTheme.accent : NanoTheme.muted)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(stage.status == "doing" ? NanoTheme.softAccent : NanoTheme.canvas, in: Capsule())
                        }
                    }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 15))
        .overlay { RoundedRectangle(cornerRadius: 15).stroke(NanoTheme.border, lineWidth: 1) }
    }

    // MARK: - Shared Card Elements

    @ViewBuilder
    private func crumbView(for item: TaskSummary, interactive: Bool = true) -> some View {
        let isSubnode = item.effectiveNodeID != item.root_node_id
        let isMultiGoal = isSubnode || item.mode != "none" || (item.direct_counts?.total ?? 0) > 0
        if isMultiGoal {
            let rootName = item.root_title ?? item.parent_path?.first?.title ?? item.title
            let trail = (item.parent_path ?? []).dropFirst().map(\.title)
            let label = L("所属目标：", "Goal: ") + ([rootName] + trail).joined(separator: " › ")
            TaskCrumbPill(text: label, highlight: true, action: interactive ? {
                pushedGraph = GoalRoute(graphID: item.graph_id, scopeID: item.scope_id ?? item.root_node_id)
            } : nil)
        } else {
            TaskCrumbPill(text: L("单卡 · ", "Single · ") + item.conversation.title)
        }
    }

    private func metadataRow(_ item: TaskSummary) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 8) {
                TaskStatusBadge(status: item.status)
                Text(L("负责人：", "Assignee: ") + (item.assignee?.taskName ?? L("未分配", "Unassigned")))
                    .font(.caption)
                    .foregroundStyle(NanoTheme.muted)
                    .lineLimit(1)
                Spacer(minLength: 0)
            }
            if item.status == "waiting", let wait = item.wait {
                HStack(spacing: 6) {
                    Image(systemName: "clock").font(.caption2)
                    Text(wait.reason).lineLimit(2)
                    if let next = wait.next_check_at, !next.isEmpty {
                        Text("·")
                        NanoDateTime(value: next)
                    }
                }
                .font(.caption)
                .foregroundStyle(Color(red: 0.60, green: 0.38, blue: 0.09))
            }
        }
    }

    private func calmZeroCard(_ text: String) -> some View {
        Text(text)
            .font(.caption)
            .foregroundStyle(NanoTheme.muted)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 14)
            .padding(.vertical, 11)
            .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 11))
            .overlay { RoundedRectangle(cornerRadius: 11).stroke(NanoTheme.border, lineWidth: 1) }
    }

    // MARK: - Data & Mutations

    private func showToast(_ message: String) {
        let token = UUID()
        toastToken = token
        withAnimation(.easeInOut(duration: 0.18)) { toastText = message }
        Task {
            try? await Task.sleep(for: .seconds(2.4))
            if !Task.isCancelled, toastToken == token {
                withAnimation(.easeInOut(duration: 0.18)) { toastText = nil }
            }
        }
    }

    private func loadMetadata() async {
        contacts = (try? await client.contacts()) ?? []
        if let page: ItemsPage<Conversation> = try? await client.get("/im/v1/conversations") {
            conversations = page.items
            if captureConversationID.isEmpty {
                let writable = page.items.filter { $0.can_write == true && $0.dissolved_at == nil }
                captureConversationID = writable.first(where: { $0.category == "agent" })?.id ?? writable.first?.id ?? ""
            }
        }
    }

    private func load() async {
        guard !loading else { return }
        if scope == "assignee" && ownerKey.isEmpty {
            loaded = true
            return
        }
        loading = true
        defer { loading = false }
        let capturedScope = scope
        let capturedQuery = query
        let capturedConv = filterConversationID
        let capturedAssignee = selectedOwnerActor
        do {
            let response = try await client.taskFocus(
                scope: capturedScope,
                query: capturedQuery,
                assignee: capturedAssignee,
                conversationID: capturedConv.isEmpty ? nil : capturedConv
            )
            try Task.checkCancellation()
            guard capturedScope == scope, capturedQuery == query, capturedConv == filterConversationID else { return }
            focus = response
            error = nil
            loaded = true
        } catch is CancellationError {
        } catch {
            self.error = error.localizedDescription
            if [403, 404].contains((error as? APIError)?.status ?? 0) { focus = nil }
        }
    }

    private func loadMoreFocus(section: String, cursor: String) async {
        guard !loading else { return }
        loading = true
        defer { loading = false }
        do {
            let more = try await client.taskFocus(
                scope: scope,
                query: query,
                assignee: selectedOwnerActor,
                conversationID: filterConversationID.isEmpty ? nil : filterConversationID,
                section: section,
                cursor: cursor
            )
            guard var current = focus else { return }
            func appendUnique(_ target: inout [TaskSummary], _ additions: [TaskSummary]) {
                for item in additions where !target.contains(where: { $0.id == item.id }) {
                    target.append(item)
                }
            }
            switch section {
            case "needs_you":
                appendUnique(&current.needs_you, more.needs_you)
                current.next_cursors.needs_you = more.next_cursors.needs_you
            case "stashed":
                appendUnique(&current.stashed, more.stashed)
                current.next_cursors.stashed = more.next_cursors.stashed
            case "active":
                appendUnique(&current.active, more.active)
                current.next_cursors.active = more.next_cursors.active
            case "goals":
                appendUnique(&current.goals, more.goals)
                current.next_cursors.goals = more.next_cursors.goals
            default: break
            }
            focus = current
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func loadCompleted(more: Bool) async {
        guard !loadingCompleted else { return }
        loadingCompleted = true
        defer { loadingCompleted = false }
        do {
            let response = try await client.taskFocus(
                scope: scope,
                query: query,
                assignee: selectedOwnerActor,
                conversationID: filterConversationID.isEmpty ? nil : filterConversationID,
                section: "completed",
                cursor: more ? completedCursor : nil,
                limit: 25
            )
            if more {
                for item in response.completed where !completedItems.contains(where: { $0.id == item.id }) {
                    completedItems.append(item)
                }
            } else {
                completedItems = response.completed
            }
            completedCursor = response.next_cursors.completed
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func submitQuickCapture() async {
        let trimmed = quickTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, let chat = selectedCaptureChat, !quickSaving else { return }
        quickSaving = true
        defer { quickSaving = false }
        do {
            try await client.createQuickTask(conversationID: chat.id, title: trimmed)
            quickTitle = ""
            lens = .actions
            showToast(L("已记入进行中（\(chat.title)）：\(trimmed)", "Added to Active (\(chat.title)): \(trimmed)"))
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func approve(_ item: TaskSummary) async {
        busyTaskIDs.insert(item.id)
        defer { busyTaskIDs.remove(item.id) }
        do {
            try await client.approveTask(graphID: item.graph_id, revision: item.revision, nodeID: item.effectiveNodeID)
            showToast(item.isPrereqBlocked
                      ? L("已批准立项（进入待办）：\(item.title)", "Approved to To do: \(item.title)")
                      : L("已批准开工：\(item.title)", "Approved & started: \(item.title)"))
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func updateStatus(_ item: TaskSummary, status: String, toast: String) async {
        busyTaskIDs.insert(item.id)
        defer { busyTaskIDs.remove(item.id) }
        do {
            try await client.applyTaskOperations(
                graphID: item.graph_id,
                revision: item.revision,
                operations: [TaskOperations.setStatus(nodeID: item.effectiveNodeID, status: status)]
            )
            showToast(toast)
            await load()
            if completedExpanded && ["done", "closed"].contains(status) {
                await loadCompleted(more: false)
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func expandToGoal(_ item: TaskSummary) async {
        busyTaskIDs.insert(item.id)
        defer { busyTaskIDs.remove(item.id) }
        do {
            var ops: [JSONValue] = []
            if item.mode == "none" {
                ops.append(TaskOperations.setMode(nodeID: item.effectiveNodeID, mode: "dag"))
            }
            if item.status == "backlog" {
                ops.append(TaskOperations.setStatus(nodeID: item.effectiveNodeID, status: "todo"))
            }
            if !ops.isEmpty {
                try await client.applyTaskOperations(graphID: item.graph_id, revision: item.revision, operations: ops)
            }
            await load()
            pushedGraph = GoalRoute(graphID: item.graph_id, scopeID: item.effectiveNodeID)
        } catch {
            self.error = error.localizedDescription
        }
    }
}
