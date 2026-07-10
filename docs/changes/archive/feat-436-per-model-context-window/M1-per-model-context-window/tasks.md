# feat-436-M1 tasks — per-model-context-window

> 由 orchestrator 亲自实施（用户指示不派 impl worker）。单 M1。

## Roadpoints

- [x] R1: `context_window` 字段贯通 5 跳透传链（照抄 `extra_request_body`）
  - PA `local_store.LLMModelPayload` + `_parse_llm`（非法值→None）+ `save_local_config` 序列化
  - SDK `dto.LLMModel` + `from_payload`（鸭子类型）+ `from_json`
  - `kernel._init_model_registry_from_llm_config` 映射
  - core `llm.config.LLMModelPayload` + `to_json`/`from_json`
  - `model_registry.ModelMetadata` + `init_model_registry` + `resolve_model_metadata`
- [x] R2: 压缩判定按 active model 取窗口 + 三级回退
  - 新增 `model_registry.context_window_for_model(model)`（安全查询，never raises）
  - `loop._resolve_context_window` + `_should_compact`/`_maybe_compact` 贯通 `active_model`
  - `runtime.py` hook_metadata 的 `context_window` 按 model 解析（前端显示分母随之 per-model）
- [x] R3: `CompactionSettings.reserve_tokens` 默认 4096 → 20480
- [x] R4: 测试（扩展既有文件，无新建）+ ruff + 全非-e2e 回归

## 测试策略

- 被测行为(来自退出标准):
  - context_window 从 YAML/payload 透传到 ModelMetadata；未配→None
  - `context_window_for_model`：配置值 / 未配 / 未知 id / 非法值(0/负/bool) / 注册表未初始化 各自返回
  - core wire schema to_json/from_json 往返保真
  - SDK from_payload → build_kernel 注册表端到端带窗口
  - PA YAML 解析 context_window（非法→None）+ save 回写往返
  - 压缩阈值随 per-model 窗口移动（大窗口不压、回退默认窗口压）
  - 注册表空时压缩按全局默认窗口判定、不抛错
  - reserve 默认 = 20480
- 已有测试在(扩展，不新建):
  - `tests/unit/test_llm_config.py`（core wire schema 往返）
  - `tests/unit/test_llm_model_registry.py`（注册表 + context_window_for_model + SDK 端到端）
  - `tests/unit/personal_assistant/config/test_parse_llm.py`（PA 解析 + 回写往返）
  - `tests/unit/test_loop_compact.py`（压缩判定 + reserve 默认；该文件 main 上已 415 行 >400，
    契约只卡新增文件，扩展既有文件豁免；是 `_should_compact` 行为 canonical 归属）
- 落层/目录/marker: tests/unit/ , marker: 无
- 可选依赖 importorskip: 无
- 一次性验收证据(不进套件): 无（无独立验收脚本）

## 边界说明

- 私有 helper `_resolve_context_window` 不直接测；改测可观察的 `_should_compact`（既有模式）。
- `context_window_for_model` 是 model_registry 公开函数，直接测合规。
