# Verification Report: refactor-382

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 7/7 tasks done; 3 requirements covered |
| Correctness | 8/8 scenarios covered |
| Coherence | 6/8 decisions followed; 2 minor deviations (WARNING) |

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

**Tasks: 7/7 complete**（R0~R7 全 DONE，`tasks.md` 验证）

**Spec 覆盖：**
- Requirement "端用户在 IM 里看到的模型选择行为不变" — 实现存在，registry 工厂化 + upstream_reporter 适配
- Requirement "运维通过编辑 YAML 增减模型" — 实现存在，`_parse_llm` + `local_store.py` YAML 驱动
- Requirement "Gateway 在 LLM 配置错误时立即报错" — 实现存在，硬失败路径在 `_parse_llm` 和 `_parse_agents`

**退出标准核查：**
- `pytest -m "not e2e"` 全绿（2381 passed）
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
| D2: model_registry.py 工厂化（单例 + 显式 init + 未 init 硬失败） | 部分（见 WARNING-1） | `model_registry.py:32-88`；但 `main.py:1094-1097` 静默吞重复 init |
| D3: Gateway→Kernel 通过 env NANO_MULTIAGENT_LLM_CONFIG_JSON 传 payload | 是 | `main.py:1298-1303`；`kernel_app.py:17-23` |
| D4: base_url 解析顺序 env > config > error（无值时抛 ValueError） | 部分（见 WARNING-2） | `factory.py:40`（env > registry default）；但 None base_url 被 `model_registry.py:57` 静默变为空字符串，无错误路径 |
| D5: default_model 显式必填；default_provider 由 default_model 推导 | 是 | `local_store.py:454`（_require_non_empty_string）；`model_registry.py:73-81` |
| D6: capabilities 死字段顺手清除 | 是 | `model_registry.py:12-19`（ModelMetadata 无四字段）；`global_routes.py`（无 supports_* 输出）；前端 wire 类型已清 |
| D7: agent.default_model 解析期硬失败 | 是 | `local_store.py:488-527`（_parse_agents 接收 llm 参数，校验 known_models） |
| D8: 不留 backward compat fallback | 是 | `local_store.py:450-451`（缺 llm 段 raise ValueError，无 hardcoded 默认） |

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**WARNING-1: Gateway 侧 `init_model_registry` 静默吞掉 RuntimeError，绕过 D2 的"重复 init 抛错"守卫**

- `src/personal_assistant/main.py:1094-1097`：
  ```python
  try:
      init_model_registry(config.llm)
  except RuntimeError:
      pass  # already initialized (test environment with autouse fixture)
  ```
- 问题：注释说"test environment with autouse fixture"，但在生产进程中 Gateway 也会走这条路径，任何真实的双重初始化错误都会被静默吞掉，违反 D2"未 init 时抛 RuntimeError"的守卫精神。
- 修复方向：把对测试环境的兼容移到 conftest，而不是在生产代码里打补丁。生产代码应该直接 `init_model_registry(config.llm)`（不 try/except）；测试 fixture 在调用 `run_gateway_foreground` 前先 `_reset_for_tests()`，或者通过 `factories` 注入跳过 init 的版本。具体方案：在 `tests/conftest.py` 的 autouse fixture 里 yield 前后确保 reset，生产路径不需要 try/except。

**WARNING-2: `base_url=None` 时静默降级为空字符串，未实现 D4 的"都没有 → 抛 ValueError"路径**

- `src/agent/core/llm/model_registry.py:57`：`base_url = provider_payload.base_url or ""`
- 问题：当 provider 在 config 中未填 `base_url`（为 None），且 `NANO_MULTIAGENT_LLM_BASE_URL` 环境变量也未设置时，`factory.py:40` 的 `os.getenv("NANO_MULTIAGENT_LLM_BASE_URL", get_default_base_url(provider))` 会返回空字符串 `""`，然后把它当 URL 传给 AnthropicClient，产生的是连接错误而非明确的配置错误。
- design.md D4 明确要求：`都没有 → 抛 ValueError("base_url unset for provider X")`。
- 修复方向：在 `factory.py:from_env()` 中加检查：`if not base_url: raise ValueError(f"base_url unset for provider '{provider}' — set NANO_MULTIAGENT_LLM_BASE_URL or add base_url to llm.providers config")`。或者在 `model_registry.py:57` 保留 `None`（不强转 `""`），让调用方（factory）在 `base_url is None or base_url == ""` 时报错。

### SUGGESTION（可以修）

**SUGGESTION-1: `test_llm_model_registry.py` 无测试覆盖"doubao 模型的 extra_request_body 保真"**

- 目前只测了 K2.6（`test_llm_model_registry.py:42-47`），doubao 的 `extra_request_body={"thinking": {"type": "adaptive"}}` 未显式断言。
- 建议在 `test_llm_model_registry.py` 加一个 `test_resolve_doubao_metadata_extra_request_body_preserved`，与 K2.6 测试对称。不是硬要求，但可增强 thinking roundtrip 链路的覆盖宽度。
