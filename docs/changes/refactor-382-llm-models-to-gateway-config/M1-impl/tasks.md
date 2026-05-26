# refactor-382-M1: impl — Tasks

## 目标

将 LLM 模型清单从硬编码常量迁移到 Gateway YAML 配置，config 驱动的注册表，Gateway→Kernel env 传 payload。

## 退出标准

- `pytest -m "not e2e"` 全绿
- `pytest tests/contract/` 全绿（依赖方向不破）
- `pytest -xvs tests/unit/personal_assistant/config/test_local_store.py` 含 `_parse_llm` 新单测全绿
- `pytest -xvs tests/unit/test_llm_model_registry.py` 含 `init_model_registry` + `_reset_for_tests` + 未 init 时硬失败 + `extra_request_body` 保真的单测全绿
- `ModelMetadata` 不含 `supports_text/image/tools/streaming` 四字段（grep 验证）
- `DEFAULT_PROVIDER` 常量被 `get_default_provider()` 函数完全替代（grep 验证零残留）
- e2e：`scripts/e2e-up.sh` 起服务，至少跑通一次心跳 + 一次 chat send

## 测试策略

后端 API 改动 — 重构类型（行为不变）。

现有测试 (`test_llm_model_registry.py` / `test_local_store.py`) 是直接入口，重构后应通过而不是报错。新增测试覆盖：
1. `init_model_registry` + `_reset_for_tests` 工厂行为
2. 未 init 时调用任何函数抛 RuntimeError
3. `extra_request_body` 保真（K2.6 roundtrip 必须是 `{"thinking": {"type": "adaptive"}}`）
4. `_parse_llm` 的 hard-fail 路径：缺 llm 段、agent 引用不存在模型
5. `conftest.py` autouse fixture 保证所有其他测试不因 "not initialized" 失败

前端改动（`im-agent-config-api.ts` 清死字段）— visual-only 类型，不新增 E2E，做 TypeScript 编译验证。

## UI 状态矩阵

N/A（无前端 UI 行为变更，只清 wire 类型死字段）

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R0 | 基线修复（预存在的 test mock 缺 reasoning_signature） | DONE |
| R1 | 新 agent.core.llm.config 模块 + 测试 | DONE |
| R2 | model_registry.py 工厂化 + conftest autouse fixture + 测试 | DONE |
| R3 | factory.py 适配 + global_routes 死字段清理 + anthropic client 字段适配 + 前端 wire 类型 | DONE |
| R4 | local_store.py 加 LLMConfigPayload 解析与校验 + 测试 | TODO |
| R5 | main.py spawn env 注入 + kernel_app.py 启动期 init + upstream_reporter 适配 | TODO |
| R6 | AGENTS.md 配置样例 + scripts/e2e-up.sh 同步 | TODO |
| R7 | e2e 验证（心跳 + chat send） | TODO |
