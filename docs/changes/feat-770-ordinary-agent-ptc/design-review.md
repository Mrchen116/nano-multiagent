# feat-770 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/ptc_design_review`（独立 reviewer，未参与受审文档创作）
- review_mode: `full`
- mode_reason: Gate 2 首轮，覆盖 spec、design、delta 与单 M1；同时采用 agent-context-review 和 performance-review 的设计模式。
- started_at: `2026-11-15T04:33:00+09:00`（近似，首工具未单独计时）
- completed_at: `2026-11-15T04:37:30+09:00`
- duration: 约 4 分 30 秒，不作为性能测量。
- baseline: `be23e8fc7`；受审 checkout HEAD `208cf25dc3570a32d8cfee6d0e92211383d0707d`，spec 已提交，design/delta/M1 骨架为冻结工作区文件。
- dependency evidence: 同锁版本主 checkout 安装的 DSH `0.2.1-alpha.1` 公开包；dsh-agent-context 另从锁文件对应的 v0.3.0-rc.11 官方 release tarball 只读提取 `package/lib/history.js` 核验（主 checkout 安装的 rc.9 不作为最终版本依据）。不安装依赖、不启动服务、不改代码。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

主要技术方向可行，但普通执行模型恢复原始子调用证据的路径尚未闭合，见 R1-W1。当前仅完成方案审查，不代表已实现、已测得节省或获准实施/部署。

### Coverage 与证据

1. **范围与用户约束。** spec 的 S1–S5 和非目标已逐项对照。默认 native、owner 显式试用、主 Global/PA 与 Dreaming/审核器不切、Workflow 排除、不改持久 REPL、不部署，与用户“先整理方案”的授权一致。M1 将模式、审核和经历材料一起交付，避免半套功能先启用；目录 `.gitkeep` 只是骨架，不当作实施证据。

2. **实际角色与配置装配。** 核对 `src/index.ts:322–346` 的 `agent/created` 入口、`agent-config.ts:152–172` 的业务 attach、`child-role.ts:18–67` 的真实 lineage/fork 判定以及 `capabilities.ts:20–88` 的实际工具集合。Global worker 的默认工具独立于 root allowlist，故设计以有效 bash 资格判断有依据；不能只按 owner allowlist 判断的决定正确。features 经 product-contracts canonical 和 Node 配置保留布尔键，复用配置链合理。`index.ts:870–906` 当前有先撤销选择再等待 idle 的路径；实现需落实设计要求的模式安全边界，不能只在现有 setFeatures 上无条件加 presentAs。设计已经明确此行为并安排热更新/冷恢复验证，未把当前代码当已实现。

3. **DSH 公开能力与职责。** 安装包 `@deepseek-ai/dsh-tools` public exports 与公开声明确认 scoped `presentAs()`、registry schemas、工具执行 hook 及 `tool/ptc-dispatch-start`/`tool/ptc-dispatch` 词汇可用。`lib/types/index.d.ts:576–609`、`lib/types/types.d.ts:8–62` 与 README 的 PTC 说明支持单 scope 单声明、继承最近 scope、opaque call IDs 和子调用日志。Node runtime README 确认每次新进程、直接 Node API、120 秒默认/600 秒最大 deadline，含内部等待。复用 DSH runtime、由 ToolSelection 统一模式、由 knowledge 做有界投影，职责和依赖方向成立；没有必要新增 runtime、第二份全量日志或第二套 Agent Loop。

4. **完整程序审核与子调用。** `policy/approval.ts:120–150` 确认当前顶层 run_code 免 Nano 审核及 alwaysAllowTools 分支；design 明确同时堵住这两条免审路径，保留 explicit skip、Auto off 与无人值守既有规则。`policy/sources.ts:156–188` 已按有效外层历史关联子事件，复用而不改其压缩边界合理。完整 Node 代码先审、实际 bindings 参数继续审核，且不宣称 syscall 沙箱，符合实际信任边界。计划涵盖允许/拒绝/审核故障和拒绝后副作用不存在，足以验证新增权限路径；尚无运行结果。

5. **fork、恢复与退出。** 核对 `history.ts:103–135` 的配置 override、`index.ts:330–340` 的恢复配置及 current `agent-capabilities.md:1354–1395` 的 fork 前缀/分层执行契约。设计区分首次继承与明确配置更新，没有要求在 fork 创建后任意改前缀；要求 worker fork、冷恢复和关闭后的模式验证合理。实际有效模式的创建/恢复证据应在实施测试中明确保存并核验，不能以 owner 开关替代来源模式。这是已规定目标的实施验证事项，不单列缺陷。

6. **Dreaming 原始证据与回查。** `knowledge/memory-source-view.ts:5–49` 当前仅处理 native 配对，`memory-sources.ts:270–323` 有独立 child 选材路径，`dreaming-history.ts:45–110` 有冻结范围、后代认证、generation 与分页。设计同时覆盖 root/child、outer/inner 关联、source_history 专用 action、原始 seq/time、继承来源和 Unicode 分页，不把 outer item_id 冒充 inner 定位，方向成立；不重新按聊天来源删除已记录执行经历，与 current spec 一致。新增工具参数可从宿主返回的 session/sub_call IDs 获得。普通业务模型的恢复是另一条消费链，不能据 Dreaming 链已闭合放行，详见 R1-W1。

7. **Context 与验证深度。** 受影响消费者为执行模型、审核器、Dreaming 与 fork/nested worker。已核对 SDK、外层输出、子事件、维护自身 history 和业务 source_history 的分工。首次/下一请求/失败/换窗/重启的真实 provider 输入与真实模型行为均进入 M1；受控 provider 只证明装配的证据边界准确。无新增视觉交互决定，无需为 Gate 制作原型。

8. **效率。** 设计选三类任务、native/PTC 各至少三次、交替顺序，并约束结果质量、模型、工具返回数据、权限、冷/热缓存；区分 input/cached-input/output、主/child/reviewer、审核等待与总墙钟，不叠加并行耗时。能检验全程序审核是否抵消节省，且允许结论无收益，方法可接受。尚未实测，不能据此承诺收益。

9. **delta 与交付。** delta 以 ADDED requirements 锚定正确 canonical `docs/specs/gateway/agent-capabilities.md`，没有误删 MODIFIED 旧场景。原权限、职责、退出与依据恢复均有消费者契约；R1-W1 需要在 design/验证中补齐而非通过缩小既定 S4/S5 消除。无一次性迁移，无需 deployment-prompt。隔离真实旅程与资源回收已经进入 M1；未访问生产、未创建运行资源。

### 历史问题闭环

首轮，无历史 findings 或 Author Resolutions。

### Issues

#### R1-W1 — 普通执行模型缺少原始 PTC 子调用的恢复入口

- **位置：** `design.md:84–96`、`design.md:116–129`；对应 spec S4、S5 及“原始操作依据可恢复”“部分完成后的取消或恢复”。
- **证据状态：CONFIRMED（设计消费链缺口，不是已实现故障）。** 设计明确执行模型只接收程序输出/返回值，同时规定两个新回查 action 仅给已有 source_history 的维护阶段。当前 `agent-context.ts:5` 提供普通 Agent 的 history；锁定 release v0.3.0-rc.11 的 `package/lib/history.js:18–32` 仅投影 user/message、assistant/message、tool/result，忽略 PTC 子事件。DSH public `dsh-tools/types` 也明确子调用是 log-only，不进入 deriveMessages。当前 `registerDreamingHistory` 只注册在维护上下文，因此不能给普通 Agent 提供替代入口。
- **具体失败条件：** 程序成功完成一项工具写入并得到回执，但在打印/return 之前因后续调用错误、超时或进程退出结束；或者用户之后追问被筛掉的原始查询结果。宿主日志中可能已有完整 `tool/ptc-dispatch`，普通 Agent 的当前输出与 history 却都没有它。设计要求模型“先核对已完成效果”，但没有交代模型如何取得这个已存在的完成回执/原结果。将其一律标 unknown 会丢掉本来可恢复的已完成事实；依靠重新执行查询也不能恢复原时间点结果，更不能作为安全重试写操作的依据。
- **未修后果：** Dreaming 能审计，实际承接用户追问和继续任务的 Agent 却无法可靠区分已完成与未知；S4/S5 与 M1 的普通任务恢复退出标准未闭合。只写指导“不重放”不能补足信息通路。
- **建议修订：** 明确普通执行模型的一条有界、宿主认证的子调用发现/读取路径，或等价的可恢复结果投影；复用现有持久事件和关联 helper，不要求复制日志或扩大至任意 session。交代入口、outer→inner 参数来源、当前会话/fork 范围、失败及换窗后的可发现性。补一个“子调用已成功但 outer 未输出，随后恢复且不重复副作用”的确定性/真实模型代表案例，并覆盖用户追问被筛掉的原始依据。

### Recommendations

无额外建议；避免把已明确的实现细节扩成新的设计门禁。

### Author Resolutions

- R1-W1 — **accepted**。在 design“普通执行模型的 PTC 原始回查”增加 scope-local ptc_history 的发现/读取、参数来源、自身/实际继承事件边界、关闭后保留及换窗/重启恢复；与 source_history 共享有界事件关联但分别认证范围。不依赖程序主动打印回执，不扩大到父会话后续。补成功子调用未输出即 outer 失败、恢复后不重复副作用和用户追问原文验证。delta 补执行者消费者，spec 既有 S4/S5 不变。本轮为实质修订，交独立 reviewer 复核。

## Round 2

### Metadata

- reviewer_target: `/root/ptc_design_review`（原独立 reviewer）
- review_mode: `delta`
- mode_reason: R1-W1 的修订新增有界、scope-local 的只读回查工具，需要检查工具可发现性、权限与恢复交互，超出纯文字 closure；原需求、核心执行/审批边界、既有共享接口和单 M1 不变，不重复 full 审查。
- started_at: `2026-11-15T04:39:41+09:00`
- completed_at: `2026-11-15T04:40:00+09:00`
- duration: 约 19 秒；复用同 reviewer 的 R1 上下文与已核验依赖证据。
- baseline: `be23e8fc7`；checkout HEAD 仍为 `208cf25dc3570a32d8cfee6d0e92211383d0707d`，本轮审查 author 冻结的工作区 design/delta 修订和 Author Resolutions。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1 在设计层面关闭；没有新增 findings。此结论仅批准方案完整性，不代表运行验收通过或新增实施/部署授权。

### Coverage 与证据

- **原始证据恢复。** `design.md:110–121` 明确 `ptc_history.list/read`；list 无需已有 ID 即可发现最近调用，返回宿主认证的 sub_call_id，再供 read 获取原始调用/结果与续读位置。参数来源、失败后下一步和用户追问路径均已闭合。它读取现有持久事件，不依赖失败程序主动打印，也不以重新调用外部工具替代原时间点证据。
- **范围与生命周期。** `design.md:116–119` 不接受任意 session_id，只允许当前 session 及实际继承事件；未继承原件明确 unavailable，不据 parentSession 读取父会话后续。注册/重挂载同时覆盖首次 PTC、已有历史、换窗、重启和关闭后的只读恢复；ToolSelection、NanoApproval 与 scope-local guard 的职责已交代，不把恢复工具加入会污染 Dreaming 的通用 contextTools。现有 fork 前缀规则仍适用，没有另开跨会话授权。
- **共享逻辑与独立权限。** `design.md:112、125–136` 复用窄事件关联/分页 helper，同时保留普通执行和 Dreaming 各自的范围认证；不是让普通 Agent 使用维护阶段的冻结来源目录，也不新增日志副本。该职责划分与 R1 已确认的公开 Session/PTC 事件能力兼容。
- **状态与验证。** `design.md:121、142` 与“验证与效率对照”新增子调用成功但 outer 未打印即失败、换窗/重启后取回回执且不重复写入、用户追问筛掉的原文、关闭后回查和 fork unavailable。raw Node 无逐 syscall 回执的限制保留 unknown，未作虚假保证。M1 仍要求全部 spec 场景、实际 provider Context 和真实入口回查，新增用例已落入既定退出标准。
- **delta。** `specs/gateway/agent-capabilities.md` 的“回查被程序缩减的中间结果”明确普通执行者、用户追问与 Dreaming 三种消费者，按各自获准历史范围读取；未缩小 S4/S5，也未改变 canonical target。
- **retained_from: Round 1。** 配置/角色资格、完整程序和子调用审核、Node runtime/公共 API、fork 模式、Dreaming 冻结边界、性能对照、无迁移与隔离资源安排继续采用 R1 Coverage 1–9 的证据与判断；本轮修订没有改变这些决定。性能仍未实测，不新增收益结论。未启动服务或创建运行资源。

### 历史问题闭环

- **R1-W1 — closed（设计层面）。** Author Resolution 为 accepted；本轮亲自核对 `design.md:110–121` 的宿主事件发现/读取、调用者范围、生命周期与提示，及新验证案例和 delta 消费者。原失败条件现在有明确且可实现的恢复通路，实施时仍须执行已列验证，不能用本次文档 Approved 替代。

### Issues

无。

### Recommendations

无。

### Author Resolutions

- 接受 Round 2 的 Approved；已核实 R1-W1 的完整恢复路径、范围边界和验证投影，无未关闭实质问题。审查后仅追加本结论，spec/design/delta/骨架未作实质修改。Gate 2 文档审查完成；本轮不进入实施或生产切换。
