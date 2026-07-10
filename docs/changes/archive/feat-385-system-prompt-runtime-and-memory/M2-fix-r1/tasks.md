# feat-385-M2 fix-r1: tasks

## 目标

修复 reviewer round 1 + verifier round 1 验收回来的 4 个问题:
1. I1: `MemoryStore.format_for_prompt` 空内容时返回 None，避免空 banner
2. I2: `/v1/prompt-preview` volatile 段以占位符呈现 + 末尾追加说明
3. W1: `AgentLoop` 接 `on_compaction` callback，compaction 后回调 `_invalidate_memory_snapshot`
4. W2: 真彻删 `LOCAL_CODING_SYSTEM_PROMPT` / `CODING_SYSTEM_PROMPT` / `_DEFAULT_TOOL_SPECS` 常量 + 退役 test_agent_prompting.py 残留引用

## 退出标准

- `MemoryStore.format_for_prompt` 空内容返回 None 单测通过
- `AgentLoop` compaction 成功后触发 `on_compaction` callback 单测通过
- `pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e"` 全绿
- `grep -E "LOCAL_CODING_SYSTEM_PROMPT|CODING_SYSTEM_PROMPT|_DEFAULT_TOOL_SPECS" src/` 无命中
- `/v1/prompt-preview` 端点单测：volatile 段以占位符呈现 + 末尾有说明文字

## 测试策略

- 后端逻辑 (I1/I2/W1/W2) 均用单元测试覆盖
- W2 通过 grep 验证无残留引用

## Roadpoints

### R1 — I1: MemoryStore.format_for_prompt 空内容返回 None
- 状态: DONE
- 影响文件: `src/agent/core/memory/store.py`
- 测试文件: `tests/unit/agent/` (memory 相关)

### R2 — I2: prompt-preview volatile 段占位符 + 末尾说明
- 状态: DONE
- 影响文件: `src/agent/platform/http_api/routes/global_routes.py`
- 测试文件: `tests/unit/platform/` 或新建 `tests/unit/test_prompt_preview.py`

### R3 — W1: AgentLoop on_compaction callback 接通
- 状态: DONE
- 影响文件: `src/agent/core/agent/loop.py`, `src/agent/core/agent/runtime.py`
- 测试文件: `tests/unit/test_agent_loop.py`

### R4 — W2: 真彻删老常量 + 退役 test_agent_prompting.py 残留引用
- 状态: DONE
- 影响文件: `src/agent/core/agent/prompting.py`, `tests/unit/test_agent_prompting.py`
