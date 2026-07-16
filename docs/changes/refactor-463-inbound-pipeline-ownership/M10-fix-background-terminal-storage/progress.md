# M10 Progress

## 2026-07-16 — Planning

- Round 4 issue fingerprint `heartbeat-late-baseline` 首次出现：consumer 在 scheduler submit 后才统计 transcript，快 run 会把本轮 prompt/ack 纳入基线。
- Round 4 issue fingerprint `heartbeat-terminal-ignored` 首次出现：typed failed/cancelled outcome 被当作普通静默完成并可能 trim。
- Round 4 issue fingerprint `cron-no-delivery-success` 首次出现：支持的 `stream_delivery=None` 路径 submit 后立即写 completed。
- Round 4 issue fingerprint `cron-runs-or2` 首次出现：每次 status update 全量 materialize 无界 runs.jsonl，累计 I/O 为 O(runs²)。
- 正确修复边界：terminal consumption 是 background owner 的必选职责，用户投递/observer 是可选 adapter；持久化 owner 维护单次装载后的 materialized state。
