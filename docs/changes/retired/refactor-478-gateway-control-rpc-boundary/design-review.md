# refactor-478 Design Review v3

> 评审对象：`motivation.md` v1、`design.md` v3\
> 评审日期：2026-07-25\
> 评审方式：不继承旧报告结论，重新追生产 wiring、11 类 wire codec、ACK/FIFO、领域 owner、canonical specs/tests 与 Claude Code 对照源码

## Design 评审：refactor-478-gateway-control-rpc-boundary

**结论：Issues Found**

v3 的主架构方向成立：IM 继续由 `GatewayControl` 独占 correlation，PA 继续由
`IMConnectionManager` 独占 receive/wire/FIFO/ACK/reconnect/同步 close，并通过一个窄
`ControlRequestDispatcher` 把 11 类 operation 语义移出 transport；单 M1 原子切换也正确。
生产组装、配置 provider/local-store 写入边界、managed-channel 排除和 CC 对照均核实成立。

但 v3 仍有两个阻断实施的行为等价缺口：

1. 新 codec seam 没有逐 operation 固定 request 字段当前哪些严格报错、哪些宽松归一化；IM result
   matrix 还漏了 `agent.capabilities.workspace_root` 的现有必填校验。worker 必须猜 codec，可能把现有
   空值 result 改成断连/timeout，或把现有 malformed result 改成成功 ACK。
2. v3 新写的 cron raw delete 规则与当前生产实现对“JSON list 混有非-dict row 且目标 job 不存在”
   的行为相反，照文档实现会把当前 `deleted:true` + 清理写回改成 `deleted:false` + 不写。

另有一处不阻断架构方向、但应补入 grounding 的 canonical/live drift：cron HTTP canonical 写
`/cron-jobs`，生产与守护测试实际使用 `/cron/jobs`。

## 核实台账

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状：IM 有 11 张 waiter map | 逐项读 `GatewayControl.__init__` | ✓ 11 张 map 分别位于 `src/IM/ws/gateway/control.py:24-34`，与 11 个 request/result family 一一对应。 |
| 现状：IM request register-before-send、timeout、finally cleanup 重复 | 对照各 request 方法 | ✓ `agent.config` 在 `control.py:102-120`，其余 request 重复同一生命周期直到 `control.py:557`；统一私有 lifecycle 有真实删除对象。 |
| 现状：IM runtime 原栈发送 resolver 返回值 | 从 WS serve 正向追 handler | ✓ `GatewayRuntime.serve()` 在 `src/IM/ws/gateway/runtime.py:73-90` await handler 后原栈 `send_json(response)`；11 个 result handler wiring 在 `runtime.py:147-157`。 |
| 现状：生产 PA receive owner 唯一 | 从 CLI/组装/监督入口正向追 | ✓ `main.py:104-108` → `process_lifecycle.py:823-827` → `composition.py:551-591` → `gateway/runtime.py:284-293,634-675` → `IMConnectionManager.run_forever()` `im_connection.py:673-718` → `_listen_once()` `im_connection.py:843-1356`；没有平行生产 receive loop。 |
| 现状：PA connection 独占 wire/FIFO/ACK | 追 `send_json` 到 owner release | ✓ `send_json` 只入统一队列（`im_connection.py:477-483`）；`_flush_pending_frames` 只允许一个 owner（`:1358-1400`）；`_ack_pending_frame` 仅在 ACK `message_type` 等于原始 result frame 时释放（`:1432-1446`）。 |
| 现状：managed-channel close 必须同步 | 追 status result await 栈 | ✓ status result 在 `_listen_once` 原栈调用 bindings，收到 `CLOSE_CONNECTION` 立即 await close（`im_connection.py:948-970`）；v3 决策 3/7 明确排除并保留。 |
| 现状：配置 live read 经 provider，不直接读 local-store | 追 composition 注入到 owner | ✓ production 注入 `IMAgentConfigSync.current_agent_payload`（`composition.py:551-564`）；它从 `RuntimeConfigOwner` snapshot 投影（`agent_config_sync.py:565-582`），dispatcher 应继续只见该 provider。 |
| 现状：agent create 写入经既有 owner | 追 create handler 到持久化 | ✓ production 注入 `IMAgentConfigSync.handle_agent_create`（`composition.py:575`）；它通过 `_publish_agent_config` → `_persist_agent_config` → `RuntimeConfigOwner.persist` 先 durable save 后 publish（`agent_config_sync.py:529-558`；`local_store.py:351-364`）。v3 保留“existing handler”边界成立。 |
| 现状：capabilities/prompt/fork 已有 provider/handler | 追 composition wiring | ✓ agent/node capabilities、prompt preview、session fork 全由 `composition.py:564-580` 注入；v3 没让 dispatcher 反向 import local-store/kernel 内部。 |
| 现状：heartbeat 仍内联文件 IO | 读生产分支与错误投影 | ✓ `im_connection.py:1188-1214` 仅 request id 严格，workspace 非 string 归一为 `""`；缺失/OSError 回 `content:""`。 |
| 现状：cron list/delete 仍内联 raw JSON IO | 读生产分支与存储 owner | ✓ list 在 `im_connection.py:1216-1247` 保留原 JSON list；delete 在 `:1269-1314` 直接过滤 raw rows。另有 typed `CronJobStore` 在 `scheduler/cron_scheduler.py:65-152`，其 `_read_all()` 会丢 invalid row/unknown typed 信息，v3 选择新增 control-compatible raw codec 的方向正确。 |
| 现状：skills usage 是 connection 同文件 helper | 读 helper 完整数据源/错误路径 | ✓ request branch 在 `im_connection.py:1248-1267`；聚合、shared roots、损坏文件 skip 在 `:1675-1814`，适合整体移入一个 projection owner。 |
| 现状：canonical 有已知 skills wire drift | 对照 canonical、生产、测试 | ✓ canonical `gateway/relay-protocol.md:31-42` 写 `skills_usage_request/response`，生产是 `node.skills.usage.request` / `node.skills.usage`（`im_connection.py:1248-1267`）；v3 `design.md:62-64,281-282` 已上报并指定 live wire + tests 为 authority。 |
| 现状：canonical 另有 cron HTTP path drift | 对照 canonical route 与守护测试 | ✗ canonical `docs/specs/im/agents-nodes.md:102-108` 写 `/cron-jobs`，生产 routes 是 `/cron/jobs`（`src/IM/api/routes/agents.py:735-787,833-873`），integration tests 也固定 `/cron/jobs`（`tests/im_service/integration/test_agent_config_api.py:739-857,1016-1119`）；v3 只上报 skills drift。 |
| CC 对照：transport interface 窄化 | 读本地 CC 源码 | ✓ `replBridgeTransport.ts:11-70` 把连接版本差异藏在 `ReplBridgeTransport` 后；v3 没照抄其部署形态。 |
| CC 对照：ingress routing 与 typed control handler 分开 | 读本地 CC 源码及 production wiring | ✓ `bridgeMessaging.ts:218-300` 先 parse/dedupe/routing，`:304-381` 定义 typed handler，`remoteBridgeCore.ts:449-473` 组装；v3 提炼为 transport/codec/dispatcher 分责是有效类比。 |
| 决策 1：具名 API + 单 pending table | 检查完整性、归属、删除测试 | ✓ public named request 保持 route 可发现性，私有 `_request` 收敛 11 份 lifecycle；删除该 abstraction 会把重复重新散回 11 个方法。 |
| 决策 1：同锁、发送前注册、timeout/finally/late 统一 | 对照现有并发顺序 | ✓ `control.py:105-120` 等现有路径先在共享 lock 注册、再 send、finally pop；v3 明确保留。 |
| 决策 2：settlement 与 exact ACK projection 同入口 | 对照全部现有 result handler | ✓ 所有现有 handler 即使无 waiter也返回 operation-specific ACK（`control.py:559-787`）；v3 `design.md:108-121` 明确 valid unknown/late/mismatch 仍 ACK，malformed 不伪 ACK。 |
| 决策 2：不顺带 node identity correlation | 对照 scope/auth owner | ✓ motivation 明示不改 auth/node routing；IM runtime 在 handler 前按 socket owner authorize（`runtime.py:130-142`）。独立 bugfix 而非本重构扩 scope 合理。 |
| 决策 3/op1：`agent.config.get → agent.config` | 逐字段核 request/result/ACK/failure | ✓ PA 严格 request id/agent id，provider 缺失回 `agent:null`（`im_connection.py:977-993`）；IM result 接受 object/null，ACK 带 agent id（`control.py:559-580`）；5s/None fallback 在 `control.py:94-120`。 |
| 决策 3/op2：`agent.create → agent.created` | 同上 | ✓ request id + agent mapping 严格，missing/non-mapping handler result 回 `{}`（`im_connection.py:994-1011`）；IM 要求 node id + agent object，ACK 带 node id（`control.py:582-599`）；5s/None fallback `:122-148`。 |
| 决策 3/op3：`session.fork.request → session.fork.result` | 同上 | ✓ PA 只先严格 request id，raw body 交既有 handler，missing/exception 断连，mapping result 展开（`im_connection.py:1013-1031`）；IM 除 node id 外原样 settle，ACK 带 node id（`control.py:233-251`）；10s/None fallback `:183-231`。 |
| 决策 3/op4：`node.capabilities.resolve → node.capabilities` | 同上 | ✓ request id/required provider，provider failure 断连（`im_connection.py:1032-1051`）；IM 要求 node id + object capabilities，ACK 带 node id（`control.py:626-645`）；15s/None fallback `:253-278`。 |
| 决策 3/op5：`agent.capabilities.resolve → agent.capabilities` | 同上 | ✗ PA 严格 request id/agent id/workspace，optional provider 非 mapping回 `{}`（`im_connection.py:1052-1074`）；IM 除 capabilities 外还**显式要求 result 的 `workspace_root`**（`control.py:601-624`），但 v3 result matrix `design.md:219` 没列该必填字段。 |
| 决策 3/op6：`agent.prompt.preview.request → agent.prompt.preview` | 同上 | △ frame/result/10s/ACK 正确（`im_connection.py:1076-1131`；`control.py:280-340,647-671`），但 request codec 对 features/custom/tool/skill/scenario 的宽松归一化没有写进 v3，见 CRITICAL-1。 |
| 决策 3/op7：`node.prompt.preview.request → node.prompt.preview` | 同上 | △ frame/result/10s/ACK 正确（`im_connection.py:1132-1187`；`control.py:342-390,673-697`），但只有 request id 严格、其余多字段宽松归一化；v3 未固化，见 CRITICAL-1。 |
| 决策 3/op8：`node.heartbeat.md.request → node.heartbeat.md` | 同上 | △ result/10s/ACK/empty fallback 正确（`im_connection.py:1188-1215`；`control.py:392-433,699-721`），但当前不校验 agent id、workspace 非 string→空；v3 未固化 request codec。 |
| 决策 3/op9：`node.cron.jobs.request → node.cron.jobs` | 同上 | △ result/10s/ACK/empty fallback 正确（`im_connection.py:1216-1247`；`control.py:435-475,723-744`），但当前不校验 agent id、workspace 非 string→空；v3 未固化 request codec。 |
| 决策 3/op10：`node.skills.usage.request → node.skills.usage` | 同上 | △ result/10s/ACK/empty projection 正确（`im_connection.py:1248-1268`；`control.py:521-557,770-787`），但当前 request id/agent id 严格而 workspace 宽松；v3 未固化 request codec。 |
| 决策 3/op11：`node.cron.delete.request → node.cron.delete` | 同上 | ✗ result/10s/ACK/false fallback 基本正确（`control.py:477-519,746-768`），但 v3 新 raw-delete 规则和当前混合脏行行为冲突，见 CRITICAL-2；request job/workspace 的宽松 codec 也未固化。 |
| 决策 3：只含 11 类、排除单向/managed/transport | 对 `_listen_once` 全部分支做集合差 | ✓ v3 `design.md:123-145` 精确列 11 类并排除 relay/register/ACK/error/config.sync/heartbeat.trigger/permission/channel/bootstrap/reconcile；与 `im_connection.py:843-1356` 全分支一致。 |
| 决策 4：一个 operation-family dispatcher | 检查职责与 async 顺序 | ✓ dispatcher 只接 typed union、调用 provider、回 typed result，不持 socket/queue/cursor/task；单类避免 per-RPC class 爆炸。 |
| 决策 5：唯一 codec seam，connection 一个稳定分支 | 检查接口是否让两个 worker 无需猜 | ✗ seam 形状成立，但 v3 只有 frame inventory，没有 11 类 request 字段严格/宽松规则；“current `_require_text/_require_mapping` etc”不足以覆盖大量直接 fallback codec。IM result matrix还漏 agent capabilities 的 workspace 校验。 |
| 决策 5：decode exception 与 NotControlRequest 分离 | 对照现有 reconnect边界 | ✓ `_listen_once` 的 ValueError 上抛到 `run_forever`，后者断连并退避（`im_connection.py:673-718,843-861`）；NotControl 才继续现有分支是正确边界。 |
| 决策 6：HeartbeatDocumentReader owner | 删除测试与错误投影 | ✓ 文件规则从 transport 移到 scheduler/heartbeat 领域后，connection 可不再读文件；empty/not-found/OSError 规则明确。 |
| 决策 6：CronControlService + raw `CronJobStore` codec | 对照每个 raw row 分支 | ✗ unknown dict字段保留与不复用 `_read_all()` 正确；但“只有命中目标才写/true”不等于当前 `len(filtered)<len(data)` 判定，混合非-dict row 会漂移。 |
| 决策 6：SkillUsageProjection owner | 删除测试与数据依赖 | ✓ 当前 helper 有足够领域深度（local/shared usage、session refs、30 天 projection）；移入 gateway domain 后 transport 只编排。 |
| 决策 7：同步 dispatch、ACK 后释放 FIFO、close 同步 | 追完整 receive-owner 回路 | ✓ v3 `design.md:189-199` 与 `im_connection.py:843-970,1358-1446` 一致，没有 background dispatch 或异步 close mailbox。 |
| 决策 7：逐 operation failure matrix | 对照 provider missing/exception/文件失败 | ✓ matrix `design.md:231-247` 与生产大类一致，并明确不合成 universal failure frame；但 request decode 细节仍缺，不能替代 codec matrix。 |
| spec：不按 RPC 拆类、不引 event bus | 对照澄清记录与决策 | ✓ motivation `:19-24`，design 决策 1/4/5 均遵守。 |
| spec：不新增 RPC/不改 wire、timeout、错误和响应 | 对照 11 类 inventory | ✗ frame/timeout/ACK/failure大体闭合，但 codec matrix缺口与 cron delete冲突会改变错误/响应语义，违反 motivation `:32-36`。 |
| spec Scenario：配置 live read 与 save 保持 | 追 GET/PATCH 两条生产路径 | ✓ GET 经 `GatewayControl.request_agent_config`（`agents.py:322-353`）；PATCH仍由 IM route/service 持久化，相关 RPC registry 明确只纳 live read，单向 `config.sync` 排除。 |
| spec Scenario：prompt/fork/heartbeat/cron/skills 保持 | 对照 providers/文件 owner/route fallback | ✗ 架构落点齐，但 CRITICAL-1/2 未修前不能证明所有响应与副作用等价。 |
| spec Scenario：offline/timeout/late 保持 | 对照 request methods与 result handler | ✓ 所有 named request offline/send false/timeout 返回 None；finally移除 waiter（`control.py:94-557`）；v3 valid late result仍 exact ACK且不 settle。 |
| spec：回滚不留第二 queue/bus/compat dispatcher | 删除/回退检查 | ✓ v3 `design.md:284-294` 只整体回滚单路径，无双写长期态。 |
| delta-spec：kernel no delta | 对照包影响 | ✓ 不触及 `agent.sdk` 对外契约。 |
| delta-spec：IM no delta | 对照 motivation 与 canonical | △ 目标是纯内部重构，no delta成立；但 CRITICAL-1/2 若照文档实施会产生行为 delta，必须先消除。 |
| delta-spec：gateway no delta | 对照 motivation 与 canonical | △ 同上；设计须保持 live parity，不能借重构静默修 cron 脏行语义。 |
| delta-spec：cli no delta | 对照包影响 | ✓ 不触及 CLI。 |
| M1：单 milestone 原子切换 | 检查横切/并行/退出双轨 | ✓ IM correlation 与 PA dispatch 共享一条 wire cutover，拆成“IM/PA”会造半迁移；单 M1有明确 `[reviewer]` 与 `[worker]` 两轨退出。 |
| M1：11 类 contract inventory | 对照退出标准与缺口 | ✗ 退出标准虽提 request/result decoder，但 design 本体没给 request 字段基线，也没点出 agent capabilities result workspace；worker无法从架构契约无歧义产出 tests。 |
| 基线：相关协议与路由测试 | 运行当前分支窄基线 | ✓ 相关 10 个 test files 共 127 passed。 |
| 基线：全量非 e2e | 运行 `.venv` + xdist | ✓ `pytest -q -m 'not e2e' -n auto`：3725 passed，1 skipped；当前分支没有先验失败掩盖本报告结论。 |

## 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | IM pending registry、PA dispatcher、provider/local-store、heartbeat/cron/skills owner | △ 总体归属正确：correlation 留 `GatewayControl`，wire 留 connection，配置写入仍经 `IMAgentConfigSync/RuntimeConfigOwner`，cron raw IO归已有 store。存活问题是 codec contract 未完整归属到 descriptor/codec seam；不补会让严格/宽松规则继续散在 worker理解和测试偶然覆盖里，每次新增 operation 重现横切 drift。 |
| 该不该存在 | 单 pending table、ControlRequestDispatcher、三个领域 owner | ✓ 走完无存活发现。删除 pending abstraction会恢复 11 份 lifecycle；删除 dispatcher会把 operation switch 留在 transport；skills/cron规则也有真实领域复杂度，不是假想多态。 |
| 深还是浅 | `try_decode / dispatch / encode` 与 `CronControlService` | ✗ seam 的结构够深，但契约内容不完整：接口写“typed”却未隐藏/固定当前字段 normalization，worker仍需回到 500 行分支逐项猜；Cron wrapper 对脏行语义还写错。长期代价是 abstraction 表面统一、真实兼容规则仍散落或丢失。 |
| 治本还是补丁 | 消除新增 RPC 的横切修改 | △ 11 类封闭 inventory、单 registry、exact ACK 与同步 FIFO方向已经治本；CRITICAL-1/2 未修时，codec/存储边界仍会以回归测试补洞，不能宣称行为保持。 |

## Issues

### [CRITICAL] 决策 5 / 接口与数据流：codec inventory 没有固定现有逐字段严格/宽松语义，typed seam 仍迫使 worker 猜

**不改的具体坏事**

`design.md:157-171,231-247` 定义了 typed decode 与 failure matrix，但没有给 11 类 request payload
的字段 codec。当前生产并不是“一律 typed strict”：

- agent prompt 只严格 `request_id/agent_id/workspace_root`，`features` 非 object→`{}`、
  tool/skill list过滤非字符串、scenario 非 string→`direct`
  （`src/personal_assistant/ws/im_connection.py:1079-1104`）。
- node prompt 仅 request id 严格，workspace 非 string→`""`，其余字段同样宽松
  （`:1135-1163`）。
- heartbeat/cron list 不验证 agent id，workspace 非 string→`""`
  （`:1192-1196,1219-1224`）。
- skills usage严格 request id/agent id、宽松 workspace（`:1249-1254`）。
- cron delete严格 request id、宽松 job id/workspace且不验证 agent id（`:1273-1279`）。

若 worker按“typed request”把这些字段都改成 required，旧 IM/异常 payload 原本返回 empty/default
result的路径会变成断连、重连和 HTTP timeout；若全部宽松，又会把当前真正 malformed 的 request
静默接受。反向 result codec 也有实漏：现有 IM `_handle_agent_capabilities` 明确要求 result
`workspace_root`（`src/IM/ws/gateway/control.py:604-611`），v3 表 `design.md:219` 未列，worker可能
让该 malformed result从连接错误变成 settlement + ACK。

**精确修订要求**

1. 在 `## 接口与数据流` 增加 11 行 **PA request decode matrix**，每行至少列：
   - strict required fields；
   - tolerant/default/filtered fields；
   - raw passthrough（尤其 fork）；
   - decode failure 结果（connection failure → IM timeout）。
2. 把 IM result matrix改成完整 schema，而非只列“主要 normalization”；明确
   `agent.capabilities` result 仍要求 `workspace_root`，并核齐其余 operation-specific required
   fields与 ACK projection。
3. 更新 M1 `[worker]` 退出标准：contract inventory必须逐行覆盖 strict-invalid 与
   tolerant-invalid 两类样本，不能只覆盖 happy payload。

### [CRITICAL] 决策 6：cron raw delete 的“命中目标才写”与当前生产脏行语义相反

**不改的具体坏事**

当前 `node.cron.delete.request` 用：

```text
filtered = [item for item in data if isinstance(item, dict) and item.id != job_id]
if len(filtered) < len(data): write(filtered); deleted = true
```

证据是 `src/personal_assistant/ws/im_connection.py:1290-1303`。因此当文件为
`[{"id":"other"}, "corrupt-row"]`、请求删除不存在的 id 时，当前会过滤脏 row、写回并返回
`deleted:true`；v3 `design.md:177-183` 却要求“只有命中目标时才写，写成功才 true”，会返回 false
且不写。HTTP 可观察结果随之从 204 变 404，违反 motivation “不改变响应语义”与 no spec delta。

**精确修订要求**

二选一并拍死，不能继续把两者都称为“当前语义”：

1. 本纯重构 unit 保持 live parity：把 `delete_for_control()` 的 write/deleted 判定写成当前
   `len(filtered) < len(raw_list)` 语义，并要求 contract test覆盖“目标不存在 + 存在 non-dict row”；
   或
2. 若要纠正该现有行为：从 refactor-478 移出成独立 bugfix；若坚持同 unit，则必须回到 motivation
   明示行为修正、补用户可观察验收与相应 delta/契约 drift 说明，不能继续宣称 no behavior delta。

### [WARNING] 现状分析 / canonical grounding：遗漏 cron HTTP path 的 canonical/live drift

v3 已正确上报 skills wire drift，但 canonical `docs/specs/im/agents-nodes.md:102-108` 写
`/im/v1/agents/{id}/cron-jobs`，生产和前端/集成测试实际使用
`/im/v1/agents/{id}/cron/jobs`（`src/IM/api/routes/agents.py:735-873`；
`tests/im_service/integration/test_agent_config_api.py:739-857,1016-1119`）。

不补会让后续 worker/reviewer按 canonical 走 runbook 时请求错误路径，或误把协议边界重命名纳入本
unit。请在 `### 相关历史` 与 delta-spec authority 说明中把该 drift 和 skills drift并列，明确本 unit
不改名、live routes + tests为迁移基线；canonical 修复另行处理。

## Recommendations

无额外非阻断建议。先修 CRITICAL-1/2，并顺手补全 canonical drift 声明后再进入
`change-orchestrator`。
