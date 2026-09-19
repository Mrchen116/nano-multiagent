# 实施与验证

## 范围与结果

M1-tool-projection：新增同步 ToolCallProjector，集中 start/end presentation、in-flight 状态、normal cleanup 和 abnormal 两目的地投影。observer 保留 shadow-before-live、offline/visibility gates、Workflow bindings、任务命名及 await/detach。

## 测试策略与证据

- 基线 main c5f1d5620：工具流、reconcile、shadow、steer、candidate 既有测试 83 passed。
- 实施首版：上述套件及 test_shadow_reply_images 集成测试共 89 passed。
- 新增 `tests/unit/personal_assistant/test_tool_delivery_projections.py`：四个目的地 schema / online-offline revalidation 场景；经 observer 和真实 SQLite shadow store 观察帧及持久化结果，不测试 projector 私有状态。
- 同一新增测试在 main 源码和修改源码各 4 passed。属于行为保持基线，未虚构 Red 阶段。
- 既有 `test_reconcile_preserves_tool_input.py`、`test_gateway_shadow_sync.py`、`test_inbound_pipeline_streaming.py`、steer/candidate/image 集成覆盖 keep，保护不同生命周期与接线风险。未删除既有测试。
- 新文件归属理由：同时比较实时 wire shape 和持久 shadow shape 的漂移风险，现有 shadow 文件超过 400 行且没有字段差异矩阵；不向超长文件追加独立行为。新文件保持低于 400 行。
- no spec delta；无数据迁移。

## A1 验收修复

真实 stop 验收暴露基线已有 current drift：coordinator suppress 后，observer 丢弃 reconcile，writer 又以正文准入阻止终态收口。分别在 main 4394ad424 的独立探针确认只有 tool_call_upserted、终态 writer 发送计数为 0。

设计 R2 提出 cancelled 二次 suppress 问题，R3 closure Approved 后实施。stop 与其 cancelled 事实保留仅终态清理授权，reset 或 generation 失效撤销且不可恢复；writer 仅对已有同 message_id 放行 failed tool 和 bodyless completion。新正文/新气泡/成功工具结果均不准入。

新增六项回归先失败（API 未实现，另有上述基线行为复现），修复后包含真实 coordinator integration 的窄套件 60 passed。扩展现有 image writer 文件，覆盖 stop→cancelled、stop→reset→late cancelled 以及错误目标/正文/新气泡反例。既有 tests 保留。

首版完整本地 CI（151928fed）：3992 Python /770 frontend passed，docs-check、ruff check、format check 通过。A1 后重跑受影响 Python 全量；前端与依赖未变，770 项保留。
