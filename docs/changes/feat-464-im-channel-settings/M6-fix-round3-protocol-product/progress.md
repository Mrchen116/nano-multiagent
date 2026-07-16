# M6 — Progress

实现基线：`e05d59c56344f3f45c74474416b16d126198445d`。Baseline focused backend `45 passed`；focused frontend `22 passed`。

## R1 — 公共上行身份与 terminal FIFO

- Context: M5 已在 IM dispatcher 统一要求所有 node-scoped 上行帧携带并匹配注册 node，但 Gateway 的 `agent.config`、`agent.message`、streaming/system 和若干 report/result producer 仍可省略该字段；IM 的 generic error 又只记日志，当前 FIFO head 和 ack waiter 会永久占槽。
- Decision: 在 `_send_frame()` 这个唯一 wire 边界以 reporter 注册 node 覆盖 payload `node_id`；generic protocol error 依据单槽 wire FIFO 终结当前 pending frame，给显式 waiter 设置异常并立即 flush 后继。
- Rationale: sender identity 属于 transport envelope，不应由二十余个业务 producer 各自维护；客户端一次只允许一个未确认 frame，因此没有 request metadata 的旧 server error 也能无歧义对应当前 head。
- Evidence:
  - Tests: C1 两项 regression 先稳定 `2 failed`；C2 后 `pytest -q test_gateway_im_connection_behavior.py test_channel_status_protocol.py test_channel_reconcile.py test_gateway_im_resilience.py test_gateway_im_auth.py` → `47 passed`；focused Ruff → passed。
  - Entry: 公共 `send_json` 入口逐一发送 IM guard 的 21 种业务 frame，最终 websocket JSON 全部为 `node-1`；bad `agent.message` 后 waiter 收到 `bad_payload` 异常且下一 `node.report` 已上 wire。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py::test_every_guarded_upstream_frame_carries_registered_node_identity` 与 `::test_protocol_error_terminally_releases_waiter_and_flushes_next_frame`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R1 C1/C2/C3 commits；会恢复旧 producer 缺 identity 与 error 卡 FIFO 行为。
- Commits: C1=`cf46a3931`，C2=`560b0f94c`。

## R2 — 安全 startup/bootstrap 配置收敛

- Context: Gateway composition root 会先用普通配置 writer 持久化 `feishu-doc` allowlist，再建立 `RuntimeConfigOwner` 和执行 legacy channel bootstrap；默认主配置路径上的普通 writer 会把尚含 `appSecret` 的旧文件复制进 `backups/`。
- Decision: 在 skill activation 前建立唯一 `RuntimeConfigOwner`，并将该启动期变更改由 `save_sensitive_local_config` 串行持久化；bootstrap applied handler 继续复用同一 owner 清理 legacy secret。
- Rationale: migration 完成前的每一次完整 YAML 写入都属于敏感写入；共享 owner 同时避免 skill 激活与 credentialRef 迁移彼此覆盖。
- Evidence:
  - Tests: C1 真实 `build_runtime → bootstrap provider → applied handler` 先因配置目录残留明文 backup 稳定失败；C2 后四个 focused 文件 `19 passed`，focused Ruff passed。
  - Entry: 默认 `$HOME/.nano-assistant/config.yaml` 含 legacy marker、Feishu 显式 skills 缺 `feishu-doc`，启动后 reload 得到 `credentialRef + feishu-doc`，主文件 mode `0600`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 递归扫描配置目录所有文件均无 marker，且 `*.bak` / `*.tmp` 均为空。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R2 C1/C2/C3 commits；会恢复启动顺序中的普通 backup writer。
- Commits: C1=`491a2f264`，C2=`1d13b1d3d`。

## R3 — 断线内存 status 队列有界化

- Context: durable outbox 已按 runtime incarnation 设置 barrier，但 websocket manager 在断线时仍把每次 replacement 的 `channel.status` 逐条 append；恢复后会重放旧实例，并让无关 frame 等待过时结果。
- Decision: 在唯一 pending-frame 入队边界按 `channel_id` 合并未发送 status；新 incarnation 淘汰旧 incarnation，同 incarnation 保留必要 barrier；成功写过 wire 的 head、带显式 waiter 的 frame 和所有非 status frame不参与合并。
- Rationale: durable outbox 决定可接受的 generation barrier，内存层只负责消除尚未发送的陈旧快照；已发送 head 的投递结果不确定，必须等待关联 result，不能被本地猜测删除。
- Evidence:
  - Tests: C1 断线 40 次 replacement 稳定得到 41-frame queue；C2 后 status protocol/outbox/connection/resilience focused suite `46 passed`，focused Ruff passed。
  - Entry: `node.report` 先入队，40 个 status replacement 后 pending 仅 `node.report + status-39`；连接后 wire 只出现 current `inc-39`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `status-0` 迟到 result 不释放 `status-39` head，只有 current result 触发 handler。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R3 C1/C2/C3 commits；会恢复断线队列随 replacement 次数线性增长。
- Commits: C1=`84d7558d0`，C2=`7d7a27cd3`。
