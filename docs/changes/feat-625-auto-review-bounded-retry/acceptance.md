# feat-625 — 验收报告

> 对齐：本 unit `spec.md`、`design.md`、`reviewer-runbook.md`；GitHub #361。
> 本次干净重测；不继承旧群、旧实现或旧验收的 pass。

## Round 1 — 2026-10-26，full（覆盖尝试未收齐）

> Validation snapshot: `d72e220f1d21827c65e046f704c13837ea39d7c2 → 4282c0488510c4a46a81d4b5632ebaa236f619ac`
> validated tree: `d571923726b267eb65c8f48907fa9e82c073b59e`；approved design: `407b6e096ec4e6b0bdc9a4a30774dd2e2bed0148`。
> 独立产品验收者未参与该 unit 实现、静态审查或 verifier；只写本报告，没有修改受审实现、测试、设计或受控配置。

## Verdict

**fail — 必验安全/路由证据仍有 inconclusive，不能整体放行。**

- 实际观察到的双策略真实 Global 自建插件、安装生效、两组原生插件调用及用户收到结果均成功（180、55）；额外真实负数调用均按期望拒绝。**这不是插件失败结论。**
- 独立真 IM 故障执行的六组驱动全部通过；真实默认 CC 30/60 秒、Guardian 90 秒超时已实际等待，未缩短生产预算；请求中/退避中 stop 及超过晚到窗口后的零执行已观察。
- 但 Global/child 恢复耗尽、schedule/heartbeat allow/deny 的真 IM 路由没有本轮可执行交接；有效最终 deny、永久配置、连续/混合超时耗尽及 Guardian 并发/context/PA 交叉安全证据未在本冻结版本闭环。不能用普通 interactive、正常 Global 插件成功或后续漂移版本的 native 通过代替。
- 17 个 Scenario：**6 pass / 11 inconclusive / 0 observed fail / 0 not-applicable**。整体 fail 是验收门禁结论，不是宣称发现了 11 个实现缺陷。
- issues_count：2 个 blocking 验证缺口；已证实产品缺陷 0。Highest Required Action：`fix-implementation`（交 E 补齐冻结版本资源/验证，是否需要代码修复由证据决定）；needs_re_review：yes；未新建外部 issue。

## 环境、版本与真实入口

本报告的 `QROOT` 为 `/Users/czj/.nanoassistant/workspaces/nano-quality-r2-1026`；`EROOT` 为 `/Users/czj/.nanoassistant/workspaces/nano-engineering-r2-1026/.worktrees/unit-feat-625-r2-361`。以下 `output/` 均是本轮本机 ignored 证据，不是已提交附件；不提交 raw 日志、DB、截图、身份配置或 secret。

| 项目 | 实际值与核对方式 |
|---|---|
| Q checkout | `qa/feat-625-r2-361-acceptance`；开始及报告写入前 HEAD 精确为 validated_at，tree 如上，working tree clean；不切新 HEAD |
| 集中准备 | E 中性交接 `EROOT/output/feat625-Q-HANDOFF-4282.md`，daily 生命周期由 E 持有；本 Q 未重启/停止 daily、共享 4000 代理或生产 |
| Codex daily | `http://127.0.0.1:61762`；node `wt-feat625-daily-codex-4282-15069`；owner `u_n92b1jz1`；`daily-engineering` 的 IM user `u_3ey5rqjc`；Global / explicit `approval_mode=codex` |
| CC daily | `http://127.0.0.1:61924`；node `wt-feat625-daily-cc-4282-15244`；owner `u_7rcp5qwh`；`daily-engineering` 的 IM user `u_jdz7lccv`；Global / explicit `approval_mode=cc`（audit rules=`nano`） |
| 阵容/模型 | 两套均独立 owner/node/workspace/运行数据/DSH home；实际 P/E/Q Sol/high、PA Astra/medium，审核 `anthropic / codexOAuth:gpt-6-luna / low`；IM config、在线 node、Work 和实际审核请求/trace 交叉核对，不仅看 health/PID 文件 |
| 临时增量 | E 仅将 `plugin_manager` 并入原 allowlist，Auto 开、未 skip permissions；本轮开始无预装成功插件；未改产品默认策略，无手动 allow 绕过 |
| 产品驱动 | 真 IM HTTP/WS（仓库 `tests/e2e/critical_paths/_im_client.py`），真实 user message → Global Inbox → 工具；浏览器再独立阅读 Chat、展开 Work；未用 RuntimeClient.submit 代替旅程 |
| DM 边界 | 调用 create-direct 时服务按同一双方去重，返回此前仅 printf smoke 的 `c_m4mxne6x` / `c_3bx4bhug`，不是另一个全新 DM。插件是 Q 新消息交办、首次自建安装，未继承 smoke 的插件 pass |
| 浏览器 | Chromium 桌面 1440×1000，两套 Chat 与 Work 实际操作并查看图片；无 iOS/移动端或新 attempts UI 结论；详细 attempts 按设计使用只读 domain 导出 |

构建溯源：E 在冻结后构建产物时间 14:42:45–14:42:51（+08:00），daily 原进程分别于 14:43/14:44 启动；本轮核对至 15:20 六 PID `15093/15134/15149/15268/15292/15304` 未替换。`packages/dsh-integration/lib/policy/approval.js` SHA256=`b01ac3cb0e3f17117aacbe0ec3ba6d3c80d447c03aab1ddb0bdf539b74f97be4`，`recovery.js`=`853aef73fc26ef3f78f17b24331711c206bd4235ed5f2496d5e7e267ac43d6a2`；构建时间/哈希在 E 源码更新后未变。Q 的真 IM driver 导入 Q 冻结且未修改的测试/fixture/export；仅将 e2e 起停根指向已构建 E 现场。

**版本限制：** 验收期间 E 源码后续进入 `32a45c7754463aecdc9e77aadf7dfe9f5121e483`，Q 未切换、未让旧 daily 冒充新版。导出器 `--sha` 是调用方标签，不是构建证明；晚到 cancel 导出即使带 E 当前 HEAD，也只按上述仍未替换的 4282 构建评价。源码漂移后启动的 Vitest 不能按 4282 采信，详见分层证据。

## 用户旅程体验

用户从聊天交办规则，得到短确认和必要的安装进度，最后收到包含两组输入、逐项报销与总计的结果。CC 最终表格清楚呈现 180/55，负数结果明确列出实际错误；Codex 的结果也可直接比对原始两组数据。不是只看 Agent 称 done：Q 从完整分页 Work 读到公开 API 查询、文件创建、真实 install_bundle 的 applied 状态和两次原生工具输出，再在浏览器展开相同 Work 查看返回字段。

Work 的回合折叠、Completed/Call failed 状态和原生工具名称能区分安装失败、修正路径后安装成功及实际业务调用。展开第二次调用可见金额、限额、逐项结果和 total=55；回到 Chat 能核对用户实际收到的摘要。详细 audit 的 review/attempt/request 不在该 UI 新增，本轮没有将 Work 普通卡片误说成 attempts UI。整体上，**已观察的正常插件旅程可完成、结果可理解/核查**；尚不能从它推出故障耗尽各模式同样可交付。

现场存在一次路径摩擦：两策略均先依 daily 共享项目说明在 `project/` 写插件，安装器拒绝“必须在当前 workspace 内且在 managed profile 外”。Agent 随后将同内容源码放入自己的 `daily-engineering/` workspace，原生安装成功，没有改 Host 配置或绕过安装器。两次 install 是不同 callId、第一次未成功的路径修正，**不是同一 review 内重复业务副作用**。记录为范围/模板摩擦 side finding；本轮不能归因为 625 回归，未另提缺陷。

## Reference Artifacts Reviewed

N/A：本次设计没有引用原型、reference screenshot 或 must-match 视觉清单；不新增前端 attempts 界面。独立实际阅读/操作结果仍如上记录。

## 可复查证据索引

`P = QROOT/output/feat625-q-4282`；`B = QROOT/output/playwright`。文件中的多处 Work 投影会重复同一 call，统计按 session/turn/callId 去重，不能把 JSON 重复投影当重复执行。

### E1 — 真实 provider / 双策略 Global 插件

- 输入、身份、完整配置：`P/codex-launch.json`、`P/cc-launch.json`。Q 新交办消息分别 `cf627ff8e6a64c28b3fc6258d4186944` / `26696068256e44aab87f871ae6fb99e4`。
- 完整 Work/session/turn/items 分页及聊天取证：`P/{codex,cc}-complete-journey.json`；读至 next cursor=null（每套插件 turn 2，56 items / 35 tool calls）。主 session：Codex `447545e4-adfb-4aaa-854e-31269c177b22`；CC `abf959c1-35e9-49c7-8e4a-c88269632845`；Work 入口 `/im/v1/agents/daily-engineering/work`，再按 sessions/turns/items 分页。
- Codex 安装源码：`EROOT/output/feat625-daily-codex-4282/.gateway-workspace/wt-feat625-daily-codex-4282-15069/daily-engineering/q625-travel-reimbursement-plugin`；bundle `q625-travel-reimbursement-codex-4282@1.0.0`；成功 install call `call_348e925384b1448496a574fa948c5271`。业务工具 `q625_travel_reimbursement`，calls `call_c6be16e5812c40c4b6c7f162cda09fd0` / `call_061cf28184194c37bead01024554d7c7`。
- CC 安装源码：`EROOT/output/feat625-daily-cc-4282/.gateway-workspace/wt-feat625-daily-cc-4282-15244/daily-engineering/travel-reimbursement-q625-4282`；bundle `travel-reimbursement-q625-4282@1.0.0`；成功 install call `call_df666704a6634a92ada98e1d96023fc1`。业务工具 `travel_reimbursement_q625_4282`，calls `call_cf719096b2d94155870af114fa76e8cb` / `call_bf02773497604613b79353e5a66db5e8`。
- 两套安装均 `stage=enable, enabled=true, application=applied, packageResult.exitCode=0, warnings=[]`；第一调用 `[80,150] / 100 → [80,100], total 180`；第二 `[25,40] / 30 → [25,30], total 55`，各一次。实际 sent 最终消息：Codex `50a2a9f891464312a73d515c8d0e312d`；CC `209bb112b40f4623859bed175be9bf91`。不以私有 final 替代 sent。
- 只读审核导出：`P/{codex,cc}-trace-export.json`，每套含 smoke+插件的 41 行，按 callId 关联上述 Work；原数据在各 runtime `.dsh-runtime/<node>/storages/nano_approval/sessions/<main-session>.json`。真实审核路由为 Luna/low，而不是主 Sol/high。未声称真实供应商恰好返回过 503。
- 负数补验：`P/{codex,cc}-negative-request.json` / `-negative-result.json`，turn 3；同一已安装插件仅再调用一次 `[-1,25] / 30`，实际 error `amounts[0] must be a finite non-negative number`，随后 sent 报告，未修插件/未重试。此为期望业务拒绝，不是有效审核 deny 测试。
- 实际查看的画面：`B/q625-codex-inprogress.png`、`B/q625-codex-work-output55.png`、`B/q625-cc-delivered.png`、`B/q625-cc-work-output55.png`。全部 1440×1000，图片已独立阅读，而非仅检查存在。浏览器进入 `/chat/<conversation>` 和 `/settings/agents/daily-engineering?view=work`，展开 turn 2 与工具返回。

### E2 — 真 IM + 受控 HTTP（独立执行，非真实 provider）

- `P/faults/summary.json`：六组 driver 成功，耗时依次 104.05 / 40.89 / 39.76 / 102.10 / 73.30 / 20.26 秒；driver 从 Q 冻结文件导入 `test_auto_review_retry_critical_path.py`，不执行 E 后改的同名测试。e2e 起停复用 E 的合格 Python3.11 环境和已构建产物；原型为 default/main-config，与真实 daily 分离。
- `P/faults/http-matrix/`：双策略 20 cases，503、429 秒数/date、socket 断开、格式失败、503→格式→allow、401、持续失败、Retry-After 15 秒拒绝提前重打。通过真实 IM 发消息，不直接 submit runtime。获准的隔离文件副作用一次且发生在审核完成之后，阻断零次；原 interactive 审批卡按真实拒绝收束，未手动 allow。
- `P/faults/safe-summary.json` 和 `P/faults/trace-<case>.json`：共 32 个本轮 case trace，含取消、阶段及配置事务补充。主 action call=`retry-<case>`，每个 reviewId 下独立 attempts/requestOrdinal；例如 `codex-mixed` review=`8bfa1524-707d-486e-9228-1bcd56bb2156`，3 attempts，retriesUsed=2、formatRetriesUsed=1，503/invalid_verdict/allow 可分别辨认。
- `nano-timeout` 实际 30,561ms，budgets=[30000,30000]；`nano-stage2-timeout` 60,567ms，budgets=[30000,60000,60000]；`codex-timeout` 90,676ms，budgets=[90000,90000]。对应 `_default_full_timeout_recovery` / `_cc_stages...` 驱动；没有改短 timeout。成功恢复工具各一次。
- `nano-stage-exhaust`：第一阶段用两次恢复后正常推进第二阶段，第二阶段故障立即 interactive_pending，额外次数仍2；`nano-stage2-service` 仅重试失败第二阶段，未重放有效第一阶段。
- 配置事务：`P/faults/config-release/`，两策略 × request/backoff，真实 IM PATCH 撤下忙碌 bash → 409 capability_in_use → 事务 release 后原 action 继续。`*-config-request` retries=0；`*-config-backoff` retries=1，原模型和预算未变，effects 各一次。这里只证明 prepare-reject release，不冒充 persist-failure、metadata-only、真正 disable 或新配置 idle 生效。
- 原始请求/运行日志和副作用文件留在对应 stack 目录，仅用于本地复核，不提交。usage 不可得时 `usageComplete=false`，knownUsage 只计可得请求，不补零为完整总成本。

### E3 — 真 IM 主动停止与晚到（独立执行）

`P/faults/cancel/` 覆盖两策略请求中与 backoff `/stop`；另 `P/late-cancel/summary.json` 在四次 cancel durable 后保持隔离栈存活，分别继续观察约131/121/110/100秒（超过 fixture CC35/Guardian95 秒晚到窗口）。四例均 finalRoute=cancel、每例仅1条 reviewer HTTP、0业务副作用、终态 trace 未被迟返修改，不新发 attempt。所有测试栈最后正常 down。

### E4 — fake-clock / native / 工程证据边界

- 冻结版本 `M1-review-recovery/progress.md` §Additional executed evidence、§Executed engineering checks 可作为**工程补充**：recovery19、真实配置生命周期20 controls、精确并发归属、来源/parser/PA等；不是本 Q 产品旅程通过，也不替代 runbook 要求的真 IM Global/child/schedule 路由。
- Q 尝试窄 Vitest 补证前做文件 hash 校验，发现 E `approval.test.ts` 已漂移，第一命令停止而没有运行。其后仅选测试文件 hash 仍同冻结版本的六组53 tests及 lifecycle10 tests执行，工具均 exit0；但它们解析到 E 已变更的实现源码，**不能计入 validated_at=4282 的独立 pass，也不能冒充对32a45c7的正式验收**。本地输出 `P/narrow-supplements.txt`、`P/lifecycle-supplement.txt` 仅留作此限制的审计。
- 因此连续/混合 timeout 耗尽、Guardian context rebuild/并发隔离、严格 PA disclosure/来源冻结、persist-failure/metadata-only 与实际 owner-disable反证、inspection卡FS、trace写失败等未收齐本冻结版本独立可适用证据。下一轮应按新精确 SHA 和受影响范围补齐，不重复全量环境安装，不拿旧 pass 覆盖新实现。

## 问题清单

| # | 严重度 / Regression Relation | 期望 / 实际 / 复现证据 | Recommended Action / Action Rationale |
|---|---|---|---|
| Q625-R1-01 | blocking（验收证据） / unclear | spec S14/S15、runbook§5要求真 IM Global/child/schedule/heartbeat耗尽路由；现有中性fixture只有普通请求 bash/interactive 路由，未提供 Global 委派或真实 schedule/heartbeat触发包。正常 Global 插件成功不能覆盖技术耗尽路径。见 E1/E2、S14/S15 | fix-implementation：E交付同冻结版本可执行中性路由包，再由本独立验收者实跑；不新增产品debug开关、不伪造source、不以人工allow跳过。没有该证据不能确认权限不扩大 |
| Q625-R1-02 | blocking（版本/验证适用性） / unclear | E源码在验收中进入新SHA；已编译真 IM结果仍属4282，但后跑 native的实现源码不再属4282。有效最终deny/永久配置、连续/混合timeout耗尽与Guardian/PA交叉安全未闭环。见 E4、S2/S4–S10/S12/S17 | fix-implementation：保留历史证据，在parent冻结新SHA、构建和路由包后定向复验；先补具体缺失分支，不预断实现缺陷，也不通过改报告将漂移结果升级为pass |

Side finding：daily共享项目路径与workspace插件安装范围提示存在摩擦；已在真实旅程自动修正，不是本轮确认的625缺陷，不新增out-of-unit工作。

## 验收标准覆盖

各行源为本 unit `spec.md` 对应同名 Scenario；以下 S编号只用于报告定位。pass 仅对本轮具体观察成立，inconclusive 不以工程说明补齐。

### Requirement: 临时失败在同一待审动作内有界恢复 — 组内结论：fail（含 inconclusive）

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S1 短暂故障后放行 | spec§临时失败，U1 | 真IM双策略503/429秒/date/socket→allow，E2 `*-service/rate/rate-date/transport`；call内部恢复，工具一次且最后review后才产生effect | pass | 无主Agent再次调用来伪装恢复；真实provider旅程独立见E1 |
| S2 混合失败共享额外两次额度 | spec§临时失败，U2 | E2 `*-mixed`共3次/format1；`*-persistent`2次后停止；CC跨stage不重置 | inconclusive | 已证503+format和跨stage；timeout→503→timeout、Guardian context/retry共享组合未闭环，E4不能当冻结独立结果 |

### Requirement: 每次恢复保留正常完整判断预算 — 组内结论：fail（含 inconclusive）

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S3 CC 恢复后的完整阶段判断 | spec§完整预算，U2/U3 | E2实际30秒/60秒超时再成功，trace完整30000/60000；stage2只恢复失败阶段，正常推进不占retry | pass | 没有缩时或共享首次残余预算 |
| S4 Codex 恢复后的完整审核判断 | spec§完整预算，U2/U3 | E2 `codex-timeout`实际90,676ms，两个90000预算，恢复成功一次effect | inconclusive | 正常90秒预算子项通过；同action只读/context重建与服务额度共享边界还需适用native组合证据 |
| S5 等待可以延长但不会无限延长 | spec§完整预算，U2 | E2真实90秒及有界Retry-After；E4工程fake-clock补充 | inconclusive | 未收齐连续完整超时及最后一次预算/action360s的冻结可适用组合，不拿单次90秒成功证明全上界 |

### Requirement: 空白或非法判定仅获得共享额度内的一次恢复 — 组内结论：fail（含 inconclusive）

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S6 首次格式失败后有效判定 | spec§格式恢复，U2 | E2双策略 `*-format` invalid_verdict→allow，retries1/format1，effect一次；`*-mixed`计入共享总额 | pass | 观察为allow分支；有效deny的整体安全结论仍归S8/S10待验 |
| S7 再次格式失败或总额度先耗尽 | spec§格式恢复，U2/U4 | E2双策略 `*-invalid`第二次格式失败立即interactive_pending，categories不混为503/有效deny | inconclusive | 重复格式子项通过；503→503→首次format时总额已尽组合未独立闭环 |

### Requirement: 技术恢复不改变授权、策略与最终拒绝 — 组内结论：fail（含 inconclusive）

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S8 CC 两阶段与最终拒绝 | spec§授权策略，U3 | E2 `nano-stage2-service/stage-exhaust/stage2-timeout`正常第一阶段非allow进第二阶段，失败不重放第一阶段 | inconclusive | 阶段语义子项通过；有效最终deny/拒绝计数/升级及不刷allow缺同版可适用证据 |
| S9 Codex 风险、授权与检查约束 | spec§授权策略，U3 | E1真实工具动作与审核call关联；E2恢复新full记录；E4工程并发/来源/PA补充 | inconclusive | 精确并发fork/另一parent、readonly/context/source与PA交叉安全不能以正常插件结果或漂移native代替 |
| S10 有效拒绝与永久错误不作故障恢复 | spec§授权策略，U3/U4 | E2双策略 `*-auth`单次permanent、retries0、interactive_pending、effect0 | inconclusive | 401子项通过；有效最终deny、永久配置/QUOTA未独立收齐；业务负金额error不是审核deny |

### Requirement: 主动取消优先于超时恢复 — 组内结论：fail（含 inconclusive）

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S11 请求中或退避期间停止 | spec§主动取消，U4 | E3真IM双策略四种stop；终态cancel，无后继HTTP，无审批新流程；继续观察100秒以上，0effect，晚到trace不变 | pass | 对本fixture取消窗口成立；shared-owner disable/FS特殊反证未在此行扩大声称 |
| S12 非主动取消的单次超时 | spec§主动取消，U2/U4 | E2真IM CC30/60、Guardian90默认超时，父有效时完整预算恢复 | inconclusive | 首次timeout恢复子项通过；连续timeout耗尽的共享上限未收齐同版适用证据 |

### Requirement: 耗尽严格沿用既有模式与配置分流 — 组内结论：fail（含 inconclusive）

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S13 有人值守聊天审核不可用 | spec§耗尽分流，U4 | E2双策略persistent/invalid/long/auth转interactive_pending、实际审批卡拒绝、effect0 | pass | 没有把技术不可用当有效安全拒绝或自动allow；不声称人工allow分支已体验 |
| S14 Global 与子任务审核不可用 | spec§耗尽分流，U4 | E1为正常Global成功，不是耗尽；现有fault driver为普通交互入口，见Q625-R1-01 | inconclusive | 缺Global与委派child真实耗尽return_to_agent、child无卡/0effect证据 |
| S15 无人值守的 allow 与 deny 配置 | spec§耗尽分流，U4 | runbook要求真实schedule/heartbeat触发；本轮未收到可执行中性包，见Q625-R1-01 | inconclusive | 未伪造source.kind；不能声称耗尽一律零执行，既有allow配置应只执行一次 |

### Requirement: 审核恢复可追踪并以真实旅程验证 — 组内结论：fail（含 inconclusive）

| Scenario | 期望来源 | 验证方式 / 证据 | 结果 | 备注 |
|---|---|---|---|---|
| S16 一次动作与再次工具调用可区分 | spec§轨迹，U5 | E1完整Work callId关联E2 domain；同reviewId attempts/request ordinal、类别/模型/耗时/usageComplete/finalRoute可查；`codex-mixed`例及两次不同install call | pass | 不新增attempts UI；unknown usage不当零；终态domain非进行中journal，不承诺进程突死完整trace |
| S17 真实全局插件旅程与受控证据分别交付 | spec§轨迹，U1/U5 | E1双策略真实安装/两次工具/180+55/实际sent/完整Work及负数补验；E2/E3确定性故障另列 | inconclusive | 真实provider可用和插件旅程子项通过；本Scenario还要求最终deny/各模式fallback等完整故障矩阵，缺口如上，不能单次服务成功代替 |

## 上层文档同步

- [x] `SPEC.md`：无需更新；未改变跨包顶点架构。
- [x] `docs/specs/gateway/agent-capabilities.md`：需要由 orchestrator 在最终实现确定后按本 unit delta-spec 校正归并（含有界恢复与旧“已有重试”模糊描述）。本轮冻结 `design.md` 明确该唯一 canonical target；Q 不代写，当前报告不宣称已完成归并。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；未改变文档体系。

## 清理与下一轮边界

Q 启动的六组fault栈和一组late-cancel栈已由正常finally down；2026-10-26约15:21(+08:00)独立连接核实7个IM端口 `65327/49668/49825/49963/50416/50840/51986` 均释放，未发现本轮fixture残留进程。Q创建的浏览器session `q625-clean-9cb` / `q625-cc-9cb` 均已close。未删除原始证据；未停共享代理、生产或E daily。

E仍持有两套daily/已安装测试插件和本机运行数据生命周期。parent已收到安全切换ready边界；可协调E保留4282可达refs/domain导出/必要原始证据后准备新版。本报告不自选新SHA，需新的精确版本/构建/路由包再续用同验收者、同现场定向复验，追加Round2，保留本轮全部inconclusive直至有证据关闭。报告完成不等于产品通过，也不授权merge/deploy。

## Round 2 — 2026-10-26，targeted（同验收者、同现场）

> Validation snapshot: `d72e220f1d21827c65e046f704c13837ea39d7c2 → fe623b4bb8227f06d720cd5b11f81dd98e5af72f`
> validated tree: `b7b3f470d628b930c56ec594d48d952772acdaee`；approved design 仍为 `407b6e096ec4e6b0bdc9a4a30774dd2e2bed0148`。
> Round 1 的 165 行原文完整保留；原 blob=`b81a295950845d4a63f3ab824bd1de4ac562f544`，Q 历史 ref=`evidence/feat625-q4282-r1-15bf9925`。本轮不是将 R1 的 inconclusive 静默改为 pass。

### Verdict

**pass — 本冻结版本的适用产品验收通过。**

- 17 个必验 Scenario 的当前结论为 **17 pass / 0 fail / 0 inconclusive / 0 not-applicable**，其中明确区分本轮新执行、同冻结工程证据复用与未失效的具体前轮观察，不声称 17 项均全量重跑。
- Q625-R1-01、Q625-R1-02 在本轮关闭；**open issues_count=0，新增已证实产品缺陷=0，blocking=0**。Highest Required Action=`pass`，needs_re_review=`no`（限此 validated_at 与已审范围；后续产品改动另判）。
- 独立真 IM 7 行 × 双策略共 14 个耗尽路由全部通过；独立同冻结窄控制 4 文件 45 tests 通过；两套新 daily 的真实 provider 新插件自建、安装和两次原生调用均实际完成，用户收到 180/55，Q 实际操作 Chat/Work 并阅读关键图片。
- 该结论不是 Ready PR、全仓 CI、canonical/delta 归并、dependency audit 或 merge/deploy 结论；这些仍由各 owner 独立收口，不能以本报告替代。

### 复验范围与保留条件

本轮中性包 `EROOT/output/feat625-Q-HANDOFF-fe623.md` 交接了新构建、真实路由与可复查原始材料。Q 核对 Git 范围文件清单：相对 R1，产品变更集中在 `policy/approval.ts` 的终态审计/并发拒绝路由，另有验证、fixture、报告及 runbook 增量；没有把审查角色改为源码静态 reviewer。由此定向重验终态路由与 audit fail-closed、同冻结此前缺失的预算/context/授权/生命周期控制，并重新跑真实插件组装旅程；不重新安装全部环境或再等待整套三次生产时长超时。

R1 的 S1/3/6/11 等具体真实 HTTP/默认 30/60/90 秒等待、stop 及晚到观察仍是 **4282 的原始观察**。其预算/恢复控制与 adapter 未因本次终态修正失效，且新冻结工程完整真 IM 13 行与 native 结果交叉支持，故可按范围保留；不是把原始 trace 的 SHA 改为 fe623。R1 源码漂移后执行的 native 仍不适用，**本轮完全不采信那两份漂移测试为新版本证据**，由 R2 的同冻结材料替代。

### 本轮真实环境与构建溯源

| 项目 | 本轮实值 / 核对 |
|---|---|
| Q checkout | 同一 `QROOT`，安全切到精确 fe623，新报告分支 `qa/feat-625-r2-fe623-acceptance`；切前保留旧 ref、核原报告 blob；写报告前 working tree clean |
| Codex daily | `http://127.0.0.1:59905`，node `wt-feat625-daily-codex-4282-37997`，owner `u_ymjyco1l`，Global daily-engineering，显式 codex |
| CC daily | `http://127.0.0.1:59920`，node `wt-feat625-daily-cc-4282-38039`，owner `u_3xg68xqv`，Global daily-engineering，显式 cc（audit rules=nano） |
| 身份边界 | 同两 runtime 根复用，但新的 IM DB/owner/node/main session，不是连续旧会话；目录名 `4282` 仅路径后缀。旧插件没有被迁入作为本轮成功；E 保留旧 before/after-down archives、Work/domain 与插件 payload receipt，含凭据的 archive 不公开 |
| 实际配置 | Q 读取两套 daily manifest、IM config/在线 node/Work；P/E/Q Sol/high、PA Astra/medium，真实独立 reviewer anthropic / codexOAuth:gpt-6-luna / low；Auto 开、未 skip permissions；仅既有 plugin_manager allowlist 增量，无临场放宽 |
| 构建与 loader | Q 独立逐个校验 131 tracked source/test 与 fe623 Git blob、487 compiled artifacts hash；两实际 profile 的 createRequire 均解析到 EROOT `packages/dsh-integration/lib/index.js`，不是旧 snapshot/lib。记录 `QROOT/output/feat625-q-fe623/independent-freeze-check.json` |
| 末次核对 | 16:40(+08:00) 再核上述全部 131+487 均不变，实际六 PID `38021/38065/38083/38066/38120/38126` 仍为 16:00 启动进程；无重建/重启。导出器 `--sha` 仍只作标签，不当构建证明 |
| 真入口 | Q 通过实际 IM HTTP/WS 发新用户任务；create-direct 按双方去重至本轮 smoke DM `c_6cuslf8f` / `c_z8fc3gwm`，不是声称第三个全新 DM。只读 Work 全分页到 null cursor；未直接 runtime.submit |
| 浏览器 | Chromium 1440×1000；独立阅读两套 Chat 已投递结果，再从 View Work 展开本轮回合及第二次业务工具；无 iOS、新 attempts UI 或移动体验结论 |

### R2 分层证据索引

以下 `P2=QROOT/output/feat625-q-fe623`，本机 ignored 原始证据仍不提交；`E2=EROOT/output`。测试驱动、原始 HTTP 和 domain 的结论与真实供应商分列。

#### R2-A — 独立真 IM 耗尽与原模式路由

命令使用 E 已锁定 Python3.11 环境、冻结测试/构建，隔离 subprocess proxy 环境：`pytest tests/e2e/critical_paths/test_auto_review_routes_critical_path.py -k exhaustion_preserves_source -q --basetemp=<Q新唯一绝对目录>`。本次目录为 `P2/routes-9cb-r2`，事前核为不存在；7 passed，206.57s，exit0。未改实现、测试或 daily 受控配置。

- `P2/routes-execution.log`、`P2/routes-safe-summary.json`；每行 runtime 的 `q-trace-export-fe623.json` 与 captured requests/effect 文件保留。7 行各含两策略：interactive、Global、实际 native child、schedule deny/allow、heartbeat deny/allow。Global 走真实 Inbox/read，child 真委派，schedule 用真实 timer，heartbeat 用真实 HEARTBEAT/cadence；不伪造 source.kind。
- 14 个待审 bash 均收到 3 条 reviewer 503 请求、retriesUsed=2、formatRetriesUsed=0；CC budget 每次 30000，Guardian 每次 90000。`decision=no_verdict/source=classifier_unavailable`，拒绝计数均0；未把技术失败当有效模型 deny。
- interactive 两策略 `interactive_pending`，原审批卡拒绝收束、effects=0；Global/child 两策略 `return_to_agent`，即使配置 fallback allow 也无子任务卡、fallbackOutcome=null、effects=0。
- schedule/heartbeat 均 `finalRoute=unattended`；既有 deny 零 effect，既有 allow 各恰好一条 effect。配置 before/after 未扩大，allow 原因是既有技术不可用 fallback，绝不是模型有效 allow；没有手动 allow 做绿。
- Global reviewId：Codex `b6830a5d-54da-413b-8965-1c6dec56d349`，CC `d55f0017-dd19-4687-a973-965c6981f4c4`；child reviewId：Codex `8f363f79-d501-47b8-8ba4-75caf0b2fe9e`，CC `4fc948b0-0ed2-4e53-9a17-100a6524e265`。完整其余定位在 safe-summary，统计的 http_records 包含 main/event，不误称全部是审核请求。

#### R2-B — 独立同冻结 fake-clock/controller 与窄 facade

`P2/narrow-controls.log`：`pnpm exec vitest run` 指定 `review-recovery-budget.test.ts`、`review-recovery.test.ts`、`codex-approval-lifecycle.test.ts`、`approval-retry.test.ts`，4 files / 45 tests passed，exit0，16:28:38。全部 source/test 输入已独立核为 fe623，而不是 R1 的漂移 source。

- 完整 30/60/90 秒 × 三次连续超时、TIMEOUT→503→TIMEOUT共享额度，无第四条请求；CC 正常阶段推进不占恢复，action360秒撤销 generation、末次正常预算不截短。这些是 fake-clock，不宣称真实供应商连续等待了三次。
- service→service→format、重复格式、EMPTY_RESPONSE 子额度；AUTH/QUOTA/CONFIGURATION/INVALID_REQUEST 与 context/abort/unclassified 不盲重试。CONFIGURATION 与503并存仍永久错误优先。Retry-After15秒不截成10秒重打，unknown/partial usage 不冒充完整零成本。
- Guardian 同 action context rebuild 最多1次，跨503与重复 overflow不重新领取；输入/action/config 在异步准备前冻结，supported effort不擅换模型；晚到 create/dispose quarantine 与 PA disclosure namespace/预算分离。
- 直接针对本次产品改动：有效 allow/deny/unavailable 后 **durable audit 写失败** 均 reviews/writes/effects=1/1/0，不重审、不借 unattended allow 执行；原子并发 deny 计数所选路由与 durable trace 一致。是公开 facade+受控 table 失败，不夸成实际 IM 磁盘满或进程突死 journal。

#### R2-C — 可适用的同冻结工程执行材料（复用，不改称 Q 全量重跑）

Q 实际读取并核适用性：`E2/feat625-native-regression-fe623.log` 15 files / 89 tests passed（16:04:02，103.35s，默认并发），`E2/feat625-codex-parser-fe623.log` 9 tests passed（16:09:36），以及 `E2/feat625-im-complete-fe623.log` / `-summary.json` / 每 root `trace-export-fe623.json`（13 rows、499.64s、51 traces）。编译/input attestation 与 Q 末次实测 hash 一致。

- native 涵盖真实 DSH scope/delta/fork、实际默认 Guardian90秒 timeout/同输入恢复、并发 idle I / active A / fork B / 另一 parent C / CC D / disclosure P / main M / auxiliary X 的精确 stream归属；另一 owner 不中断。不是只按相同模型或 parent 粗分。
- 双策略 configuration reservation 的 rejected prepare/persist-failure/metadata release 保持旧 action；真正 cancel/disable 撤销，含 request/backoff 与另 owner 反证。source14、personal-security8、child delivery、workspace/workflow、attribution 和当前 Guardian parser 独立覆盖；只读 inspection/阻塞FS与PA指导隔离有 native 证据。
- 同冻结完整 IM 材料重新覆盖 HTTP503/429/date/socket/format/mixed/permanent、实际默认 CC30/60/Guardian90秒恢复、CC跨stage、取消与真实 PATCH 409 release。与 R1 已独立实跑的具体未失效观察相互印证，不把工程13行标为本 Q 另一次执行。
- parent 协调的额外6文件最小资源复验属于 E 的另项执行；本报告不预报它的结果，也不依赖将来结果来给当前 pass。

#### R2-D — 新 daily / 新插件 / 真实 provider 与实际投递

Q 新消息 Codex `152eb9a3cd024d93aa0de84c1b638b9d`、CC `e715f87f61a2432196ef2caba6e704c7`；输入与配置见 `P2/{codex,cc}-launch.json`。完整 Work/items/聊天见 `P2/{codex,cc}-complete-journey.json`，审核域 `P2/{codex,cc}-trace-export.json`，摘要 `P2/provider-summary.json`。

| 实际观察 | Codex | CC |
|---|---|---|
| main session / 回合 | `323dd6fb-de54-4ba6-9d83-863e8463780b` / turn2，35 tool calls，Completed | `02b33ee2-0ab7-4dca-87f4-c2c57ea42592` / turn2，36 tool calls，Completed |
| 新源码（各新 node 的 daily-engineering 下） | `plugins/travel-reimbursement-r2-fe623` | `travel-reimbursement-r2-fe623` |
| 真 install call | `call_122a2ad5a198430f8e850bf65043395d` | `call_21343936215b4b868bb4f5771d09e8b6` |
| bundle / 生效 | 两者均 `travel-reimbursement-r2-fe623@1.0.0`；enabled=true、application=applied、warnings=[]、package exit0 | 同左，非等待重启状态 |
| 原生业务工具 | `travel_reimbursement_r2_fe623` | `travel_reimbursement_r2_fe623` |
| 第一调用 | `call_b973100dbd83429d9491afc47a4fcbe5`，amounts[80,150]/limit100 → reimbursable[80,100]，total180 | `call_0aed37a4b26240309a346c0140890d54`，amounts[80,150]/itemLimit100 → reimbursed[80,100]，total180 |
| 第二调用 | `call_ff92d6f207ed46bda1ef619ce1e11aad`，amounts[25,40]/limit30 → reimbursable[25,30]，total55 | `call_9f06b1047ad7409f8fd771563882641e`，amounts[25,40]/itemLimit30 → reimbursed[25,30]，total55 |
| 最终实际 sent | `9db5fc33e7d44fc2a55aeae939a4d9c6`，DM `c_6cuslf8f` | `ed1baacaad90470e9aa4f486a183b3b9`，DM `c_z8fc3gwm` |

不是仅相信模型自述：安装与两次业务工具各一次，由原生输出、Work callId、audit 关联和实际聊天投递共同确认。两套均先查当前公开 Skill/API，在自己 workspace、managed profile 外创建新 bundle；未复用旧 node 业务插件，未用 bash 算结果。按本轮明确两次业务调用限制，没有对新插件再调用负数；R1 负数 pass 仍只属旧插件，不将新插件“已实现”自述当作本轮负数动态验收。

额外实际有效拒绝：CC 定位时试图批量打印 DSH 环境变量，被审核阻止。bash `call_d28adf90c15e4dbe818eac3343e6fc5f` / review `d2cf67da-e7dc-4a27-be04-8907da92e8ae`，合法 CC 两阶段最终 deny、classifier_block、计数1/1、retriesUsed=0、formatRetriesUsed=0、finalRoute=deny，工具未执行。Agent 明确放弃该操作，改用 pwd/公开插件路径完成新插件，未换身份或重试泄露操作。这是实证有效安全拒绝，不是负数业务 error，也不将该安全保护列成产品失败。

独立体验：Chat 中用户能核对两组输入/逐项报销/180及55，得到简短进度和最终可读安装状态；从 View Work 展开回合能区分初始不存在文件的 read 失败、成功写入、安装及两个 Completed 业务调用，第二调用展开可见 total55 等字段。未见妨碍此旅程的整体阅读/操作问题。`QROOT/output/playwright/q625-r2-{codex,cc}-delivered.png`、`q625-r2-{codex,cc}-work55.png` 四幅1440×1000图片均已实际阅读。详细 attempts 仍用 domain 导出，不冒称新 UI。Reference Artifacts Reviewed：N/A（设计无 must-match 原型，沿用 R1 范围）。

### Round 1 问题处置

| 问题 | 本轮处置与结论 |
|---|---|
| Q625-R1-01 真IM路由缺口 | **closed at fe623**：R2-A 独立实跑真实 Global/委派child/schedule/heartbeat双策略耗尽，source、原路由、卡片、effect、配置均核对；未用普通成功旅程代替 |
| Q625-R1-02 同版适用性/安全矩阵缺口 | **closed at fe623**：131输入/487产物/真实loader及进程建立版本链；R2-B关键45项独立执行，R2-C同冻结native/parser/全IM可适用材料，R2-D真实最终deny与新插件旅程；旧漂移native仍排除，不改写历史 |

### 全部必验 Scenario 的当前结论

来源均为本 unit spec 同名 Scenario，S编号沿用 R1；下表的 pass 是综合范围判定，证据层次已逐行标明。

#### Requirement: 临时失败在同一待审动作内有界恢复 — 组内结论：pass

| Scenario | 本轮与保留证据 / 实际结论 | 结果 |
|---|---|---|
| S1 短暂故障后放行 | 保留R1-E2双策略503/429/date/socket成功且effect一次；R2-C同冻结原始HTTP矩阵支持。预算/adapter未因终态修正改变，R2-A耗尽也无提前执行 | pass |
| S2 混合失败共享额外两次额度 | R2-B连续/混合TIMEOUT→503→TIMEOUT、跨stage与context组合补齐，最多2恢复/无第四次；R1 mixed与R2-C真IM仍支持 | pass |

#### Requirement: 每次恢复保留正常完整判断预算 — 组内结论：pass

| Scenario | 本轮与保留证据 / 实际结论 | 结果 |
|---|---|---|
| S3 CC 恢复后的完整阶段判断 | 保留R1实际30/60秒等待与stage2不重放s1；R2-B完整预算/共享上限，R2-C同冻结全IM复核 | pass |
| S4 Codex 恢复后的完整审核判断 | 保留R1实际90秒后完整恢复；R2-B同action context≤1及预算，R2-C真实native scope/read-only/context/90秒补齐 | pass |
| S5 等待可以延长但不会无限延长 | R2-B三次完整30/60/90与混合、action360s撤销、Retry-After15停止；真实默认预算仍由R1与R2-C支持，不把fakeclock说成供应商实等 | pass |

#### Requirement: 空白或非法判定仅获得共享额度内的一次恢复 — 组内结论：pass

| Scenario | 本轮与保留证据 / 实际结论 | 结果 |
|---|---|---|
| S6 首次格式失败后有效判定 | 保留R1 invalid→allow一次effect；R2-B格式子额度与R2-C当前parser/IM支持，R2-D实际最终deny不被重试 | pass |
| S7 再次格式失败或总额度先耗尽 | R2-B service→service→format、repeatedformat/EMPTY共享上限；R1/R2-C真IM格式耗尽保持技术不可用，不混作deny | pass |

#### Requirement: 技术恢复不改变授权、策略与最终拒绝 — 组内结论：pass

| Scenario | 本轮与保留证据 / 实际结论 | 结果 |
|---|---|---|
| S8 CC 两阶段与最终拒绝 | R2-C原生两阶段/有效deny计数与原升级，R2-B并发deny原子路由/trace一致；R2-D真实最终deny两阶段、0技术重试/未执行 | pass |
| S9 Codex 风险、授权与检查约束 | R2-C同冻结精确并发scope/source14/PA8/native只读及阻塞FS；R2-B context与冻结action/cache隔离，非宽泛parent归属；R2-D原生安装/工具实际审核 | pass |
| S10 有效拒绝与永久错误不作故障恢复 | R2-B AUTH/QUOTA/CONFIGURATION/INVALID_REQUEST无恢复；R2-C当前parser和401 IM，R2-D真实最终deny0重试，不换模型刷allow | pass |

#### Requirement: 主动取消优先于超时恢复 — 组内结论：pass

| Scenario | 本轮与保留证据 / 实际结论 | 结果 |
|---|---|---|
| S11 请求中或退避期间停止 | 保留R1-E3真IM stop后观察100秒以上无新请求/晚到effect；R2-B撤销/quarantine，R2-C同冻结真IM取消及owner cancel/disable/另一owner反证 | pass |
| S12 非主动取消的单次超时 | 保留真实默认30/60/90恢复；R2-B连续超时最多2、完整末次预算补齐，R2-C原生与全IM同版支持 | pass |

#### Requirement: 耗尽严格沿用既有模式与配置分流 — 组内结论：pass

| Scenario | 本轮与保留证据 / 实际结论 | 结果 |
|---|---|---|
| S13 有人值守聊天审核不可用 | R2-A两策略3次503→interactive_pending，原审批拒绝/0effect；无自动allow；R2-B写audit失败仍fail-closed | pass |
| S14 Global 与子任务审核不可用 | R2-A真实Inbox及实际child两策略return_to_agent/无卡/0effect，即使fallback allow也不扩权；Q625-R1-01关闭 | pass |
| S15 无人值守的 allow 与 deny 配置 | R2-A真实schedule/heartbeat×allow/deny×两策略：unattended配置allow一次/deny零次，非模型allow、配置未扩；无人工allow | pass |

#### Requirement: 审核恢复可追踪并以真实旅程验证 — 组内结论：pass

| Scenario | 本轮与保留证据 / 实际结论 | 结果 |
|---|---|---|
| S16 一次动作与再次工具调用可区分 | R2-A同reviewId三attempt/request ordinal/类别预算/unknown usage/route可查；R2-B并发deny domain一致与写失败不执行；R2-D新call/Work/实际sent相关联 | pass |
| S17 真实全局插件旅程与受控证据分别交付 | R2-D新daily两策略真实自建/安装/两次180+55/Work/实际sent成功；故障/预算/取消/有效deny/各模式证据由R2-A/B/C及保留R1分层交付，不用正常服务成功代替 | pass |

### 清理、交付与后续边界

R2-A临时栈均由driver finally正常down；16:40独立连接核对7个IM端口 `64029/64088/64192/64286/64453/64570/64714` 全部释放。Q本轮浏览器 session `q625-r2-codex-9cb` / `q625-r2-cc-9cb` 已close；无仍相关未收集后台job。旧/新本地原始证据保留，没有删他人进程或旧资料。未动共享4000、生产或用户主仓；E持有两套daily及新测试bundle生命周期，Q不擅停。

本轮报告只追加 acceptance.md，提交/推送自身 QA 分支，由原 E 整合到 unit 分支后保证报告可获取；不直接改 E unit。parent 已获无活跃 Q provider/fixture计时的 safe boundary。上层文档需否更新沿用R1清单，canonical/delta的实际归并与最终CI留由orchestrator验证，不以本产品pass冒充完成。若再改产品或替换构建，须重新判受影响范围，保留两轮历史证据。

## Round 3 — 2026-10-26，integrated-main targeted（同验收者、同现场）

> Validation snapshot: `85910853ebe4a7a22c5b761029cf46da2f78cd5a → dcb65a91793f12d199a9680ee49c5b687a55eeab`
> validated tree: `ff0b91de0be3a4923be8a877c37979b8d00ec367`；base 是候选祖先。
> R1/R2 原文完整保留；R2 的17 pass仍属于实际 fe623 冻结，不改签为本候选全量重跑。

### 文档用途与证据边界

本节为仓库最小脱敏产品验收摘要。完整原件仅在授权本地保留，未提交受限原始证据；报告远端可获取性需另外核实。完整原件供授权复核，摘要用于说明判据、实际观察、裁决及适用范围。R3-A/B/C 是逻辑证据编号，不是公开原始日志或定位链接。摘要不代替原件，不能由摘要推断已公开原始证据。

### Verdict 与保留范围

**pass — 本次集成 main 影响范围的定向产品复验通过。** 本轮4项 pass / 0 fail / 0 inconclusive；新增已证实产品缺陷=0，open issues_count=0，blocking=0，Highest Required Action=`pass`，needs_re_review=`no`（仅本冻结与所述范围）。R1证据缺口继续按R2关闭记录保留，不删除历史失败。

本轮仅补普通 delegated child 的身份、续问、目录与分流，以及真实 HOST 知识维护不进入普通模型管理目录、但保留可区分的 Work 发起位置与回溯入口。来源为正式R3交办、current《Agent capabilities》的子任务/维护目录边界，以及current《Agent Work》的“深入查看 subagent 工作”“主动委派和后台维护”“系统维护保留独立可回溯轨迹”。Q不兼静态/code review，不读实现定位根因。

相对fe623，受影响范围集中在启动集成、知识维护运行和轨迹关联；审批策略、输入来源、模型归属、前端及跨包产品契约的相关输入未变。Q核文件范围与公开契约，不套用工程PASS。R2表中S1–S13、S15的故障/预算/取消/既有模式控制，S16的原审批审计关联、S17的双插件180/55旅程均保留具体前轮证据与限制；没有重跑全套17项或双插件。本轮补S14的普通child身份/管理及S16的集成Work风险；**普通成功child不替代R2-A双策略耗尽路由**。S8/S10真实有效deny仍属fe623的CC观察，不声称本轮新执行deny。

本结论不是Ready PR、canonical/delta/C1、whole-backend、全仓CI、merge/deploy或设备结论，其他owner门禁不在此改判。本轮未重启服务/模拟崩溃，页面重开回看不扩称“重启恢复已实测”。

### 验证平台、版本与前置

- 复用同一独立Q工作现场，切换前保留R1/R2历史；本轮使用新准备的隔离测试环境，不声称沿用前轮运行会话。
- Q核对冻结提交、构建收据与实际运行装载关系；开始及末次独立校验受控文件、编译产物一致，服务进程未替换。配置补选前后使用同一实际对话和父执行，不将配置变化冒充版本切换或重跑历史。
- 采用专用测试身份，经真实IM用户消息、原生产品工具和Web页面完成；未直接提交运行时任务、伪造来源或强制启动维护。自动审核开启且没有跳过权限，也没有人工放行使测试变绿。
- Chromium桌面1440×1000，实际操作Chat、Agents/Sessions、Work与原生轨迹；无iOS/移动结论。本范围无must-match原型，Reference Artifacts Reviewed=N/A。

最初目录工具未被选择，模型如实报告能力缺失，未完成当时要求的两项目录查询。Q保留此缺前置历史，不伪造结果或改实现。普通child与自然维护结束后，由工程owner在安全窗口通过正式配置API仅补选`list_agents`，Q重新核对生效选择及其他行为字段不变，再执行剩余查询。持久化伴随正常的格式规范化，不声称配置文件字节只有一处变化；没有借此放宽审核或更改知识维护条件。该临时测试配置由工程owner持有清理责任，不提升为生产默认或未来常设前提。Q未修改受控配置。

### R3-A — 普通真实child、返回与同身份续问

真实用户任务要求先读虚构示例项目的说明、反馈与核对清单，再实际委派普通内部子任务运行一次Python求和，随后内部续问相同child；不访问网络/生产、不修改文件。Q独立读取完整分页Work与聊天结果，并在浏览器实际展开相关过程。

- 父执行真正调用原生`subagent`创建普通child，不是Workflow、HOST维护或只写计划。Q核对创建结果、后续消息及Work中的身份为同一个child。
- child初次执行仅一次bash，实际命令为 `python3 -c 'print(16+21+27)'`，原生/Work可见stdout `64\n`、exit0。模型文字因未拿到显式退出码而诚实称无法确认，Q按工具字段另核，不拿模型自述代替执行事实。
- 父通过内部`send_message`续问同一child，要求仅确认刚才stdout、不再运行工具；child第二回合0工具，实际答复64后跟换行。父正常收到两次完成结果，主执行没有手算或重跑计算代替child返回。
- 用户实际收到初次结果及续问确认；没有审批卡、权限拒绝或改身份绕行。Q点Work委派旁的child入口，右栏显示同一child的两个已完成回合，首个bash可展开；父原生委派及续问位置均标“普通·后台执行·已完成”并有真实回看入口。

### R3-B — 真实HOST维护与目录排除对照

上述正常旅程后，宿主自然触发一次技能知识维护并完成。Q没有伪造维护来源、直接调用维护引擎或刷触发。Q独立核对维护域记录与对应轨迹事实：这是同一父执行下的后台维护fork，而不是普通委派child；父关联、用途、执行起止范围及结束状态一致。

补选工具后，Q在同一真实聊天只要求按序查询`children`、`descendants`，不新建、停止或续问任何child，不运行bash或写知识。实际两次原生`list_agents`调用均Completed且无错误：

| 查询 | 实际返回与核对 |
|---|---|
| `scope=children` | 仅返回R3-A的普通child，标签为“执行隔离算术并返回stdout”，状态inactive；本scope未返回parent字段，未自行补写 |
| `scope=descendants` | 仅返回相同普通child，状态inactive，parent对应原父执行，depth=1；与真实创建、续问及Work一致 |

真实已完成的维护在两种管理目录中均未混入；不是“没有维护所以目录为空”的弱反证。用户实际收到两条原始查询结果与限制说明；公开摘要不重印其中运行标识。浏览器Agents侧栏只有原测试阵容，Sessions仅显示实际两个聊天，没有维护管理项。Sessions不是子执行目录，本报告不冒称其为`list_agents`页面版。

### R3-C — 回看体验与独立裁决

Work主原生轨迹在真实发起位置展示“发起·技能复盘 / fork·后台维护·已完成”。点击“查看本次执行”进入继承父上下文的维护范围；界面显示Main Agent→技能复盘的来源关系、明确的本次起止范围，范围外上下文淡化，维护输入及末行“Nothing to save.”可读。“返回发起点”实际返回父执行原位置。普通child的委派/续问标“普通”，没有与后台维护混名。

正式配置变更及完整页面重开后，仍能在Work选择同一次维护并回看，没有恢复执行。本次维护没有工具调用或知识落盘，不能凭空要求成功写入或通知。Work的Linked executions/当前执行同时保留普通child和维护，是受权限保护的**轨迹导航**而非模型管理目录；此处保留维护才满足可回溯。维护的普通聚合侧栏没有回合，但原生入口有完整继承历史与本次输入/输出，不能以空聚合回合误判无轨迹。

| 本轮必验项/来源 | 决定性实际证据 | 结果 |
|---|---|---|
| T1 普通委派身份、分流与同child续用；交办/current子任务契约（补S14集成风险） | R3-A真创建、一次bash得到64/exit0、同child续问0工具、父正常收到且用户实际收到结果；无维护替身或审批绕路 | pass |
| T2 children/descendants保留普通child并排除真实HOST维护；current目录边界 | R3-B同父真实维护已完成作对照；正式补选工具后两次原生完整返回仅含普通child，parent/depth一致；初始工具缺失历史保留 | pass |
| T3 管理页面不把维护当普通Agent/会话，仍可辨普通执行 | Agents侧栏为原阵容、Sessions两个真实聊天无维护；不把Work导航当管理目录，不杜撰child管理页 | pass |
| T4 独立维护可回溯，父子用途、范围与结束事实可辨；current Work契约（补S16集成风险） | R3-C实际从发起行进入维护范围并返回；正式配置后重开Work仍能回看，域关联与界面一致 | pass |

Q已实际阅读1440×1000关键画面：普通child的委派与bash结果、后台维护的原生轨迹、父发起位置、用户收到的目录结果、管理页面以及重新打开的维护轨迹。界面能区分父任务、普通child与后台维护并沿真实入口回看，未见阻碍本范围目标的整体阅读或操作问题；不是仅确认图片存在。受限画面及原始取证未作为远端附件公开。

### 清理与交付限制

实际模型执行结束、主执行idle；Q的后台取证已正常结束并收集成功，任务浏览器均已关闭，没有Q临时服务或fixture遗留。末次版本核对后已向主会话报告安全执行窗口结束；未停止工程owner管理的环境、共享或生产资源，未修改实现、测试、设计或受控配置。

完整验收原件仅在授权本地保留，不由本摘要覆盖；未提交受限原始证据。报告远端可获取性、unit整合及其他交付门禁需根据实际结果另外核实，不以摘要完成冒充交付完成。产品、构建或运行身份变化时需再判受影响范围；三轮实际版本、历史失败/缺前置及原件继续保留。
