# refactor-345: compact-in-agent-loop

## Relations

- Depends on: feat-334-tool-result-budget
- Related:

## 原始诉求

> 我们要参考cc的架构，虽然我们现在只有完整compact，但是也要放在loop中正确的位置。

当前 `AgentLoop.run()` 的 `while True` 循环内部没有任何上下文治理机制。`compaction` 只在 `runtime.py` 的 turn 开始前触发一次（`_preflight_compaction`），且 `_post_turn_check_overflow` 是死代码。当一次 turn 内产生多轮 tool calling 迭代时，上下文可能在 loop 内部持续膨胀直到溢出，没有任何恢复路径。

## 澄清记录

- Q1: 范围边界——是否只把现有完整 compact 移入 loop 内部，还是一并引入 CC 的其他上下文治理层？
  A: 只做现有完整 compact 的触发位置迁移，不新增 microcompact、snip 等机制。
- Q2: loop 内部的触发策略——主动检查还是被动恢复？
  A: 每次 LLM 调用前主动检查 token，超过阈值就 compact 后继续。
- Q3: runtime 层的 `_preflight_compaction` 是否保留？
  A: 不保留。参考 CC 架构，全部让 loop 内部接管。CC 的 `query.ts` 没有外层 preflight，所有上下文治理都在 `while(true)` 每次迭代开头执行。
- Q4: compact 发生时是否保留前端/REPL 提示？
  A: 保留 compact boundary 提示信息。
- Q5: 是否需要区分本地完整历史与发给 LLM 的活跃上下文？
  A: 引入。loop 内部维护独立的 `llm_messages`（活跃上下文），compact 只操作它；`session_histories`/entries 保留完整历史不变。

## 现状痛点

1. **loop 内部无上下文治理**。`AgentLoop.run()` 的 `while True` 每次 tool calling 迭代都会追加 tool results 到 `llm_messages`，但没有任何 token 检查或 compact 触发点。单轮内多轮工具调用时上下文持续膨胀。
2. **preflight 是单次检查**。`runtime.py` 的 `_preflight_compaction` 只在 turn 开始前执行一次，无法应对 loop 执行过程中的增量膨胀。
3. **`_post_turn_check_overflow` 是死代码**。该方法只定义了但没有任何调用方，overflow 后没有任何恢复路径。
4. **compact 破坏滚动回溯**。当前 compact 直接替换 `session_histories`，被压缩的旧历史从内存中消失，REPL 无法回溯。

## 目标状态

参考 Claude Code `query.ts` 架构：

1. **loop 内部每次 LLM 调用前主动检查 token**。`while True` 每轮迭代开头估算当前 `llm_messages` 的 token 数，超过阈值就触发 compact。
2. **compact 后继续当前迭代**。用压缩后的 `llm_messages` 替换原有上下文，不中断当前 turn。
3. **分离活跃上下文与完整历史**。loop 内部维护独立的 `llm_messages`（实际发给 LLM），compact 只操作它；`session_histories` 和 entries 保留完整历史不变，支持 REPL 滚动回溯。
4. **保留 compact boundary 提示**。compact 发生后 yield 边界消息，用户知道上下文已被压缩。
5. **移除 runtime 层 preflight**。`_preflight_compaction` 不再需要在 turn 开始前执行，全部逻辑内聚到 loop。

## 影响范围

- `src/agent/core/agent/loop.py`：核心变更点，新增 token 估算、compact 触发、独立 `llm_messages` 管理。
- `src/agent/core/agent/runtime.py`：移除 `_preflight_compaction` 调用和相关逻辑，`_post_turn_check_overflow` 清理。
- `src/agent/core/agent/compaction/applier.py`：可能需要适配 loop 内部调用方式（不再操作 `session_histories`，只返回压缩后的 messages）。
- `src/agent/core/agent/compaction/planner.py`：当前 `kept_events` 始终为空，行为不变。

## 迁移与回滚策略

- **行为不变保证**：compact 的核心逻辑（planner + summarizer + prompts）完全复用，只是触发位置和上下文管理对象移动。
- **回滚**：若 loop 内部 compact 引入问题，可回滚到 runtime preflight + loop 不做检查的状态。回滚只需还原 `loop.py` 和 `runtime.py` 的调用点，不涉及 compact 核心逻辑。
- **验证**：通过单元测试验证（1）loop 内部 token 超限后触发 compact；（2）compact 后 iteration 继续；（3）session history 不被修改。
