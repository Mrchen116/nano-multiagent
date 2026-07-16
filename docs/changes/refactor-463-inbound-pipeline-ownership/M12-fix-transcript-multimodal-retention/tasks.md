# M12 — transcript、多模态与历史保留闭环

Round 5 产品验收 20/20 通过，但 implementation verification/code review 发现一个数据安全阻断项和四个发布前闭环项。本 milestone 由 orchestrator 根据用户“后续不再派 subagent、全部亲自完成”的明确要求直接实施。

## R1 — Kernel owner 精确清理 silent heartbeat

- [ ] 先写真实 Kernel/Conversation 回归：heartbeat run 后已有更晚用户 turn/reply 时，清理只删除 heartbeat turn，保留后继记录、parent chain 与下一轮 provider context。
- [ ] 为 persisted turn 写入稳定 turn identity，并由 ConversationSession 在 turn gate 内串行执行选择性删除、原子重写、tail 修复与 loaded-state invalidation。
- [ ] 通过 public Kernel run identity 暴露中立清理 seam；heartbeat completed+silent 使用该 seam，failed/cancelled 不清理；删除产品层按行数直接改 JSONL 与 submit 前文件扫描。

## R2 — steer 多模态与 cron 有界索引

- [ ] 把 active steer 的 parts 投影改为与普通 turn 相同的结构化 content；纯文本仍走 string path。
- [ ] held pending 与异常终态 continuation 从 `LLMMessage.content` 无损恢复 text/image parts，覆盖 `/stop` 与 terminal fallback。
- [ ] CronRunsStore 每 job 只保留最新 100 条 terminal materialized records，所有 accepted/running 仍保留；live append 与 restart replay 结果一致。

## R3 — 契约、e2e 与发布门禁

- [ ] 在 canonical `sdk-boundary.md` / `runs.md` 记录 `try_steer` inject-only、expected-run identity 与多模态语义，并校正 unit delta 判定。
- [ ] background critical e2e 通过公开 Agent config 显式启用 bash，避免 `tools=[]` 的无效前置。
- [ ] 格式化本 unit 改动并通过 `ruff check .`、`ruff format --check .`、test naming/size contract、聚焦测试、全量 non-e2e 与 `git diff --check`。

