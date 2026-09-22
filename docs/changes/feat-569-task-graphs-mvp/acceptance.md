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
