# TASKS (Current Milestone: M14)

## [TODO] R14.1 anthropic 协议适配实现
- Steps:
  - 新增 anthropic 协议红测，固定 mapper/client/translator 的契约缺口（Red）。
  - 实现 `llm/protocols/anthropic/{client,mapper}.py` 与 translator 分支。
  - 保证 `X-Session-Id` 在 anthropic 链路透传。
  - 跑目标测试并记录证据。
- Expected Tests:
  - `tests/unit/test_anthropic_mapper.py`
  - `tests/contract/test_llm_anthropic_contract.py`
  - `tests/integration/test_anthropic_generation_integration.py`
  - `tests/e2e/test_anthropic_generation_e2e.py`
- DoD:
  - R14.1 目标测试红转绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R14.1 hash 与证据

## [TODO] R14.2 provider 切换验收
- Steps:
  - 新增 provider 切换红测，固定“仅配置切换”的约束（Red）。
  - 在 factory/model_registry 完成 anthropic 与 openai_compat 切换接线。
  - 完成双 provider 回归与错误语义一致性校验。
  - 执行全量回归并收口 M14。
- Expected Tests:
  - `tests/unit/test_llm_factory_provider_switch.py`
  - `tests/contract/test_provider_switch_contract.py`
  - `tests/integration/test_provider_switch_integration.py`
  - `tests/e2e/test_provider_switch_e2e.py`
- DoD:
  - R14.2 目标测试红转绿
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R14.2 hash 与证据
