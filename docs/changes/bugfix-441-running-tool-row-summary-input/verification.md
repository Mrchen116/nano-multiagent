# Verification Report: bugfix-441

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks complete; 8/8 incident requirements covered |
| Correctness | 7/7 scenarios covered |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: 10/10 complete. `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/tasks.md` marks every exit criterion complete, including live IM Web UI evidence, all scoped presenters, gateway relay, frontend running gate, reducer overwrite, and broad test/build gates.
- Requirement coverage: covered.
  - Running collapsed rows receive parameter summaries via presenter start detail and Gateway `tool_start` forwarding: `src/agent/platform/tools/builtins/bash.py:95`, `src/personal_assistant/main.py:3697`.
  - Running expanded rows receive parameter detail from builtin/product presenters: `src/agent/platform/tools/builtins/write.py:25`, `src/agent/platform/tools/builtins/agent.py:48`, `src/personal_assistant/tools/web_search.py:47`, `src/personal_assistant/tools/send_message.py:21`, `src/personal_assistant/tools/cron.py:281`.
  - Running result/completion markers are gated in the frontend: `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:263`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:305`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:390`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:431`, `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:464`.
  - Completion replaces running parameter detail with final result detail through normal reducer merging: `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.ts:67`.
  - Large parameter content is capped for write/memory start detail: `src/agent/platform/tools/builtins/write.py:31`, `src/agent/platform/tools/builtins/memory.py:51`.
  - `send_message` and `cron` have product-owned presenters and structured GenericCard-compatible detail: `src/personal_assistant/tools/send_message.py:18`, `src/personal_assistant/tools/cron.py:278`.
  - Contract deltas are documented for kernel, gateway, and IM under `docs/changes/bugfix-441-running-tool-row-summary-input/specs/`.
  - Live IM evidence is committed: `docs/changes/bugfix-441-running-tool-row-summary-input/M1-split-param-display/progress.md:51`.

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 工具执行中折叠行显示参数摘要 | `src/personal_assistant/main.py:3697` forwards `presentation.summary` into `tool_call.output`; builtin/product presenters emit start summaries, e.g. `src/agent/platform/tools/builtins/bash.py:100` and `src/personal_assistant/tools/web_search.py:48`. | `tests/unit/personal_assistant/test_tool_end_detail_passthrough.py:193`; live UI evidence in `progress.md:55`. | covered |
| 工具执行中展开卡显示参数 detail | `format_start.detail` is present across builtin/product presenters, e.g. `read.py:44`, `bash.py:95`, `agent.py:48`, `send_message.py:21`, `cron.py:281`; Gateway forwards it at `main.py:3700`. | `tests/unit/platform/tools/test_presentation.py:39`; `tests/unit/personal_assistant/test_send_message_tool.py:77`; `tests/unit/personal_assistant/test_cron_tool_closure.py:129`; live UI evidence in `progress.md:56`. | covered |
| 工具执行中不显示结果或完成标记 | `ToolDetailBody` passes `isRunning` at `tool-detail-renderers.tsx:544`; cards gate result regions for web_search, agent, memory, skill_manage, and task_stop. | `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx:454`, `:469`, `:484`, `:499`, `:513`; live UI evidence in `progress.md:64`. | covered |
| 工具完成后显示参数 + 结果全貌,且非 send_message/cron 完成态保持旧路径 | `format_end` paths remain the source of full detail; reducer completion overwrites running `output/detail` when final values arrive. | `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts:139`; presenter end tests in `tests/unit/platform/tools/test_presentation.py:47` and following sections. | covered |
| send_message/cron 完成态有意结构化改善,信息不少于旧裸 JSON | `send_message` end detail includes target/text/status at `send_message.py:49`; `cron` end detail merges params and result fields at `cron.py:296` and `_cron_result_detail` at `cron.py:631`. | `tests/unit/personal_assistant/test_send_message_tool.py:77`; `tests/unit/personal_assistant/test_cron_tool_closure.py:129`. | covered |
| 大字段参数片复用 cap,避免 running event/detail 撑爆链路 | `write` and `memory` start detail call `_enforce_cap`. | `tests/unit/platform/tools/test_presentation_cap.py:42`, `:55`. | covered |
| tool_end 覆盖 tool_start,避免参数片残留或错位 | Reducer spreads final event over existing call, preserving only empty input/output special cases; `detail` is replaced by final detail. | `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts:139`. | covered |

Verification commands run in this verifier worktree:

- `PYTHONDONTWRITEBYTECODE=1 pytest -q tests/unit/platform/tools/test_presentation.py tests/unit/platform/tools/test_presentation_cap.py tests/unit/platform/tools/test_presentation_golden.py tests/unit/personal_assistant/test_web_search_presenter.py tests/unit/personal_assistant/test_send_message_tool.py tests/unit/personal_assistant/test_cron_tool_closure.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py` -> 96 passed.

Frontend verification note:

- I attempted `npm run test -- src/features/chat/v2/components/tool-calls-panel.test.tsx src/features/chat/v2/chat-stream-reducer.test.ts` in the verifier worktree, but this worktree has no installed `vitest` binary (`/bin/sh: vitest: command not found`). I did not install dependencies or modify dependency state. The submitted milestone evidence records `npm run test` as 60 files / 491 tests passed and `npm run build` passed at `progress.md:52`; the relevant frontend test assertions are committed at `tool-calls-panel.test.tsx:454` and `chat-stream-reducer.test.ts:139`.

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1: `format_start` 补参数片 detail, Gateway 镜像转发, 前端 running gate, 结束路径不动 | 是 | Presenter start detail exists in `bash.py:95` and peers; Gateway mirrors summary/detail at `main.py:3697`; frontend gates at `tool-detail-renderers.tsx:544`. |
| 决策 2: 切分由 presenter 自身负责,现有全部工具逐分支对齐,大字段 cap | 是 | Builtin/product presenters own display data; `write.py:31` and `memory.py:51` reuse `_enforce_cap`; tests cover scoped presenters. |
| 决策 3: summary 纯转发,不另造语义 | 是 | Gateway maps `presentation.summary` to `output` without tool-specific logic at `main.py:3697`; tool_end mapping remains analogous at `main.py:3765`. |
| 架构边界: Gateway/PA 只通过 `agent.sdk` 产品接口使用 tool presentation; IM 不反向调用 agent | 是 | Product tools import `ToolPresentationEvent` from `agent.sdk` (`send_message.py:15`, `cron.py:33`, `web_search.py:13`); frontend only consumes IM `ToolCall.detail`. |
| 测试规范: 永久回归落在现有最低层文件,真栈截图作为一次性证据 | 是 | Existing unit/vitest files are extended; live screenshots and metadata are under unit progress/evidence, matching `docs/TESTING_GUIDE.md` temporary evidence guidance. |

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（应该修）

- None.

### SUGGESTION（可以修）

- None.
