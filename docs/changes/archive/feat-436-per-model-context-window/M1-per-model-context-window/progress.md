# feat-436-M1 progress — per-model-context-window

> 实施者：orchestrator 亲自（用户指示不派 impl worker）。

## R1 — context_window 5 跳透传链

- **Context**: 现状 context_window 全局写死 200k；需让模型各配各的。照抄 `extra_request_body` 的现成透传链。
- **Decision**: 每跳紧贴 `extra_request_body` 加同款 `context_window: int | None`，不新造抽象。
- **Rationale**: `extra_request_body` 是完全同构先例，零新模式、风险最低。
- **Evidence**:
  - PA `local_store.py`：`LLMModelPayload.context_window` + `_parse_llm` 解析（非法值归一 None）+ save 序列化（未配不落字段）
  - SDK `dto.py`：`LLMModel.context_window` + `from_payload`（`getattr` 兼容旧 payload）+ `from_json`
  - `kernel.py`：`_init_model_registry_from_llm_config` 映射带 `context_window`
  - core `config.py`：`LLMModelPayload.context_window` + to_json/from_json
  - `model_registry.py`：`ModelMetadata.context_window` + init + resolve 透传
  - 测试：`test_llm_config.py`(往返) / `test_llm_model_registry.py`(注册表+端到端) / `test_parse_llm.py`(PA 解析+回写) 全绿
- **Rollback**: revert 各 payload 字段；纯增量，无迁移。

## R2 — 压缩按 active model 取窗口 + 三级回退

- **Context**: model 是 per-run（bugfix-429 `_active_run_models`/loop `active_model`），窗口必须跟当前 run 的 model。单测/fork 路径无注册表。
- **Decision**: 新增公开 `model_registry.context_window_for_model(model)`（never raises：未初始化/未知/非法值均→None）；`loop._resolve_context_window = context_window_for_model(active_model) or settings.context_window`；`active_model` 贯通 `_maybe_compact`/`_should_compact`；`runtime.py` hook_metadata 同法解析（前端显示分母 per-model）。
- **Rationale**: 复用 bugfix-429 per-run model；三级回退保兼容 + 不引入新崩溃面。
- **Evidence**:
  - `test_loop_compact.py::test_should_compact_threshold_moves_with_per_model_window`（1M 不压 / 回退 200k 压）
  - `test_should_compact_falls_back_to_default_window_when_registry_empty`（注册表空不抛错）
  - `test_context_window_for_model_*`（配置/未配/未知/非法/未初始化 五种）
- **Rollback**: 读取点改回读 `self._compaction_settings.context_window`，删 helper。

## R3 — reserve 默认 4096 → 20480

- **Context**: 4096 不足以覆盖压缩摘要生成 + 下一轮回复额度。
- **Decision**: `CompactionSettings.reserve_tokens` 默认改 20480（全局，非 per-model）。
- **Evidence**: `test_loop_compact.py::test_compaction_reserve_tokens_default_is_20480`。
- **Rollback**: 改回 4096。

## R4 — 测试 + lint + 回归

- **测试落位**：全部扩展既有文件，无新建文件（遵 TESTING_GUIDE §2/§3，避开 `test_feat436_*` 流水号命名）。
- **窄测**：扩展的 6 个文件 51 passed。
- **lint**：`ruff check` 无问题；`ruff format` 重排 runtime.py 后全绿。
- **全树回归**：`pytest -m "not e2e"` → 初次 2960 passed / 1 failed。
  - 失败 = `test_no_hardcoded_workspace_dirname`：我在 kernel.py 加的 `context_window` 透传行把 `.nano/hooks`(375→376)、`.nano/tools`(515→516) 行号下移，行号锚定白名单失配（已知陷阱）。
  - 修法：更新白名单两个锚点 375→376、515→516（既有平台默认，仅行号移位）。复跑通过。
- **Evidence**: 全树 2960 passed + workspace-dirname 契约修后单独复跑 1 passed。

## 退出标准核对

| 退出标准 | 状态 | 证据 |
|---|---|---|
| [reviewer] 配 context_window 后压缩在配置边界触发 | 单测层等价覆盖 | test_should_compact_threshold_moves_with_per_model_window |
| [reviewer] 未配回退 200k 不报错 | ✅ | test_*_falls_back_to_default_window / PA 解析未配→None |
| [reviewer] 非法值回退不崩溃 | ✅ | test_*_invalid_value_returns_none / PA bad:model→None |
| [worker] 端到端透传单测 | ✅ | test_sdk_from_payload_carries_context_window_into_registry 等 |
| [worker] 压缩判定 + 注册表空回退单测 | ✅ | test_loop_compact 两个新测 |
| [worker] reserve 默认 20480 断言 | ✅ | test_compaction_reserve_tokens_default_is_20480 |
| [worker] 最窄测试 + 全树回归绿 | ✅ | 2960 passed（含 contract 依赖方向） |

> [reviewer] 轨的真端到端旅程（真 Gateway 配 config 跑长对话观察压缩边界）留给 reviewer 阶段；
> 单测层已覆盖等价判定逻辑。

## Next

无。M1 完成，待 reviewer/verifier/code-review 验收。
