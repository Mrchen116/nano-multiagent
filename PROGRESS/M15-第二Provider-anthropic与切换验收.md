# PROGRESS (Milestone: M15)

- Title: 第二 Provider（anthropic）与切换验收
- Goal: 在不改 runtime/tool/session 核心代码前提下新增 `anthropic` 协议实现与工厂接线。
- Exit Criteria:
  - `llm/protocols/anthropic/*` 落地并通过与 `openai_compat` 同一契约测试集。
  - provider 切换仅改配置（不改 runtime/tool/session 代码）。
  - OpenAI/Anthropic 双链路集成测试通过，`pytest -q` 全绿。
- Test command: `pytest -q`
- Branch: `milestone/M15`

> 说明：本文件用于记录 M15 的关键决策、证据、回滚点与 C1/C2/C3 哈希。`LOGBOOK.md` 仅记录可复用经验。

## Baseline
- Context:
  - 按执行技能要求在 worktree 中先执行 `pytest -q` 建立基线。
- Evidence:
  - Tests: `pytest -q` -> `1 failed, 171 passed, 2 skipped`
  - Failing test: `tests/contract/test_core_events_contract.py::test_runtime_event_types_are_stable`
  - Scope: 失败位于 runtime 事件契约，不在 M15 `allowed_scope`（`src/nano_multiagent/llm/**`）内。
- Decision:
  - 记录为既有基线失败，M15 期间保证“不新增失败”；Milestone 收口时再基于 rebase 后主线状态做全量 gate 复核。

### R15.1 Provider 契约测试集统一（OpenAI + Anthropic）
- Status: DONE
- Context:
  - 需要将 provider 适配层收敛到统一契约，避免 openai_compat 与 anthropic 分叉出两套行为语义。
  - Red 阶段先以 `tests/contract/test_llm_provider_contract.py` 覆盖 mapper 请求/响应、client header 与 streaming 错误语义；当时 `anthropic` 模块不存在，按预期红灯。
- Decision:
  - 新增共享契约测试入口，统一参数化 `openai_compat` 与 `anthropic`。
  - 落地 `AnthropicMapper` + `AnthropicClient` 最小实现，接口形态与 `openai_compat` 对齐（`LLMTranslator`、`ModelError`、上下文管理器）。
- Rationale:
  - 先统一契约再补 provider，能确保第二 provider 从第一天就遵循已有接口边界，而不是后续再补兼容层。
- Evidence:
  - Tests:
    - `pytest -q tests/contract/test_llm_provider_contract.py` -> `8 passed`
    - `pytest -q` -> `1 failed, 179 passed, 2 skipped`（仅保留既有基线失败：`test_core_events_contract`）
  - Entry:
    - `anthropic` 契约入口可完成 `/v1/messages` 请求映射、`X-Session-Id` 透传、错误归一化与响应解码。
- Rollback:
  - 若需重做，回退到 `272946c`（R15.1 C1 红测基线）。
- Commits: C1=`272946c`, C2=`6edbac4`, C3=`b7265b8`
- Next:
  - R15.2 增补 anthropic mapper 的边界单测（system 抽取、max_tokens 默认值、异常响应分支）。

### R15.2 新增 anthropic 协议实现（llm/protocols/anthropic）
- Status: DONE
- Context:
  - R15.1 最小实现已通过共享契约，但 mapper 仍缺少边界防护（仅 system 消息输入、非字符串 text chunk）。
  - 需在不改 runtime/tool/session 的前提下完善 anthropic 适配层健壮性。
- Decision:
  - 新增 `tests/unit/test_llm_anthropic_mapper.py`，覆盖 system 聚合、默认 max_tokens、无有效消息与响应归一化边界。
  - 在 `AnthropicMapper` 增加“至少一条非 system 消息”校验，并将 text chunk 做 `str()` 归一化。
- Rationale:
  - 让错误尽量在 provider mapper 层前置暴露，避免把无效 payload 下沉到远端接口才失败。
- Evidence:
  - Tests:
    - `pytest -q tests/unit/test_llm_anthropic_mapper.py` -> `4 passed`
    - `pytest -q tests/contract/test_llm_provider_contract.py` -> `8 passed`
    - `pytest -q` -> `1 failed, 183 passed, 2 skipped`（仅既有 runtime 基线失败）
  - Entry:
    - `AnthropicMapper` 可稳定处理 system-only 输入拦截和非字符串 text chunk，保持输出 `LLMGenerateResponse` 契约稳定。
- Rollback:
  - 若需重做，回退到 `0034698`（R15.2 C1 红测基线）。
- Commits: C1=`0034698`, C2=`7be80d3`, C3=
- Next:
  - R15.3 进行 model_registry/factory 接线与 provider 配置切换集成验收。

### R15.3 工厂接线与 provider 切换验收（配置驱动）
- Status: TODO
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
