# bugfix-712: 验收与合并交付

## 2026-11-05 用户确认

用户在 feat-711 隔离测试服务查看真实原生轨迹后回复：“ok，这个pr把bugfix-712-trajectory-history-prepend也带上，归档了”。据此完成本 unit 的用户验收并归档，统一由 [PR #466](https://github.com/Mrchen116/nano-multiagent/pull/466) 交付。

## 已集成范围

- 原修复来源：[PR #467](https://github.com/Mrchen116/nano-multiagent/pull/467)，提交 `35f43743a0384fc498d69f82711664deac86f3b8`。
- feat-711 集成提交：`a4533edea`；本次归档基线 `09b71b30633c31bbcf5bfc8823cdf7b5606c595a` 已包含原修复。
- 改动维持原范围：hidden contribution 及快照过滤、公开 assembler 分页回归。本次没有新的产品行为或 spec delta，恢复的既有契约仍见 [原生轨迹](../../../specs/im/agent-work.md)。

## 真实工作页证据

- 隔离服务 `http://127.0.0.1:52521`，全新 Agent `window-visible-d71f6826`；未复用已有 Agent 的会话或 Notes。
- 原生主会话 `75ebed1f-be78-42e8-b788-a771146d0a27`，工作页实际显示初始系统提示词、runtime context、请求与工具记录、两次压缩以及第三轮恢复原文的 History 结果。
- 真实消息经 IM → Inbox → RuntimeClient 执行。两次公开 `/compact` 后分别正常重启测试节点，最终公开回复精确为 `青岚-6147`、`橙色`、`秋汀-3926` 三行。该运行同时验证 feat-711 的窗口引用；本 unit 只据此记录真实轨迹可查看，不把手动换窗说成自动压力压缩。
- 本机证据目录 `/tmp/feat711-web-visible/`：`clean-start.json`、`checks.json`、`native-events.json`、`finish-reply.json`、`visible-trajectory.jpg`。原始运行数据和截图不入仓。
- 原始 all-split / repeated-prepend 等确定性分页保护及独立审查保留，见 [code-review.md](code-review.md)；不声称本次 Web 会话逐一实玩了所有分页切点，也不声称重放了最初截图中的私有会话。

## 状态边界

归档前在集成分支复跑 trajectory-ui、identity 和 task-execution-limits：5 files / 23 tests passed。CI `41963461005` 的全量结果保留为 1161 passed / 2 failed：identity 的基准过期时间与后续真实时钟跨秒，另一个 Task 运行限额测试等待超时；本次固定 identity fixture 的 Date，保留所有原断言及 Task 测试。当前 PR 需以归档提交后的 CI 结果为准，不把窄测试通过改写为原全量通过。

Completed / archived，随 PR #466 审查和合入；不单独合并 PR #467，不代表生产部署。用户要求保留的测试服务和开发 worktree 继续保留，PR CI 状态以当前 PR 检查为准。
