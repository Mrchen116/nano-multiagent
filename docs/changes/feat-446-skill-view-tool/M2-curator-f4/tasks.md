# feat-446-M2: curator-f4 — Tasks

> 对齐: ../design.md v1

## 目标

交付 per-workspace Curator 生命周期扫描与 per-skill batch review 触发链路：自动创建的 F3/F4 skill 会按 30/90 天 idle 状态流转，`skill_view` 成功读取会复活 stale skill，并在 `uses_since_last_B` 越线时即时 enqueue F4 batch，且同一 skill 不并发启动第二个 batch。

## 退出标准

- [x] 30 天未用的 F3/F4 skill 标记 stale。
- [x] stale skill 仍出现在 `<available_skills>` 和 `/skill:` 候选，并在 usage state 中标记 stale 供统计面板读取。
- [x] 90 天归档到 `.archive/` 后默认退出 `<available_skills>` 和 `/skill:` 候选，但 `.usage.json` 保留 archived 记录供统计面板 archived 过滤视图审计。
- [x] stale skill 被 `skill_view` 重新读取后复活为 active。
- [x] F1/F2/unknown skill 不被 Curator 自动流转。
- [x] `skill_view` 成功后 `uses_since_last_B` 越线即 enqueue per-skill batch review，不等待 7 天 Curator。
- [x] 同一 skill running/queued 时不并发启动第二个 batch。
- [x] batch review 至少需要 2 个 session transcript 证据才采纳 patch。
- [x] batch review 只允许 patch，不创建新 skill。
- [x] `PYTHONPATH=src pytest tests/unit/test_curator.py tests/unit/test_skill_batch_review.py -x` 全绿。
- [x] `PYTHONPATH=src pytest tests/contract/test_core_no_platform_imports.py -x` 全绿。

## 测试策略

- 被测行为（来自退出标准）：Curator 30/90 天 state transition、archived 目录退出候选、stale 复活、F1/F2/unknown 保护、F4 trigger 返回、runtime enqueue 去重、batch review 的 2-session 证据门槛与只 patch 限制。
- 已有测试在：`tests/unit/test_usage.py`、`tests/unit/test_skill_view.py`（扩展 usage/F4 trigger 与 skill_view enqueue）；无 Curator/batch 专属测试，新建 `tests/unit/test_curator.py` 与 `tests/unit/test_skill_batch_review.py`，理由：当前没有 Curator 状态机和 platform background batch 编排行为测试。
- 落层/目录/marker：`tests/unit/` + `tests/contract/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无。

前端 UI：N/A。M2 不实现 M4 dashboard 面板/API；统计面板所需的 stale/archived 审计数据由 `.usage.json` state/archived_at/archive_error 保留。

## Roadpoints

### R1 — curator state machine and archive visibility

- 状态: DONE
- 步骤: 新增 Curator 行为测试；实现 `core/skills/curator.py`，让 F3/F4 active→stale、stale/active→archived、stale→active 数据流转；更新 skill discovery 使 `.archive/` 下 skill 默认不进入候选。
- 验证: `PYTHONPATH=src pytest tests/unit/test_curator.py tests/contract/test_core_no_platform_imports.py -x`

### R2 — F4 trigger and runtime enqueue dedupe

- 状态: DONE
- 步骤: 扩展 usage bump 返回 `F4Trigger`；`skill_view` 成功读取后把 trigger 交给 runtime/kernel enqueue；同 skill queued/running 去重；enqueue 成功后 reset `uses_since_last_B`。
- 验证: `PYTHONPATH=src pytest tests/unit/test_usage.py tests/unit/test_skill_view.py -x`

### R3 — batch review orchestration and housekeeping entrypoints

- 状态: DONE
- 步骤: 新增 `platform/background/skill_batch_review.py`，过滤 reviewed/缺 transcript session，要求 ≥2 session 证据，限制 background fork 只用 `skill_view` + `skill_manage` 且 prompt 明确只 patch；补 SDK skill maintenance 入口，接入 CLI 启动和 Gateway housekeeping。
- 验证: `PYTHONPATH=src pytest tests/unit/test_skill_batch_review.py tests/unit/test_curator.py tests/contract/test_core_no_platform_imports.py -x`
