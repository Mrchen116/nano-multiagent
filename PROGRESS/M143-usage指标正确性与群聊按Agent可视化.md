# M143 Progress - Usage 指标正确性与群聊按 Agent 可视化

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M143`
- 已确认 branch：`milestone/M143`
- 已确认约束：不修改 `data/dev-tasks.json`；不创建额外 worktree；只在 canonical repo / 指定 milestone worktree 内工作。
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`docs/需求.md`（token/turn 部分）、`docs/IM-SPEC.md`、`ACCEPTANCE/M104-acceptance.md`、`PROGRESS/M137-Web-IM-token-turn与附件统一路径交付.md`。
- 当前基线判断：
  - workspace total 很可能错误地用 `selfUserId` 当 `owner_id` 查询；真实 owner 聚合因此漏数。
  - relay-backed 真链路没有把 kernel run usage 回填到 IM metrics，completion tokens 因此仍可能停在 0。
  - 前端 usage 查询只在初次加载读取，没有随 message / relay 完成事件刷新。
  - 群聊缺少按 Agent usage 的可见展示。

## 执行策略
1. 先用红测钉死 relay 真 usage、owner 聚合、群聊按 Agent 展示三个缺口。
2. 最小实现只收敛到 IM metrics 写入、前端 usage 读取/刷新、群聊 usage 展示，不扩散到无关协议层。
3. 用最小相关测试集 + 真链路 acceptance 证据 + M143 ACCEPTANCE 报告收口。

### R1 owner/workspace 与真实 completion usage
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/unit/test_nodes_metrics_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/unit/test_gateway_handler.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/unit/personal_assistant/test_main.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_nodes_metrics_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_m136_group_chat_flow.py && npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx`
  - Entry: 待补
- Rollback:
- Commits: C1=, C2=, C3=
- Next: 补红测并实现 relay 完成后的真实 usage 记录。

### R2 This chat / Workspace total 实时值
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: 同 `test_command`
  - Entry: 待补
- Rollback:
- Commits: C1=, C2=, C3=
- Next: 修正前端 owner 聚合与 usage invalidation。

### R3 群聊按 Agent usage 与验收收口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: 同 `test_command`
  - Entry: 待补
- Rollback:
- Commits: C1=, C2=, C3=
- Next: 输出 ACCEPTANCE 报告并尝试集成到 main。
