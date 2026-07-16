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

## R4 — Apply failure 首次投影与 Reconnect 入口

- Context: projection 只在存在 observed row 时把 durable `last_apply_error_json` 转成 failed，首次启动失败因此显示 pending；Reconnect 专用 SQL 又未选择 `_view_from_row()` 在有 observed 时必读的 manifest head 字段，Connected → Reconnect 触发 Row KeyError/HTTP 500。
- Decision: durable apply error 解码成功即设置 `sync_state=failed`；Reconnect 查询与标准 channel projection 对齐，join/select head revision、applied revision 和 last error。
- Rationale: desired apply outcome 是持久化控制面事实，不依赖 runtime 是否成功发过一次 status；所有构造 `ChannelView` 的查询必须提供同一 projection schema。
- Evidence:
  - Tests: C1 首次 failure 得到 pending，真实 connected-status Reconnect 得到 HTTP 500；C2 后 projection、HTTP/WS lifecycle 和 agent channels API `7 passed`，focused Ruff passed。
  - Entry: observed=null + `channel_start_failed` 返回 failed 和具体 message；same-revision applied 清除 error，在 runtime status 到达前诚实回到 pending。
  - Frontend State Matrix: error/missing data 的服务端输入已稳定。
  - Browser QA: 延至 R6。
  - E2E/Regression: 真实 websocket 注册、manifest applied、channel.status connected 后，POST Reconnect 返回 200，socket 收到相同 channel revision 的 `channel.reconnect`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: Reconnect command 不改变 desired revision，符合 `prototype.html#channel-reconnecting`。
- Rollback: 回退 R4 C1/C2/C3 commits；会恢复首次失败不可见和 connected Reconnect 500。
- Commits: C1=`14262be7d`，C2=`5e14313f7`。

## R5 — Offline last-known 与 removal retry 产品反馈

- Context: frontend 把所有 `sync_state=failed` 都放在 offline stale 判断之前，导致 runtime observed failure 在节点离线后仍冒充当前失败；removal Retry 无离线产品分支，直接把 HTTP 409/raw code 放进全局 error。
- Decision: 用非空 `apply_error` 区分 durable control-plane failure，pending/apply failure 保持高优先级，其余 observed 状态在 offline 时统一 last-known；offline Retry 不发 live command并显示 localized waiting notice，online/offline 竞态 code 也映射到同一反馈，notice 仅在对应 removal receipt 仍存在时展示。
- Rationale: desired apply failure 是当前持久化事实，runtime failure 是节点最后一次上报；live-only retry 在离线时不是请求失败，而是等待节点恢复的可解释状态。
- Evidence:
  - Tests: C1 offline runtime failed 仍呈现 Connection failed，removal Retry 调用 API；C2 后 panel Vitest `13 passed`。
  - Entry: offline connected/limited/failed 均显示最后已知状态和最后更新时间；pending 与 durable apply error 仍分别显示等待应用/具体失败。
  - Frontend State Matrix: default、empty、error、submitting、permission-limited、nullable observed、offline stale 均由同一 panel suite覆盖。
  - Browser QA: 延至 R6。
  - E2E/Regression: offline failed-removal 点击 Retry 不调用 API、不显示 `channel_node_offline`；query cache 收敛为空后 waiting notice 和 alert 同时消失。
  - Visual/Interaction: waiting notice 使用现有 amber offline 语义，未引入版本或 Web IM 文案。
  - Prototype Comparison: 对齐 `#channel-failed` 的 last-known 层级和 `#channel-deleting` 的失败可重试/成功无残影。
- Rollback: 回退 R5 C1/C2/C3 commits；会恢复 offline failure 冒充实时状态与 raw retry error。
- Commits: C1=`a21ee1a35`，C2=`76c0807ac`。
