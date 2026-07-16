# M4: 首轮验收安全与生命周期修复 — Tasks

> 对齐: ../design.md v11

## 目标

修复 Round 1 已证实的在线停用卡死，并收口认证、跨 owner 原子性、凭据恢复、本地明文、provider 诊断、worker 生命周期、metadata/activation 与前端多 provider 分派缺口。完成后真实 IM/Gateway/Feishu 和浏览器用户路径可独立复验，不再依赖 M1-M3 的声明性证据。

## 退出标准

- [x] M4-E1：真实 connected → disable 在 90 秒内进入 disabled 并停止收发；enable 不重填 secret 即恢复；delete 保留历史；stop/cache failure 可见且可重试。
- [x] M4-E2：无效凭据、Bot 未启用、长连接/事件配置不可用均产生 provider-owned 稳定原因；offline create/update/enable 在节点重连后自动收敛。
- [x] M4-E3：未认证或错误 owner 的 Gateway 无法覆盖 node/key/socket；跨 owner 并发 bind 只有一个成功，关联 channel/head/key/removal/envelope 边界不变，同 owner 幂等。
- [x] M4-E4：manifest 单项解封失败/cache key loss 不被解释为删除，不推进 applied head且 Gateway 仍可连 IM；上报 `credential_reentry_required`；迁移/导出不留明文 backup，首次可见即原子 `0600`。
- [x] M4-E5：partial start、registry failure、FIFO backpressure、disable/replace/reconnect 均回收旧 PID；重试有界、单 listener，Gateway heartbeat/ACK 不被 stop/join 阻塞。
- [x] M4-E6：bot/owner metadata 在匹配 generation 下持久化并可重放，旧 generation 被拒；activation 失败可重试；前端 registry 驱动 provider 选择、表单、mutation、卡片、诊断，第二 provider fixture 不落入 Feishu 路径。
- [x] M4-E7：十项缺口均有永久 regression；真实栈、真飞书和浏览器证据关闭 Round 1 fail/inconclusive；secret scan、进程清理及全门禁通过。

## 问题映射

| # | Round 1 / dispatch 问题 | Roadpoint | 退出标准 |
|---|---|---|---|
| 1 | connected → disable 卡住；真实 stop/disabled/re-enable | R4、R6 | E1、E5、E7 |
| 2 | 无效凭据/Bot 未启用/长连接配置错误缺少稳定诊断 | R3、R6 | E2、E7 |
| 3 | `/im/ws/gateway` 未认证及错误 owner 覆盖攻击 | R1 | E3、E7 |
| 4 | bind guard/write 跨事务并发越权 | R1 | E3、E7 |
| 5 | envelope/key mismatch 被当删除或阻止连接 | R2 | E4、E7 |
| 6 | worker partial start/backpressure/lifecycle 泄漏 | R4 | E5、E7 |
| 7 | legacy 明文 migration backup/export 权限窗口 | R2 | E4、E7 |
| 8 | metadata generation 持久化/重放与 activation retry 缺失 | R3 | E6、E7 |
| 9 | 前端 registry 仅展示，mutation/card/diagnostics 仍硬编码 Feishu | R5 | E6、E7 |
| 10 | offline create/update/enable、history delete、stop/cache fail UI 缺独立旅程 | R6 | E1、E2、E7 |

## 测试策略

- 被测行为：逐条覆盖上表十项问题与 M4-E1…E7；并保持 M1-M3 已有 channel/reconcile/status/card-action 行为。
- 已有测试在：`tests/im_service/unit/test_gateway_handler.py`、`tests/im_service/integration/test_account_binding_api.py`、`tests/unit/personal_assistant/test_channel_manifest_store.py`、`tests/unit/personal_assistant/test_local_store.py`、`tests/unit/personal_assistant/test_channel_manager.py`、`tests/unit/personal_assistant/test_feishu_worker_runtime.py`、`tests/integration/test_channel_reconcile.py`、`src/IM/frontend/src/features/settings/agents/agent-channels-panel.test.tsx`（扩展）；为隔离认证攻击、并发 bind、provider preflight、生命周期和 provider dispatch，按行为新建不超过 400 行的聚焦 regression 文件。
- 落层/目录/marker：纯状态机/序列化落 `tests/unit/`；SQLite 多连接、IM/Gateway 协议与真实子进程落 `tests/integration/`；HTTP/WS 用户边界落 `tests/im_service/integration/`；真实飞书 smoke 落 `tests/e2e/` 且 marker `e2e`；前端分派落 Vitest。
- 可选依赖 importorskip：真实 Feishu e2e 使用现有 `lark_oapi` 与本机持久配置；非 e2e regression 无可选依赖。
- 一次性验收证据：`evidence/output/playwright/` 状态截图与 snapshot、`evidence/output/runtime/` 真实栈/飞书脱敏日志、`evidence/output/secret-scan.txt`、`evidence/summary.md`。确定性 cache failure 使用 `scripts/fixtures/channel_cache_commit_failure.py`：它有显式环境门禁，只能包装隔离 Gateway，并且不向生产 API 暴露 fault switch。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | connected 卡片、provider picker、真实 Feishu 恢复 |
| loading | 保持既有 skeleton；浏览器确认无回退 |
| empty | applied removal 后才空态；历史会话仍可打开 |
| error | list error、provider 结构化失败、stop/cache failure + retry |
| disabled | observed disabled 后终态；enable 不要求 secret |
| submitting | create/update/enable/disable/delete pending 投影 |
| permission denied | limited/unknown diagnostics 保持；错误 owner WS 不产生 UI 假成功 |
| long content | provider remediation 长文在卡片内换行 |
| missing/nullable data | missing observed/metadata 与 unknown check 不崩溃 |
| mobile viewport | 375×812 picker/form/confirm/失败原因可触达 |
| desktop viewport | 1440×900 全用户旅程 |
| dark mode（如项目支持） | 当前产品无独立 dark mode contract，N/A |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| WS owner spoof / bind race | 两个真实 access token + 独立 SQLite connection 并发 | 是 |
| credential reentry / local secret | cache key/envelope 故障注入 + mode/backup/exception scan | 是 |
| provider failure / metadata / activation | provider seam 稳定错误码、断线重放、失败后 retry | 是 |
| worker 泄漏 / event-loop 阻塞 | 真实非协作 child PID、满队列、heartbeat/ACK 时限 | 是 |
| multi-provider dispatch | 注入第二 provider fixture，断言完整路径 | 是 |
| Round 1 真实产品路径 | 隔离 IM/Gateway + 真飞书 + Playwright | 临时证据 + 关键 regression 落库 |

### Prototype / Reference Contract

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| `#channel-disabling/#channel-disabled` | must-match：只有 observed/apply result 后进入 disabled | desktop disable/enable 前后截图 + WS/进程证据 | worker |
| `#channel-deleting/#channels-empty` | must-match：receipt pending/failed 不空态，applied 后空态 | offline reload、retry、history 保留截图 | worker |
| `#channel-reconnecting/#channel-failed` | must-match：稳定且可操作的 provider 原因 | 无效凭据恢复与 reconnect 截图 | worker |
| `#channel-pending/#channel-connected` | must-match：offline desired 与 observed 分离 | offline create/update/enable → reconnect 截图 | worker |
| `#channel-limited/#channels-error` | must-match：诊断与 list error 不伪造空态 | desktop/mobile 浏览器回归 | worker |
| `#channels-mobile` | must-match：375×812 单列与底部 sheet | 移动截图 | worker |

## Roadpoints

### R1 — Gateway WS 身份边界与原子 bind

- 步骤：认证 `/im/ws/gateway` 的 bearer identity；register 时校验既有 owner 后才写 socket/key；用单一 SQLite transaction owner 完成 bind guard + node/profile/default-entry 更新，保持 channel/head/key/removal/envelope 不变。
- 验证：未认证关闭；错误 owner 攻击无法覆盖/解密；两个 owner 并发仅一个成功；同 owner 重试幂等；现有 account binding/gateway 回归全绿。

### R2 — Credential re-entry 与本地 secret 安全写

- 步骤：把单项 envelope/key-loss 转成保留 desired/runtime/cache 的 `credential_reentry_required`，禁止提交不完整 manifest/applied head；Gateway 仍连接并上报；迁移和 export 使用无 plaintext backup 的 fsync + atomic replace + `0600` writer。
- 验证：单项失败不触发 stop/delete；cache key mismatch 可启动并连 IM；恢复凭据后收敛；异常中断无宽权限/临时明文；secret scan 无遗留。

### R3 — Provider preflight、metadata replay 与 activation retry

- 步骤：在 runtime cutover 前执行 Feishu provider-owned preflight，保留官方错误码语义；新 generation 接纳后持久化 bot/owner metadata 并在重连重放；activation 只有成功才记忆，连接恢复时重试。
- 验证：无效凭据、Bot 未启用、长连接配置错误分别稳定；旧 generation patch 被拒；metadata 离线后重放；activation 首次失败二次成功。

### R4 — Worker 生命周期、背压与真实停用收敛

- 步骤：任何 start/registry 失败回收 partial child；满队列触发有界生命周期处理而非孤儿 listener；stop/replace/reconnect 移出 Gateway event loop 阻塞路径；修正 disable status generation/incarnation 因果。
- 验证：真实 child PID 无泄漏；单 listener；backpressure 有稳定终态/有界重试；heartbeat/ACK 在 stop/join 期间仍推进；connected → disabled → enabled 收敛。

### R5 — 前端 provider registry 真分派

- 步骤：provider descriptor 驱动 picker、表单状态/校验、create/update serialization、card summary、diagnostics；生产 registry 只发布 Feishu，测试注入第二 provider。
- 验证：第二 provider 可选、独立唯一性、payload/card/diagnostics 不出现 Feishu 字段/链接；Feishu 与原型既有状态不回退；Vitest/build 通过。

### R6 — 独立真实旅程与全门禁

- 步骤：隔离 IM/Gateway + 真飞书关闭 Round 1 fail/inconclusive；Playwright 驱动 offline create/update/enable、connected disable/re-enable、delete/history、stop/cache failure/retry；保存脱敏证据并清理进程。
- 验证：M4-E1…E7/十项映射逐条有证据；Ruff、frontend test/build、`pytest -m "not e2e"`、test-size、secret scan、`git diff --check` 全绿。
