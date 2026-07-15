# Design Review: feat-464 IM Agent 通道设置（v7 第九次 Gate 2 全量重审）

## 结论

**Issues Found — 1 CRITICAL / 0 WARNING。**

本轮以当前磁盘 v7 为唯一基线，从头复核 15 项现状断言、9 项决策、首文档全部 Requirement/Scenario/Q/用户场景/非目标、两份 delta、prototype 与 3 个 Milestone，并重追 IM/Gateway/Feishu/frontend 的生产 wiring。

本次“通道不具有用户可见版本概念”的修订本身已经闭合：prototype 不再出现“配置版本 3 / 自动应用版本 4”，设计和 IM delta 明确不保存可浏览版本历史、不提供比较/选择/回滚，不在页面渲染 revision；内部 token 仍完整承担乐观锁、manifest 传输排序、desired/observed 关联和 stale status 隔离。此前跨 owner rebind、status terminal ACK/FIFO、removal receipt/outbox/retention、App identity generation、manual-bind bootstrap 等问题也均未回归。

第八轮问题只关闭了一部分：`accepted_scope_sets` 的 any-of/AND 集合语义、`recommended_scopes`、satisfied/missing/unknown 计算，以及 p2p/send/history 三类 legacy scope 已正确补齐；但决策 6 仍漏了飞书官方继续承认的普通群消息 legacy scope `im:message.group_msg:readonly` 和群信息 legacy scope `im:chat.group_info:readonly`。本 unit 明确迁移旧 YAML 配置，按当前表实施仍会把这两类存量应用误报为缺权限。该项修正并复审前不能进入 `change-orchestrator`。

## A. v7 用户可见版本概念专项核实

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| V1 页面不展示通道版本号 | 全文搜索 prototype 可见文本并执行 JSDOM 交互 smoke | ✓ `prototype.html:574-577` 只显示“当前配置已应用”，`661-679` 只显示“节点上线后自动应用”；DOM 可见文本无“配置版本 N / 应用版本 N / revision N”。 |
| V2 产品不提供版本历史、选择、比较或回滚 | 核决策与 IM delta | ✓ `design.md:136-151` 明确 revision 只作实现层令牌且禁止页面渲染；`specs/im/agents-nodes.md:47-75` 明确无可浏览、可选择、可回滚历史。 |
| V3 并发旧页面不会覆盖新配置 | 追乐观锁与 transaction owner | ✓ `design.md:154-159` 以独立短连接 + `BEGIN IMMEDIATE` 在事务内核对 token；IM delta `71-75` 要求过期 token 返回 conflict + latest view。 |
| V4 offline desired/observed 仍能区分“已保存/已应用” | 追 projection 与 full manifest | ✓ `design.md:142-180` 用 current desired token、observed token 与 manifest head 做服务端投影和重连收敛，UI 只消费 `sync_state`/状态结果。 |
| V5 stale status 不冒充当前配置 | 追双端 status CAS 与 terminal result | ✓ `design.md:215-223` 使用 incarnation/sequence + current internal token，stale/removed 返回可消费终态并 drop/quarantine；Gateway delta `127-170` 保持消费者契约。 |

## B. 当前实现断言台账

| 现状原子 | 核实动作 | 结论 + 生产证据 |
|---|---|---|
| A1 Agent 详情“通道”仍是占位 | 从真实 tab 渲染正向追 | ✓ `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1622-1656` 选择 channels 后仍渲染 `PrototypePlaceholder`，方案落点是生产入口。 |
| A2 IM 使用 app-scoped SQLite handle | 从 `create_app` 追 repository 注入 | ✓ `src/IM/app.py:270-332` 创建一个 app connection 并注入 handlers/repos；`src/IM/infra/db.py:177-201` 使用 `check_same_thread=False`。独立 `ChannelControlStore` 是必要 transaction owner。 |
| A3 Agent config 已有 optimistic lock 与 live 写回 seam | 从 HTTP service 追 Gateway sync client | ✓ `src/IM/application/config_service.py:165-216` 做 `profile_version` 更新并通知 sync；`src/personal_assistant/main.py:3031-3193` 装配真实 config sync / reconnect seam。 |
| A4 Gateway 生产入口从 YAML 一次性构建 channel | 从 `build_runtime` 正向追 registry | ✓ `src/personal_assistant/main.py:2920-2927,3658-3700` 静态创建 registry 与 Feishu/WebRelay，`ChannelManager` 应接入该 composition root。 |
| A5 ChannelRegistry 是浅容器 | 读唯一实现与 bootstrap caller | ✓ `src/personal_assistant/gateway/channel_registry.py:10-48` 只有 register/get/list；`gateway/bootstrap.py:67-97` 统一 start/stop。 |
| A6 Feishu listener 无真实 stop | 追 adapter → client → 安装 SDK | ✓ `src/personal_assistant/channels/feishu/client.py:159-216` daemon thread 的 `stop()` 只清引用；安装 SDK `lark_oapi/ws/client.py:29-33,160-175` 使用包级 loop 且无公开 stop。 |
| A7 card action callback 必须同步返回 SDK response | 追 Feishu callback | ✓ `src/personal_assistant/channels/feishu/client.py:602-611` 同步构造 `P2CardActionTriggerResponse`，双向 deadline RPC 必须保留此契约。 |
| A8 runtime name 决定路由/session continuity | 追 registry/outbound/session key | ✓ `src/personal_assistant/main.py:2927-3029,3683-3697` outbound 与审批按 registry name 查找，飞书稳定名为 `feishu:<agent_id>`；control UUID 不应渗入消息身份。 |
| A9 owner binder 只在 owner 为空时写入 | 追 adapter/binder | ✓ `src/personal_assistant/channels/feishu/adapter.py:459-476` 与 `src/personal_assistant/main.py:3703-3744` 为 first-wins，本设计需为 App identity replacement 增加 generation guard。 |
| A10 register、ack 与 connection 存储顺序 | 追双端状态机 | ✓ IM `gateway_handler.py:145-163,903-959` 先登记 connection、`serve()` 再发 ack；Gateway `im_connection.py:277-312` 当前只是发 register 后进入 on_connected。设计要求 server 在 ack 发出后调度同一 coordinator，落在真实路径。 |
| A11 bind confirm 当前无条件改写 owner | 追 route → service → repositories | ✓ `src/IM/application/bind_service.py:59-74` 无条件 assign/reassign；`repositories.py:2611-2617,2877-2888` 也无 guard。设计的 cross-owner 409 是生产缺口，不是旁路。 |
| A12 Feishu doc skill 当前按静态 YAML 启动补入 | 追 helper 与 composition root | ✓ `src/personal_assistant/config/local_store.py:396-435`、`main.py:2869-2884`；activation policy 复用真实 config sync 且保持 canonical 行为。 |
| A13 IM/Gateway ACK seam 是单槽上行 FIFO | 追 enqueue、ack、error | ✓ `src/personal_assistant/ws/im_connection.py:336-354,847-899` 在 `_awaiting_ack_type` 非空时阻塞后续，generic error `827-844` 只记日志；correlated terminal result 必须先 dequeue。 |
| A14 frontend 已有共享 user-stream/query invalidation seam | 追 production consumer | ✓ `src/IM/frontend/src/realtime/user-stream/index.ts:24-50` 是共享 runtime；`features/settings/nodes/nodes-page.tsx:65-75` 已精确 invalidation。 |
| A15 测试命名/大小是强 contract | 追 contract test | ✓ `tests/contract/test_test_naming_and_size_contract.py:94-152` 禁 milestone 文件名并限制新测试文件 400 行，M3-E7 已纳入。 |

## C. 编号决策台账

| 决策 | 四问核实 | 结论 + 证据 |
|---|---|---|
| D1 节点公钥 envelope | 算法/AAD/token、keep/replace、App ID change、key loss、跨 owner | ✓ `design.md:117-134` 拍死 envelope、AAD 与 key mismatch；`302-306` 拒绝 cross-owner transfer，避免 re-envelope/旧 cache 歧义。 |
| D2 desired/observed/removal 分表，用内部 token 关联 | token owner、receipt/head/error/view/re-add guard、status CAS | ✓ `design.md:136-159,329-454` 把 desired、observed、removal receipt、applied head 和 received-at/CAS 分离；不保留产品版本历史。 |
| D3 IM desired 权威 + encrypted cache | full manifest、removal intent、partial result、same-token retry、outbox/retention | ✓ `design.md:161-180` 闭合 never-seen、zero-item、partial removal、per-token outbox、ACK loss 与 retention 后 terminal replay。 |
| D4 ChannelManager 唯一 lifecycle owner | stable identity、activation、metadata generation、串行 replace/stop | ✓ `design.md:181-207` 接到生产 composition root；manager 删除后复杂度会散回 WS/main/adapter，deletion test 通过。 |
| D5 per-Bot process + 多 lane IPC | backpressure/RPC/sequence/CAS/cutover/status outbox | ✓ `design.md:209-231` 固定 stop A → active B → B seq1 → start B，六态 result/FIFO 释放、RPC deadline、drain/drop 均已拍死。 |
| D6 connection 与 diagnostics 分开 | 状态、missing/unknown、accepted scope alternatives、真实 API | ✗ `design.md:253-266` 的集合计算和 p2p/send/history 已修对，但普通群消息只列 `{im:message.group_msg}`，漏 `{im:message.group_msg:readonly}`（legacy）；群信息只列 `im:chat:readonly/read/chat`，漏已获授权应用仍可用的 `im:chat.group_info:readonly`。两类存量应用仍会被误报 missing。 |
| D7 通用 REST/UI/provider registry | provider-neutral resource、双 registry、单实例约束 | ✓ `design.md:286-294` 通用 resource + provider-owned validation 支撑当前 Feishu 与后续 provider，不预造动态 schema 服务。 |
| D8 initialized head + coordinator | register/bind/reconnect、per-node lock、request id、owner transfer | ✓ `design.md:295-321` 三触发共用 coordinator，manual bind 无需 reconnect，cross-owner 409 与 legacy compatibility 均明确。 |
| D9 三个串行纵向 Milestone | 规模举证、依赖、范围交集、两轨退出 | ✓ `design.md:322-329,683-691` 给出超单 worker 规模举证；M1→M2→M3 串行，每个 M 都跨 IM/Gateway/frontend 且有 reviewer/worker 两轨。 |

## D. 首文档约束台账

| Requirement | 覆盖 / 冲突 / 越界核实 | 结论 + design 落点 |
|---|---|---|
| R1 通用外部 channel 管理页 | 对照 4 个 Scenario | ✓ D7 + prototype 覆盖 generic empty/add/duplicate/error；Web IM 被 D4/D7 排除。 |
| R2 飞书轻量向导与 credential UX | 对照 4 个 Scenario | ✓ D1/D7 覆盖指定 launcher、必填、opaque secret、显式 keep/replace 与 App ID change。 |
| R3 连接状态与可操作诊断 | 对照 6 个 Scenario | ✗ D5/D6 有完整状态机，但 D6 仍漏普通群消息/群信息的 legacy alternatives，会把实际能力完整的存量应用错误显示为“连接受限”，冲突 `spec.md:108-129` 的准确 missing/unknown 语义。 |
| R4 离线配置与重连收敛 | 对照 2 个 Scenario | ✓ D2/D3 的 desired/observed、full manifest、cache/outbox 覆盖。 |
| R5 飞书 channel 生命周期 | 对照 3 个 Scenario | ✓ D3-D5 的 real stop、credential replace、enable/reconnect/delete/no-cascade 覆盖。 |
| R6 节点绑定不得隐式迁移跨 owner | 对照唯一 Scenario | ✓ D8 固定 409 + 零写入，manual/auto 共 guard；IM delta 用 MODIFIED 忠实覆盖。 |

### D1. 首文档逐场景

| Scenario | 结论 | 证据 |
|---|---|---|
| 尚未配置任何外部 channel | ✓ | prototype `#channels-empty`；M1-E1。 |
| 从统一入口选择 channel 类型 | ✓ | frontend/provider registry、`#add-feishu`；M1-E2。 |
| 当前类型已经存在 | ✓ | DB unique、provider disabled、pending removal guard。 |
| channel 列表加载失败 | ✓ | `#channels-error` + retry，不降级为空态。 |
| 用户查看飞书准备指引 | ✓ | prototype `795-798` 仅短说明和指定 launcher。 |
| 在线节点保存有效配置后立即连接 | ✓ | desired commit → reconcile → runtime → observed。 |
| 必填凭据缺失 | ✓ | POST/replace contract 与 prototype 字段校验。 |
| 已保存密钥不会明文展示 | ✓ | GET/list opaque，编辑显式 keep/replace。 |
| 权限完整且连接正常 | ✗ | accepted-scope 集合仍漏 group-message/group-info legacy scope，会把仍具备能力的旧应用误判 limited，见 C-D6。 |
| 权限不足但基础能力可用 | ✓ | connected + diagnostics limited 的投影完整。 |
| 缺少普通群消息权限 | ✗ | 当前表只识别 `im:message.group_msg`，会把已获 legacy `im:message.group_msg:readonly` 且仍可收普通群消息的应用误报缺失。 |
| 暂时无法完成权限检查 | ✓ | unknown，不伪造 missing。 |
| 凭据或连接无效 | ✓ | actionable failed status + prototype。 |
| 连接暂时中断 | ✓ | same-incarnation sequence + manual reconnect。 |
| 节点离线保存新增/修改/启用/停用/删除 | ✓ | desired 保存、pending projection、removal intent/outbox。 |
| 节点重连后自动应用 | ✓ | terminal status result 释放 FIFO，full manifest 自动收敛。 |
| 停用已连接 channel | ✓ | confirm → pending/disabling → observed disabled。 |
| 重新启用 channel | ✓ | credential keep；runtime 安全替换。 |
| 删除 channel 保留历史 | ✓ | no-cascade、removal receipt、failure retry、applied-head terminal。 |
| 已绑定节点被另一个 owner 确认 | ✓ | 409、事务零写、same-owner 幂等进入 D8/M1-E6。 |

### D2. 澄清、用户场景与非目标

| 原子 | 结论 | 对账 |
|---|---|---|
| Q1 完整 connection lifecycle | ✓ | D3-D6 覆盖配置、保存即连接、状态、停用、重连。 |
| Q2 offline 仍可编辑且区分 saved/applied | ✓ | D2/D3 与 v7 无版本 UI 投影闭合。 |
| Q3 轻量向导、多 channel 通用模型 | ✓ | D7 + exact launcher。 |
| Q4 不展示 Web IM | ✓ | managed manifest、REST、UI 都排除 `web_relay`。 |
| Q5 删除配置、保留历史 | ✓ | D3/D4 + schema no-cascade。 |
| Q6 权限不足允许降级并准确逐项呈现 | ✗ | missing/unknown 状态结构正确，但 accepted-scope 集合不全会伪造 missing。 |
| Q7 每 Agent/每 provider 单实例 | ✓ | unique + UI/removal guard。 |
| U1-U6 全部用户场景 | ✗ | U1/U2/U4/U5/U6 覆盖；U3 的“准确缺什么”受 C-D6 阻断。 |
| N1 不展示 Web IM | ✓ | 未越界。 |
| N2 不实现其他 provider | ✓ | 仅通用 seam，无其他 production provider。 |
| N3 不支持同类多账号 | ✓ | 未越界。 |
| N4 不复制完整平台教程 | ✓ | 只有短说明与外链。 |
| N5 不改变既有飞书消息/审批/文档行为 | ✓ | stable identity、parent approval、activation policy。 |
| N6 删除不清理历史 | ✓ | 无 cascade、manager 不调用会话仓库。 |
| N7 不新增群级白/黑名单 | ✓ | 未越界。 |
| 新反馈：通道无用户可见版本概念 | ✓ | v7 专项 V1-V5 全部成立；内部 token 不形成产品版本。 |

## E. Delta-spec 台账

| Delta Requirement | 全部 Scenario / canonical / 用法核实 | 结论 |
|---|---|---|
| IM「Agent 通道页管理通用外部 channel」 | empty / duplicate / list error；锚 `agents-nodes.md` | ✓ 真新增，THEN 均用户可观察。 |
| IM「飞书 channel 提供轻量接入向导」 | picker / required / online save | ✓ 真新增。 |
| IM「期望配置与实际运行状态分离，并通过内部一致性令牌关联」 | online/offline/manual-bind/conflict | ✓ v7 明确内部 token、无 UI 版本和无历史/回滚。 |
| IM「Channel 凭据写入后保持不透明」 | opaque / App ID new secret / cached key / missing key | ✓ 真新增。 |
| IM「状态诊断可操作且区分 missing/unknown」 | limited/group/unknown/failure/reconnect/time/causal order | ✓ delta 的消费者契约正确；当前 design D6 不能兑现“missing 必须真实”，问题升级为 C-D6。 |
| IM「生命周期不级联删除聊天历史」 | disable confirm / enable / delete / reconnect | ✓ 真新增。 |
| IM MODIFIED「设备绑定把节点归属到当前用户」 | start / initial / same owner / cross owner / stable 400 | ✓ 精确锚 canonical 原标题，旧 Scenario 全保留。 |
| Gateway「完整 manifest 调和」 | hot add / duplicate / removal / zero / never-seen / replay / retry | ✓ 真新增，internal revision 明确非产品版本。 |
| Gateway「本地密文 manifest 离线启动」 | offline restart / reconnect convergence | ✓ 真新增。 |
| Gateway「Managed Feishu 保持身份与能力」 | stable identity / owner / App replacement / skill / card action | ✓ 新控制路径保持 canonical。 |
| Gateway「动态 lifecycle 立即影响收发」 | disable / replace / multi-Bot isolation | ✓ 真 stop/replace/isolation 可观察。 |
| Gateway「上报实际状态与权限诊断」 | complete / limited / group / unknown / reconnect / causality / stale barrier | ✓ delta 语义正确；D6 catalog 实现边界需修。 |
| Gateway「旧 YAML 首次导入」 | first / manual bind / half failure / standalone | ✓ 与 D8/legacy compatibility 对账。 |

两份 delta 都指向最窄 canonical area；ADDED/MODIFIED 用法正确，MODIFIED 未静默删除旧 Scenario；THEN 均为消费者可观察结果，没有内部函数调用断言。

## F. Prototype 与 Milestone 台账

| 原子 | 结论 | 证据 |
|---|---|---|
| empty/add/connecting/connected | ✓ | empty、provider disabled、required、connecting、connected/time 可驱动；connected 无版本数字。 |
| App ID + secret replacement | ✓ | `prototype.html:947-956` App ID change 禁 keep、强制 replace；改回可恢复 keep。 |
| disabling/disabled/pending | ✓ | online confirm 先 disabling，模拟 observed 后 disabled；offline 启停仍 pending。 |
| deleting online/offline/failure/applied | ✓ | `prototype.html:883-910,1014-1021` 覆盖持久 pending、failure/retry、applied empty。 |
| reconnecting/failed/limited/error/mobile | ✓ | actionable failure、missing/unknown、retry、375px layout/state 都有锚点。 |
| M1 在线安全接入与热连接 | ✓ | 跨 IM/Gateway/frontend 的纵向切片；E1-E8 两轨齐。 |
| M2 离线收敛、迁移与 lifecycle | ✓ | full manifest/cache/bootstrap/removal/ACK loss/retention 与 UI 两轨齐。 |
| M3 权限诊断、异常态与响应式验收 | ✗ | E5 只点名覆盖 p2p/history/send legacy scope，D6 仍漏 group-message/group-info legacy scope；worker 照表实施和自测仍会误判 missing。 |
| 拆分与并行性 | ✓ | 超 20 文件/800 行举证；M1→M2→M3 串行，未伪装并行。 |

## G. 四角架构进攻

| 角度 | 攻击对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | store / coordinator / manager / Feishu worker / UI registry | ✓ 走完无存活架构发现：事务、初始化、runtime、SDK 隔离和 UI schema 均落在自然 owner，无产品包反向依赖。 |
| 该不该存在 | store/coordinator/manager/factory/policy/outbox | ✓ deletion test 均通过；删除任一层都会把事务、初始化 race、dynamic stop、provider side effect 或 offline ACK 状态机散回调用者。 |
| 深还是浅 | manager vs registry、full manifest vs command log、status/result | ✓ manager 藏住 replace/stop/cache/outbox，registry 保持 lookup；未发现可删浅包装。 |
| 治本还是补丁 | owner transfer、SDK global loop、delete/ACK loss、status order | ✓ owner guard、per-Bot process、explicit removal/outbox/head、incarnation/sequence 都解决根因；D6 是 catalog 正确性缺陷，已在核对腿升级，不是额外架构绕路。 |

## Issues

- [CRITICAL] [决策 6 / M3-E5：Feishu capability catalog]: 第八轮要求的集合模型及 p2p/send/history alternatives 已关闭，但 catalog 仍未穷尽当前迁移范围内的官方 legacy 等价权限。飞书官方[接收消息](https://open.feishu.cn/document/server-docs/im-v1/message/events/receive)的权限清单仍把 `im:message.group_msg:readonly` 作为“获取群聊中所有用户消息”的历史权限，而当前 `design.md:260` 只接受 `im:message.group_msg`；飞书官方[权限点下线说明](https://open.feishu.cn/document/uAjLw4CM/ugTN1YjL4UTN24CO1UjN/platform-updates-/message-and-group-scope-removed)明确已获得 `im:chat.group_info:readonly` 的应用不受下线影响，权限目录也仍将它关联到获取群信息 API，但当前 `design.md:263` 未接受它。不改会让从旧 YAML 导入、实际仍能接收普通群消息或读取群名的存量应用被错误标成“连接受限/缺权限”，继续违反用户要求“到底缺啥要准确呈现”。退回 `change-design-author`：为普通群消息增加 `{im:message.group_msg:readonly}` legacy alternative，为群信息增加 `{im:chat.group_info:readonly}` legacy alternative；M3-E5 不要只枚举 p2p/history/send，应要求 catalog 中全部 legacy alternatives 逐项证明 `satisfied`，仅全部集合不满足才为 `missing`。

## Recommendations

- 补齐 C-D6 剩余两项 legacy alternative 后做一次完整 Gate 2 复审；`accepted_scope_sets` 结构和 v7 的“无用户可见版本概念”修改无需回退。

## Author disposition after review

> 这不是 reviewer approval。用户于 2026-07-15 要求停止 reviewer、无需继续复审；以下仅记录设计作者如何处理上面的 finding。

- `design.md` v10 已为普通群消息加入 `im:message.group_msg:readonly`，为群信息加入 `im:chat.group_info:readonly`。
- M3-E5 已改为要求 catalog 中每个 current/legacy alternative 分别证明 `satisfied`，而不是只抽查 p2p/history/send。
- Gateway delta 已补充“存量应用持有 legacy 等价权限”场景，并要求当前权限和 legacy 等价权限都缺失时才能确认普通群消息权限 missing。
- 按用户指示未执行第十次 Gate 2，因此本报告保留最后一次独立 review 的 `Issues Found` 结论，不宣称最终方案已复审通过。
