# feat-569-task-graphs-mvp — 产品验收报告

## Round 1 — full

- Validation snapshot: `499774a56 → 99f6e16339a95b94cdb3cb6d5dabd6b301a4b813`。
- Branch: `codex/feat-569-task-graphs`；worktree: `/Users/czj/.codex/worktrees/unit-feat-569/nano-multiagent`。
- 验收时间：2026-09-22 17:29–17:51 Asia/Shanghai。
- `validated_at` 保留 `99f6e1633`；验收期间 HEAD 推进到 `cb45a06a5`，caller 确认只有测试断言变化，运行产品未更换。前端为本 worktree 的 `f407ec609` build；Gateway 在开始前已由 caller 从 `99f6e1633` 重启。初始 HEAD 独立核实一致。
- IM `http://127.0.0.1:56231`，测试 owner `nano`，节点 `wt-nano-multiagent-85871`；仅在这些隔离资源内执行产品写入。没有操作生产服务。
- 浏览器：真实 Chromium / Playwright CLI；CUA browser provider 报 `nodeRepl.fetch request failed`，原生 Chrome 登录后，经 caller 明确授权改用 Playwright skill。没有用离线原型或 API 200 代替真实产品体验。

### Verdict

**fail**。`highest_required_action=fix-implementation`；1 个 major、0 个 blocking、0 个 minor；`needs_re_review=true`；没有外发 GitHub issue。

S01–S20 的首文档用户结果均有对应通过证据，但 **P5 must-match 的“回聊天不丢草稿”失败**，所以不能通过验收。Chat 正文与 Global Work 正文中的任务链接都能复现同一问题。通过聊天顶部 Tasks 按钮进入图再返回则能保留草稿。

### 用户旅程及证据索引

以下截图均存于 `/tmp/feat569-product-evidence/`，只记录路径，不提交截图缓存、日志或凭据。`desktop-*` 除注明的边界回执图外为 **1440×960**；`mobile-*` 为 **390×844**；`nonmember-*` 为 **1440×960**。边界回执图 `desktop-invalid-relations.png`、`desktop-version-conflict.png` 实际为 **1200×730**，不拿它们充当指定 viewport 的视觉对照。

| 旅程 | 真实操作与实际结果 | 证据 |
|---|---|---|
| J1 空聊天→讨论→保存 | 在 UI 新建与 e2e-peer 的聊天 `c_xsu9vkwq`。Tasks 0 打开明确空态。仅讨论 A 选照片→B 排版→C 校对时，Agent 复述且任务仍为 0；再明确要求保存后，真实工具创建 `tg_0f7fd90f18a04a648d835921212a3255`（摄影小册验收569），revision 2、三个待办节点及 A→B→C。点击聊天中的真实链接打开图。Process 显示失败参数调用、成功 create/apply/get 的顺序，最后才回复保存成功；没有命令执行或委派。 | `desktop-chat-empty.png`、`desktop-tasks-empty.png`、`mobile-tasks-empty.png`、`mobile-discussion-no-graph.png`、`mobile-created-graph.png`、`mobile-node-detail.png`；聊天 UI 17:31、17:32 的用户/Agent 消息 |
| J2 完成→继续修改→渐进细分 | 同一图 A 完成后，B/C 仍 To do。再次要求继续修改后 A 同 ID `tn_2bd372c2640d4a0fb8fa9d1b8ae90396` 改 In progress，原“选取海边和城市照片”和“已选好12张；其中2张曝光不足，后续可能换图”保留；新增 X/Y 的探索子图。详情可读原因、e2e-peer、更新时间和 revision 4。 | `desktop-a-done.png`、`desktop-reopened-refined-a.png`；聊天 17:34、17:38 的确认与回执 |
| J3 探索增量维护 | 再次通过聊天把 X 记 Done 且结果“噪点太大，负结果”，Y 记 Paused 且结果“暂时缺替代素材”，从 X 新增 Z 并选定，理由“保留原片且噪点更少”。Web revision 5 中 X/Y 均保留，虚线 Derived 指向 Z，Current choice 有理由，A 仍 In progress。 | `desktop-photo-derived-choice.png`、`mobile-long-detail-bottom.png`；同图 A scope；聊天 17:42 |
| J4 复杂图与三层浏览 | 独立打开预置营销图 `tg_8f989d6cf6f3469e8d0d96420661bdd5`，观察 A→B、B→C、A→C、A→D、C→E、D→E。连线可辨认，A 详情的直接后续包含 B/C/D；E 的直接前置包含 C/D。进入 A 的探索层，再进 Z 的计划层，面包屑返回 A/根；没有把 B/C 混入候选层。手机缩放到60%、水平滚动到发布节点、打开详情及返回均可完成。 | `desktop-complex-dag.png`、`desktop-exploration-negative.png`、`desktop-nested-plan.png`、`mobile-nested-plan.png`、`mobile-exploration-return.png`、`mobile-complex-dag-60.png`、`mobile-merge-prerequisites.png` |
| J5 真实 Feishu→同一 Web 图 | 使用 runbook 的专用非 default profile 校验 App/Bot verified 与配置一致，向唯一测试 Bot 发普通 prompt 查询营销图并仅更新文档节点。真实 Feishu interactive 回复列明层级、选定 Z、revision 2→3、仅文档结果变化，并给出完整本栈 URL。Web 当前图自动升 revision 3，文档详情显示“飞书验收569：已检查文档目录”，重启后重读仍在。 | `desktop-feishu-update-postrestart.png`；本次专用 Bot 2026-09-22 17:35 interactive 回执（原始本机证据 `feishu-messages.json` 中只取本次时间项；旧消息不作为本轮证据）。本栈 localhost URL 是隔离环境配置，不声称手机跨设备可访问该 localhost。 |
| J6 Global 模式与 Work/成员边界 | 在 owner UI 新建 `task-graphs-global-569`，明确选择 Global，默认 task_graph 已启用，workspace 位于本 worktree。聊天 `c_4e0dxooj` 真实创建探索图 `tg_fad7d42c15a74d499273b719c70b878c`，查询并更新 X 结果“全局工具确认569”/doing，Web revision 3 中 Y 未改。独立注册非成员 `task-review-nonmember569`：任务列表 0，原图不显示标题/内容；可以读 Global Work 的既有任务记录，但点该 Work 的原图链接仍被拒，原聊天 URL 返回空聊天页。 | `desktop-global-graph.png`、`nonmember-denied.png`、`nonmember-work-readable.png`、`nonmember-work-link-denied.png`；非成员打开 `/chat/c_4e0dxooj` 后 UI `/chat` 显示 No conversations |
| J7 非法关系及旧版本 | 通过聊天明确要求真实工具分别尝试依赖环、X↔Z 衍生环和 B→内部 X 跨层依赖。Agent 获得两次 `invalid_graph: Relationships must not contain a cycle` 和一次 `Dependencies must join direct children of the same plan scope`；get 后图仍 revision 5。另一次以 base_revision 4 写 B 标题，返回 `version_conflict`/`current_revision: 5`，明确解释先重读，未擅自重试写入；Web 中 B 标题、原关系、原结果保留。 | `desktop-invalid-relations.png`（1200×730）、`desktop-version-conflict.png`（1200×730）、`desktop-photo-derived-choice.png`；聊天 17:44–17:47 的实际工具/回复 |
| J8 读取故障、恢复及持久化 | 只拦截浏览器 task-graphs GET 并 abort：已加载的图显示黄色“Refresh failed…not the latest record”且保留图；整页刷新无缓存时明确“Could not read task records. Please retry.”。解除拦截点 Refresh 恢复同图。以延迟实际 GET 响应观察 Loading task records。caller 仅重启 IM，保留同 DB/JWT/端口；本人浏览器刷新看到摄影图 revision 4 和营销图 revision 3 的嵌套、选定方向与结果。 | `desktop-stale.png`、`mobile-stale.png`、`desktop-read-error.png`、`mobile-read-error.png`、`mobile-loading.png`、`desktop-reopened-refined-a.png`、`desktop-feishu-update-postrestart.png` |
| J9 返回聊天草稿 | 同 tab 的 Chat 正文完整任务链接→节点→Discuss，原“草稿保留标记569”消失，仅 Task 引用；Global Chat 写“Work路径草稿569”→View Work→展开回合→正文任务链接→Discuss，草稿同样消失。对照路径 Chat 顶部 Tasks 1→列表→图→Discuss 正确保留原“草稿保留按钮路径569”并追加引用，不自动发送。 | `desktop-draft-lost.png`、`desktop-work-draft-lost.png`；对照 `desktop-draft-before-tasks.png`、`desktop-draft-tasks-preserved.png` |

### Reference Artifacts Reviewed

读取 `spec.md` 全部 S01–S20、`design.md` 的原型对齐契约/P1–P6、R1–R7/W1–W8 与 Runbook、`prototype.html`、change-reviewer skill/template/handoff 和 worktree-runtime。未以 frontend-notes/progress 的成功叙述代替独立判断；没有阅读实现定位问题。

原型通过本人临时 server `127.0.0.1:56379` 在真实浏览器打开；下面“match”指 must-match 的交互、层级、语义、详情及导航，不要求 may-adapt 的颜色/间距逐像素一致。产品英文文案沿用当前登录语言，中文任务名完整显示；原型场景栏与模拟工具没有进入产品。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype P1；`prototype-desktop-chat.png`、`prototype-mobile-chat.png` | Chat/Tasks/Agents 与聊天任务入口、空态 | `desktop-chat-empty.png`、`mobile-discussion-no-graph.png`、`desktop-tasks-empty.png`、`mobile-tasks-empty.png` | 1440×960 /390×844；0→1 图 | match：保留原导航；手机聊天全屏，任务页底部导航完整 |
| prototype P2；`prototype-desktop-complex.png` | 分叉、汇合、跨列依赖，节点详情可查直接前后 | `desktop-complex-dag.png`、`mobile-complex-dag-60.png`、`mobile-merge-prerequisites.png` | 1440×960；390×844 /60%图缩放 | match：实线前置依赖语义一致，横向滚动可到E；状态不自动联动 |
| prototype P3；`prototype-desktop-explore.png`、`prototype-mobile-explore.png` | X→Z 来源、负结果、选定理由、父未自动完成 | `desktop-exploration-negative.png`、`desktop-photo-derived-choice.png`、`mobile-exploration-return.png`、`mobile-long-detail-bottom.png` | 1440×960 /390×844；探索层 | match：虚线 Derived、Current choice、保留负结果与非完成父状态 |
| prototype P4；`prototype-desktop-nested.png`、`prototype-mobile-nested.png` | 计划→探索→计划与返回、面包屑 | `desktop-nested-plan.png`、`mobile-nested-plan.png`、`mobile-exploration-return.png` | 1440×960 /390×844；根→A→Z→A | match：每层局部节点，面包屑正确，子图可进可退 |
| prototype P5；prototype 节点详情/回聊天 | 完整详情、长文本、记录状态，返回聊天保留草稿 | `desktop-reopened-refined-a.png`、`mobile-long-detail-bottom.png`、`desktop-draft-lost.png`、`desktop-work-draft-lost.png`、`desktop-draft-tasks-preserved.png` | 1440×960 /390×844；详情滚动、回聊天 | **deviation/fail**：详情与手机抽屉可用；正文链接往返丢草稿（I1）。顶部 Tasks 路径通过，不能抵销失败路径 |
| prototype P6；`prototype-desktop-empty.png`、`prototype-mobile-empty.png`及 design 错误契约 | 空态、加载、读失败、stale保留旧图 | `desktop-tasks-empty.png`、`mobile-tasks-empty.png`、`mobile-loading.png`、`desktop-read-error.png`、`mobile-read-error.png`、`desktop-stale.png`、`mobile-stale.png` | 1440×960 /390×844；空/加载/故障/恢复 | match：状态明确，恢复实际重读，不把旧图当最新；无演示/模拟控件 |

### 问题清单

| ID | Severity | Regression Relation | 期望 / 实际 / 复现证据 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| I1 | major | direct | design P5/R5 要求返回聊天保留已有草稿。实际从 Chat 或 Global Work 正文中的完整本栈任务链接进入图后，Discuss 返回同一 home 聊天只剩 Task 引用，原用户草稿消失。Chat 复现：`/chat/c_xsu9vkwq` 填草稿→点击 Agent 回复的 `http://127.0.0.1:56231/tasks/tg_0f7fd90f18a04a648d835921212a3255`（同 tab）→选 A→Discuss。Work 复现：`/chat/c_4e0dxooj` 填草稿→View Work→17:44:30 回合→正文 `tg_fad7d42c15a74d499273b719c70b878c` 链接→Discuss。截图见 J9。 | fix-implementation | 正常主旅程造成用户未发送文字丢失，违反 must-match，须修复两条实际消费路径并重新验草稿/引用/不自动发送。验收不负责定位实现根因。 |

### 验收标准覆盖

每项来源均为 `spec.md` 对应 Scenario；涉及 UI 同时投影到上表的 design P1–P6。下表通过只表示该 Scenario 的 THEN 已观察，不能覆盖独立 P5 must-match 的失败。

| Requirement | Scenario | 期望来源 | 验证方式 / 实际证据 | 结果 |
|---|---|---|---|---|
| R1 | S01 讨论并保存计划 | spec S01；P1 | J1；真实聊天确认后保存、回执后说成功、真实链接打开revision2依赖图 | pass |
| R1 | S02 只讨论，不自动开工 | spec S02；P1 | J1/J2/J6；仅讨论无图；操作轨迹为任务CRUD，未委派/开工；global正常inbox回合不是图自动调度 | pass |
| R1 | S03 没有任务的聊天 | spec S03；P1/P6 | J1；明确0和讨论保存指引，桌面手机空态截图 | pass |
| R2 | S04 查看计划结构 | spec S04；P2 | J4；6条外层边、详情直接后续和汇合前置；缩放/滚动后均可读 | pass |
| R2 | S05 依赖不自动调度 | spec S05；P2 | J2；A Done之后B/C To do；`desktop-a-done.png` | pass |
| R3 | S06 从 X 衍生 Z | spec S06；P3 | J3；真实增量新增Z，X/Y保留、Derived虚线来源 | pass |
| R3 | S07 负结果和暂缓方向 | spec S07；P3 | J3/J4；X Done负结果、Y Paused结果，不删除来源 | pass |
| R3 | S08 记录选定方向 | spec S08；P3 | J3/J4；Current choice Z与理由，A仍doing/todo | pass |
| R4 | S09 计划内探索、探索内计划 | spec S09；P4 | J4；真实根→A→Z→返回，桌面/手机正确局部结构 | pass |
| R4 | S10 叶子讨论后进一步细分 | spec S10；P4 | J2；A原ID/说明/结果保留，新增Explore子图，未重建目标 | pass |
| R5 | S11 查询已有任务 | spec S11；P5 | J2/J5/J6；Web续查同图，Feishu准确返回营销图层级/选择，global get同图 | pass |
| R5 | S12 修改状态和结果 | spec S12；P5 | J2/J3/J5；真实节点新内容和刷新持久，B/C不被覆盖；P5额外草稿契约另列I1失败 | pass |
| R5 | S13 不满意后继续改 | spec S13；P5 | J2；同A改doing、原因与更新者/时间可读，未重复目标 | pass |
| R5 | S20 输入渠道不限制 Agent 的任务工具 | spec S20；P5 | J5真实测试Feishu→同营销图Web revision3；J1 Single Thread和J6 Global真实工具；J6成员边界保持 | pass |
| R6 | S14 不合法的关系 | spec S14；P6 | J7；真实三个非法修改均拒绝，revision5/原结构未变，明确原因 | pass |
| R6 | S15 同时修改冲突 | spec S15；P6 | J7；真实旧base_revision4被拒/提示current5/不覆盖；并发补证见下方B1 | pass |
| R7 | S16 刷新和服务重启 | spec S16；P4/P6 | J8；caller仅IM同DB重启，本人浏览器重读摄影revision4和营销revision3、嵌套/选择/结果保留 | pass |
| R7 | S17 网络失败或保存结果未知 | spec S17；P6 | J8真实浏览器GET故障和恢复；写未知补证B2明确局部超时注入，不声称本轮做过真实断开WS写E2E | pass |
| R8 | S18 成员边界 | spec S18；P6 | J6；真实非成员列表/原图/原聊天拒绝，Work已有记录仍可读；Agent成员撤销补证B1 | pass |
| R8 | S19 手机与桌面查看 | spec S19；P1–P5 | J1/J4/J8；手机节点/抽屉/滚动/缩放/返回及完整长文本；原Chat/Agents/Work保留 | pass |

### 边界补证与局限

- **B1**：[M1 integration evidence](M1-task-graphs/evidence/integration.md)，实施 `f407ec609`，task-graph domain/API/native-tool/bridge 29项通过。caller 精确交接 `test_write_conflict_is_atomic_across_connections_and_survives_reopen`（Global/Single Thread各一，两个真实SQLite连接同版本并发仅一成功、另一version_conflict、重开一致）与 `test_agent_writes_browser_reads_same_graph_and_atomic_replay`（幂等、旧版本、坏批原子、成员撤销）。本人没有运行这些测试，也不把其结果冒充独立UI验收；本轮另有J7真实旧版本工具调用与J6用户成员旅程。
- **B2**：caller 交接同29项边界证据中的 `test_native_tool_timeout_retains_write_identity`（HTTP读取超时；create返回write_outcome_unknown且保留同request_key重试身份；list为source_unavailable）和 `test_mapping_and_transport_failures_do_not_invent_success`（WS等待超时写未知；未排队断连source_unavailable）。是局部故障注入补证，不是真实停网的模型回合。完整真实链路另由J1/J5/J6证实。
- 建图首轮出现工具参数错误并自行恢复，耗时约28秒；最终图正确，无提前宣称成功。作为体验观察，不另列阻塞问题。
- IM重启后多标签出现401/refresh401，两个旧标签跳登录，新标签仍可用。caller 核实JWT和DB未轮换；重新登录后继续并成功重读。根因未独立判定，不归因本unit，也不据此声称任务持久化失败。
- 外部Bot原始消息文件含历史测试记录；报告仅使用本次17:35消息，不提交该原始文件。截图尚为本机证据，caller如提升为正式产物需筛选无敏感内容的必要对照图；不能提交整个缓存目录。

### 上层文档同步

- [x] `SPEC.md`：需要由 owner 核对新增任务图持久归属/边界是否已反映；验收不修改顶层架构文档。
- [x] `docs/specs/im/`、`docs/specs/gateway/`：**需要更新**。本轮读取时两个 canonical `task-graphs.md` 尚不存在；待修复与复验后归并unit delta、更新各 Canonical Areas计数。
- [x] `AGENTS.md` / `CLAUDE.md`：无需增加任务专属规则，沿用现有包边界。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新，未改文档体系。

### 清理与交接

只提交本文件。本人临时原型server和Playwright会话在报告完成时清理；IM/Gateway、测试资源和主栈tmux由caller统一按runbook清理。没有执行e2e-up重置数据，没有修改实现/测试/设计/受控配置。原型/浏览器运行缓存均在/tmp。

后续 Round 必须追加，至少复验I1两个正文入口与顶部Tasks对照，覆盖原文字/mentions/引用保留和不自动发送；受影响的P1/P5、S01/S11–S13/S19/S20继承本轮证据或针对失效证据重验，不以自动降低门槛结束。

## Round 2 — targeted（I1 / P5）

- `validated_at=21f79e3d88d0e3e7d3197d737e4779074e82fdb7`；开始前独立核对HEAD一致，caller已用该代码重建前端；未重启Python服务、未替换DB。验收时间2026-09-22 18:00–18:07 Asia/Shanghai。
- `executed_base=99f6e16339a95b94cdb3cb6d5dabd6b301a4b813`；prior report为本文件Round 1。验收期间caller同步到`d9e289f7c`，仅另一unit设计文档，明确无产品代码差异；不把这个机械同步冒充新验过的产品版本。
- 范围仅Chat、Global Work及任务链接导航影响面：验证原草稿、真实待发附件、真实mention token、追加引用与不自动发送。继续使用隔离nano身份与Playwright真实浏览器，没有阅读实现定位，没有发送模型/Feishu消息，没有重跑无关全量场景。

### Verdict

**pass**。`highest_required_action=pass`；I1关闭；0 blocking /0 major /0 minor；`needs_re_review=false`；未外发GitHub issue。

### I1复验与新增证据

截图目录仍为`/tmp/feat569-product-evidence/`。Round 1已提升的正式截图见[浏览器证据索引](M1-task-graphs/evidence/browser/README.md)；本轮截图由caller筛选提升，原始缓存不提交。

| 路径 | 实际操作、结果 | 证据 / viewport | 结论 |
|---|---|---|---|
| Chat正文任务链接（原失败路径） | `/chat/c_xsu9vkwq`输入“修复后Chat草稿569 @”，正常文件drop附加`draft-569.txt`（UI显示文件名与Remove按钮）。点击既有Agent正文摄影图链接→选择A→Discuss this task in chat。返回同聊天，正文原样保留，文件仍待发；只追加A的Task引用。最后消息仍为17:46旧版本保护回执，未自动发送。DM中的尾部@只是普通文字，不冒充mention token。 | `r2-desktop-chat-before.png`、`r2-desktop-chat-preserved.png`；1440×960 | pass |
| Global Work正文任务链接（原失败路径） | `/chat/c_4e0dxooj`输入“修复后Work草稿569”，正常drop附加`work-draft-569.txt`。View Work→展开17:44:30回合→正文Global图链接→打开根详情→Discuss。返回原聊天，原正文和附件保留、追加Global根引用；消息仍为原17:44一问一答，没有发送新消息。手机详情和返回操作未被裁掉。 | `r2-mobile-work-before.png`、`r2-mobile-work-preserved.png`；390×844 | pass |
| 真实mention跨任务链接保留补证 | 预置`c_effntspv`实际为Agent单聊，不具备mention菜单，因此在专用身份内正常新建仅nano/e2e/e2e-peer的群`c_6dsfj2lw`（R2-mention-569），没有发送消息。输入“真实mention草稿569 @”，从成员菜单选e2e-peer，UI出现高亮mark `@e2e-peer`。经Agents→Global Work→真实正文任务链接进入图，再从Chat切回该群；原文字和高亮mention token仍在，群仍No messages yet。该补证验证跨页面完整composer保留，不声称它验证了群home图的Discuss引用；引用追加由上述两条原失败路径独立验证。 | `r2-desktop-mention-before.png`、`r2-desktop-mention-preserved.png`；1440×960 | pass |

以上三组修复后截图均已本人读取视觉核对：附件条、正文、引用、mention高亮和发送按钮在真实UI可见。原型P5要求的“保留文字与mentions、追加引用而不自动发送”现已满足；附件保留是同一完整草稿的补充核对。Round 1顶部Tasks入口控制的有效证据继续保留，本轮没有发现该入口关联回归。

### Reference / Scenario retained范围

- **P5**：Round 1的详情、长文本、手机抽屉证据保留；I1两个失败证据由本轮同路径修复后证据关闭，P5结果更新为**match/pass**。原型契约未改，不重新运行离线演示充当产品验收。
- **P1–P4、P6**：Round 1全部有效；本次只改变任务链接导航，未改变图布局、节点/连线语义、数据读写、持久化、ACL或错误状态。Chat/Work真实入口在本轮再次经过，未发现关联问题。
- **S01、S11、S12、S13、S19、S20**：Round 1主功能证据继续有效，本轮以两个链接往返和手机/mention补证复核其受影响导航面；全部**pass**。
- **S02、S03、S04、S05、S06、S07、S08、S09、S10、S14、S15、S16、S17、S18**：保留Round 1逐Scenario的真实证据与必要边界补证，全部**pass**。未因targeted省略而将未知项自动判通过；这些项已有Round 1有效证据，且未在本次差异中失效。
- 全部S01–S20与P1–P6现均通过，无遗留fail/inconclusive，未降低验收门槛。

### 上层文档与清理

产品修复未改变spec/design目标，无需修订需求或原型。Round 1所列canonical归并与索引更新仍由caller收尾，不由reviewer改写。本人只追加并提交acceptance.md，浏览器关闭；本轮专用群/文件及IM/Gateway仍由caller统一清理，不触碰生产或运行e2e-up重置数据。

## Round 3 — targeted（依赖分列布局）

- `validated_at=24bb6faad681c859f60388dcee1cd585e4575739`；`fix_delta_range=1ef600438..24bb6faad`；`executed_base=2e9c83df9`。开始前核对HEAD一致，caller确认前端dist由此版本构建；2026-09-22独立浏览器验收，原隔离IM/Gateway端口56231及nano身份，营销图revision3。
- 来源为用户新增的“从左到右按依赖分列，同列可并行”要求、design末尾2026-09-22布局决策补充，以及原P2/P3/P4、spec S04/S09/S19。原型的节点/边关系、嵌套与详情must-match保留；列内排序、曲线和间距依新决策适配，不要求复刻旧手工坐标。
- 只经自己的Playwright真实浏览器查看既有营销图，没有读取实现、发送模型/飞书消息、新增fixture、修改数据或重启服务。未操作用户IAB标签页。

### Verdict

**pass**。`highest_required_action=pass`；0 blocking /0 major /0 minor；`needs_re_review=false`。本轮受影响的P2/P3/P4及S04/S09/S19均通过。

### 实际旅程与原型对照

以下截图均已本人打开视觉核对，目录为`/tmp/feat569-layout-review/`；caller可筛选无敏感内容的图提升至[正式浏览器证据索引](M1-task-graphs/evidence/browser/README.md)，不提交原始浏览器缓存。

| 来源 / 受影响面 | 实际观察 | 截图 / viewport | 结果 |
|---|---|---|---|
| P2、S04；根DAG分叉、汇合、直接长边 | 打开`/tasks/tg_8f989d6cf6f3469e8d0d96420661bdd5`。根图明确四列：A选择方向→B开发/D文档同列→C测试→E发布；第二列标Parallel，说明文字明确依赖从左到右、不会自动开工。100%横向画布可滚动，降至80%后六条边全部可见：A→B、B→C、A→C、A→D、C→E、D→E。A→C和D→E沿卡片外留白跨列，未穿卡片或隐藏直接边；发布详情实际列出测试、文档两项直接前置。 | `desktop-root-100.png`、`desktop-root-edges-detail.png`；1440×960，100%/80% | match/pass |
| P3；探索语义和结果 | 点击A的Enter subgraph。X生成视频Done、Y模板Paused、Z混合方案Current choice均保留；X→Z仍为带Derived标签的绿色虚线，与根图实线依赖有明确区别。选中Y后详情显示“质量不足，暂缓”；底部选择理由“成本和质量更平衡”，没有要求全部探索分支完成。 | `desktop-explore.png`；1440×960，100% | match/pass |
| P4、S09；计划→探索→计划与返回 | 从A进入Z，局部图为原型→评估→决定三列实线DAG；选择评估后直接前置为原型、直接后续为决定，面包屑为营销视频产品→选择方向→混合方案。点击根面包屑返回原根图。手机又独立走根→A→Z、打开决定详情、关闭、逐级返回A及根，scope与结构切换正确。 | `desktop-nested-plan.png`（1440×960，100%）、`mobile-nested-plan.png`、`mobile-return-parallel.png`（390×844，60%） | match/pass |
| S19；手机分列与详情 | 390×844根图100%可读A和分叉；缩放下限60%仍需横向滚动，不声称全图能在手机单屏容纳。实际向右查看C/E及两路汇合，打开发布详情并滚动至直接前置，测试/文档均可见。返回根后左侧A→B/D并行列及跨列A→C清楚。探索页有X→Z虚线、Y和选择理由；可横向滚动触达Z的进入按钮。布局控制、面包屑、详情关闭均可操作。 | `mobile-root.png`（100%）、`mobile-root-right.png`（60%）、`mobile-release-detail.png`、`mobile-explore.png`（80%）、`mobile-return-parallel.png`（60%）；390×844 | match/pass |

### Retained范围与清理

- **S04、S09、S19**：上述实际浏览器证据更新其布局/导航部分，其他先前有效行为保留。**P2/P3/P4**的关系语义保持，新的分列结果满足本轮用户要求；不以元素存在或单测通过代替视觉结论。
- **S01–S03、S05–S08、S10–S18、S20及P1/P5/P6**：保留Round 1/2有效证据；本次仅布局坐标/边通道变化，数据写入、持久化、成员权限、外部Bot、错误语义和草稿导航证据未失效。P3相关探索呈现本轮再次实看，没有发现需要扩大到新写入旅程的副作用。
- I1仍按Round 2关闭，未发现关联回归。本轮没有新增问题或降低验收门槛。
- 仅提交本报告；关闭自己的`feat569layout`浏览器。按用户明确要求保留IM/Gateway及既有测试数据供继续体验，不执行e2e-down或其他服务清理。

## Round 4 — targeted（图内稳定短节点ID）

- `validated_at=5f667ba71`；`executed_base=2e9c83df9`；`fix_delta_range=4cb266658..5f667ba71`；验收时间2026-09-22 18:56–18:59 Asia/Shanghai。开始HEAD为158ff52d4，caller确认其后仅报告/归并文档，IM/Gateway已从5f667ba71重启；前端无变化，沿用与当前前端一致的24bb6faad构建。
- 依据用户要求减少Agent节点UUID读写token及明确无需开发态后向兼容的决策：节点采用图内稳定`n1..n500`，graph_id仍全局UUID，无永久别名。本轮验证正常创建、读取、就地修改、依赖引用和短ID深链接；不把一次性测试数据重编号声称为产品迁移，不验旧UUID节点URL兼容。

### Verdict

**pass**。`highest_required_action=pass`；0 blocking /0 major /0 minor；`needs_re_review=false`。

### 真实入口与工具边界证据

在隔离nano的`/chat/c_xsu9vkwq`向e2e-peer发送两条必要提示。均通过Chat的Process展开真实task_graph参数及结果核对，没有只采信Agent最终文字，没有读取实现。工具面板本地快照为`/tmp/feat569-r4-create-tools.txt`和`/tmp/feat569-r4-update-tools.txt`，含原会话记录，不提交。未读取或提交原始模型日志，UI内实际工具边界足以验证本轮结果。

| 路径 / 来源 | 实际prompt及结果 | 结论 |
|---|---|---|
| S01创建、S11读取的短ID影响面 | 18:56提示创建新图“短ID书签569”，根DAG、整理素材→发布书签，两节点待办，仅记录；明确真实create/apply/get，不修改旧图。create回执`graph_id=tg_e141700ba7d241898cea137db75a1e14`、`root_node_id=n1`、revision1。apply参数以`container_id=n1`添加两节点，批内`client_ref=A/B`及`@A→@B`是一次调用引用；回执映射`A:n2/B:n3`、changed_ids为n1/n2/n3、revision2。get all实际返回n1根、n2整理素材、n3发布书签，依赖`[{from:n2,to:n3}]`。没有永久UUID节点或双ID别名。 | pass |
| S12/S13就地更新的短ID影响面 | 18:57提示先get同新图，只把n2标题改“精选素材”、status=doing、order=7，不删除重建，不改n3/依赖，随后get复核。实际链get→apply→get；apply是`update_task,node_id=n2,patch={order:7,status:doing,title:精选素材}`，request_key=`bookmark-569-n2-update-20260922T1857`，回执revision3、changed_ids仅n2。get中n2创建时间仍为10:56:44.860142Z，n3仍todo/order2，依赖仍n2→n3。排序字段变化不重分配ID。 | pass |
| P2/P5、S04/S19；Web与深链接 | 点击Agent真实回复链接`/tasks/tg_e141700ba7d241898cea137db75a1e14?scope=n1&node=n2`。1440×960显示n2精选素材In progress→n3发布书签To do，右侧Node details·n2和直接后续发布书签，revision3。改390×844并整页刷新同短ID深链接，自动打开n2详情抽屉，标题/状态/更新说明/直接后续完整可读。 | pass |
| P3/P4、S09；已有图重编号后的嵌套读取 | 直接打开营销图`tg_8f989d6cf6f3469e8d0d96420661bdd5?scope=n2`，revision4，显示选择方向的n7生成视频Done、n8模板Paused、n9混合方案Current choice，n7→n9的Derived虚线和理由保持。实际点击混合方案进入`scope=n9`，原型n10→评估n11→决定n12；面包屑返回n2正常。只读取，没有修改既有图。 | pass |

### 视觉证据与retained范围

本人已打开截图视觉核对；选定两张无敏感内容图片供caller提升到[正式浏览器证据索引](M1-task-graphs/evidence/browser/README.md)：

- `/tmp/feat569-short-id-review/desktop-short-id-update.png`：1440×960，100%，新图revision3，短ID卡片、依赖及n2详情。
- `/tmp/feat569-short-id-review/mobile-short-id-deeplink.png`：390×844，刷新短ID深链接后的n2详情。

营销探索返回另有本地观察截图`/tmp/feat569-r4-nested-observation.png`和两份nested快照；无需全部归档。P2/P5的结构、详情must-match仍满足，短ID代替截断UUID；P3/P4的嵌套与探索语义保持。

本轮仅更新S01/S04/S09/S11–S13/S19的ID影响面证据。其他S场景、ACL、外部渠道、冲突/失败、持久化、草稿及Round 3 DAG布局证据明确retained；没有重发Feishu消息或重跑全量场景。旧UUID节点深链接按用户明确决策不保留，前轮截图作为当时行为证据，不再作为当前节点URL。caller交接的窄测试30及全量1986+2066通过仅为辅助，不冒充本轮产品结果。

只追加提交本报告并关闭自己的feat569short浏览器；IM/Gateway、原三图和新短ID书签图保留供用户体验。不停止服务、不push。
