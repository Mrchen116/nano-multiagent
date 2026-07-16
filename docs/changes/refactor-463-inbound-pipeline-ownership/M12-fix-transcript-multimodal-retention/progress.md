# M12 Progress

## Context

- Round 5 acceptance：20/20 用户场景通过，0 issue。
- Round 5 verification：FAIL，1 CRITICAL（silent heartbeat prefix trim 可删除后继用户历史）、3 WARNING（steer 图片降级、public SDK 契约缺口、format gate）。
- Round 5 code review：另确认 CronRunsStore materialized terminal history 随运行次数线性增长；critical background e2e 默认 Agent 未启用 bash，首次等待不构成有效产品证据。
- 用户约束：本轮现有 agent 结束后不再派发任何 subagent；M12 的实现、测试、复验、审查与发布由 orchestrator 本人完成。

## Decisions

- 数据修复必须发生在 Kernel conversation/transcript owner 内，以 run 的 terminal turn identity 选择性删除；不接受产品层 prefix truncate 或仅重置文件行数。
- 多模态 pending message 的 source of truth 是 `LLMMessage.content` 的 structured blocks；所有 steer/held/continuation 路径共用无损反投影。
- Cron durable JSONL 继续 append-only；只限制进程内 materialized terminal index，不删除审计历史。

## Evidence

待 R1-R3 完成后回填。

## Rollback

M12 独立提交；可按 R1/R2/R3 commit 逐项回退，不影响已通过的 M1-M11 产品主链路。
