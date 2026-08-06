# bugfix-508: Code Review

## Review scope

- Base: `0e79d9b4a264703807c25f25ec121a8b000c5f11`
- Head: 本 unit 的未提交工作树
- Review mode: `full`
- Included commits: None
- Included uncommitted files: 本 unit 的前端、Gateway、测试、delta-spec 与 canonical spec 修改。

## Round 1

- Result: Pass after fixes
- Findings:
  - [P1] Web IM 群 relay 曾将不同 node 的 Agent 全部推到首个 Agent 的 node，跨节点群聊无法让每个 Agent 收到 `/new`。
  - [P1] 回复某个 Agent 的文本 `/new` 会被裸命令例外误识别为全群重开。
  - [P1] `group_reply_policy=ALWAYS` 会使裸 `/compact` 绕过明确目标门控。
  - [P1] Web IM 结构化 `<mention/> /new` 未被 Gateway 控制命令解析，不能只重开被点名 Agent。
  - [P2] slash picker 从单聊切到群聊时没有重算 `/new` 的说明。
  - [P2] 规范曾把 Web IM 的全群 `/new` 误扩展到外部飞书群聊；外部通道并不做参与 Agent fan-out。
- Resolutions:
  - group relay task 按 participant Agent 的 configured node 创建，HTTP route 按每条 task 的 node 推送；新增跨 node 路由回归测试。
  - 仅内置 Web IM、无结构化 mention / reply 的精确裸 `/new` 允许全群重开；定向 `/new` 与所有 `/compact` 在 `ALWAYS` 之前强制目标校验。
  - Gateway 控制命令解析剥离前端标准结构化 agent mention；新增定向 XML mention 回归测试。
  - `isGroup` 加入 memo 依赖并新增 rerender 测试；外部通道 current spec 与 delta 均恢复为原有 Bot 定向规则。
- Tests after fixes:
  - `pytest -q tests/unit/personal_assistant/test_gateway_stop_command.py tests/unit/IM/test_messages_broadcast.py` — 25 passed
  - `npm --prefix src/IM/frontend test -- --run src/features/chat/components/slash-picker.test.tsx src/features/chat/components/message-pane.test.tsx` — 107 passed
  - `npm --prefix src/IM/frontend run build` — passed
  - `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` — passed

## Closure

- Follow-up mode: Phase-2 independent verifier rechecked all six Round-1 findings after the fixes.
- Findings closed: 6/6
- Remaining findings: None
- Final result: Pass
