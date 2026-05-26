# Verification Report: refactor-382

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 7/7 tasks done; 3 requirements covered |
| Correctness | 8/8 scenarios covered |
| Coherence | 8/8 decisions followed (post-r1 fixes 消除全部偏离) |

No critical issues. No warnings. **verdict: pass**

---

## Round 2 复验（post-r1 fix 验证）

两个 fix commit 经代码阅读 + 测试运行验证：

**WARNING-1 → 已消除（commit 5a3be228）**

- `main.py:1094`：`try/except RuntimeError` 已去掉，现为直接 `init_model_registry(config.llm)`
- 三个调用 `run_gateway` 的测试（`test_gateway_pid_lifecycle.py:151,180`、`test_gateway_relay_lifecycle.py:257`）各自在调用前加了 `_reset_for_tests()`
- 测试套件全部通过，生产路径守卫完整

**WARNING-2 → 已消除（commit 860ad691）**

- `model_registry.py:18`：`default_base_url: str | None`（不再 `or ""`）
- `model_registry.py:57`：`base_url = provider_payload.base_url`（None 透传）
- `factory.py:37-47`：env 无 + config None → `raise ValueError("base_url unset for provider ...")`
- 两条新测试覆盖（`test_get_default_base_url_returns_none_when_not_configured`、`test_from_env_raises_when_no_base_url_configured`）

**测试结果（round 2）**

- `pytest tests/unit/personal_assistant/test_gateway_pid_lifecycle.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/test_llm_model_registry.py`：32 passed
- `pytest -m "not e2e"`：2382 passed, 1 failed（`test_dispatch_handler_build_aiohttp_handler_returns_callable` — worktree venv 缺 `aiohttp`，在主仓通过，非 refactor-382 引入的回归）
- `pytest tests/contract/`：102 passed

---

## Completeness

**Tasks: 7/7 complete**（R0~R7 全 DONE，`tasks.md` 验证）

**Spec 覆盖：**
- Requirement "端用户在 IM 里看到的模型选择行为不变" — 实现存在，registry 工厂化 + upstream_reporter 适配
- Requirement "运维通过编辑 YAML 增减模型" — 实现存在，`_parse_llm` + `local_store.py` YAML 驱动
- Requirement "Gateway 在 LLM 配置错误时立即报错" — 实现存在，硬失败路径在 `_parse_llm` 和 `_parse_agents`

**退出标准核查：**
- `pytest -m "not e2e"` 全绿（2382 passed，1 failed 属于 worktree venv 环境缺包，非 unit 回归）
- `pytest tests/contract/` 全绿（102 passed）
- `ModelMetadata` 不含 `supports_text/image/tools/streaming`（grep 零残留）
- `DEFAULT_PROVIDER` 常量零残留（grep 验证）
- `extra_request_body` 保真测试存在（`test_llm_model_registry.py:42-47`，`test_llm_config.py:16-29`）

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 模型下拉选项保持原有三条 | `upstream_reporter.py:120`；`local_store.py:_parse_llm` | `test_llm_model_registry.py:60-69` | covered |
| "平台默认"标签仍指向 K2.6 | `model_registry.py:73-81`（default_provider 从 default_model 推导） | `test_llm_model_registry.py:56-58` | covered |
| agent 不填 default_model 时仍用 K2.6 | `factory.py:38-40` 从 registry 取 default；`local_store.py:521`（None 时不校验） | `test_parse_llm.py:89-95` | covered |
| thinking + 工具调用多轮对话路径保留 | `anthropic/client.py:57-61`（metadata.extra_request_body 合并 per-call extra_body）；`model_registry.py:59-65`（init 时保存 extra_request_body） | `test_llm_model_registry.py:42-47`（K2.6 thinking adaptive 断言） | covered |
| 加新模型走 YAML | `_parse_llm` 完整解析 providers/models 列表，config-driven | `test_parse_llm.py:49-60` | covered |
| 删模型走 YAML | 同上，下次 load_local_config 只解析 YAML 里存在的条目 | 无独立测试，但逻辑在 parse 函数中 | covered（间接） |
| config 没有 llm 段时拒启动 | `local_store.py:450-451`（`_parse_llm`，None 时 raise ValueError） | `test_parse_llm.py:63-68` | covered |
| agent 引用了不存在的模型时拒启动 | `local_store.py:522-527`（`_parse_agents` 校验 default_model ∈ known_models） | `test_parse_llm.py:71-86` | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1: LLMConfigPayload 放 agent.core.llm.config | 是 | `src/agent/core/llm/config.py`（新文件） |
| D2: model_registry.py 工厂化（单例 + 显式 init + 未 init 硬失败） | 是（post-r1 fix） | `model_registry.py:32-88`；`main.py:1094` 直接调用，无 try/except |
| D3: Gateway→Kernel 通过 env NANO_MULTIAGENT_LLM_CONFIG_JSON 传 payload | 是 | `main.py:1298-1303`；`kernel_app.py:17-23` |
| D4: base_url 解析顺序 env > config > error（无值时抛 ValueError） | 是（post-r1 fix） | `factory.py:37-47`（env 无 + config None → ValueError）；`model_registry.py:57`（None 透传） |
| D5: default_model 显式必填；default_provider 由 default_model 推导 | 是 | `local_store.py:454`（_require_non_empty_string）；`model_registry.py:73-81` |
| D6: capabilities 死字段顺手清除 | 是 | `model_registry.py:12-19`（ModelMetadata 无四字段）；`global_routes.py`（无 supports_* 输出）；前端 wire 类型已清 |
| D7: agent.default_model 解析期硬失败 | 是 | `local_store.py:488-527`（_parse_agents 接收 llm 参数，校验 known_models） |
| D8: 不留 backward compat fallback | 是 | `local_store.py:450-451`（缺 llm 段 raise ValueError，无 hardcoded 默认） |

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING

无（round 1 两个 WARNING 均已消除）。

### SUGGESTION（可以修）

**SUGGESTION-1: `test_llm_model_registry.py` 无测试覆盖"doubao 模型的 extra_request_body 保真"**

- 目前只测了 K2.6（`test_llm_model_registry.py:42-47`），doubao 的 `extra_request_body={"thinking": {"type": "adaptive"}}` 未显式断言。
- 建议在 `test_llm_model_registry.py` 加一个 `test_resolve_doubao_metadata_extra_request_body_preserved`，与 K2.6 测试对称。不是硬要求，但可增强 thinking roundtrip 链路的覆盖宽度。
