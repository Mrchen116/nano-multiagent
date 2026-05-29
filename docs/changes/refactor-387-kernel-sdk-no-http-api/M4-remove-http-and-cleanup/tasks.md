# refactor-387-M4: remove-http-and-cleanup — Tasks

> 对齐: ../design.md v1

## 目标

删除 HTTP 残骸（`agent/platform/http_api/`、`coding_cli` 死 HTTP 文件），迁移 EventStreamHub 到 core，将 HTTP/ASGI 合约测试平移到 agent.sdk 表面，去除所有 xfail，更新文档到最终目标态。

## 退出标准

- [ ] `agent/platform/http_api/` 目录已删除，无任何 src 文件 import 它
- [ ] `EventStreamHub` / `StreamEvent` / `SubscriberOverflowError` 已迁到 `agent/core/events/`
- [ ] `coding_cli/{client,kernel_app,managed_server,session_stream}.py` 及其专属测试已删除
- [ ] 全量 contract + unit + integration 全绿，零 failed，零 xfail 残留
- [ ] `test_spec_declares_zero_import_acceptance_rules` 绿（SPEC.md 新边界原文）
- [ ] `test_architecture_docs_describe_zero_residue_target_state` 绿（docs 清理完毕）
- [ ] `test_top_level_packages_keep_zero_import_boundaries` 去 xfail 后绿（agent.sdk-only 边界）

## 测试策略

- 被测行为：HTTP 残骸删除后 src 无 agent.platform.http_api import；EventStreamHub 新路径可用；SDK 契约测试绿；xfail 清除；文档测试绿
- 已有测试在：`tests/contract/test_cli_http_only_contract.py`（改写）、`tests/contract/test_multi_product_architecture_acceptance.py`（改写）、`tests/contract/test_agent_sdk_boundary_contract.py`（清除 whitelist）
- 落层/目录/marker：tests/contract/、tests/unit/（删除死测试文件）
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据：无（纯代码删除+重构）

前端 UI：N/A（后端重构 milestone）

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 迁移 EventStreamHub 出 http_api → agent/core/events/ | DONE |
| R2 | 删 coding_cli 死 HTTP 文件及其专属测试 | DONE |
| R3 | 删 agent/platform/http_api/ 整目录 | TODO |
| R4 | 平移 HTTP/ASGI contract 测试到 agent.sdk 表面（删旧文件） | DONE |
| R5 | 修两个 M4 文档红测 + 去 xfail + 文档收尾 | TODO |
