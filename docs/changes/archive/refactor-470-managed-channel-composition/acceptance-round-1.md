# refactor-470 — Round 1 产品验收报告

> 验收对象：`unit/refactor-470` @ `20582b3cfb4fccb23c8300cb7ce7073bf593a55c`
>
> 验收口径：`motivation.md` 的用户侧验收标准与 `design.md` 的 Reviewer Runbook。

## Verdict

**fail**

**Highest Required Action：out-of-unit**

Gateway 的 managed Feishu 在线重连、IM 不可达时的 cached autonomy、IM 韧性和重启会话连续性均有真实进程/真实消息往返证据；但 heartbeat 的「有内容时冒泡」仍被既有产品缺陷 #126 阻断。`design.md` 已明确该路径是 strict xfail，且不能把 runner 单测替代成用户可见冒泡成功，因此本轮不能诚实地把完整用户验收判为 pass。

## User Journeys Exercised

1. **Gateway 重连与会话连续性**：本轮在隔离 worktree 运行 `scripts/e2e-critical.sh -k 'gateway_im_resilience or restart_session_continuity'`；真 IM 与真 Gateway 进程下 3 项通过，耗时 38.74 秒。用户消息在 IM 暂时异常后仍能得到回复，重启后会话继续可用。
2. **真实 Feishu 在线 reconnect**：复用 M4 在同一 unit 分支记录的真实 1:1 消息往返证据。IM 显示目标 channel `applied/connected`；用户发送 `refactor470-online-20260720-05 请只回复 ONLINE-470-OK` 后，在原 Feishu 会话收到 `ONLINE-470-OK`。
3. **真实 Feishu cached offline autonomy**：复用 M4 的真实离线验收。Gateway 指向无监听的本地高位 IM 地址、仍由 cached manifest/key 启动；用户发送 `refactor470-offline-20260720-01 请只回复 OFFLINE-470-OK` 后，在原 Feishu 会话收到 `OFFLINE-470-OK`。
4. **Cron 主动投递**：复用 M4 的隔离真栈证据：带可用模型路由的临时 Gateway 配置下，`test_cron_push_critical_path.py` 经 IM 用户可见路径收到 cron 哨兵消息，`1 passed in 39.48s`。本轮以默认 e2e source config 运行同一筛选时该项在等待 agent 回复阶段超时；M4 已记录其原因为该 source config 缺少测试固定模型，而不是 Gateway 旅程失败，故不将该未配置测试环境重复计为产品缺陷。
5. **进程启动与 auto-bind**：本轮重新运行 `scripts/e2e-up.sh`，其为 worktree 创建隔离 IM/Gateway、独立 node/workspace 并成功返回 ready；M3 记录的同分支真入口验收确认首次节点已自动绑定且没有要求打开浏览器。验收服务随后已停止，未保留与主服务竞争的进程。

## Reference Artifacts Reviewed

N/A。`design.md` 明确本 unit 没有前端交互或展示变更，也没有 prototype/reference 对齐契约。

## Issues

### 1. Heartbeat 有内容时无法完成可追问的用户消息旅程

- **Severity**：major
- **Regression Relation**：unrelated-existing
- **Recommended Action**：out-of-unit
- **Action Rationale**：`design.md` 的 Reviewer Runbook（第 444–445 行）明确当前 heartbeat 真链路受既有 #126 影响并保持 strict xfail；本轮没有可观察到「有内容时在 canonical 直聊冒泡」的结果。runner/scheduler 单测只能说明迁移未改变该内部执行面，不能证明用户收到可追问消息。
- **Existing issue**：#126（不重复创建 GitHub issue）。

## 验收标准覆盖

### Requirement: Managed channel 在线控制行为保持一致 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 在线保存后无需重启即可使用 | `motivation.md` 第 58–63 行；`design.md` 第 459–480 行 | 真实 Feishu 1:1 reconnect 后向同一 Bot 发送哨兵消息；对配置 apply、状态和能力激活的无破坏性覆盖按 Runbook 指定的 fixture suite 执行 | M4 `progress.md` 第 108 行：`applied/connected`，原会话收到 `ONLINE-470-OK`；本轮直接受影响回归 96 passed | pass | 真实 Bot 未被改写配置；避免在共享 channel 上作破坏性保存。 |
| 无效配置不伪装成功且不影响其他 Bot | `motivation.md` 第 64–68 行；`design.md` 第 483–484 行 | Runbook 指定的可控 unit/integration fixture 覆盖失败诊断和隔离 | 本轮 `test_channel_manager`、`test_channel_manifest_store`、`test_channel_status_*`、`test_channel_reconcile` 等直接回归合计 96 passed | pass | 设计明确要求该类破坏性场景用可控 fixture，不在共享真实 Bot 上制造无效凭据。 |
| 停用、删除或替换只作用于目标 channel | `motivation.md` 第 70–74 行；`design.md` 第 483–484 行 | Runbook 指定的多 channel/removal fixture 覆盖 | 本轮 `tests/integration/test_channel_removal_reconcile.py` 与 managed-channel 直接回归通过（96 passed） | pass | 不在共享真实 channel 上删除配置；真实 1:1 消息链路另见在线旅程。 |

### Requirement: Managed channel 离线自治与重连收敛保持一致 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| IM 离线重启后缓存 channel 仍可用 | `motivation.md` 第 78–82 行；`design.md` 第 459–480 行 | 同一 review cache/key、不可达 IM 地址下启动真 Gateway，再从真实 Feishu 私聊发送消息 | M4 `progress.md` 第 109 行：离线 Gateway 存活且持有 Feishu long connection；原会话收到 `OFFLINE-470-OK` | pass | 这是用户可见的真实消息往返，不以启动日志替代。 |
| IM 恢复后收敛到最新配置 | `motivation.md` 第 84–87 行 | 隔离真 IM/Gateway 韧性旅程；在线 Feishu reconnect 复核 | 本轮 `gateway_im_resilience` 真进程旅程通过；M4 第 108 行记录 reconnect 后 channel 为 `applied/connected` 并可完成往返 | pass | 运行中无需手工重启 Gateway。 |

### Requirement: Gateway 服务生命周期保持一致 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| start、stop、restart 结果不变 | `motivation.md` 第 91–94 行 | 隔离真 Gateway 关键路径重启，并运行 lifecycle 直接回归 | 本轮 `restart_session_continuity` 真进程旅程通过；`test_gateway_launch`、`test_gateway_pid_lifecycle` 等直接回归包含在 96 passed | pass | 本轮所有由验收启动的隔离服务均已停掉。 |
| 新节点自动绑定行为不变 | `motivation.md` 第 96–99 行 | 隔离 `e2e-up.sh` 自动建立新节点；复核已记录的真入口 auto-bind 证据 | 本轮 `e2e-up.sh` 返回 isolated stack ready；M3 `progress.md` 第 50 行记录唯一新节点获得 `owner_id`、日志记录 auto-bind，且无浏览器交互 | pass | 本轮隔离服务已清理。 |

### Requirement: Heartbeat 与 Cron 主动行为保持一致 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Heartbeat 有内容时冒泡、无内容时静默 | `motivation.md` 第 103–106 行；`design.md` 第 444–445 行 | 真用户可见冒泡要求不能由 runner 单测替代 | `design.md` 明确该真链路仍为 #126 strict xfail；本轮没有可观察到有内容 heartbeat 冒泡 | inconclusive | 既有缺陷，不归因给本 unit；但用户面结果未出现，不能标 pass。 |
| Cron 定时与手动运行保持现有语义 | `motivation.md` 第 108–111 行 | 带可用模型路由的隔离真 IM/Gateway 运行 cron critical path | M4 `progress.md` 第 107 行：经 IM 用户可见路径收到 cron 哨兵消息，`1 passed in 39.48s` | pass | 本轮默认 source-config 的超时已按 M4 已验证的配置前置判定，未将其当成迁移回归。 |

## Side Findings

- 本轮没有发现与本 unit 旅程相邻的新增 UI、消息或服务生命周期异常。
- `scripts/e2e-critical.sh` 的默认 source config 未配置 cron 固定模型时会超时；M4 已用隔离且可用的模型路由完成同一用户旅程。该环境前置不改变本 unit verdict。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。该文档已有 Gateway/IM 离线自治的跨包职责描述；本 unit 没有对外架构 delta。
- [x] `docs/specs/gateway/`（长青行为契约层）：无需更新。`design.md` 说明本 unit 不改变 current observable behavior；本轮所见 heartbeat #126 是既有 issue，不是本次 delta。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`：无需更新。
