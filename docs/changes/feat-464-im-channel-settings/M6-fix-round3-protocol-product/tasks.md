# M6: Round 3 protocol and product recovery — Tasks

> 对齐: ../design.md v13

## 目标

闭合 Round 3 verifier 与真实产品验收确认的协议发送端、安全迁移、断线队列、首次 apply failure 投影，以及 Reconnect/offline/removal retry 缺口。完成后，Gateway 所有 node-scoped 上行帧都满足统一身份 guard，离线状态和操作反馈不再冒充实时事实，通道生命周期可从失败恢复到无残影终态。

## 退出标准

- [ ] `agent.config`、`agent.message`、streaming/system message、heartbeat/report/result/delivery/channel 等真实 Gateway 上行帧在公共发送边界携带当前注册 `node_id`；协议错误作为 terminal result 释放当前 FIFO 与 waiter，后续帧继续发送。
- [ ] legacy Feishu `appSecret` 与缺失 `feishu-doc` 的显式 skills 组合启动时，skill 激活和 bootstrap migration 共享安全配置 owner；递归扫描配置目录无明文 backup/temp，最终主文件仅有 `credentialRef`、skills 已持久化、mode `0600`。
- [ ] IM 断线期间，同 channel 多次 runtime replacement 的内存 `channel.status` 队列只保留当前 incarnation 的可重放帧；不影响其他 frame FIFO，重连不发 superseded status，迟到 ACK/result 幂等。
- [ ] current manifest 的 durable apply error 在没有 observed row 时也投影 `sync_state=failed` 和具体原因；同 revision applied 后立即清错。Connected → Reconnect 通过真实 HTTP/WS action 进入 reconnecting 或可操作失败，不返回 500。
- [ ] 节点离线时 observed connected/limited/failed 统一显示 last-known；desired pending 与 durable apply failure 继续优先。offline removal Retry 显示等待节点的产品反馈，不暴露 raw 409，手动或自动成功后旧提示消失，空态无残留 alert。
- [ ] 三个 Round 3 失败旅程与直接回归完成真实浏览器复验；focused/full backend、frontend test/build、Ruff、test-size、secret scan、`git diff --check` 和进程清理全绿。

## 测试策略

- 被测行为（来自退出标准）：公共 sender 注入 node identity、protocol rejection terminal dequeue、断线 status incarnation 合并、安全 startup/bootstrap migration、无 observed 的 apply failure、Reconnect HTTP/WS action、offline last-known、offline removal Retry 与成功清警报。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_im_connection_behavior.py`、`tests/unit/personal_assistant/test_channel_status_protocol.py`、`tests/unit/personal_assistant/test_channel_legacy_migration.py`、`tests/unit/personal_assistant/test_sensitive_local_config.py`、`tests/unit/IM/test_channel_apply_failure_projection.py`、`tests/im_service/integration/test_agent_channels_api.py`、`src/IM/frontend/src/features/settings/agents/agent-channels-panel.test.tsx`（扩展）；不新建流水号命名测试文件。
- 落层/目录/marker：`tests/unit/`、`tests/integration/`、`tests/im_service/integration/` 与前端 Vitest，marker：无；真进程/真浏览器只作本 milestone durable evidence，不把一次性脚本提交进测试套件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：隔离高位端口 IM/Gateway/frontend 的浏览器驱动脚本和运行日志；截图与 sanitized journey report 保存在 `M6-fix-round3-protocol-product/evidence/`，临时脚本/PID/配置收尾删除。

用户路径分类：
- critical-path：Gateway→IM 上行 FIFO、bootstrap migration、manual reconnect/removal retry，永久 regression + 真实产品入口。
- normal-ui：offline last-known 与 waiting-for-node 反馈，永久 Vitest + 真实浏览器。
- visual-only：状态文案和 alert 清理，以 desktop/mobile 截图对照。
- bug-regression：Round 3 verifier/acceptance 的七项确认问题全部落永久回归。

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | online connected 与 applied 保持现有结构 |
| loading | 复跑既有 channels loading 测试 |
| empty | removal 成功后空态无旧 alert |
| error | durable apply failure 无 observed；removal failure 保持具体原因 |
| disabled | disable/re-enable 既有状态不回归 |
| submitting | Reconnect 显示稳定 reconnecting；Retry 显示 waiting 或成功 |
| permission denied | offline limited 以 last-known 呈现 |
| long content | apply/removal 原因可换行，不显示 raw JSON |
| missing/nullable data | observed=null + apply_error 仍失败可见 |
| mobile viewport | 375×812 offline failed/removal recovery |
| desktop viewport | Connected→Reconnect、offline failed、removal retry |
| dark mode（如项目支持） | 项目无独立 dark-mode contract，N/A |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| sender 缺 node_id 被统一 guard 拒绝 | 真实 producer shape unit + FastAPI websocket regression | 是 |
| protocol error 阻塞 FIFO/waiter | connection FIFO unit | 是 |
| migration 前含密 backup | composition-root/bootstrap 文件扫描 | 是 |
| 断线 status 内存增长/旧 incarnation 重放 | connection queue unit + durable outbox regression | 是 |
| 首次 apply failure / reconnect 500 | store projection + HTTP/WS action integration | 是 |
| offline stale/removal raw error与残影 | Vitest + 真浏览器 desktop/mobile | 是（截图为交付证据） |

Prototype / Reference Contract：
| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| `prototype.html#channel-reconnecting/#channel-failed` | must-match：Reconnect 进入恢复过程；offline failed 不冒充当前探测 | desktop 真实操作 + offline 截图 | worker |
| `prototype.html#channel-deleting` | must-match：失败可重试，offline 是等待节点反馈，成功后 card/警报同时消失 | desktop 失败→offline retry→恢复截图 | worker |
| `prototype.html#channel-pending/#channels-mobile` | must-match：offline last-known/pending 层级与 375×812 可用 | desktop + 375×812 对照 | worker |

## Roadpoints

### R1 — 公共上行身份与 terminal FIFO

- 步骤：在 Gateway 唯一发送边界为所有受 guard 的业务帧注入注册 `node_id`；把可关联的 generic protocol error 转成 terminal dequeue/ack-future failure，再 flush 后续帧。
- 验证：真实 agent.config/agent.message/streaming/system/report/delivery/channel producer shape 全部携带 node；bad frame 不阻塞后续 frame，waiter 得到明确异常。
- 状态：完成。最终 wire sender 统一用本机 reporter identity 覆盖所有上行 payload；serialized protocol error 终结当前 head、失败 waiter 并立即发送下一帧。

### R2 — 安全 startup/bootstrap 配置收敛

- 步骤：把 Feishu skill activation 纳入单一 `RuntimeConfigOwner` 和无 backup 的安全 writer；bootstrap cleanup 在同一 owner 上同时保留 skill 变更并移除 secret。
- 验证：legacy secret + 显式 skills 缺 skill 的真实 build/bootstrap 后，目录递归零明文、零 backup/temp，主文件 `credentialRef + feishu-doc + 0600`。
- 状态：完成。composition root 在任何 skill bootstrap 持久化前建立共享 owner，并统一使用 sensitive writer；后续 manifest bootstrap cleanup 在同一快照上移除 legacy secret。

### R3 — 断线内存 status 队列有界化

- 步骤：队列入口按 channel/revision/current incarnation 合并尚未发送的 `channel.status`，新 incarnation 淘汰旧状态；已发送 head 与其他业务帧保持 FIFO。
- 验证：断线 40 次 replacement 后队列有界；重连只发 current；迟到旧 result no-op；node.report 等 frame 顺序不变。

### R4 — Apply failure 首次投影与 Reconnect 入口

- 步骤：把 current head apply error 的失败投影移出 observed-row 条件；修复 reconnect 读取 projection 缺失 manifest head 字段的根因，保持 command 不改 desired revision。
- 验证：observed=null 时 failed+reason，same revision applied 清错；真实 API → notifier → Gateway downstream action 返回 200 并进入 reconnecting，不再 500。

### R5 — Offline last-known 与 removal retry 产品反馈

- 步骤：区分 durable apply failure 与 observed runtime failure，offline observed failed/limited/connected 都降级 last-known；offline Retry 映射为 waiting-for-node notice，资源成功消失时自动清理 notice/alert。
- 验证：pending/apply failed precedence、offline failed/limited/connected、raw 409 屏蔽、manual/automatic success 清提示与空态无 alert 的 Vitest。

### R6 — 浏览器复验与全量门禁

- 步骤：隔离高位端口重跑 Connected→Reconnect、offline failed、removal retry 三个失败旅程及首次 apply failure/安全迁移直接回归，保存 prototype 对照与 sanitized 证据；执行全量 gate 并清理进程、symlink 与临时文件。
- 验证：真实浏览器无 500/raw 409/stale alert，desktop/mobile 状态收敛；所有测试、build、lint、size、secret、diff、process gate 全绿。
