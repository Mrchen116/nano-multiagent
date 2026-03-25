# M316 Align direct-chat send availability with target agent node status

## Startup
- 已阅读并遵守：`SPEC.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 基线命令（按派发）`npm test -- --run src/features/chat/chat-workspace-page.test.tsx` 无法执行（文件名已是 `.test.ts`）。
- 实际门禁命令：`npm test -- --run src/features/chat/chat-workspace-page.test.ts`。

### R1.1 Direct-chat 发送可用性按目标 agent 节点解析
- Context: 页面 sendAvailability 与 retry 可达性依赖 bootstrap 状态，导致 direct-agent 会话在目标节点 online 时仍显示 `Chat unavailable`。
- Decision:
  - `ChatWorkspacePage` 发送可用性优先读取当前 direct-agent 会话的 `node_id/node_status`，缺省旧数据才回退 bootstrap。
  - `im-chat-api` 在 `listConversations` 中按会话目标 agent 解析绑定节点状态，并写入会话 summary。
  - `im-chat-api.sendMessage` 的前置可发送校验改为按当前会话目标节点解析，避免 bootstrap 误判。
- Rationale: 让前端可发送状态、重试门禁和 Settings 节点在线语义对齐到“当前会话真实目标”。
- Evidence:
  - Tests: `cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts`
  - Result: 新增 M316 mismatch 回归用例通过；该文件仍有 2 个既有失败（与 M316 改动无关，基线已存在）。
- Rollback: 回退到 `0be58cc`（仅含 C1 测试提交）可撤销实现变更。
- Commits: C1=`0be58cc`, C2=`c81f0d2`, C3=`(this commit)`
- Next: 更新 `data/dev-tasks.json` 为 `DONE` 并回传结果摘要。
