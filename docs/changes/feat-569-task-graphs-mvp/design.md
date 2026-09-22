# feat-569：讨论驱动的任务图 MVP — 技术方案

> 对齐：spec.md v1.2 · 取证基线：`c0313d9c62891d4d452162d7f1d30a2680556885`（2026-09-22 读取）。
> 本文件是待本地独立审查的设计稿，不是 as-built，也不表示 Gate 2 已通过。技术细节为作者提案；用户已确认的是首文档中的精简产品范围。

## Changelog

## 现状分析

### 涉及范围

| 已核实路径 | 当前职责 | 本次触及方式 |
|---|---|---|
| `src/IM/app.py` | FastAPI 装配、SQLite 与 WebSocket runtime、静态入口 | 注册任务图路由和服务；若新增 `/tasks` 路由，补静态深链接入口。 |
| `src/IM/ws/gateway/runtime.py` | 校验已注册 Gateway、按类型分派上行帧 | 增加任务图命令帧，不复用聊天消息语义。 |
| `src/IM/frontend/src/app/shell/app-shell.tsx` | 桌面 48px 顶栏，Chat/Agents；手机底部导航 | 增加“任务”入口；保留既有导航与聊天手机全屏行为。 |
| `src/IM/frontend/src/features/chat/chat-workspace-page.tsx` | 会话列表、MessagePane、群设置、既有 Work 返回导航 | 加“本聊天任务”入口，不替换 MessagePane 或新造聊天实现。 |
| `src/IM/frontend/src/styles/global.css` | 白色内容、冷灰导航、teal 操作色 | 沿用既有变量，不换主题。 |
| `src/IM/frontend/package.json` | React / Router / TanStack Query / Radix / Playwright 等 | 无图引擎依赖；本版不引入新的图编辑库。 |
| `src/personal_assistant/product.py` | 产品工具目录、PromptSlots、按会话启用工具 | 注册原生 `task_graph`，同步工具发现、预览与提示。 |
| `src/personal_assistant/tools/inbox.py` | session 身份附带到 Gateway loopback 的工具范式 | 复用调用模式，不把任务数据塞进 Inbox。 |
| `src/personal_assistant/gateway/internal_dispatch.py` | 已有 loopback listener、session provenance 捕获与查询分派 | 单独任务图 handler 复用已核实身份，不复制消息投递逻辑。 |
| `src/personal_assistant/gateway/composition.py` | 装配产品工具、Gateway、IMConnectionManager | 注入任务图 bridge；不新增常驻进程。 |
| `src/personal_assistant/ws/im_connection.py` | 被 composition 引用的现有 IM 连接管理器 | 追加请求/回执分派；具体 pending-request 接线由本地实现前核对。 |

以上是 targeted source reading，不是全仓审计或运行验收。sources.json 提供固定版本路径和调查边界；未声称本地运行已验证。

### 既有约束

`AGENTS.md`、`SPEC.md`、`docs/specs/kernel/sdk-boundary.md` 要求：PA 只 import `agent.sdk`；IM 不执行内核、不读 Gateway workspace；三个产品包不互相 import。`docs/specs/im/spec.md` 当前没有任务图 area，Work 与聊天可见性不同，不能把 Work 的公开可读规则套给任务图。

本次不改内核工具契约、不改普通 Agent/Workflow 的完成语义，不把业务记录绑定到 session/run 终态。新功能的数据可以依赖 IM 在线；IM 离线时不建本地影子账，但 Gateway 原有本地自治能力不受影响。

### 可复用能力

| 能力 | 用 / 改 / 不用 | 理由 |
|---|---|---|
| 会话成员访问、浏览器登录、Gateway 已绑定节点身份 | 用 | 不新建另一套用户/工作空间授权。 |
| IM SQLite 初始化与 repository/service 模式 | 用 | 图是小型业务文档，单库事务足够。 |
| Gateway 现有 loopback 与已认证 IM WS | 改：追加一类业务调用 | 不增加服务、端口或 Kernel HTTP server。 |
| SDK 原生工具与 presenter | 用 | 工具调用在已有 Work/轨迹可查看，不改聊天日志语义。 |
| TanStack Query、Router、i18n、Radix Dialog | 用 | 数据查询、深链接、文案与对话框沿用现有能力。 |
| `agent` / `send_message` / `task_stop` / Workflow | 不改 | 用户仍决定怎么执行；图更新不会调用它们。 |
| 预算、Mailbox、自动评审、自动调度 | 不用 | 本版明确不做。 |

### 相关历史

current specs 指向 feat-552（全局 Agent/SDK）、feat-546/554（Work）、feat-517（Workflow）；本次 main HEAD 是 bugfix-567 的合并提交，涉及入站附件。这里只沿用其已归入 current 的职责边界，不据编号推断活动状态，不重做这些能力。导入时检查 active/archive/retired 中是否已有同主题 unit；存在则交接已有 unit，不重复领号。

## 架构总览

**IM 持有唯一持久任务文档；Agent 通过现有 Gateway 通道读写；浏览器显示同一文档。没有任务执行引擎。**

```text
用户从现有聊天输入 prompt ─────→ Agent（沿用已配置工具）
                                     │ task_graph（新原生工具）
                                     ▼
                               PA loopback handler
                               session provenance 校验
                                     │ 现有已认证 WebSocket
                                     ▼
浏览器 Tasks ── 已登录 HTTP ──→ IM TaskGraphService
                                     │ 校验权限/图/版本，单事务
                                     ▼
                               IM SQLite 文档与写入回执
```

现有执行链不经过这个文档服务。工具一次更新可以让图变为“进行中”，但不会因此启动任何模型或命令。

## 关键决策

### D1 **一个轻量任务节点模型，节点内部可为未细分、DAG 或探索。**
每个节点都有说明、记录状态、结果。`mode` 只说明“内部子图怎么组织”，不是执行策略。`none` 表示未细分；`dag` 表示同层任务的前置依赖；`explore` 表示同层候选的来源衍生。顶层图必须是 dag 或 explore。

不为 MVP 新建候选/实验/评审/决策等多套生命周期。探索节点能记录一次或多次尝试的总结，需要细分时再建子图。以后需要实验实体可扩展，不在本版预实现。

### D2 **归属与衍生是两回事；跨层只通过节点包含子图表达。**
外层 R 的 A、B、C 都有 `container_id=R`。A 内 X、Y、Z 都有 `container_id=A`；Z 的 `derived_from_id=X`。Z 不是 X 的归属子任务，因此 X 不会被误画成探索的父级 scope。Z 内可以有自己的 DAG。

每个探索方向最多一个来源，形成允许多个初始方向的森林；不做多父合并。依赖边只允许同一 dag scope 的直接子节点，衍生边只允许同一 explore scope 的直接子节点。所有图校验各自无环，不混成一张通用运行 DAG。

### D3 **只有显式记录更新，没有自动传播状态。**
`status`：`todo`（待做）、`doing`（进行中）、`done`（已记录完成）、`paused`（暂缓）、`dropped`（放弃）。探索的负结果可以是 done + 负结果文字，不等于 failed。UI 显示“记录状态”，不写“已系统验收”。

允许 done→doing；这种返工更新必须附普通变更说明。选定方向不完成容器；子节点全 done 也不完成父任务；A done 不启动 B。不做“ready 队列”。若父节点仍 todo 而孩子 done，可以如实显示；摘要不伪造完成百分比。

### D4 **工具属于 Agent 能力，输入渠道不参与准入。**
Agent 按用户已表达的意图创建/更新。工具说明提醒“先讨论结构；有明确保存或调整指令再写；不要自动执行”。这个提醒不是产品审批门禁，不证明每次写入都有人签字。

`task_graph` 注册到 PA 工具目录和默认工具集，沿用现有工具配置、permission classifier 与工具下发。显式 allowlist 没有它时仍不可用；不为任务图绕过配置或新增审批机制。具备工具且能核实注册 PA Agent 身份的会话按同一契约调用，不另加 Web IM/飞书或 global/single_thread 的来源白名单；图系统不创建或唤醒会话。

内核 `agent` 工具创建的 child 使用临时 agent_id，当前没有直接注册成 IM/PA Agent；本版不为它增加代父身份授权。子执行结果仍交回具有 PA 身份的 Agent 更新；未能核实 PA 归属的调用明确返回 unsupported_context。这里沿用现有身份边界，不从 prompt 输入渠道做推断。

Gateway 只核实 ToolContext 对应的真实 Agent 身份及其有效运行时来源；`capture_session_provenance` 用于 session→Agent 归属，不再被误用为“来自原生聊天/主会话”的证明。任务目标由工具业务参数明确表达，不能从最近唤醒消息猜测。IM 断连时明确返回 source_unavailable，不新增离线图存储。

### D5 **图的归属独立于输入来源；一张图关联一个既有 IM conversation。**
同一聊天可有多张图；每张图只有一个 home conversation，全部内层共享它的 ACL。用户是当前成员即可查看；Agent 是该聊天当前成员且来自匹配的已注册 node，才可按现有权限调用读写。Agent 可以从任一输入上下文引用同一 graph_id；最终权威访问检查只看图的 home conversation。

home conversation 可以是 Web IM 原生聊天，也可以是既有外部聊天映射。复用 [外部会话 current 契约](../../specs/im/conversations-messages.md)：`(external_source, external_chat_id, agent_id, owner_id)` 对应的既有 IM 会话，不能用一个外部群原始 ID 合并多个 Agent/owner 的图。创建时解析目标；get/apply 一旦给定 graph_id，无须输入聊天与 home 相同，也无须该输入聊天已映射。

不授予模型“代某个用户写”的参数，不把已登录或能看 Work 当作图访问权；成员移除后 list/get/apply 都失效。暂不做图跨聊天迁移、额外共享、管理员角色 UI。MVP UI 不提供图形/表单编辑器，人在聊天要求 Agent 修改。

任务资源与 Work 中的副本沿用各自既有边界：TaskGraphService 校验图的成员权限；已进入全局 Work 的工具参数、结果和 Agent 正文继续遵循 [Work 当前可见性](../../specs/im/agent-work.md)，不新增按图 ACL 过滤、脱敏或撤回副本。登录的非成员可以看到 Work 已记录的任务内容，但从 Work 打开原图或原聊天仍被成员检查拒绝。此处落实用户“怎么简单怎么来，自洽就行”的权限决定，不承诺任务内容在所有转录副本中保密。

### D6 **IM 作为唯一存储；离线明确失败，避免双向同步。**
本功能是 IM 协作记录，不是 Gateway 长期任务运行责任层。选择中心存储使刷新、多聊天访问与同一图更新简单。之前长程方案中的“Gateway 负责目标的唯一写入点”不在此 MVP 中实施。

### D7 **单个 `task_graph` 工具，四个动作。**
`create / list / get / apply` 足够覆盖本版。`apply` 是有限类型操作的原子批次，不允许任意 JSON Patch，也没有 dispatch/approve/review/complete 自动行为。批量操作避免“加完节点、加边失败”产生半张图。

### D8 **JSON 文档 + revision + 小型幂等回执，不建设通用事件系统。**
每次修改由服务校验完整候选文档后提交。revision 做并发冲突保护；幂等回执覆盖未知写入结果后的原请求重试。不是完整历史事件溯源；仅保留节点最近修改信息与当前结论，追加长实验历史不是本期目标。

### D9 **图只负责查看，原型采用 SVG 连线 + HTML 节点，产品可同样实现。**
沿用现有依赖，无新增可视化库。按每层图做拓扑分层布局：dag 按依赖最长路径分列；explore 按衍生深度分列；并列节点按 `order`、id 稳定排列。跨列依赖从节点间隙绕行到卡片上方的独立通道，避免穿过中间卡片；分叉/汇合使用不同连接点，不能把多条直接依赖合成一条。节点详情列出直接前置/后续作为可读关系清单。具体线形可调整，但每条关系可辨认。原型“复杂 DAG”覆盖 A→B→C 加 A→C，以及 A→D、C→E、D→E。

不显示整个递归大图。节点选择、缩放、画布内滚动、面包屑和键盘列表是核心；拖拽坐标和拖线创建不是本版。

## 接口与数据流

### 1. 文档模型

持久文档形态（字段均为拟议）：

```json
{
  "schema_version": 1,
  "graph_id": "tg_...",
  "home_conversation_id": "c_...",
  "root_node_id": "tn_root",
  "revision": 7,
  "nodes": [
    {"id":"tn_root","container_id":null,"title":"视频产品验证","description":"先选方案，再实现和测试","mode":"dag","status":"doing","result":"","derived_from_id":null,"selected_candidate_id":null,"selection_reason":"","links":[],"order":0},
    {"id":"tn_a","container_id":"tn_root","title":"A 找到视频生成方案","description":"比较质量和成本","mode":"explore","status":"doing","result":"","derived_from_id":null,"selected_candidate_id":"tn_z","selection_reason":"质量达标且成本可接受","links":[],"order":0},
    {"id":"tn_x","container_id":"tn_a","title":"X 全生成","description":"先验证质量上限","mode":"none","status":"done","result":"画面较好，成本偏高","derived_from_id":null,"selected_candidate_id":null,"selection_reason":"","links":[],"order":0},
    {"id":"tn_z","container_id":"tn_a","title":"Z 仅生成关键镜头","description":"在 X 基础上限制生成范围","mode":"dag","status":"doing","result":"待完成验证","derived_from_id":"tn_x","selected_candidate_id":null,"selection_reason":"","links":[],"order":2}
  ],
  "dependencies": [
    {"from":"tn_a","to":"tn_b"},
    {"from":"tn_b","to":"tn_c"}
  ]
}
```

示意 JSON 仅摘录部分 nodes，B/C 的完整定义见 prototype，不能将这段不完整示意当测试 fixture。生产服务返回 id、UTC 时间和可信 actor 来源；`created_at/updated_at/updated_by` 由服务生成，工具不得传入。普通链接仅允许 http/https 或受保护 IM 附件引用；本版不上传、验证或自动抓取链接，不把 Gateway 本地路径伪装成网页下载地址。

根节点也可以更新 title/description/status/result。所有非根节点有且只有一个归属父节点；所有节点沿 container 链能到根。`mode=none` 不能有孩子；空 scope 可以改 mode；非空 dag↔explore 直接转换拒绝，避免默默重解释已有边。空叶子可一次 apply 变 mode 并增加孩子。

选择仅在 explore scope 上可设置，目标必须是该 scope 内未 dropped 的直接候选；Z 虽从 X 衍生，仍是 A 的直接候选。选择不是达标证明，可以选 doing 候选。取消选择显式置 null；若要放弃当前被选方向，必须同批清除/替换 selection，否则拒绝，不能留下悬空推荐。

### 2. 存储、并发和身份

建议新增 `src/IM/infra/repositories/task_graphs.py`，将表纳入现有 `initialize_schema`：

- `task_graphs`：id、home_conversation_id、root_title（索引摘要）、revision、document_json、created_at、updated_at、updated_by。文档是权威，摘要列与文档同事务写。
- `task_graph_mutation_receipts`：actor_key、request_key、operation_hash、graph_id、result_json、created_at，唯一键 `(actor_key, request_key)`。

create/apply 在一个事务内处理：**先校验当前权限，再查相同请求回执，再校验 base_revision，再验证全部操作/完整图，最后同事务保存文档和回执**。相同身份、相同 request_key、相同参数重试返回原回执；同 key 不同参数返回 request_key_reused。回执命中不能绕过成员已撤销的权限检查。

使用现有 SQLite 连接约定并确保写事务串行/CAS 等价安全。校验通过但写事务失败时不得返回成功。第一版不做自动冲突合并；version_conflict 返回 current_revision 与“先 get 再根据最新内容调整”。不得自动换新 request_key 重做一次结果未知的创建。

### 3. 工具契约

所有传参字段 action-specific，未知字段拒绝。模型只能提交业务字段；身份由 ToolContext/session provenance + 注册 Gateway 注入。

| action | 参数 | 返回 |
|---|---|---|
| `list` | 可选 `target`（聊天引用）、`query`、`cursor`、`limit`（默认20，上限50） | 已过滤权限的摘要项、稳定 graph_id、root_node_id、title、mode、status、revision、updated_at、next_cursor、home_conversation_id、relative_url |
| `get` | `graph_id`，可选 `scope_id`（默认根）、`view=scope\|all`（默认scope） | 当前图 revision、根摘要、面包屑、scope 节点、该层孩子、该层 dependencies/derivations、节点内部 child_count；all 返回完整文档 |
| `create` | `target`（聊天引用）、`title`、`description`、`mode=dag\|explore`、`request_key` | 新图、根节点、revision=1、相对 IM URL；只创建空根，不执行任何任务 |
| `apply` | `graph_id`、`base_revision`、`request_key`、`operations[]`、`change_note` | 新 revision、此次 changed_ids、局部 client_ref→id 映射、relative_url；可不返回整张图 |

`target` 使用现有会话引用：IM conversation_id 或现有 Inbox/conversations 提供的 opaque target。Gateway 复用已保存的目标映射，归一化为 IM conversation_id 再发送命令，不让 IM 解析 PA 私有 target；`target` 是业务目标，不是身份凭据。global Agent 可从现有 Inbox/conversations 获得引用；single_thread 的运行时聊天上下文应暴露已绑定的同一引用供模型使用。`create` 必须明确 target，`list` 不传 target 则查询该 Agent 当前可访问的图，不回退猜测“最近聊天”。缺少目标返回 invalid_arguments；目标尚未映射为 IM 会话时返回 source_unavailable，等待现有映射恢复后再操作，不自行创建另一套映射或改绑到别的聊天。

所有图结果附 `home_conversation_id` 与稳定 `relative_url`；Gateway 基于注册得到的 `IMConnectionManager.im_user_url` 生成 `web_url`，Agent 在外部回复使用该绝对 Web IM 链接。沿用现有公开 IM 入口及登录，不把 loopback/Gateway 本机地址发给用户。缺少公开入口不得编造可打开的地址；保存回执与链接是否可用分别如实说明。

create 后一次 apply 可完成全部初始拆分。创建空根成功但第二步失败时如实报告“目标已建，拆分未保存”；不声称整图已创建。

`request_key` 为调用方稳定生成的业务请求标识，不是权限凭据；网络未知后必须原样重用。普通读取不修改任务、人的已读或 Agent Inbox。

`apply.operations` 六种：

| op | 字段与限制 |
|---|---|
| `add_task` | `client_ref`（本批唯一）、`container_id`、`title`，可选 description/mode/status/result/derived_from_id/links/order；ID 由服务生成，可用 `@client_ref` 引用本批新节点。 |
| `update_task` | `node_id`、`patch`；仅 title/description/mode/status/result/links/order 可改；不改 id/container_id/actor/revision，返工说明写 change_note。 |
| `add_dependency` | `from`、`to`；同一 dag scope，去重，无自环。 |
| `remove_dependency` | `from`、`to`；删除指定存在的边，不波及节点。不存在返回 relation_not_found。 |
| `set_derivation` | `node_id`、`derived_from_id` 或 null；同一 explore scope，至多一来源，禁止环。 |
| `select_candidate` | `scope_id`、`node_id` 或 null、`reason`；设置 explore scope 当前选项，不改任何 status。 |

操作按数组顺序解释 @ref，但最终统一验证后原子提交。引用后定义的 ref 拒绝并指出操作位置。没有通用 delete；不再做的节点标 dropped，仍可追溯。不做重新挂父层；要换归属，讨论后新建正确节点并把旧节点标明放弃，后续再扩展迁移能力。

技术保护：单图最多500节点/1000依赖、单批最多100操作、嵌套最多8层、文本/请求体有固定上限并返回明确错误，不截断保存。这是请求/渲染安全边界，不是运行资源预算。样例与验收不依赖触达上限。

### 4. 模型实际调用样例

用户：“按我们讨论的 A→B→C 建图，A 先探索 X、Y，别开始执行。”

```json
{"action":"create","target":"c_example","title":"营销视频产品","description":"讨论驱动，先选方案再实现","mode":"dag","request_key":"g-create-01"}
```

服务返回 `graph_id=tg_1, root_node_id=tn_root, revision=1`，再调用：

```json
{
  "action":"apply","graph_id":"tg_1","base_revision":1,"request_key":"g-plan-01","change_note":"按用户确认的拆分保存；未执行",
  "operations":[
    {"op":"add_task","client_ref":"A","container_id":"tn_root","title":"A 选择生成方案","mode":"explore"},
    {"op":"add_task","client_ref":"B","container_id":"tn_root","title":"B 实现方案"},
    {"op":"add_task","client_ref":"C","container_id":"tn_root","title":"C 测试上线"},
    {"op":"add_dependency","from":"@A","to":"@B"},
    {"op":"add_dependency","from":"@B","to":"@C"},
    {"op":"add_task","client_ref":"X","container_id":"@A","title":"X 全生成式视频"},
    {"op":"add_task","client_ref":"Y","container_id":"@A","title":"Y 模板拼装"}
  ]
}
```

@ref 只在同批内有效；下一次调用使用真实返回 ID。实际 target 必须来自 Inbox/conversations/运行时的真实聊天上下文，示例标识不是可执行凭据。

“X 做过了，成本高，基于它试 Z”：先 get 最新，再同批更新 X 结果并 `add_task(Z, container_id=A, derived_from_id=X)`。“把 Z 拆成原型→评测”：同批 `update_task(Z, mode=dag)`、增加内部孩子及其依赖。“Z 暂时最好”：`select_candidate(A,Z,reason)`。“A 可以结束”：另一次明确 `update_task(A,status=done,result=...)`，B 不变。

工具描述必须说明：done 只是记录；不从底层 run 的 completed 推导；不假定依赖边能执行；只讨论时不用写工具；工作依然用现有 read/write/bash/agent 等能力。global 主 Agent 的最终说明用 send_message 投递，不能只返回无人看到的 final text。

### 5. 调用与 UI 刷新路径

1. `TaskGraphTool`（新 PA 原生工具）通过当前 listener provider 请求 `POST /internal/task-graph`，附 origin session、真实 source_agent_id、tool_call_id，不携带 JWT 给模型。
2. 新 handler 按 binder 捕获 session provenance 并使用既有 guard；拒绝 session/Agent 归属不匹配，不接受模型提供的 actor。此处不沿用 inbox 的 global_main 限制，也不从 channel 或当前 conversation 推断工具权限；按 D4 沿用真实工具下发与 PA 归属，不把 child 的临时 agent_id 当作已注册 PA Agent。create/list 的 target 仅按既有映射归一化为目标 conversation_id。
3. bridge 复用 IMConnectionManager.send_json_await_ack 的待回执、断连和重发机制（不建第二套队列），经已认证连接发 `task_graph.command`，payload 包含 request correlation id、注册 node_id、已核实 agent_id、业务 action/args。
4. IM Gateway runtime 按既有 registered sender/owner 验证，再核实 Agent 属于该节点且是 home conversation 成员；调用同一个 TaskGraphService。
5. 返回 `task_graph.result`，保持 correlation id；断连未获确认时工具返回 `write_outcome_unknown` 和相同 request_key 的恢复指引，不落影子库。
6. 浏览器 API 调同一 service，以登录用户作为 actor。工具 presenter 呈现真实参数、回执/错误；Work 副本按 D5 沿用现有可见性。
7. 前端当前打开的 graph 用 TanStack Query 每3秒可见页轻量 refetch，加重新聚焦刷新和手动刷新；成功后显示新 revision。后台/不可见页不轮询。这个轮询不调用 Agent/LLM。MVP 不增加一套业务通知/唤醒系统。

浏览器只读 HTTP（create/apply 由 Agent WS 命令进入同一 service，本版不增加未使用的浏览器写接口）：

| method / path | 对应 |
|---|---|
| `GET /im/v1/task-graphs` | list；浏览器用 conversation_id/query/cursor/limit，直接传 IM 会话 ID |
| `GET /im/v1/task-graphs/{graph_id}` | get，scope_id/view 为查询参数 |

错误码统一：`not_found_or_forbidden`、`invalid_arguments`、`invalid_graph`（含 operation_index/具体原因）、`version_conflict`、`request_key_reused`、`relation_not_found`、`source_unavailable`、`unsupported_context`、`write_outcome_unknown`。无权访问和不存在不泄露标题或内容。

浏览器 get/list 要有加载、空态、明确错误及保留旧图的 stale 提示；不要先乐观修改图再假装保存成功。相同 revision 的 refetch 不重置缩放、选择和面包屑。被移除权限时清除已有缓存并退出受保护内容。

### 6. 页面与导航

- 顶栏增加 `/tasks`；任务列表只列当前用户能访问的顶层图，支持名称查询。
- `/tasks/:graphId?scope=:nodeId&node=:selectedNodeId` 表达稳定位置；刷新可恢复，非法 scope 不回退到别人的图。
- 当前聊天添加“任务（数量）”按钮；打开该会话的任务列表，有单张图也可直接进入。生成后的普通聊天链接指向同一入口；消息 Markdown 的内部链接按现有渲染能力验证。
- 桌面：左侧目标列表，中间当前层图，右侧节点详情。详细结果不挤进小卡。
- 手机：沿用底部主导航，增加任务入口；进入聊天详情时仍隐藏全局导航。当前图全宽，可横向滚动/缩放；详情用底部抽屉，关闭回到同一图；“目标”按钮可打开顶层图列表，根/层级面包屑不丢。
- “回聊天讨论”打开 home conversation 的 Web IM 聊天，只把任务引用附加到现有 composer store 草稿，保留文字与 mentions，不覆盖 draftSeed；不自动发送、不另开 Agent。若 home 是外部映射聊天，沿用该聊天既有 Web IM trigger_source 与回复去向，不自动向外部重发。
- 节点显示内部模式标记与“进入子图”；叶子显示“未细分”。原型工具模拟区是演示辅助，不进入产品。

## 前端原型

原型文件：[prototype.html](prototype.html)。纯离线 HTML/JS，模拟图数据和工具回执，不连接模型/IM。状态仅用于设计说明；浏览器 LocalStorage 是原型持久化，不是产品存储方案。

### 现有 UX grounding

| 当前入口 / 组件 | 继承的 UX | 本次嵌入 |
|---|---|---|
| AppShell / NanoBrand | 48px顶栏、nano IM品牌、Chat/Agents、手机既有全屏聊天 | 新“任务”入口，不另建平台导航。 |
| ConversationSidebar / MessagePane | 左会话、右聊天，用户浅绿色气泡 | 在原聊天加任务入口和普通任务链接；讨论仍在 Chat。 |
| global.css | 白底、冷灰导航、teal 强调、统一字体回退 | 图节点/连线/详情沿用同组变量。 |
| Agent Work | 真实执行轨迹单独查看 | 图中不搬运完整执行 transcript，不把任务视图命名为 Work。 |

### 原型对齐契约

| ID / 区域 | 级别 | 产品入口 | 必验 viewport / 状态 | 下游投影 |
|---|---|---|---|---|
| P1 导航与聊天入口 | must-match | Chat任务按钮、/tasks | 1440×960；390×844；空态/已有图 | R1 / W6 |
| P2 计划图 | must-match | /tasks/:id 根层 | A→B→C 加 A→C；A→D、C/D→E 分叉汇合；每条边及直接前置/后续可辨认；状态更新无自动开工 | R2 / W6 |
| P3 探索图 | must-match | A scope | X→Z 来源边、Y负结果、选定方向 | R3 / W6 |
| P4 双向嵌套 | must-match | 根→A→Z→返回 | 面包屑、内部模式、局部详情 | R4 / W6 |
| P5 详情与回聊天 | must-match | node参数/手机抽屉 | 长文本、记录状态、结果、草稿引用 | R5 / W6 |
| P6 错误/空态 | must-match | /tasks及图详情 | 加载、空、读取失败、stale保留旧图 | R6 / W6 |
| 颜色细节、节点间距、线弯曲 | may-adapt | 图组件 | 服从 current design tokens；不能改变边语义 | W6 |
| 工具模拟区、场景按钮、演示重置 | out-of-scope | 不进入产品 | 原型顶/底演示控件明显标识 | R7 / W6 |

## 契约层增量 (delta-spec)

- IM：`specs/im/task-graphs.md` → `docs/specs/im/task-graphs.md`（新 area）。归并时在 IM spec.md 的 Canonical Areas 增加同名入口和实际 Requirement 数。
- Gateway：`specs/gateway/task-graphs.md` → `docs/specs/gateway/task-graphs.md`（新 area）。归并时同步 Gateway area 索引。
- Kernel / CLI：`no spec delta`。不得为了业务 CRUD 添加内核任务生命周期。
- 暂不改 current spec；实现验收后按最终行为归并。

## 风险与回退

**范围膨胀：**禁止顺手加 task.dispatch、预算/审批/评分/验收引擎、自动监听 run 结束。用户记录 done 不表示执行器结束，UI 和提示都必须保留这一区别。

**图关系误用：**container 和 derived_from 分离，并用嵌套 fixture 测试；同层边校验必须在服务端，不能仅依赖前端。

**任务资源授权：**所有读写/list摘要与幂等命中都先执行当前成员检查。不得信任模型传来的 actor，也不得根据 Work 可见性授权；Work 中既有副本的展示边界见 D5。

**回执未知/并发：**同请求重放与版本冲突分别处理，不透明重试新写。所有操作原子；任一失败不落部分图。

**可视化复杂度：**无环不等于布局无重叠；测试分叉、汇合、多个根、长标题和500节点保护；首版逐层查看，不做全文大图编辑。

**新路由与构建漂移：**检查 IM 静态入口的 /tasks 深链接与当前构建；不提交 dist，不引用其他 worktree 的 dist。

**回退：**关闭 task_graph 工具暴露并移除任务导航/新路由；新增表保留，不删除用户记录；现有 Chat/Agent/Workflow 不依赖这些表，回退后原功能可用。后续重启用 schema_version=1 继续读取；未知 schema_version 明确拒绝，不覆盖。

## Runbook for Reviewer

**Review 驱动方式：**端到端真栈。本 unit 修改客户端面，必须真实驱动浏览器：Chat 讨论建图→任务图→嵌套→回聊天更新→重读。API/单测不代替该旅程；离线 prototype 的点击也不能充当产品验收。

**验收前置：**使用仓库 `.venv`、前端依赖和真实浏览器；`config/e2e/gateway.yaml` 与 `scripts/e2e-up.sh` 创建隔离用户/节点，不使用生产账号。2026-09-22 本地已核实 Python yaml/httpx、Node/npm 和前端依赖可用，Chromium 原型在 1440×960、390×844 可驱动；配置中的模型 `deepseek:deepseek-v4-flash` 经 `http://127.0.0.1:4000/v1/messages` 返回 HTTP 200、文本 OK、end_turn。此项仅证明模型资源可用，不是产品 Agent/任务工具验收；实施后的真实 Agent 回合仍必须在隔离栈运行。

S20 通过现有消息入口构造内部/外部 prompt，并覆盖真实 tool→loopback→WS→service，随后在真实 Web IM 查看同一图。输入 channel 不作为任务工具字段或准入条件；本 unit 不修改外部客户端或 channel adapter。专用 Feishu 联调沿用 [worktree-runtime](../../development/worktree-runtime.md) 的 `--feishu` 与测试 profile；本机私有 E2E 文件存在、权限0600、四项必需键齐全，专用非 default CLI profile 已只读验证 `verified=true`，App 与私有测试配置一致；未启动或占用 Bot。需要覆盖真实飞书收发的产品验收前必须按该 runbook 验证测试 App/Bot/User，资源失效时如实阻塞该场景，不用生产账号或原型代替。

在正确 unit worktree 中执行，不触碰主实例8011/5173，不改用户 ~/.nanoassistant：

```bash
WT_ROOT="$(git rev-parse --show-toplevel)"
cd "$WT_ROOT"
python -c 'import yaml'
npm --prefix src/IM/frontend ci
npm --prefix src/IM/frontend run build
./scripts/e2e-up.sh --wt "$WT_ROOT"
source "$WT_ROOT/.e2e-ports.env"
curl -fsS "$IM_URL/openapi.json" >/dev/null
printf 'Browser: %s\n' "$IM_URL"
```

上面栈启动后跨工具保持存活须按 worktree-runtime 使用受控终端/tmux，不用退出即被宿主回收的后台 shell。使用脚本登记的隔离用户登录（默认配置为 nano/nano1234，仅用于隔离栈；以当前配置核实）。先检查 Gateway 在线、一个真实回合成功，再执行 S01–S20。改为 global 的 Agent 配置走现有配置入口；single_thread 同样复核一次。

| 本 unit 相关服务 | 停止 | 启动/构建 | 健康检查 |
|---|---|---|---|
| IM + Gateway 隔离栈（脚本统一持有） | `./scripts/e2e-down.sh --wt "$WT_ROOT"` | `./scripts/e2e-up.sh --wt "$WT_ROOT"` | OpenAPI、当前 Gateway 注册在线、真实模型回合 |
| 前端静态产物 | 无独立进程 | `npm --prefix src/IM/frontend run build`，然后启动该 worktree IM | /chat、/tasks 和深链接刷新；核对受审 commit与dist |

**持久化复验不要用 e2e-up 重建数据来冒充重启。**该脚本可能重建隔离数据；worker 为 S16 提供只重启 IM 进程而保留同一隔离 DB/secret 的测试夹具，或以相同 db_path 的两次应用实例验证，并在浏览器走刷新重读。真实服务停止/重启命令以该次夹具保存的准确配置为准，不能打印 secret。关闭测试终端前执行 e2e-down；由自己启动的 Vite/浏览器另行清理。

最窄验证建议（新文件名最终由 worker确认）：

```bash
pytest tests/im_service -q
pytest tests/contract -q
npm --prefix src/IM/frontend test -- task-graphs
npm --prefix src/IM/frontend run build
```

单元/集成覆盖：图无环与归属、事务不部分落盘、版本冲突、重复写/未知回执、用户/Agent成员撤销、tool→loopback→WS→service真实接线、500节点保护、不同来源 prompt 与 global/single_thread 的相同工具授权规则、显式工具 allowlist、伪造 session/Agent 拒绝以及未注册 child 身份的明确失败。浏览器留下 P1–P6 原型对照截图和 S01–S20 覆盖结论；凭据/DB/runtime logs 不提交。

## Milestones

只设一个端到端 M1：本范围本身是一个完整小产品切片，按数据库/API/UI拆 M 不形成独立交付价值。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 可讨论、可维护的双模式任务图 | 无 | 单组，按用户要求组织执行 | IM service/repository/routes/WS；PA tool/bridge/product/wiring；frontend task图/聊天入口/shell/i18n；对应测试与delta归并 | [reviewer] R1–R7；[worker] W1–W8。 |

**[reviewer] 退出标准**

- **R1**：S01–S03；P1 的真实 Chat/Tasks入口可用，空态不混演示数据。
- **R2**：S04–S05；P2正确显示链、分叉、汇合和跨列直接依赖，详情可查直接前置/后续；更新A不自动更改/执行B。
- **R3**：S06–S08；P3展示来源衍生、负结果、暂缓/放弃和明确选项，选择不完成父节点。
- **R4**：S09–S10；P4的两种嵌套均可逐层进入、返回、刷新和增量细分。
- **R5**：S11–S13、S20；P5详情、结果、继续修改以及回聊天引用不丢草稿。工具调用不以 prompt 输入渠道授权；Agent 更新的同一图可在 Web IM 重读，外部回复使用可登录访问的 Web IM 链接。
- **R6**：S14–S19；P6失败/冲突/持久化/权限/手机旅程均有真栈证据，不把旧图或未确认保存当最新。S18 同时核对非成员可读 Work 中已有任务内容、但不能打开原任务图或原聊天。
- **R7**：产品无原型场景选择器与工具模拟面板；没有自动调度、预算、审批、独立验收或多Agent强制流程，现有Chat/Work/Agent执行不回归。

**[worker] 退出标准**

- **W1**：D1/D2数据与操作校验含无环/同层/根可达/模式转换/选项有效性；原子事务与版本冲突测试通过。
- **W2**：当前ACL贯穿list/get/create/apply、回执重放、用户/Agent成员撤销；伪造actor或session归属不能写图，不把内核 child 临时身份冒充为注册 PA Agent，子执行返回由已有 PA Agent 记录。
- **W3**：原生tool完整接到真实Gateway listener与IM WS；失联、未知回执、重试去重、实际permission classifier行为可测。无私有内核import。
- **W4**：同一 DB 重开保留文档；初始化兼容旧库，schema未知不覆盖；GET无消费副作用。
- **W5**：无自动执行依赖；done/选择/建图不调用Kernel.submit、agent、Workflow、调度器或预算组件（工具本身所在正常模型回合除外）。
- **W6**：P1–P6逐条留下桌面1440×960、手机390×844的真实浏览器截图/必要录屏与原型对照结论，放 M1/evidence；may-adapt的偏差有解释；out-of-scope控件不进入产品。
- **W7**：前端get重读不重置视图、错误保留明确stale、无权后清缓存、构建/类型/相关测试通过；/tasks深链接由IM正确提供。
- **W8**：两个delta按已实现行为归并，canonical索引Requirement计数正确；运行清理符合仓库规范；无secret/dist/生产配置提交。Gate 2独立评审通过后才进入正式实施。
