# Verification Report: feat-436

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 4/4 |
| Correctness | 5/5 |
| Coherence | Followed |

All checks passed. Ready for PR.

---

## Completeness

### Task 完成情况
Tasks: 4/4 complete（R1/R2/R3/R4 全部标 `[x]`）。

### Spec 覆盖
- **Requirement: 每个模型可在配置中声明自己的上下文窗口** — 已实现（5 跳透传链全打通）
- **Requirement: 未配置 context_window 的模型保持现有行为** — 已实现（`context_window_for_model` 返回 None → 回退 200k）
- **Requirement: 压缩安全余量（reserve）的全局默认提高到 20k** — 已实现（`CompactionSettings.reserve_tokens = 20_480`）

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 模型显式配置了 context_window → 在配置值边界触发压缩 | `loop.py:844`（`_should_compact` 调 `_resolve_context_window`）；`model_registry.py:236`（`context_window_for_model`） | `test_loop_compact.py::test_should_compact_threshold_moves_with_per_model_window`（190k tokens，大窗口不压 / 回退 200k 触发） | covered |
| 不同窗口配置的模型，压缩时机随配置移动 | `loop.py:809-821`（`_resolve_context_window` 按 active_model 查注册表） | 同上测试（big-window=1M 不压，no-window 回退 200k 压） | covered |
| 模型条目未声明 context_window → 回退 200k，不报错 | `local_store.py:728-734`（未配→None）；`context_window_for_model` 返回 None；`_resolve_context_window` 回退 settings | `test_llm_model_registry.py::test_context_window_for_model_unconfigured_returns_none`；`test_loop_compact.py::test_should_compact_falls_back_to_default_window_when_registry_empty` | covered |
| context_window 配成非法值（0/负/bool）→ 回退默认，不崩溃 | `local_store.py:729-734`（PA 端：非正整数/bool 归 None）；`model_registry.py:237`（core 端：非正整数/bool 归 None） | `test_parse_llm.py::test_load_local_config_parses_context_window`（bad:model 0→None）；`test_llm_model_registry.py::test_context_window_for_model_invalid_value_returns_none` | covered |
| 默认余量 → 系统在"窗口 − 20480"触发压缩 | `compaction/types.py:24`（`reserve_tokens = 20_480`） | `test_loop_compact.py::test_compaction_reserve_tokens_default_is_20480` | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1: context_window 作为 per-model 字段，照抄 extra_request_body 的 5 跳透传链 | 是 | `local_store.py:31`/`621-624`/`726-740`；`dto.py:85`/`206`/`316`；`kernel.py:181`；`config.py:22`/`58`/`89`；`model_registry.py:21`/`72`/`211` |
| 决策 2: 压缩判定按 active_model 查注册表 + 三级回退（未初始化/缺失/非法→默认） | 是 | `loop.py:809-821`（`_resolve_context_window`）；`model_registry.py:215-239`（`context_window_for_model` never raises）；`runtime.py:412-413` |
| 决策 3: 非法/缺失 context_window 等同未配，回退默认，不 fail-loud | 是 | PA 端：`local_store.py:729-734`；core 端：`model_registry.py:237`；`context_window_for_model` 对 bool/非 int/≤0 均返回 None |
| 决策 4: reserve_tokens 全局默认 4096 → 20480，非 per-model | 是 | `compaction/types.py:24`；无 per-model 结构 |
| 依赖方向：PA 只 import agent.sdk，PA 侧与 core 侧各加字段一次 | 是 | contract tests 129 passed；PA 独立维护 `LLMModelPayload`（`local_store.py`），SDK 桥接 `from_payload(getattr, None)` |
| 复用 bugfix-429 的 active_model 机制（loop.py 已有 `active_model` 在作用域） | 是 | `loop.py:189`（`active_model = model_override or self._model`）→ `loop.py:295`（传入 `_maybe_compact`）→ `loop.py:861` |
| 读取点 B（runtime.py hook_metadata.context_window）按 model 解析 | 是 | `runtime.py:412-413`（`context_window_for_model(model) or self._compaction_settings.context_window`） |

### 代码模式一致性
- 注释符合项目规范：关键决策注释以 `feat-436 决策N:` 标注，`context_window_for_model` 有完整 Google 风格 docstring
- 命名一致：全链路统一使用 `context_window`，与 `extra_request_body` 同级同风格
- 测试命名遵循既有模式：扩展原有测试文件，未新建流水号文件

---

## Issues

无 CRITICAL、无 WARNING、无 SUGGESTION。
