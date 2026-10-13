import SwiftUI

struct TaskEditorView: View {
    let client: IMClient
    let node: TaskNode?
    let parentID: String?
    let completed: () -> Void
    private let initialDraft: TaskDraft
    private let initialConversationID: String
    @State private var graph: TaskGraph?
    @State private var baseline: TaskNode?
    @State private var draft: TaskDraft
    @State private var parentMode = "dag"
    @State private var conversations: [Conversation] = []
    @State private var conversationID = ""
    @State private var participants: [ActorRef] = []
    @State private var error: String?
    @State private var busy = false
    @State private var needsRefresh = false
    @State private var cannotSave = false
    @State private var creationRefreshed = false
    @State private var comparison: TaskConflict?
    @State private var showingComparison = false
    @State private var showingStatus = false
    @State private var showingAssignee = false
    @State private var showingConversation = false
    @State private var showingNote = false
    @State private var confirmLeave = false
    @State private var requestKey = UUID().uuidString
    @State private var submittedBody: [String: JSONValue]?
    @FocusState private var focusedField: String?
    @Environment(\.dismiss) private var dismiss

    init(client: IMClient, graph: TaskGraph?, node: TaskNode?, parentID: String?, conversationID: String? = nil, completed: @escaping () -> Void) {
        self.client = client; self.node = node; self.parentID = parentID; self.completed = completed
        initialDraft = TaskDraft(node: node)
        initialConversationID = graph?.conversation.id ?? conversationID ?? ""
        _graph = State(initialValue: graph); _baseline = State(initialValue: node)
        _draft = State(initialValue: initialDraft)
        _conversationID = State(initialValue: initialConversationID)
    }
    private var dirty: Bool { draft != initialDraft || conversationID != initialConversationID || parentMode != "dag" }
    private var reworking: Bool { baseline?.status == "done" && draft.status == "doing" }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                if let error { ErrorNotice(message: error) }
                if needsRefresh {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(L("草稿已保留", "Your draft is retained")).font(.headline)
                        Button(L("读取最新内容", "Read latest content")) { Task { await reload() } }.disabled(busy)
                    }
                }
                if creationRefreshed {
                    Text(L("已读取最新版本。输入已保留，请确认后再次保存。", "Latest version loaded. Your input is retained; review it and save again."))
                        .font(.subheadline).foregroundStyle(NanoTheme.accent)
                }
                if comparison != nil {
                    Button(L("继续确认更新", "Continue reviewing changes")) { focusedField = nil; showingComparison = true }.buttonStyle(.bordered)
                }
                VStack(alignment: .leading, spacing: 24) {
                    if graph == nil {
                        Button { showingConversation = true } label: {
                            TaskPropertyRow(title: L("所属会话", "Conversation")) {
                                Text(conversations.first { $0.id == conversationID }?.title ?? L("请选择", "Select"))
                                    .foregroundStyle(NanoTheme.accent)
                            }
                        }.buttonStyle(.plain)
                    } else if let graph {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(graph.conversation.title).font(.subheadline).foregroundStyle(NanoTheme.muted)
                            if let parentID, let parent = graph.nodes.first(where: { $0.id == parentID }) {
                                Text(L("父任务：", "Parent: ") + parent.title).font(.subheadline).foregroundStyle(NanoTheme.muted)
                            }
                        }
                    }
                    field(L("任务标题", "Task title"), prompt: L("这项任务要完成什么？", "What needs to be done?"), text: $draft.title, key: "title", title: true)
                    VStack(spacing: 0) {
                        Button { focusedField = nil; showingStatus = true } label: {
                            TaskPropertyRow(title: L("状态", "Status")) { TaskStatusBadge(status: draft.status) }
                        }.buttonStyle(.plain)
                        Divider()
                        Button { focusedField = nil; showingAssignee = true } label: {
                            TaskPropertyRow(title: L("负责人", "Assignee")) { TaskActorLabel(actor: draft.assignee) }
                        }.buttonStyle(.plain)
                    }.padding(.horizontal, 16).background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 14))
                    field(L("任务说明", "Description"), prompt: L("补充目标与必要背景", "Add the goal and useful context"), text: $draft.description, key: "description")
                    Divider()
                    field(L("当前结果", "Result"), prompt: L("记录进展或交付结果", "Record progress or the outcome"), text: $draft.result, key: "result")
                    if node == nil {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(L("子任务结构", "Subtask structure")).font(.subheadline).foregroundStyle(NanoTheme.muted)
                            Picker(L("子任务结构", "Subtask structure"), selection: $draft.mode) {
                                Text(L("计划", "Plan")).tag("dag"); Text(L("探索", "Exploration")).tag("explore")
                            }.pickerStyle(.segmented)
                        }
                        if let graph, let parentID, graph.nodes.first(where: { $0.id == parentID })?.mode == "none" {
                            VStack(alignment: .leading, spacing: 10) {
                                Text(L("首次拆分的本层结构", "Structure for this first decomposition")).font(.subheadline).foregroundStyle(NanoTheme.muted)
                                Picker(L("本层结构", "Parent structure"), selection: $parentMode) {
                                    Text(L("计划", "Plan")).tag("dag"); Text(L("探索", "Exploration")).tag("explore")
                                }.pickerStyle(.segmented)
                            }
                        }
                    }
                    if showingNote || reworking || !draft.changeNote.isEmpty {
                        field(reworking ? L("返工原因 · 必填", "Rework reason · required") : L("变更说明", "Change note"), prompt: L("说明这次调整的原因", "Explain this change"), text: $draft.changeNote, key: "note")
                    } else {
                        Button { showingNote = true; focusedField = "note" } label: { Label(L("添加变更说明", "Add a change note"), systemImage: "plus") }.font(.subheadline)
                    }
                }.disabled(busy || comparison != nil)
            }.padding(24)
        }.background(NanoTheme.surface).scrollDismissesKeyboard(.interactively)
            .navigationTitle(node == nil ? L("创建任务", "Create task") : L("编辑任务", "Edit task"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(L("取消", "Cancel")) { if dirty { confirmLeave = true } else { dismiss() } }.disabled(busy) }
                ToolbarItem(placement: .confirmationAction) {
                    Button { focusedField = nil; Task { await save() } } label: {
                        if busy { ProgressView() } else { Text(L("保存", "Save")).fontWeight(.semibold) }
                    }.disabled(busy || needsRefresh || cannotSave || comparison != nil || draft.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || conversationID.isEmpty)
                }
                ToolbarItemGroup(placement: .keyboard) { Spacer(); Button(L("收起键盘", "Hide keyboard")) { focusedField = nil } }
            }
            .interactiveDismissDisabled(busy || dirty)
            .confirmationDialog(L("放弃本次修改？", "Discard changes?"), isPresented: $confirmLeave, titleVisibility: .visible) {
                Button(L("放弃修改", "Discard changes"), role: .destructive) { dismiss() }
                Button(L("继续编辑", "Keep editing"), role: .cancel) {}
            } message: { Text(L("任务尚未保存。", "Your changes have not been saved.")) }
            .sheet(isPresented: $showingStatus) { TaskStatusPicker(status: $draft.status) }
            .sheet(isPresented: $showingAssignee) { TaskActorPicker(actors: participants, selectedKey: draft.assignee?.taskKey, context: graph?.conversation.title ?? conversations.first { $0.id == conversationID }?.title ?? "") { draft.assignee = $0 } }
            .sheet(isPresented: $showingConversation) { conversationPicker }
            .navigationDestination(isPresented: $showingComparison) {
                if let comparison {
                    TaskConflictView(conflict: comparison) { resolved in
                        draft = resolved; self.comparison = nil; showingComparison = false
                        Task { await save() }
                    }
                }
            }
            .task {
                if graph == nil {
                    do { let page: ItemsPage<Conversation> = try await client.get("/im/v1/conversations"); conversations = page.items.filter { $0.can_write == true } }
                    catch { self.error = error.localizedDescription }
                }
                await loadMembers()
            }
            .onChange(of: conversationID) { _, _ in draft.assignee = nil; Task { await loadMembers() } }
    }

    private func field(_ label: String, prompt: String, text: Binding<String>, key: String, title: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(label).font(.subheadline).foregroundStyle(NanoTheme.muted)
            TextField(prompt, text: text, axis: .vertical).font(title ? .title2.weight(.semibold) : .body)
                .foregroundStyle(NanoTheme.ink).focused($focusedField, equals: key).accessibilityLabel(label)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
    private var conversationPicker: some View {
        NavigationStack {
            List(conversations) { chat in
                Button { conversationID = chat.id; showingConversation = false } label: {
                    HStack {
                        AvatarView(name: chat.title, kind: "group", size: 36)
                        Text(chat.title).foregroundStyle(NanoTheme.ink)
                        Spacer()
                        if conversationID == chat.id { Image(systemName: "checkmark") }
                    }.padding(.vertical, 6)
                }
            }.nanoList().overlay { if conversations.isEmpty { ContentUnavailableView(L("暂无可写入的会话", "No writable conversations"), systemImage: "bubble.left.and.bubble.right") } }
                .navigationTitle(L("所属会话", "Conversation")).navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L("关闭", "Close"), systemImage: "xmark") { showingConversation = false }.labelStyle(.iconOnly) } }
        }.presentationDetents([.medium, .large]).presentationDragIndicator(.visible)
    }
    private func loadMembers() async {
        guard !conversationID.isEmpty else { participants = []; return }
        let id = conversationID
        do { let chat: Conversation = try await client.get("/im/v1/conversations/\(id.pathComponent)"); if conversationID == id { participants = chat.participants } }
        catch { self.error = error.localizedDescription }
    }
    private func reload() async {
        guard let graph else { return }
        busy = true; defer { busy = false }
        do {
            let fresh = try await client.taskGraph(graph.graph_id)
            let target = fresh.nodes.first { $0.id == (node?.id ?? parentID) }
            guard let target, fresh.conversation.can_write, target.can_edit == true else {
                cannotSave = true
                error = L("任务已被删除或不可编辑，草稿保留供复制。", "This task was deleted or is no longer editable. Your draft remains available to copy.")
                return
            }
            if let baseline, node != nil {
                comparison = TaskConflict(baseline: baseline, draft: draft, latest: target)
                self.baseline = target
                showingComparison = true
            } else { creationRefreshed = true }
            self.graph = fresh; needsRefresh = false; cannotSave = false; error = nil
            requestKey = UUID().uuidString; submittedBody = nil
        } catch { self.error = error.localizedDescription }
    }
    private func save() async {
        guard !busy, !needsRefresh, !cannotSave, comparison == nil else { return }
        if draft.needsReworkReason(after: baseline) {
            error = L("从完成恢复进行中，请填写返工原因。", "Provide a rework reason before reopening completed work.")
            showingNote = true; focusedField = "note"; return
        }
        busy = true; error = nil
        var body: [String: JSONValue]
        let path: String
        if let graph {
            var operations = draft.operations(node: baseline, parentID: parentID)
            if node == nil, let parentID, graph.nodes.first(where: { $0.id == parentID })?.mode == "none" { operations.insert(.object(["op": .string("update_task"), "node_id": .string(parentID), "patch": .object(["mode": .string(parentMode)])]), at: 0) }
            body = ["base_revision": .number(Double(graph.revision)), "operations": .array(operations), "change_note": .string(draft.changeNote)]
            path = "/im/v1/task-graphs/\(graph.graph_id.pathComponent)/apply"
        } else {
            body = ["conversation_id": .string(conversationID), "title": .string(draft.title), "description": .string(draft.description), "mode": .string(draft.mode), "status": .string(draft.status), "result": .string(draft.result), "assignee": draft.assignee?.taskValue ?? .null]
            path = "/im/v1/task-graphs"
        }
        // Preserve the key for an uncertain identical submission; edited drafts are new requests.
        if let submittedBody, submittedBody != body { requestKey = UUID().uuidString }
        submittedBody = body; body["request_key"] = .string(requestKey)
        do {
            let receipt: JSONValue = try await client.send(path, body: body)
            if let id = graph?.graph_id ?? receipt["graph_id"].stringValue { _ = try await client.taskGraph(id) }
            busy = false; completed()
        } catch {
            self.error = error.localizedDescription
            needsRefresh = (error as? APIError)?.code == "version_conflict" || (error as? APIError)?.status == 409
            busy = false
            if needsRefresh { await reload() }
        }
    }
}
