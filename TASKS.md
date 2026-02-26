# TASKS (Current Milestone: M3)

## [DONE] R3.1 LLM 抽象接口与 openai_compat 非流式链路
- Steps:
  - 先新增 `llm` 相关 unit/contract/integration 失败测试（Red）
  - 实现 `llm/interfaces.py` 作为运行时唯一抽象接口
  - 实现 `llm/model_registry.py` 与 `llm/factory.py` 支持 provider/model 配置切换
  - 实现 `llm/translator.py` 与 `openai_compat/{mapper,client}`，保证请求头包含 `X-Session-Id`
  - 运行目标测试并记录证据
- Expected Tests:
  - `tests/unit/test_llm_model_registry.py`
  - `tests/contract/test_llm_interfaces_contract.py`
  - `tests/integration/test_openai_compat_generation_integration.py`
- DoD:
  - 目标测试全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R3.1 hash 与证据

## [DONE] R3.2 本地 LLM_PROXY e2e 与文档纠偏
- Steps:
  - 新增 e2e 失败测试，走 `create_llm_client` + 真实本地代理
  - 验证默认配置可直连 `http://127.0.0.1:4000` 与模型 `codexOAuth:gpt-5.2-codex`
  - 在测试中补充 `X-Session-Id` 验证证据
  - 全量运行 `pytest -q` 并收集结果
  - 回填 M2/R3.1 文档中的 `PENDING-C3-*` 为真实 hash
- Expected Tests:
  - `tests/e2e/test_openai_compat_generate_e2e.py`
  - `pytest -q`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R3.2 hash 与证据
  - 回填 `PENDING-C3-R2.2` 与 `PENDING-C3-R3.1`

## Milestone M3 状态
- `R3.1` 与 `R3.2` 均已完成，达到 M3 Exit Criteria。
