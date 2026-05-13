# refactor-345 — 验收报告 (Round 1)

> 对齐: motivation.md / design.md 的验收标准
> 日期: 2026-05-13
> 模式: full (纯后端逻辑重构，无前端 UI/用户旅程)

## Verdict

pass

## 用户旅程体验

本单元为纯后端逻辑重构，无用户可见的 UI/前端入口。用户旅程通过以下替代验证方式完成：

### 旅程 1: loop 内部 token 超限触发 compact
- **操作**: 运行 `pytest tests/unit/test_loop_compact.py::test_loop_triggers_compact_when_token_threshold_exceeded -xvs`
- **期望**: 当 `llm_messages` 估算 token 超过阈值时，loop 内部触发 compact 并 yield compact summary message
- **实际**: 测试通过。Fake planner 返回 dropping all events 的计划，summarizer 返回固定 summary，loop 正确 yield 了带 `is_compact_summary=True` metadata 的 Message
- **证据**: `test_loop_compact.py:143` assert 通过

### 旅程 2: compact 后 iteration 继续
- **操作**: 运行 `pytest tests/unit/test_loop_compact.py::test_loop_continues_iteration_after_compact -xvs`
- **期望**: compact 后 loop 不中断，继续当前 turn 的 LLM 调用并返回 assistant 响应
- **实际**: 测试通过。compact 后 FakeLLMClient 返回 "after-compact"，最终 `result.messages[-1].content == "after-compact"`
- **证据**: `test_loop_compact.py:168` assert 通过

### 旅程 3: session history 不被修改
- **操作**: 运行 `pytest tests/unit/test_loop_compact.py::test_loop_compact_does_not_modify_session_history -xvs`
- **期望**: compact 只修改内部 `llm_messages`，不修改传入的 `state.history_messages`
- **实际**: 测试通过。`state.history_messages` 与原始 history 完全相等，长度保持 10
- **证据**: `test_loop_compact.py:196-197` assert 通过

### 旅程 4: runtime 消费 summary msg 时正确写 compact_boundary
- **操作**: 运行 `pytest tests/unit/test_runtime_compact_boundary.py::test_runtime_writes_compact_boundary_when_consuming_summary_msg -xvs`
- **期望**: runtime 在消费 loop yield 的 compact summary message 时，先向 JSONL 写入 `compact_boundary` entry，再写入 summary turn entry
- **实际**: 测试通过。JSONL 中检测到 1 条 `CompactionEntry`，`reason == "threshold"`
- **证据**: `test_runtime_compact_boundary.py:132-134` assert 通过

### 旅程 5: system prompt 在 compact 后不丢失
- **操作**: 运行 `pytest tests/unit/test_loop_compact.py::test_loop_preserves_system_prompt_after_compact -xvs`
- **期望**: compact 后每次 LLM 请求的 `messages[0]` 仍然是 system prompt
- **实际**: 测试通过。所有 LLM request 的 `messages[0].role == "system"` 且包含原始 system prompt 文本
- **证据**: `test_loop_compact.py:227-228` assert 通过

## 问题清单

无问题。

## 验收标准覆盖

| ID | 验收项 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| R1 | loop 内 token 超限触发 compact | 单元测试 `test_loop_triggers_compact_when_token_threshold_exceeded` | `test_loop_compact.py:143` assert 通过 | pass | 使用 Fake 组件注入，token 阈值设低强制触发 |
| R2 | compact 后 iteration 继续 | 单元测试 `test_loop_continues_iteration_after_compact` | `test_loop_compact.py:168` assert 通过 | pass | compact 后 assistant 响应正常返回 |
| R3 | session history 不被修改 | 单元测试 `test_loop_compact_does_not_modify_session_history` | `test_loop_compact.py:196-197` assert 通过 | pass | `state.history_messages` 引用未变 |
| R4 | runtime 消费 summary msg 时正确写 compact_boundary | 单元测试 `test_runtime_writes_compact_boundary_when_consuming_summary_msg` | `test_runtime_compact_boundary.py:132-134` assert 通过 | pass | JSONL 中检测到 CompactionEntry |
| R5 | system prompt 在 compact 后不丢失 | 单元测试 `test_loop_preserves_system_prompt_after_compact` | `test_loop_compact.py:227-228` assert 通过 | pass | 所有 LLM request 含 system message |

## 行动账本

| 桶 | 计数 | 关键内容 |
|---|---|---|
| READ(文档/源码) | 5 | motivation.md, design.md, loop.py diff, runtime.py diff, prompting.py diff |
| START_SERVICE / RESTART_SERVICE | 0 | 本单元无常驻服务 (design.md §Runbook for Reviewer 明确说明) |
| BROWSE / INVOKE(用户旅程) | 0 | 纯后端重构，无浏览器/CLI 用户旅程 |
| CAPTURE(取证) | 0 | 测试输出即为证据 |
| SHELL_MUTATION(改机器状态) | 0 | 无 |
| SENDMESSAGE 给 orchestrator | 0 | 无 |

## 环境声明

| 服务 | 动作 | PID | 端口 | commit hash |
|---|---|---|---|---|
| 无 | N/A | N/A | N/A | e55da366 |

留下的临时文件 / 占用端口 / 后续 reviewer 需要知道的状态:

- 无。本单元不涉及常驻服务或端口占用。

## 上层文档同步

- [x] `SPEC.md`（架构总览）：无需更新 —— 本单元为内部实现重构，不涉及四个顶层包职责或部署图变更
- [x] `docs/内核设计SPEC.md`（agent 内核）：无需更新 —— loop/runtime 的交互契约未变，只是内部调用位置移动
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新 —— 启动命令、架构总览无变化
- [x] 相关产品 SPEC（CodingCLI / NodeGateway / IM 等）：无需更新 —— 本单元只改 agent core 内部逻辑，产品层无感知
