# Design Review: feat-464 IM Agent 通道设置（v7 第七次 Gate 2 全量重审）

## 结论

**Approved — 0 CRITICAL / 0 WARNING。**

本轮以当前磁盘 v7 为唯一基线，从头重建现状、9 项决策、首文档全部 Requirement/Scenario/Q/用户场景/非目标、两份 delta、prototype 与 3 个 Milestone 台账，并重追 IM/Gateway/Feishu/frontend 的生产 wiring。此前全部问题均保持根因级关闭：BindService 对首次空 owner、同 owner 幂等与跨 owner 409 的事务边界已拍死；`channel.status` 有 correlated terminal/retry/fatal result 并先释放单槽上行 FIFO；removal receipt 的 7 天清理与 applied-head terminal replay 已闭合；IM delta 的 canonical 归并语义与 Scenario 归属也已修正。

设计主体、两份 delta、原型和 Milestone 已具备交给 `change-orchestrator` 的边界。IM delta 现在把 canonical 原标题「设备绑定把节点归属到当前用户」放入 `MODIFIED Requirements`，完整保留既有 start/稳定 400 场景，并补齐首次空 owner、同 owner 幂等、跨 owner 409；「并发更新发生 revision 冲突」也已回到 desired/revision Requirement。机械归并后 canonical 唯一、自洽，核对腿与四角架构进攻均无存活发现。

## 历次问题关闭复核

| 旧问题 | v7 结论 | 证据 |
|---|---|---|
| C1 已初始化节点跨 owner rebind 未定义 | 已关闭、未回归 | design.md:298-302 固定首次空 owner 才绑定、同 owner 幂等、跨 owner 返回 `409 node_owner_transfer_not_supported`；跨 owner 路径对 node/Agent/channel/head/key/removal 零写入，manual/auto 共用 guard，换 owner 必须使用新 node_id。spec.md:177-184、IM delta:184-218 与 M1-E6 测试约束同步覆盖。 |
| C2 stale/removed status barrier 会堵单槽 ACK FIFO | 已关闭、未回归 | design.md:214-216 固定六态 correlated result；stale/removed 正常 terminal dequeue，removed 额外摘 registry 并 quarantine/stop，store busy dequeue 后尾部重试，owner mismatch close + 全 managed quarantine。design.md:473-481 固定按 request_id 先释放 `_awaiting_ack_type` 再派发 domain handler；Gateway delta:164-170 与 M3-E6 覆盖。 |
| W1 7 天 receipt 清理后 Gateway outbox 永久重放 | 已关闭、未回归 | design.md:171-173 只有 `>7d` 且 applied head 覆盖 deletion revision 才清 receipt；清理后仍在 node/owner/current absence/head 校验下返回 `already_applied_by_head`，Gateway 收 terminal ACK 删除 per-token outbox。Gateway delta:40-45 与 M2-E1/E5 覆盖 retention 后重放。 |
| IM delta 把既有绑定行为写成 ADDED，且 revision conflict 归属错误 | 已关闭 | IM delta:184-218 以 canonical 精确原标题写入 `MODIFIED Requirements`，保留 `start 返回绑定结构` 与 `缺动作必填字段返回稳定 400`，增加首次/同 owner/跨 owner 三分支；revision conflict 位于 desired/revision Requirement 内（47-75）。 |

## A. 当前实现断言台账

| 现状原子 | 核实动作 | 结论 + 生产证据 |
|---|---|---|
| A1 Agent 详情“通道”仍是占位 | 从真实 tab 渲染正向追 | ✓ `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1625-1656` 选择 channels 后仍渲染 `PrototypePlaceholder`，方案落点是生产入口。 |
| A2 IM 使用 app-scoped SQLite handle | 从 create_app 追 repository 注入 | ✓ `src/IM/app.py:255-332` 创建共享 connection 并注入 handlers/repos；`src/IM/infra/db.py:177-201` 使用 `check_same_thread=False`。设计引入独立 `ChannelControlStore` 作为单一事务 owner 合理。 |
| A3 Agent config 已有 profile_version 与 live 写回 seam | 从 HTTP service 追 Gateway sync client | ✓ `config_service.py:165-216` 做乐观锁；`main.py:325-478,634-707,858-881` 已有 fetch/PATCH/retry、live register 与 YAML 持久化，`FeishuActivationPolicy` 可复用真实 seam。 |
| A4 Gateway 生产入口从 YAML 一次性构建 channel | 从 `build_runtime` 正向追 registry | ✓ `main.py:2880-2927,3658-3700` 静态创建 WebRelay/Feishu；`ChannelManager` 接入同一 composition root，不是旁路实现。 |
| A5 ChannelRegistry 是浅容器 | 读唯一实现与 bootstrap caller | ✓ `gateway/channel_registry.py:10-48` 只有 register/get/list，`gateway/bootstrap.py:67-96` 统一 start/stop；扩锁与 replace/remove、把 reconcile 留给 manager 通过 deletion test。 |
| A6 Feishu listener 无真实 stop | 追 adapter → client → 安装 SDK | ✓ `channels/feishu/client.py:198-216` 仅清引用；lark-oapi 1.6.9 `ws/client.py:29-33,160-175` 使用包级 loop 且无公开 stop。每 Bot 进程隔离是根因级方案。 |
| A7 card action callback 必须同步返回 SDK response | 追 Feishu callback | ✓ `channels/feishu/client.py:602-611` 同步构造 `P2CardActionTriggerResponse`；双向 deadline RPC 保留生产契约。 |
| A8 runtime_name 决定路由/session continuity | 追 registry/outbound/session key | ✓ `main.py:3683-3697` 固定 `feishu:<agent_id>`，outbound router/session key 消费 channel name；control-plane UUID 不渗入消息身份。 |
| A9 owner binder 只在当前 owner 为空时写入 | 追 adapter/binder | ✓ `adapter.py:459-476` 与 `main.py:3703-3744`；App identity revision + generation CAS 防止旧 App open_id 继承。 |
| A10 register、ack、on_connected 的真实顺序 | 追双端状态机 | ✓ IM `_handle_register` 先登记 connection（`gateway_handler.py:927-959`），serve 返回后才 ack（145-163）；Gateway `_send_frame` 只发送、不等待 register ack（`im_connection.py:277-312,863-871`）。ack 后调度 coordinator 的前提成立。 |
| A11 bind confirm 当前无条件改写 owner | 追 route → service → repository | ✓ 现有 `src/IM/application/bind_service.py:59-74` 无条件 `assign_owner` + `reassign_owner_by_node`，repositories 的 owner 更新也无 guard。design.md:298-302 明确要求把 guard 收进同一事务、跨 owner 零写，确实修改生产路径并关闭旧缺口。 |
| A12 Feishu doc skill 当前由静态 YAML 启动补入 | 追 helper 与 canonical | ✓ `config/local_store.py:396-430`、`main.py:2880-2884` 与 `docs/specs/gateway/agent-capabilities.md:116-135`；activation policy 复用 config sync 并保持启动行为。 |
| A13 IM/Gateway ACK seam 是单槽上行 FIFO | 追 enqueue、ack、error 三条路径 | ✓ `src/personal_assistant/ws/im_connection.py:336-354,847-899` 在 `_awaiting_ack_type` 非空时阻塞后续且普通 ack 才 dequeue；827-844 generic error 只记日志。design.md:214-216,473-481 已精确要求 correlated result 先按 request_id 释放槽位，再处理 stale/removed/retry/fatal。 |
| A14 frontend 有共享 user-stream 与 query invalidation seam | 追 runtime 与 settings consumers | ✓ `realtime/user-stream` 是共享 runtime；`nodes-page.tsx:65-75`、`agent-status-ws-consumer.ts:58-70` 已使用精确 query invalidation，可承接 channel status。 |
| A15 测试命名/大小是真 contract | 追 contract test | ✓ `tests/contract/test_test_naming_and_size_contract.py:94-152` 禁 milestone 文件名并限制新测试文件 400 行；M3-E7 明确纳入。 |

## B. 编号决策台账

| 决策 | 四问核实 | 结论 + 证据 |
|---|---|---|
| D1 节点公钥 envelope | 算法/AAD/revision、keep/replace、App ID change、key loss、跨 owner | ✓ design.md:116-133 拍死 envelope 与 AAD；298-302 选择拒绝跨 owner transfer，避免 re-envelope/旧 cache 歧义，spec.md:177-184 驱动。 |
| D2 desired/observed/removal 分表分版本 | transaction owner、receipt/head/error/view/re-add guard、status CAS | ✓ design.md:135-155 与 388-439 把 desired、observed、removal receipt、partial unique guard 和 received-at/CAS 分离；无双 owner。 |
| D3 IM desired 权威 + encrypted cache | full manifest、removal intent、partial result、same-revision retry、outbox/retention | ✓ design.md:157-175 闭合 never-seen、zero-item、partial removal、per-token outbox、ACK loss 与 retention 后 terminal replay。 |
| D4 ChannelManager 唯一 lifecycle owner | stable identity、activation、metadata generation、串行 replace/stop | ✓ design.md:177-203 接到生产 composition root；registry 不承载 reconcile，manager 删除后复杂度会散回 WS/main/adapter。 |
| D5 per-Bot process + 多 lane IPC | capacity/backpressure/RPC/sequence/CAS/cutover/status outbox | ✓ design.md:205-227 固定 stop A → active B → B seq1 → start B，六态 status result 与 FIFO 释放、RPC deadline、drain/drop 均无二义。 |
| D6 connection 与 diagnostics 分开 | state catalog、missing/unknown、scope catalog、received-at | ✓ design.md:229-276 与 spec.md:106-140 一致，且覆盖真实 Feishu send/history/reaction/chat/scope 调用面。 |
| D7 通用 REST/UI/provider registry | provider-neutral resource、前后端 provider registry、单实例约束 | ✓ design.md:278-285；通用 resource 与 provider-owned validation/schema 能支撑当前 Feishu 和下一 provider，不预造动态 schema 服务。 |
| D8 initialized head + coordinator | register/bind/reconnect、per-node lock、request id、ack 后调度、owner transfer | ✓ design.md:287-312 拍死三触发同一 coordinator、同 WS manual bind、full manifest 与 owner guard；跨 owner 明确非目标并要求新 node_id。 |
| D9 三个串行纵向 Milestone | 规模举证、依赖、范围交集、两轨退出 | ✓ design.md:314-323,675-683 给出超单 worker 规模举证，M1→M2→M3 明示串行；每个 M 都跨 IM/Gateway/frontend 且有 reviewer/worker 两轨。 |

## C. 首文档约束台账

| Requirement | 覆盖 / 冲突 / 越界核实 | 结论 + design 落点 |
|---|---|---|
| R1 通用外部 channel 管理页 | 对照 4 个 Scenario | ✓ 通用 REST/provider registry、single-provider unique、empty/error/duplicate-provider UI，design.md:278-285,510-527。 |
| R2 飞书轻量向导与 credential UX | 对照 4 个 Scenario | ✓ 指定 launcher、必填、opaque secret、keep/replace、App ID 强制新 secret，design.md:116-133,278-285。 |
| R3 连接状态与可操作诊断 | 对照 6 个 Scenario | ✓ 状态 catalog、missing/unknown、actionable failure、received-at、causal sequence 与 manual retry，design.md:205-276。 |
| R4 离线配置与重连收敛 | 对照 2 个 Scenario | ✓ IM desired + Gateway encrypted cache + full manifest/removal/outbox，design.md:157-175。 |
| R5 飞书 channel 生命周期 | 对照 3 个 Scenario | ✓ real stop、credential replace、enable/reconnect/delete、no-cascade、删除待应用与 failure retry，design.md:177-227,388-439。 |
| R6 节点绑定不得隐式迁移跨 owner channel | 对照唯一 Scenario | ✓ design.md:298-302 固定 409 与零状态写入，manual/auto 同 guard，换 owner 用新 node_id；IM delta:184-218 以 MODIFIED 完整投影，worker 与收尾归并均无须猜。 |

### C1. 首文档逐场景

| Scenario | 结论 | 证据 |
|---|---|---|
| 尚未配置任何外部 channel | ✓ | prototype `#channels-empty`；M1-E1。 |
| 从统一入口选择 channel 类型 | ✓ | provider registry、`#add-feishu`；M1-E2。 |
| 当前类型已经存在 | ✓ | DB unique、provider disabled；pending removal guard，applied 后可 re-add。 |
| channel 列表加载失败 | ✓ | `#channels-error` + retry，不降级为空态。 |
| 用户查看飞书准备指引 | ✓ | 短说明与指定 launcher。 |
| 在线节点保存有效配置后立即连接 | ✓ | desired commit → reconcile → seq1 barrier → runtime → observed。 |
| 必填凭据缺失 | ✓ | POST/replace contract 与 prototype 字段校验。 |
| 已保存密钥不会明文展示 | ✓ | GET/list opaque，编辑显式 keep/replace。 |
| 权限完整且连接正常 | ✓ | complete/connected + causal status。 |
| 权限不足但基础能力可用 | ✓ | limited + raw scope/effect/remediation。 |
| 缺少普通群消息权限 | ✓ | `im:message.group_msg` 与群背景上下文影响明确。 |
| 暂时无法完成权限检查 | ✓ | unknown，不伪造 missing。 |
| 凭据或连接无效 | ✓ | actionable failed status/delta/prototype。 |
| 连接暂时中断 | ✓ | same-incarnation reconnect sequence；manual reconnect 使用确定 cutover。 |
| 节点离线保存新增/修改/启用/停用/删除 | ✓ | desired 保存、pending projection、removal intent 与 outbox 齐全。 |
| 节点重连后自动应用 | ✓ | stale/removed status terminal ACK 先释放 FIFO，full manifest/result/status 可继续收敛。 |
| 停用已连接 channel | ✓ | confirm → pending/disabling → observed disabled。 |
| 重新启用 channel | ✓ | credential keep；stop-old/active-new/barrier/start-new。 |
| 删除 channel 保留历史 | ✓ | no-cascade、never-seen、partial outcome、failure retry 与 applied-head terminal 均齐。 |
| 已绑定节点被另一个 owner 确认 | ✓ | 409、事务零写、旧 owner API 隔离与 same-owner 幂等均进入 design/M1-E6。 |

### C2. 澄清、用户场景与非目标

| 原子 | 结论 | 对账 |
|---|---|---|
| Q1 完整 connection lifecycle | ✓ | D3-D6 覆盖配置、保存即连接、状态、停用、重连。 |
| Q2 offline 仍可编辑且区分 saved/applied | ✓ | desired/observed/removal projection 与 cache/outbox 闭合。 |
| Q3 轻量向导、多 channel 通用模型 | ✓ | 通用 registry + Feishu 首实现。 |
| Q4 不展示 Web IM | ✓ | `web_relay` 排除。 |
| Q5 删除配置、保留历史 | ✓ | receipt 与 history no-cascade。 |
| Q6 权限不足允许降级并逐项呈现 | ✓ | limited/missing/unknown。 |
| Q7 每 Agent/每 provider 单实例 | ✓ | DB unique + UI/removal guard。 |
| U1 通用 channel 管理页 | ✓ | 架构/API/UI 一致。 |
| U2 首次飞书接入 | ✓ | coordinator、向导、热连接。 |
| U3 全状态与诊断 | ✓ | causal status、actionable diagnostics、received-at。 |
| U4 offline save/reconnect | ✓ | full manifest + local cache + terminal result。 |
| U5 edit/enable/disable/reconnect/delete/secret | ✓ | D1-D5 闭合整个 lifecycle。 |
| U6 一对一与未来 provider 扩展 | ✓ | stable UUID/runtime name + provider unique。 |
| N1 不展示 Web IM | ✓ | 未越界。 |
| N2 不实现其他 provider | ✓ | 只有 Feishu production validator/factory。 |
| N3 不支持同类多账号 | ✓ | 未越界。 |
| N4 不复制完整平台教程 | ✓ | 只有短说明和外链。 |
| N5 不改变既有私聊/群聊/影子会话/审批/文档行为 | ✓ | stable identity、activation policy、父进程 approval、generation metadata。 |
| N6 删除不清理历史 | ✓ | schema 无 cascade，manager 不调用 conversation/message owner。 |
| N7 不新增群级白/黑名单 | ✓ | 未越界。 |

## D. Delta-spec 台账

| Delta Requirement | 全部 Scenario / canonical / 用法核实 | 结论 |
|---|---|---|
| IM「Agent 通道页管理通用外部 channel」 | 未配置空态 / 同 provider 禁重复 / list error；锚 `agents-nodes.md` | ✓ 真新增，THEN 均为用户可观察结果。 |
| IM「飞书 channel 提供轻量接入向导」 | provider 向导 / App ID+Secret 必填 / online save | ✓ 真新增。 |
| IM「Channel 期望配置版本化且与实际运行状态分离」 | online result / offline final desired / manual bind / revision conflict | ✓ revision conflict 位于同一 Requirement 下（IM delta:47-75）；四个 Scenario 完整且 THEN 可观察。 |
| IM MODIFIED「设备绑定把节点归属到当前用户」 | canonical:189-204；start / 首次空 owner / 同 owner 幂等 / cross-owner 409 / stable 400 | ✓ 标题精确锚 canonical，正文是修改后的完整契约；原 start/400 场景忠实保留，新增三分支与 design/spec 一致（IM delta:184-218），归并后不会留下平行矛盾。 |
| IM「Channel 凭据写入后保持不透明」 | opaque / App ID 必须新 secret / offline cached key / missing key | ✓ 真新增，consumer-visible。 |
| IM「Channel 状态诊断可操作且区分 missing 与 unknown」 | limited / group permission / unknown / actionable failed / reconnecting / status time / same-revision old status | ✓ 与 D5/D6 和 user-stream 对账。 |
| IM「Channel 生命周期不级联删除聊天历史」 | disable confirm / disable-enable / delete history / manual reconnect | ✓ 真新增，用户可观察。 |
| Gateway「完整 manifest 调和 managed external channels」 | hot add / duplicate / higher revision missing / zero-item / never-seen / ACK-loss replay / stop failure retry | ✓ 真新增，removal intent/outbox/head terminal 完整。 |
| Gateway「本地密文 manifest 离线启动」 | offline restart / reconnect convergence | ✓ runtime 自治与 authoritative manifest 收敛无冲突。 |
| Gateway「Managed Feishu 保持既有身份与能力」 | stable identity / owner bind / App replacement / feishu-doc / card action | ✓ 新控制路径保持 canonical 行为。 |
| Gateway「动态 lifecycle 立即影响实际收发」 | disable / credential replace / multiple Bots isolation | ✓ 真 stop/replace/isolation 可观察。 |
| Gateway「上报实际状态与权限诊断」 | complete / limited / group permission / scope unknown / SDK reconnect / same-version causality / stale cached barrier terminal | ✓ v6 新增 stale/removed terminal Scenario 正确覆盖 status FIFO。 |
| Gateway「旧 YAML 只在首次初始化时导入」 | first import / manual bind no reconnect / half failure / standalone | ✓ 与 D8 coordinator、legacy compatibility 对账。 |

两份 delta 都指向最窄 canonical area；ADDED/MODIFIED 用法正确，MODIFIED 未静默删除旧 Scenario；所有 Scenario THEN 都是消费者可观察结果，没有内部函数/类调用断言，Gateway 作为代码消费者的视角也对准。

## E. Prototype 与 Milestone 台账

| 原子 | 结论 | 证据 |
|---|---|---|
| `#channels-empty / #add-feishu / #channel-connecting / #channel-connected` | ✓ | empty、provider disabled、required、online connecting、connected/time 均可驱动。 |
| App ID + secret replacement | ✓ | prototype.html:947-956 检测 App ID 变化、禁 keep、自动选择 replace 并说明原因；改回原 ID 恢复 keep。 |
| `#channel-disabling / #channel-disabled` | ✓ | online confirm 先 disabling，模拟 observed 后才 disabled；re-enable 先 connecting。 |
| `#channel-pending` offline enable/disable | ✓ | desired 文案变化但保持 pending/offline。 |
| `#channel-deleting` online/offline/failure/applied | ✓ | prototype.html:883-910 区分 deleting/deleting_online/delete_failed；1014-1021 覆盖 confirm/retry/applied；reload 文案和 applied 后空态齐全。 |
| `#channel-reconnecting / #channel-failed / #channel-limited / #channels-error` | ✓ | stable reconnecting、actionable error、missing/unknown、load retry 齐。 |
| `#channels-mobile` | ✓ | 375×812 单列与 bottom sheet 对齐。 |
| M1 在线安全接入与热连接 | ✓ | 跨 IM/Gateway/frontend 的可用纵向切片；M1-E1..E8 两轨齐，补充约束把 legacy 收窄为 factory/generation seam，并覆盖 owner bind guard、App replacement、IPC/cutover。 |
| M2 离线收敛、迁移与完整 lifecycle | ✓ | M2-E1..E8 覆盖 full manifest/cache/bootstrap/removal never-seen/ACK loss/retention、离线 UI 与真 apply result。 |
| M3 权限诊断、异常态与响应式验收 | ✓ | M3-E1..E8 覆盖 diagnostics/status ordering/stale terminal FIFO、移动端、全量检查与真飞书 smoke。 |
| 拆分与并行性 | ✓ | design.md:314-323 给出规模/密码学/跨进程/前端状态机举证；M1→M2→M3 串行且共享范围被诚实声明，无同组 worktree 冲突。 |

## F. 四角架构进攻

| 角度 | 攻击对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | `ChannelControlStore` / coordinator / `ChannelManager` / Feishu worker / frontend provider registry | ✓ 走完无存活发现：事务、初始化、runtime lifecycle、SDK 隔离与 UI schema 分别落在自然 owner；组合后不产生 core/platform 或产品包反向依赖。 |
| 该不该存在 | store、coordinator、manager、provider factory/policy、removal/status outbox | ✓ deletion test 均通过：删掉任一层都会把 owner guard/事务、初始化 race、动态 stop、provider side effect 或离线 ACK 状态机散回 route/main/adapter。 |
| 深还是浅 | registry vs manager、full manifest vs command log、status/reconcile result | ✓ manager 藏住 replace/stop/cache/outbox，registry 保持浅容器；full manifest 和 correlated results 比调用方猜测重试/删除更深，无平行同类设施可直接复用。 |
| 治本还是补丁 | owner transfer、SDK global loop、deletion/ACK loss、status causal order | ✓ 当前方案选择 server-side owner guard、per-Bot process、explicit removal + per-token outbox + applied head、incarnation/sequence + terminal result，均解决根因而非叠特例。 |

## Issues

无。

## Recommendations

- 可进入 `change-orchestrator`；实施时按 M1→M2→M3 串行推进，并保留补充验收约束中 owner bind、status terminal FIFO、removal retention 与 runtime cutover 的交错测试。
