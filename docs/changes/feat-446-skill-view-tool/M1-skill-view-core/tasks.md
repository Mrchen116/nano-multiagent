# feat-446-M1: skill-view-core — Tasks

> 对齐: ../design.md v1

## 目标

交付独立只读工具 `skill_view`，把 `skill_manage` 收敛为写侧工具，记录 skill 使用统计，并让默认产品工具集、prompt guidance、self-improvement fork 与 compaction 存活机制都走新的读侧工具。

## 退出标准

- [x] agent 调用 `skill_view` 返回 SKILL.md 内容。
- [x] `skill_manage` 不含 `view` action。
- [x] `skill_manage(create, scope=agent/pa)` 写入指定 root，且不可用 PA root 时失败不回退。
- [x] PA 默认工具集合和 capability projection 均包含 `skill_view` 且 `default_on=true`。
- [x] 未显式配置工具白名单的 PA agent 默认启用 `skill_view`。
- [x] 已有显式 `tool_allowlist` 不被自动扩宽，不含 `skill_view` 时后续 session 不启用 `skill_view`。
- [x] 使用统计记录到 `.usage.json`（含 source=F1/F2/F3/F4），同一 `tool_call_id` 重放不重复计数。
- [x] compaction 时按 location 重读当前 SKILL.md 并以 `<system-reminder>` 注入，resume 后 metadata 可恢复。
- [x] `PYTHONPATH=src pytest tests/unit/test_skill_view.py tests/unit/test_usage.py tests/contract/ -x` 全绿。

## 测试策略

- 被测行为（来自退出标准）：`skill_view` 成功/失败读取、`skill_manage` schema 与 create scope、PA 默认工具语义、usage 幂等与 source、compaction re-injection metadata 恢复。
- 已有测试在：`tests/unit/test_skill_manage_tool.py`（扩展 create scope/schema 行为）、`tests/unit/test_runtime_tool_allowlist_filtering.py`（扩展默认/显式 allowlist）、`tests/unit/test_self_improvement_hook.py`（扩展白名单）；新建 `tests/unit/test_skill_view.py` 覆盖独立工具和 compaction 存活，新建 `tests/unit/test_usage.py` 覆盖 usage sidecar，理由：当前没有 `skill_view` 与 usage 追踪行为对应测试文件。
- 落层/目录/marker：`tests/unit/` + `tests/contract/`，marker：无；本 milestone 不起真服务、不走浏览器。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无。

前端 UI：N/A，本 milestone 仅内核/PA 工具集合，不改 IM 前端展示。

## Roadpoints

### R1 — tool contract and usage sidecar

- 状态: DONE
- 步骤: 新增 `skill_view` 行为测试、usage sidecar 测试、`skill_manage` schema/create scope 测试；实现 root resolver、usage 记录、`skill_view` tool、`skill_manage` scope 与注册。
- 验证: `PYTHONPATH=src pytest tests/unit/test_skill_view.py tests/unit/test_usage.py tests/unit/test_skill_manage_tool.py -x`

### R2 — prompt gates, defaults, and self-improvement

- 状态: DONE
- 步骤: 扩展 feature gate OR 逻辑、prompt guidance、self-improvement 白名单与提示、CLI/PA 默认工具和 capability projection。
- 验证: `PYTHONPATH=src pytest tests/unit/test_agent_prompting.py tests/unit/test_self_improvement_hook.py tests/unit/test_runtime_tool_allowlist_filtering.py tests/contract/ -x`

### R3 — compaction survival and final contract gate

- 状态: DONE
- 步骤: `skill_view` 成功调用注册 invoked skill；compaction 写入 `<system-reminder>` synthetic message；resume metadata 恢复 invoked skill refs。
- 验证: `PYTHONPATH=src pytest tests/unit/test_skill_view.py tests/unit/test_usage.py tests/contract/ -x`
