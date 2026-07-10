# FIX-round-2-runtime tasks

## 目标

修复 round-2 verifier / acceptance 中归属 backend/runtime 的问题：`/skill:<name>` 必须确定性走 `skill_view` 工具执行路径并产生审计/统计/压缩存活数据；F4 threshold enqueue 后必须在运行中的 CLI/Gateway 产品会话里被 drain；Gateway usage dashboard 要能读取 shared/owning root usage；F2 transcript discovery 补齐 backend 可发现路径。

## 测试策略

- 被测行为(来自退出标准): `/skill:` 产生 `skill_view` tool row + `.usage.json`；F4 live enqueue 后 drain；same-name F4 queue 按 owning root 去重；Gateway usage payload 聚合 shared root 中属于当前 agent session 的 refs；IM conversation source_jsonl_path 递归发现 nested session JSONL。
- 已有测试在: `tests/integration/test_agent_runtime_skill_command_integration.py`、`tests/unit/test_agent_runtime.py`、`tests/contract/test_skill_commands_contract.py`、`tests/unit/test_cli_product.py`、`tests/unit/personal_assistant/test_gateway_process_manager.py`、`tests/unit/personal_assistant/test_gateway_im_connection_behavior.py`、`tests/unit/test_skill_batch_review.py`、`tests/im_service/unit/test_repositories_user_conversation.py` 扩展。
- 落层/目录/marker: `tests/unit` / `tests/integration` / `tests/contract`，marker: 无。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据(收尾删除,不进套件): 无。

## Roadpoints

| Roadpoint | Status | Scope | Gate |
|---|---|---|---|
| R1 | DONE | Slash skill command runtime path + parser contract | `PYTHONPATH=src pytest tests/integration/test_agent_runtime_skill_command_integration.py tests/unit/test_agent_runtime.py::test_runtime_skill_command_rewrite_runs_through_normal_pipeline tests/contract/test_skill_commands_contract.py -q` |
| R2 | DONE | F4 live drain + root-aware queue/review identity | `PYTHONPATH=src pytest tests/unit/test_cli_product.py tests/unit/test_skill_batch_review.py tests/unit/personal_assistant/test_gateway_process_manager.py -q` |
| R3 | DONE | Gateway shared usage dashboard + F2 transcript backend discovery | `PYTHONPATH=src pytest tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/unit/test_repositories_user_conversation.py -q` |
