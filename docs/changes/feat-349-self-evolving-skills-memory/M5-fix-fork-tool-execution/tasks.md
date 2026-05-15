# feat-349-M5: fix-fork-tool-execution — Tasks

## 目标

修复两个 post-acceptance bug（round 2 验收报告触发）：

1. **主 bug [BLOCKING]**: Fork AgentLoop 的 `tool_registry` 为 `None`，导致 LLM 返回 `tool_use`（round 1）后，loop 走 `tool_registry_unavailable` 出口，round 2 永不发生，`skill_manage` 从未执行，`.nanocode/skills/` / `.nanocode/memory/` 永远空。

   根因：`app.py` 里 `AgentRuntime` 先构造（此时 `tool_registry=None`），再通过 `bind_tool_registry` 后绑定。但 `bind_tool_registry` 只更新 `self._loop`，`self._context_fork._loop._tool_registry` 一直是 `None`。

2. **次 bug [MINOR]**: `_format_self_evolution_review` 读 `event.get("data", {})` 寻找 `reviewed_skills`，但 SSE 事件是 flat dict，字段在顶层。导致 subject 永远是 `"self-evolution"` 而非 `"skills"`。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 失败测试：fork loop 因 tool_registry=None 提前退出 + echo wording bug | DONE |
| R2 | 修复实现：bind_tool_registry 同步到 _context_fork + fix background_runs | DONE |
| R3 | 文档 + 全量回归确认 | DONE |

## 退出标准

- `bind_tool_registry` 同时更新 `self._context_fork._loop._tool_registry`；
- 新增单元测试：模拟 bind_tool_registry 调用后 fork loop 能进入 round 2 并执行工具；
- `_format_self_evolution_review` 从顶层 event 读 `reviewed_skills`/`reviewed_memory`；
- 全量 `tests/unit/` 无新增失败；
- E2E: LC managed 模式 `skill_nudge_interval: 3`，发 3 条消息后 `.nanocode/skills/` 出现 SKILL.md 文件。

## 测试策略

后端逻辑 bug，策略：
- C1: 失败单元测试，精确复现 `tool_registry=None` 导致 loop round 2 缺失
- C2: 最小修复；全量单测绿
- E2E: LC managed 模式验证真实文件落盘

## 前端

N/A（纯后端 bug）
