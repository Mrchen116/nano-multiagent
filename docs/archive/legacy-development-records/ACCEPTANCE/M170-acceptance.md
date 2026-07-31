# 重建真实群聊验收运行态并复验 M141 剩余缺口（after M217）

- Scope ID: M170
- Verdict: pass
- Reviewed By: claude-main
- Run ID: `run-67b6122ad5834b32b554c32646974c63`

## Scope

基于 `/Users/czj/Repos/nano-multiagent` current-main 的 fresh rebuilt runtime，重新验收真实 Web IM 群聊主链路：群聊创建、同线程双 Agent 回复、typed mention、mention picker + 键盘选择，以及 NO_REPLY 完全静默。结论仅基于本轮 fresh runtime 证据。

## Runtime

- Chat URL: `http://127.0.0.1:18031/chat`
- Runtime root: `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime`
- Runtime DB: `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/im_service.sqlite3`
- Gateway ready check: `state=open`, quiet window `12000ms`

## User Journeys Exercised

1. 在真实浏览器打开 Web IM，并创建 `Agent M170 Alpha + Agent M170 Beta` 群聊。
2. 在同一线程发送 `@agent-m170-alpha please answer exactly as configured.`。
3. 在同一线程发送 `@agent-m170-beta please answer exactly as configured.`。
4. 在 composer 输入 `@agent:`，打开 mention picker，用 picker 路径选择 Beta，再发送 picker 消息。
5. 将 Alpha prompt 改为 `Reply exactly with NO_REPLY.`，在同一线程发送静默验证消息并检查页面是否泄漏内部状态。

## Evidence

### Fresh artifacts

- `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-result.json`
- `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-home.png`
- `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-group-panel.png`
- `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-group-thread.png`
- `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-picker.png`
- `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-no-reply.png`
- Archived run dir: `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/.staging/runs/run-67b6122ad5834b32b554c32646974c63`

### Conversation and turn outcomes

- Conversation id: `e1eb7cc2e2dc4f37851058bcda98aff6`
- Participants: user + Alpha + Beta all present in one shared thread
- Alpha turn completed with receipt `ALPHA_ACK_M170`
- Beta turn completed with receipt `BETA_ACK_M170`
- Picker turn completed with receipt `BETA_ACK_M170`
- NO_REPLY probe result: `status = passed`, `violations = []`

### Mention picker exact visible text

Live browser capture and saved rerun evidence both show the picker is user-facing label text, not internal stable token text:

- Listbox role/label: `role=listbox`, `aria-label="Mention candidates"`
- Composer ARIA while open: `aria-expanded="true"`, `aria-controls="mention-candidate-list"`, `aria-autocomplete="list"`
- Visible option 1 text:
  - `Agent M170 Alpha`
  - `Agent M170 Alpha mention`
- Visible option 2 text:
  - `Agent M170 Beta`
  - `Agent M170 Beta mention`
- Visible composer value after picking Beta: `@Agent M170 Beta `
- Persisted sent message for lookup/runtime: `@agent:agent-m170-beta please answer via picker route.`

## Acceptance Result

### 1. 群聊创建通过

- 本轮 fresh runtime 中成功创建标题为 `Agent M170 Alpha + Agent M170 Beta` 的群聊。
- 结构化结果中的 `participants` 证明三方都在同一线程。

### 2. 同线程双 Agent 回复通过

- Alpha / Beta 两个普通 mention turn 都完成了完整事件链：
  - `message.sent`
  - `relay.accepted`
  - `relay.processing`
  - `relay.report`
  - `relay.completed`
  - `message.delivered`
- 回执分别为 `ALPHA_ACK_M170` 与 `BETA_ACK_M170`。

### 3. mention picker + 键盘选择通过

- rerun 脚本本轮稳定完成，没有再在 picker 阶段超时。
- picker 可见文案是显示名；选择后 composer 显示 `@Agent M170 Beta `。
- 提交后运行态中的真实消息内容稳定落为 `@agent:agent-m170-beta please answer via picker route.`，说明 UI 显示名与后端稳定 token 的映射正确。

### 4. NO_REPLY 完全静默通过

- 本轮 `no_reply_turn.status = passed`。
- `violations = []`。
- 页面摘录未出现 `NO_REPLY`、`suppressed_by=no_reply_token`、`Agent replied`、`The latest agent response finished successfully.` 等违规文案。

### 5. 关键页面文案通过本轮复验

- 群线程页面摘录中目标文案已是 `Target: Shared thread`，不再是早前失败报告中的 `Multiple participants` 工程化文案。
- picker 也不再向用户暴露内部 `@agent:...` token 作为主要可见文本。

## Code/behavior notes tied to this pass

- Picker rerun lookup now waits on the stable stored payload text rather than the visible display-label draft: `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
- Frontend mention UX keeps visible labels while encoding stable tokens only at send time: `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/chat/components/message-pane.tsx:358`, `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/chat/components/message-pane.tsx:640`, `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/chat/components/message-pane.tsx:705`, `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/chat/components/message-pane.tsx:828`

## Verdict

M170 本轮 fresh current-main 真实前端验收通过。此前 M170 报告中的 major 问题（NO_REPLY 泄漏、picker fresh rerun 不稳定）已在本轮闭环。当前不需要再为 M170 派生新的修复 milestone。
