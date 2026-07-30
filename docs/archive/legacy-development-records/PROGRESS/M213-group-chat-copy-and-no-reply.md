# M213 群聊文案与 NO_REPLY 收口进展

## Milestone summary
- Goal: 修复真实群聊 NO_REPLY 对普通用户的可见残留，并把群聊线程与 mention picker 收口为产品化文案。
- Scope: 仅修改前端聊天相关代码、测试，以及本 milestone 的 TASKS/PROGRESS 记录。
- Non-goals: 不做产品验收，不修改 `data/dev-tasks.json`，不触碰 acceptance 脚本。

### R1 群聊线程与列表隐藏 NO_REPLY 内部态
- Context: M170 真实群聊仍会在群聊列表/线程头部暴露工程化 ownership 与 `Multiple participants`，同时必须继续保证 `NO_REPLY` SSE 不生成任何可见 agent 成功态。
- Decision: 保留现有 `toRelayAgentMessage` 的 NO_REPLY 过滤，并在群聊语义/展示层新增最小清洗：把工程化 ownership 兜底替换为产品化说明，把群聊 target 文案统一为 `Shared thread`。
- Rationale: 问题是普通用户真实可见文本泄漏，不需要改协议；直接在前端语义层与展示层收口，能最小化影响 direct chat 与发送链路。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M213/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build`
  - Entry: 群聊 SSE 的 `relay.processing/report NO_REPLY` 不会生成线程消息，群聊列表/线程头部不再显示 `Using your main agent ... ready to chat` 与 `Target: Multiple participants`。
- Rollback: `f808027`。
- Commits: C1=`f808027`, C2=`38d6c8c`, C3=
- Next: 继续收口 mention picker 与输入框中的稳定 token 可见泄漏。

### R2 mention picker 与群聊可见文案产品化
- Context: 群聊 mention picker 与输入框仍直接显示 `@agent:...` 稳定 token，用户可见层面带有工程实现细节；但发送 payload 仍必须保持稳定 mention 协议。
- Decision: 将 composer/picker 的显示态改为 `@<产品名>`，提交时再把显示态编码回稳定 token；同时保留键盘选择和整 token Backspace 删除体验。
- Rationale: 显示态与发送态分离能同时满足产品化文案与后端兼容，不需要改接口结构。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M213/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build`
  - Entry: picker、输入框和群聊头部只显示产品化名称/文案；发送 `onSend` 仍收到 `@agent:<id>` payload。
- Rollback: `0ecef2a`。
- Commits: C1=`0ecef2a`, C2=`4ca4a2a`, C3=
- Next: 提交本 milestone 文档收口并准备整体集成。
