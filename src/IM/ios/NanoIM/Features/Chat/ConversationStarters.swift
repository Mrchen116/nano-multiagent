import SwiftUI

struct ConversationStarters: View {
    let store: ChatStore
    let conversation: Conversation?
    let canStart: Bool
    let start: (String) -> Void
    @State private var ownerAgent: Contact?
    @State private var needsRole = false
    @State private var deferred = false
    private var personal: Bool { ownerAgent?.role == "personal" }

    var body: some View {
        Group {
            if let agent = ownerAgent, personal || (needsRole && !deferred) {
                VStack(alignment: .leading, spacing: 12) {
                    AssistantPortrait(personal: personal, seed: agent.agent_id ?? agent.user_id, selected: agent.avatar_variant, size: 62)
                    Text(personal ? L("和\(agent.display_name)，从一件小事开始。", "Start small with \(agent.display_name).") : L("先和\(agent.display_name)对齐职责", "Agree on \(agent.display_name)’s responsibilities"))
                        .font(.title2.bold()).fixedSize(horizontal: false, vertical: true)
                    if personal {
                        starter("pencil.line", L("理清一个想法", "Untangle an idea"), L("我有个还没想清楚的想法，想和你一起理一理。请先问我想做什么，一次问一个问题。", "I have an idea I haven’t quite figured out. Help me think it through. Start by asking what I want to do, one question at a time."))
                        starter("calendar", L("安排接下来的一周", "Plan the week ahead"), L("帮我安排接下来的一周吧。先问我有哪些想做的事、截止时间和可用时间，再一起排个轻松可行的计划。", "Help me plan the week ahead. First ask about what I want to do, my deadlines, and the time I have, then help me make a manageable plan."))
                        starter("checklist", L("找到第一步", "Find a first step"), L("我想推进一件事，但不知道从哪里开始。先问问我的目标和现在的情况，再帮我找到今天就能做的第一步。", "I want to move something forward but don’t know where to start. Ask about my goal and where I am now, then help me find one step I can take today."))
                    }
                    if needsRole && !deferred {
                        if personal { DisclosureGroup(L("聊聊长期合作", "Discuss working together")) { agreement } }
                        else { agreement }
                    }
                    Text(canStart ? L("点选后可在输入框编辑，再发送。", "Pick a draft, then edit and send it.") : L("输入框里已有草稿，可以接着写。", "Keep going with your current draft."))
                        .font(.footnote).foregroundStyle(NanoTheme.muted)
                }.frame(maxWidth: .infinity, alignment: .leading).padding(16)
                    .background(NanoTheme.surface, in: RoundedRectangle(cornerRadius: 16))
            } else {
                Text(L("还没有消息", "No messages yet")).font(.callout).foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity).padding(.vertical, 24).accessibilityIdentifier("conversation.empty")
            }
        }.task(id: conversation?.id) { await resolveAgent() }
    }
    private var agreement: some View {
        VStack(alignment: .leading, spacing: 6) {
            starter("bubble.left.and.text.bubble.right", personal ? L("先介绍一下自己", "Introduce myself") : L("聊聊工作背景和目标", "Discuss the context and goals"), personal ? L("我想先让你了解我，再一起讨论你可以怎样长期帮助我。请从我目前的工作、目标或困扰开始，一次问我一个问题。", "I would like you to get to know me and discuss how you can help over time. Start with my current work, goals or difficulties, and ask one question at a time.") : L("我们先对齐你的工作职责。请了解工作背景、我希望你负责的结果，以及与其他人的分工，一次只问一个关键问题。", "Let’s agree on your responsibilities. Learn about the work, the outcomes I want you to own and the division of work. Ask one focused question at a time."))
            starter("list.clipboard", personal ? L("我已有想交给你的长期职责", "I have an ongoing responsibility in mind") : L("我已有明确的职责安排", "I already have responsibilities in mind"), personal ? L("我想和你约定一项长期职责。请先听我介绍希望你持续负责的事情和协作边界，整理后交给我确认，再保存。", "I would like to agree on an ongoing responsibility. First listen to what I want you to own and our collaboration boundaries, then draft an agreement for me to confirm before saving.") : L("我有明确的长期职责安排要交给你。请先听我介绍职责范围、交付标准和协作边界，整理成约定供我确认，再保存。", "I have ongoing responsibilities to assign to you. First listen to the scope, delivery expectations and collaboration boundaries. Draft an agreement for me to confirm before saving."))
            Button(L("稍后再聊", "Maybe later")) { deferred = true }.font(.caption)
        }
    }
    private func starter(_ icon: String, _ title: String, _ prompt: String) -> some View {
        Button { if canStart { start(prompt) } } label: {
            HStack(spacing: 10) {
                Image(systemName: icon).frame(width: 24).foregroundStyle(NanoTheme.accent)
                Text(title).font(.subheadline.weight(.medium)).foregroundStyle(NanoTheme.ink)
                Spacer()
                Image(systemName: "arrow.up.left").font(.caption).foregroundStyle(.secondary)
            }.padding(10).background(NanoTheme.canvas, in: RoundedRectangle(cornerRadius: 10))
        }.buttonStyle(.plain).disabled(!canStart)
    }
    private func resolveAgent() async {
        ownerAgent = nil; needsRole = false; deferred = false
        guard let conversation, conversation.can_write != false, conversation.is_observer != true, let actor = conversation.peerAgent else { return }
        do {
            let contacts = try await store.client.contacts(kind: "agent", search: actor.id)
            try Task.checkCancellation()
            guard let agent = contacts.first(where: { $0.agent_id == actor.id }),
                  agent.owner_id == store.user.owner_id || agent.owner_id == store.user.id,
                  agent.role == "personal" || agent.work_mode == "global" else { return }
            ownerAgent = agent
            if agent.status == "online" {
                let role: AgentRoleDocument = try await store.client.get(agentPath(actor.id) + "/role")
                try Task.checkCancellation()
                needsRole = role.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            }
        } catch { }
    }
}
