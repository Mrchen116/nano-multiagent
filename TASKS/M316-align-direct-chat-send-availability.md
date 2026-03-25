# M316 Align direct-chat send availability with target agent node status

## Context
- Milestone: `M316`
- Goal: direct-agent 会话发送可用性与重试门禁必须按“当前会话目标 agent 节点”判断，而不是 bootstrap 默认节点状态。
- Scope: `src/IM/frontend/src/features/chat/`

## Roadpoints

### R1 Direct-chat send/retry gating source of truth
- Status: DONE
- Acceptance:
  - direct-agent 会话在目标 agent 节点 online 时，composer 与 retry 路径可用。
  - direct-agent 会话在目标 agent 节点 offline/unbound 时，composer 与 retry 路径禁用。
  - send 可用性判断从当前会话目标节点解析，不依赖无关 bootstrap 默认状态。
  - 补充 mismatch 回归测试（bootstrap 与目标会话节点状态冲突场景）。
- Tests Plan:
  - 在既有 `chat-workspace-page.test.ts` 中新增 mismatch 回归用例（不新建测试文件）。
  - 运行 `npm test -- --run src/features/chat/chat-workspace-page.test.ts` 验证新增用例。
- DoD:
  - C1/C2/C3 三提交完成。
  - 新增回归用例覆盖 mismatch case，并在实现后通过。
