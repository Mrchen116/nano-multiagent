# bugfix-441-M2: fix-review-findings — Tasks

> 对齐: ../design.md v1

## 目标

修复 post-review 阻塞发现：abnormal `run_terminal_reconcile` 不丢 tool_start 参数侧展示字段；cron in-band failure 不再被前端按绿色完成展示。

## 退出标准

- [ ] interrupted/stalled/reconciled in-flight tool call 的 completed payload 保留 tool_start 参数侧 `output`/`detail`/`emoji`。
- [ ] reconcile 仍覆盖 `status=failed`、`reason`，且有 stop attribution content 时用 reconcile content 覆盖 `output`。
- [ ] 刷新/历史回放保留 command/prompt/query 等参数侧 detail。
- [ ] cron `{ok:false,error}` / enqueue declined / missing service 产出前端可识别失败态，例如 `success:false` 和 `error` detail。
- [ ] cron 成功态结构化展示保持不退化。
- [ ] 相关窄口 pytest 全绿。

## 测试策略

- 被测行为（来自退出标准）：Gateway reconcile 异常收口 payload；cron presenter success/failure detail。
- 已有测试在：`tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py`、`tests/unit/personal_assistant/test_cron_tool_closure.py`（扩展）。
- 落层/目录/marker：tests/unit/，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无。

用户路径分类：bug-regression

UI 状态矩阵：N/A，本 milestone 不改前端组件；cron 失败态复用前端已有 `detail.success === false` 判定。

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| abnormal reconcile 丢 running 参数展示字段 | 扩展 Gateway observer unit，模拟多工具 tool_start 后 reconcile | 是 |
| 用户 /stop attribution 覆盖 output 时丢 detail/emoji | 扩展 Gateway observer unit，模拟 reconcile content | 是 |
| cron in-band failure 被当成功 | 扩展 cron presenter unit，断言 `success:false` + `error` | 是 |
| cron 成功态结构化退化 | 扩展 cron presenter unit，断言 `success:true` 且保留 accepted/requestId | 是 |

## Roadpoints

### R1 — reviewer blocking fixes

- 状态: TODO
- 步骤: 补红测；修复 Gateway reconcile 缓存 payload；修复 cron presenter success/failure detail；跑窄口 pytest。
- 验证: `pytest -q tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py tests/unit/personal_assistant/test_cron_tool_closure.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py`
