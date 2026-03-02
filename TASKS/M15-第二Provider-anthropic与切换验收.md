# TASKS (Milestone: M15)

- Test command: `pytest -q`
- Branch: `milestone/M15`

## [TODO] R15.1 Provider 契约测试集统一（OpenAI + Anthropic）
- Acceptance:
  - 新增共享 provider 契约测试集，`openai_compat` 与 `anthropic` 走同一套用例入口。
  - 契约覆盖请求映射、响应解析、错误归一化与 `X-Session-Id` 头传递语义。
  - 现有 `openai_compat` 行为不回退（旧链路仍通过契约/集成验证）。
- Tests Plan:
  - unit: 选用（覆盖 mapper 纯映射逻辑与边界）
  - contract: 选用（本 Roadpoint 主目标）
  - integration: 不选（R15.3 统一覆盖工厂接线）
  - e2e: 不选（R15.3 统一覆盖 provider 切换入口）
- Expected Tests:
  - `tests/contract/test_llm_provider_contract.py::test_provider_mapper_request_contract`
  - `tests/contract/test_llm_provider_contract.py::test_provider_mapper_response_contract`
  - `tests/contract/test_llm_provider_contract.py::test_provider_client_contract_non_stream_and_headers`
  - `tests/contract/test_llm_provider_contract.py::test_provider_client_contract_streaming_not_supported`
- DoD:
  - R15.1 目标测试红转绿
  - C1/C2/C3 三次提交完整
  - `PROGRESS` 记录决策、证据与哈希
  - `pytest -q` 在仓库基线允许范围内不新增失败
- Commits:
  - C1: TBD
  - C2: TBD
  - C3: TBD

## [TODO] R15.2 新增 anthropic 协议实现（llm/protocols/anthropic）
- Acceptance:
  - `src/nano_multiagent/llm/protocols/anthropic/{mapper.py,client.py,__init__.py}` 落地。
  - anthropic 请求使用 `POST /v1/messages`，与 `LLMTranslator` 对齐并携带 `X-Session-Id`。
  - anthropic 响应可稳定映射为 `LLMGenerateResponse`，错误场景转为 `ModelError`。
- Tests Plan:
  - unit: 选用（mapper 输入输出与 content 归一化）
  - contract: 选用（复用 R15.1 共享契约）
  - integration: 不选（R15.3 统一覆盖工厂接线）
  - e2e: 不选（R15.3 统一覆盖）
- Expected Tests:
  - `tests/contract/test_llm_provider_contract.py -k anthropic`
  - `tests/unit/test_llm_anthropic_mapper.py`
- DoD:
  - anthropic 协议实现通过共享契约
  - C1/C2/C3 三次提交完整
  - `PROGRESS` 记录关键结构与回滚点
  - `pytest -q` 在仓库基线允许范围内不新增失败
- Commits:
  - C1: TBD
  - C2: TBD
  - C3: TBD

## [TODO] R15.3 工厂接线与 provider 切换验收（配置驱动）
- Acceptance:
  - `model_registry` 与 `factory` 支持 `provider=anthropic` 并保持 `openai_compat` 兼容。
  - provider 切换只通过 `LLMFactoryConfig` 或环境变量配置，不改 runtime/tool/session 代码。
  - OpenAI/Anthropic 双链路集成测试通过，补齐最小 e2e 入口验证。
- Tests Plan:
  - unit: 选用（`model_registry` provider/model 默认值）
  - contract: 选用（provider 双实现共享契约回归）
  - integration: 选用（工厂 -> client -> translator 全链路，双 provider）
  - e2e: 选用（本地代理可用时验证 anthropic provider 真实入口）
- Expected Tests:
  - `tests/unit/test_llm_model_registry.py`
  - `tests/integration/test_openai_compat_generation_integration.py`
  - `tests/integration/test_anthropic_generation_integration.py`
  - `tests/integration/test_agent_runtime_integration.py`
  - `tests/e2e/test_anthropic_generate_e2e.py`
  - `pytest -q`
- DoD:
  - R15.3 目标测试通过并满足 Milestone Exit Criteria
  - C1/C2/C3 三次提交完整
  - 文档记录含 gate 结果、哈希与下一步
- Commits:
  - C1: TBD
  - C2: TBD
  - C3: TBD
