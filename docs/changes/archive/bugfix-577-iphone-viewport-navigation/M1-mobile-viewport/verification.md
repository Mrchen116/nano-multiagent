# Verification Report: bugfix-577-iphone-viewport-navigation

## Round 1 — full（历史，最终结论见文末）

- reviewer: `/root/review_577_static`，独立，未参与实现；此前 code review 已完成，本轮不重复。
- verification_mode: `full`，同次核对 `corrected-delta`。
- branch: `codex/bugfix-577-iphone-viewport-navigation`
- executed_base: `1daf6676debe129088d9bd0612b489d1eba0301a`
- validated_at: `e6b202cb87c4deb4e9f9763d5c78e59d28576dba`；现场 HEAD 已独立核实一致。
- 范围: 全部 incident Requirement/Scenario、design 决策、M1 R1–R4/W1–W3、delta、相关 current specs 与架构/测试规范。
- requires_full_verification: `false`；本轮已按 full 核对，不是轻量复验。
- 状态: **未通过，待收口**。静态核对没有新增缺陷，但 caller 转交的独立真机观察证明 R3 未满足；收到固定修复版本及完整 regression 后再更新最终 verdict。

### Summary

| 维度 | 结果 |
|---|---|
| Completeness | W1 已有证据；R1/R2/R4/W2 部分证据已到，等待完整 regression；R3 未完成，W3 门禁待关闭 |
| Correctness | 两项 delta 均有实现；真机镜像硬件输入辅助条场景出现实际偏离（实体软件键盘未测），不能据静态实现判全部 covered |
| Coherence | 5 项 design 决策遵守，架构和测试责任未迁移 |

### Completeness

本 unit 是单 M1，没有独立 tasks.md，使用 design 的退出标准和 progress 交接。未以测试数量替代用户旅程。

| 退出标准 | 实际证据与边界 | 当前状态 |
|---|---|---|
| R1 登录/搜索/聊天输入及跨页比例 | progress 记录 Safari 登录聚焦/结束输入无额外放大；caller 转交产品 reviewer 主屏登录及搜索无裁切；完整跨页矩阵待 regression | 待完整证据 |
| R2 未登录安装、登录、四入口、详情刷新/重新打开 | caller 转交 HTTPS 未登录安装→登录→四入口无系统栏；刷新/再次启动等由产品 reviewer 继续记录 | 待完整证据 |
| R3 真机软件键盘开关、返回、草稿、输入/发送 | caller 转交独立实际发现：standalone composer 经镜像硬件输入聚焦粘贴两行、出现iOS输入辅助条后 header 上移并与状态栏重叠，输入/发送仍完整 | **未通过** |
| R4 Safari 浏览器栏、375/430/600px、桌面1440px | progress 有 375×812、430×430、600×960 真实浏览器渲染/测量摘要；完整 Safari 和桌面证据等待 regression | 待完整证据 |
| W1 focused tests/build、manifest HTTP、字号/viewport | progress 的 8 frontend/6 HTTP tests、build 及真实 HTTP manifest 证据；直接核读实现和测试，完整前端最终日志807 passed | covered |
| W2 must-match 对照、设备/构建记录 | progress 有浏览器截图及构建资产定位；不把镜像硬件输入冒充软键盘，真机最终报告未完成 | 待 regression |
| W3 final tests、CI等价、独立review/verifier | full code review `[]` 已归档；Python4119/front807/build/Ruff/docs检查有可信结果；verifier及产品问题尚未关闭 | 待收口 |

复用可信测试：`PYTHONPATH=src <main>/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal -q` 4119 passed；`npm run test -- --maxWorkers=2` 最终86 files/807 passed/102.73s（独立读取 `output/bugfix-577/frontend-final.log` 结尾）；窄测试和构建命令/结果见 progress。首轮806 passed/1 timeout及独立文件20 passed与最终全量重跑分别记录，不将首轮描述为全绿。全仓Ruff/docs与build结果复用 caller/progress；本轮未重复全量测试、未启动服务、未操作手机或浏览器。

### Correctness

| Requirement / Scenario | 实现位置 | 回归保护/直接证据 | 状态 |
|---|---|---|---|
| delta：输入聚焦后保持比例，结束输入并跨页可用，镜像对齐及主动缩放 | `src/IM/frontend/src/styles/global.css:5594` 手机16px同时覆盖textarea与mirror；`hooks/use-mobile-viewport.ts:12` scale门控 | `app/providers.test.tsx:23,40,54` 覆盖焦点/resize/blur/卸载、桌面、主动缩放及无VisualViewport；progress computed font均16px | 静态 aligned，产品矩阵待齐 |
| delta：浏览器栏/键盘变化下标题返回、输入发送可用，恢复高度，列表安全区和详情隐藏底栏 | `global.css:6,72,76,85,90,5599` 高度/安全区；`hooks/use-mobile-viewport.ts:18` 生命周期；`app/shell/app-shell.tsx` 原有详情隐藏导航 | providers lifecycle tests和既有shell tests；真机header偏移直接反例由caller转交 | **implementation-mismatch（R3）** |
| delta：未登录入口安装、登录、四入口/详情站内导航，保留登录目标 | `public/manifest.webmanifest:2` id/start_url/scope `/`、standalone；`index.html:7`；`src/IM/app.py:216` JSON静态分发；router/auth unchanged | `tests/im_service/unit/test_app_factory.py:157` shell/manifest真实HTTP seam；caller主屏安装及登录四入口实际观察 | 静态 aligned，产品矩阵待齐 |
| delta：已登录再次启动、详情刷新及返回，登录/路由语义保持 | manifest根入口复用 `app/router.tsx` RequireAuth/index Navigate；登录return-to代码未改 | auth/router及完整前端套件保持；设备再次启动/刷新待regression | 静态 aligned，产品矩阵待齐 |
| incident：普通Safari及桌面既有体验保持 | CSS默认100dvh/100vh fallback；16px及safe-area限定767px；hook桌面不覆盖 | providers desktop test，既有shell/auth/composer/draft/history测试在807全量通过；实际Safari/桌面矩阵待regression | 待完整证据 |

current `docs/specs/im/auth-tenancy.md` 的认证协议、自然单列与纵向主操作可达没有被替换；认证页仍有独立纵向滚动，header安全区纳入最小高度。current `web-chat-ux.md` 的composer自动增高、消息历史、按会话草稿及真实anchor行为代码未修改，现有测试保留。没有主动缩放限制或认证fallback。

### Coherence

| design 决策 | 遵守 | 代码证据 |
|---|---|---|
| 1 整站manifest，沿用名称/favicon，根路由分流及深链 | 是 | manifest/index及IM窄静态路由；router/login unchanged |
| 2 手机至少16px，mirror相同metrics，允许主动缩放 | 是 | `global.css:5594` 同一规则；既有textarea/mirror padding/font/line-height/wrapping未分别改写；viewport meta无禁缩放 |
| 3 统一100dvh，100vh基线，布局容器负责safe-area | 是 | `global.css:6,72,76,85,90,451,4928,5599`；移除chat header重复top inset，保留composerbottom inset及认证滚动 |
| 4 AppProviders单hook，仅移动编辑scale≈1覆盖，失焦/卸载清理 | 是 | `main.tsx` 包含全部auth/protected路由的Providers；`providers.tsx:9`；`hooks/use-mobile-viewport.ts:4` 全部监听及清理对应。真实offset问题仍须按证据修复，design已允许该路径 |
| 5 与原生iOS App独立 | 是 | diff没有原生客户端、签名、推送或PA/Gateway/agent变更 |

架构核对：`SPEC.md:148` 的IM与agent/PA/CLI依赖红线未改变；改动仅IM静态分发/前端，无跨包import、REST/WS业务schema或数据库变化。IM manifest handler沿用现有dist候选与FileResponse，未新增通用文件服务器、缓存框架或Service Worker。

测试规范核对：扩展已有app-factory HTTP seam，manifest JSON/MIME可观察，不按私有解析函数或实现调用次数断言；新增providers测试有新的viewport到CSS生命周期owner，直接挂载真实AppProviders并驱动浏览器事件，CSS变量是设计显式公开的布局seam。保留既有AppShell覆盖，无重复新建shell tests、流水号测试或一次性E2E脚本进永久套件。真实iOS CSS/native机制交产品reviewer，不误以jsdom证明。

### Prototype / Reference Contract

verifier只核显式契约与证据链，不替代产品reviewer的视觉判断。

| must-match | M1投影 | 实现证据 | durable evidence | 状态 |
|---|---|---|---|---|
| 登录字段/提交，375/430/600及短高可滚动 | R1/W2 | 全站编辑16px、认证独立滚动、同源高度 | progress 浏览器尺寸/观察/构建资产；完整regression待写 | 待齐 |
| 列表四入口、安全区 | R2/W2 | shell顶部inset、底栏固定安全高度且不缩 | progress及caller转交主屏四入口观察 | 待完整regression |
| 详情返回/输入发送，无全局底栏 | R3/W2 | AppShell原语义、hook同步height、composer保留safe-area | progress短视口草稿；真机header重叠反例 | **未通过** |

### Issues

#### CRITICAL

- **R3 未满足，暂不允许full pass。** 契约：`specs/im/web-chat-ux.md` 的“可用高度随浏览器栏和键盘变化”及 `design.md` M1 R3；实现路径：`src/IM/frontend/src/hooks/use-mobile-viewport.ts:13` 只发布height，`global.css:5599` shell顶部安全区。caller转交独立产品reviewer发现：真实iPhone standalone经镜像硬件输入聚焦composer并粘贴两行、出现iOS输入辅助条后，header上移与状态栏重叠；输入/发送可见不抵消标题返回要求。建议按该实际offset证据修复，冻结新版本，再让产品reviewer复验软键盘开关、标题返回、草稿及跨页恢复；把完整设备/操作/构建/证据定位写入regression后由verifier核对。此复现不含实体软件键盘证据；该条是已观察未完成退出标准，不以静态推测认定某个具体offset补偿算法。

#### WARNING

- 无静态偏离；完整产品矩阵证据尚在交接中，保持待收口状态。

#### SUGGESTION

- 无。

## Round 2 — targeted-closure（历史，最终结论见文末）

- reviewer: `/root/review_577_static`；未参与修复。
- verification_mode: `targeted-closure`；同次继续 `corrected-delta`。
- executed_base: `1daf6676debe129088d9bd0612b489d1eba0301a`
- validated_at: `bd170820be5f17f17093189d36290c377b0463ff`；HEAD已独立核实一致。
- fix_delta_range: `e6b202cb87c4deb4e9f9763d5c78e59d28576dba..bd170820be5f17f17093189d36290c377b0463ff`
- focus: 产品Round1 I1 / verifier Round1标题返回偏移问题及批准的design offset修订；产品I2缺口仍有效。
- prior_verification: 本文件Round1；未受影响的manifest、字号、架构/测试责任核对保留。
- requires_full_verification: `false`；offset变更有界，未扩大共享边界或破坏此前静态结论。
- 当前 verdict: **pending**。patch code review `[]`、静态closure aligned；完整产品复验及最终前端检查未交接，不标full pass。

### 问题闭环与实现证据

| Focus | 冻结版本证据 | 状态 |
|---|---|---|
| I1 / header因编辑平移侵入状态栏 | `hooks/use-mobile-viewport.ts:15` 发布实际offsetTop；`global.css:5595` mobile根容器relative top；scroll监听已有；聚焦、缩放/桌面/blur和卸载与height同步清理 | 静态fix覆盖；独立产品Round2尚待 |
| design第4决定有界修订 | 单hook/CSS职责不变，无68px常量、强制scrollTo、全局touch禁用、根fixed或transform；design-review Round2 Approved 0/0，已读受审差异及author摘要同步 | aligned |
| 回归保护 | `app/providers.test.tsx:31` 同一最低层测试驱动offsetTop=68及scroll、观察CSS offset=68px、blur清除；其余焦点/桌面/scale/无VisualViewport保护保留；caller提供1项红测及修后providers+shell 8passed/build | aligned，复用可信结果 |
| I2 / 实体软件键盘与主动缩放等设备必验缺口 | 仍由产品reviewer负责；caller冷启及聚焦观察只作补充，不能代替独立regression | 未关闭 |

Round1描述已更正：实际反例是镜像硬件输入触发的iOS输入辅助条与自动平移，实体软件键盘当时未测。verifier此前final摘要把它称为软键盘不准确，以regression Round1 I1及本次更正为准。

### Corrected-delta静态补查

消费者delta文件没有变更；新增offset只落实原“标题返回、输入与发送保持可见”要求，没有新增业务/路由/认证或独立对外行为。统一height/offset临时覆盖由批准设计描述，providers CSS seam测试保护；当前静态实现和最终测试方向aligned。唯一Corrected Delta Reconciliation段暂保留其标注的Round1快照结果，收到Round2产品证据后更新为当前快照最终outcome，不提前把产品未验场景标通过。

## Round 3 — delta / targeted-closure（实体确认前记录，最终结论见下节）

- reviewer: `/root/review_577_static`，独立；仅写本报告及code-review，未改受审源码/测试/设计，未操作UI或服务。
- verification_mode: `delta` / `targeted-closure`；同次 `corrected-delta`。
- executed_base: `76fe1d7e7c2a4d07da06453fd2b4658749bb6f87`
- validated_at: `fbb77fe83e1132c57b9ad9af4c8a5a0ffbb4f162`；HEAD已独立核实一致。
- fix_delta_range: `71c6ec84c1df79a3d3dcd38b039d0fac800aa99f..fbb77fe83e1132c57b9ad9af4c8a5a0ffbb4f162`
- focus: 用户实体IMG_9428.PNG反馈的白带/手机换行发送语义、相应incident/design/M1与delta，以及旧I1/I2关联闭环。
- retained_from: Round1全范围静态验证，Round2 offset修复核对；新增main仅独立feat-578文档，对577/source/tests旧结论无影响。旧手机Enter发送不再作为保留约束，由用户新决定和明确REMOVED退役。
- requires_full_verification: `false`。消费者输入语义变化已按批准的full design覆盖，但实现/验证delta仍仅MessagePane输入事件与原viewport/CSS生命周期；无跨包、消息传输或草稿模型扩展。旧full范围结论可保留，新增行为在本轮完整核对。
- 当前full verdict: **pending**，不可提作产品门禁通过。静态代码/契约无新偏离；R3实体软件键盘、中文IME与缩放同版本复查尚未交接，最终front全量已由caller完成，独立读取日志确认86 files/808 passed/145.72s。

### Completeness / Correctness / Coherence

| 范围 | 契约 / 决策 | 代码与测试证据 | 结论 |
|---|---|---|---|
| 手机Enter换行、草稿保留、按钮多行发送 | incident新增手机键盘需求、design第6决定、delta新增手机换行Requirement、M1 R3 | `message-pane.tsx:663` 手机Enter最前stopPropagation/return；不preventDefault/commit；`message-pane.test.tsx:610` 真textarea原生多行后按钮onSend完整草稿 | aligned，实体IME未代验 |
| 手机slash/mention候选不抢Enter，候选点击仍可用 | 同上明确包括候选前缀 | 本地slash分支被手机Enter提前避开；mention/slash `window.addEventListener("keydown")`均冒泡阶段；两项手机候选Enter测试；现有pointer选择回调未变 | aligned；设备候选点击/中文确认需产品/用户证据 |
| 桌面Enter、Shift+Enter、候选及IME保持 | incident桌面Scenario；delta MODIFIED完整条目 | 手机条件为false时原handler原样执行；已有桌面快捷键、组合输入和picker测试保留 | aligned |
| 键盘/辅助条收缩时只移除重复Home安全区 | design第5决定；delta新增安全区Scenario | `hooks/use-mobile-viewport.ts:17`实际vv与documentElement.clientHeight比较，容差1px；`global.css:5558`变量fallback为原env；正常9.6pxdropzone内边距未改 | aligned，实际软件键盘画面待齐 |
| 键盘收起但焦点仍在恢复 | delta明确不要求失焦；M1 R3 | providers `:39`保持焦点令vv从420恢复780，触发resize并观察安全区覆盖清除；hook其他条件及卸载同清理 | aligned |
| 原header offset问题 | 旧I1与手机可视区域要求 | offset hook及mobile root relative top未改；独立regression Round2已确认聚焦、多行、返回、草稿等I1 resolved | closed（原已测硬件辅助条路径）；新增实体状态仍待R3 |
| 实体软件键盘与手动缩放 | 原I2和更新后M1 R3，incident要求不得镜像代验 | 用户原图/反馈证明修前问题，不能证明修后pass；独立产品Round3进行中 | 未关闭，full pending |

复用证据：progress列出的红4fail/93pass、绿97targeted tests/build及assets `index-DXqgLd_B.js` / `index-C9hmrQPD.css`；设计Round3 full Approved0/0并独立实走原型多行→箭头发送。源码未改Python/manifest服务，4119passed仍适用，不因新SHA重跑无效重复全量。独立读取`output/bugfix-577/input-r3-full.log`末尾：最终单worker全量86 files/808 passed/145.72s，与caller新增progress一致。

测试规范：替换既有两项旧输入语义测试并补同owner的mention冒泡风险；既有viewport-to-CSS seam扩展同生命周期恢复证据，无重复文件、隐藏失败或永久一次性脚本。当前仅布局与事件变化，无SPEC跨包依赖/REST/WS/数据库变化。

### Prototype / Reference evidence

原型新增Enter原生多行与箭头发送已在design-review Round3通过独立真实Chrome操作复查；未变的登录/列表/375/430/600/1440布局沿用原证据。本轮explicit must-match增加键盘期正常内边距及多行发送，投影M1 R3/W1/W2，由MessagePane/viewport实现与97窄测试承担低层证据，产品Round3及用户实体同版本复查承担真实画面/输入法证据。verifier不以原型或镜像辅助条代软件键盘。

### Current issues / actions

- CRITICAL：**1个未完成退出条件（I2）**。契约位置为incident实体输入要求及design M1 R3；需要独立产品Round3和同构建实体软件键盘/中文候选确认/收起恢复/手动缩放证据，不能以jsdom或修前用户截图关闭。待caller转交结果再更新最终full verdict；该项是验收缺口，不是新增已确认代码缺陷。
- WARNING：0。
- SUGGESTION：0。

## 最终 Full Verdict — 同版实体确认收口

- verdict: **pass**；CRITICAL **0** / WARNING **0** / SUGGESTION **0**。
- requires_full_verification: `false`；无需新的实现或复审轮次。
- executed_base: `76fe1d7e7c2a4d07da06453fd2b4658749bb6f87`
- validated_at（产品源码）: `fbb77fe83e1132c57b9ad9af4c8a5a0ffbb4f162`
- report/document HEAD: `cbb4d4af881377d50644b0fdcbcae80d3acec6fd`。独立执行`git diff --stat fbb77fe83e..HEAD -- src tests`为空；后续仅文档未使源码/测试审查及808passed失效。
- effective_base: 上述executed_base；effective_through: 上述document HEAD。原始各轮固定快照保留，未改写其当时结论。
- final evidence: `regression.md`“最终 Verdict — 用户实体复查收口”；已独立读取完整最终更新及此前Round1–3相关证据。没有重跑UI或测试。

### 最终完成度与证据链

| 退出标准 | 有效最终证据 | 判定 |
|---|---|---|
| R1 输入比例、搜索/跨页、镜像和主动缩放 | 产品Round1登录/搜索宽度及桌面窄屏；Round2群mention token、群设置/Tasks往返；用户同构建实体两行中文及双指缩放恢复确认 | covered |
| R2 未登录安装、登录、四入口、重新启动/刷新 | 产品Round1未登录HTTPS安装→登录→四入口；Round2真正主屏冷启、登录保持及Safari实际刷新/返回；manifest/路由未受R3改动影响 | covered |
| R3 标题返回、草稿、软件键盘/正常留白与恢复、新换行/箭头发送 | Round2/3独立镜像I1已消除；Round3真实硬件Return、普通/mention/slash前缀换行、箭头发送多行及Agent OK、草稿往返和间距对比；用户实体确认补齐中文输入/软件键盘/白带/候选点击/收起恢复 | covered |
| R4 Safari系统栏和原桌面/375/430/600体验 | 原完整真实浏览器辅助矩阵及草稿收发；Round2Safari刷新/输入恢复；R3未改桌面路径，既有回归保护在808套件中通过；实体缩放恢复确认 | covered（明确保留未受影响证据） |
| W1 focused/build/manifest接线、字体和viewport | 红测后97targeted passed/build、新assets加载；808最终前端全量；4119Python及manifest真实HTTP、16px、height/offset/gap测量记录 | covered |
| W2 must-match和设备/构建记录 | design-review与产品review独立原生Chrome实际多行→发送/正常内边距对照，原移动布局/导航对照；iPhone15ProMax/iOS26.4，最终assets与隔离URL明确 | covered |
| W3 窄/相关CI等价、review/verifier闭环 | 独立full+两次patch code review均[]；当前静态full/delta闭环；808前端/4119Python/build/Ruff/docs证据，产品最终pass | covered，可进入PR；远端CI随后由caller跟进 |

### 历史问题最终状态

| Issue | 结论及证据边界 |
|---|---|
| I1 / 标题状态栏重叠 | **closed**。Round2/3独立产品镜像实测标题/Back保持，offset实现与测试均核对；不把最初辅助条反例称为软件键盘实测 |
| I2 / 实体键盘与缩放缺口 | **closed — user accepted**。caller转交用户对上一轮同版实体清单直接回复“没问题，提pr了吗”；清单涵盖中文两行换行/箭头发送、白带、slash点击、收键盘与双指缩放恢复。此为用户实体确认，verifier及产品reviewer均未亲测实体输入法，也不扩写成逐项测量日志 |
| I3 / 镜像slash点击未填入 | **解除产品阻塞，保留测试通道差异**。用户实体确认点击可填入，当前实现的指针选择路径未改；镜像失败原始记录保留，根因未确证，不将额外mousedown/(-1,-1)线索写成因果或声称通道已修复 |
| Create group附带观察 | 非本unit已确证回归，继续由owner单列处理；不因API fixture建群宣称该入口已验收 |

独立reviewer最终`regression.md`给出pass、needs_re_review=false，以用户确认补齐最后的实体证据；这与当前静态实现/测试和批准设计一致。此前full pending及CRITICAL是当时证据状态，现已被此最终结论替代。保留各轮原始失败和矩阵边界，没有宣称全矩阵在最终SHA机械重跑或穷举所有设备/输入法。

**All checks passed. Ready for PR.** 本结论不等于已创建/合并/部署；机械current delta归并与归档由caller随后执行。

## Corrected Delta Reconciliation

- snapshot: `76fe1d7e7c2a4d07da06453fd2b4658749bb6f87 → fbb77fe83e1132c57b9ad9af4c8a5a0ffbb4f162`
- 独立核对全部最新delta与最终静态实现/测试，并检查完整unit diff遗漏的对外行为。当前实体证据已按上述最终结论收口，corrected-delta与final full verdict均有效；后续current归并应机械保留已审完整条目。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| ADDED手机输入比例、镜像、主动缩放与可用高度 | 手机16px、统一dvh/height、scale门控、实际offset与安全区生命周期 | providers/Shell及既有布局；regression Round2 I1已closed；用户同版实体软件键盘/缩放确认，来源与范围见regression最终节 | aligned |
| ADDED主屏登录/站内导航、再启动刷新 | manifest整站id/start/scope、standalone及IM JSON分发，auth/router unchanged | HTTP factory tests；regression Round1/2新安装/四入口/再启动/Safari刷新记录 | aligned |
| ADDED手机多行/按钮发送/候选不抢Enter | 手机keydown最前stopPropagation+原生编辑，enterKeyHint；按钮原submit/commit | message-pane测试手机普通/slash/mention Enter与多行按钮发送；实体中文多行输入已由用户同版确认，非reviewer亲测 | aligned |
| ADDED编辑期不重复安全区，收起且有焦点也恢复 | vv.height < documentElement.clientHeight-1时safe-bottom=0；恢复及其他生命周期移除；CSS env默认 | providers既有生命周期测试含收缩/有焦点恢复 | aligned |
| REMOVED旧“Web IM 移动端输入法回车发送消息” | 不再手机Enter commit；明确用户新意图，未静默改spec掩盖旧问题 | 旧发送测试按新意图改为多行/按钮，发送仍完整 | aligned |
| MODIFIED桌面/移动共同体验完整替换 | 桌面旧快捷键，手机新换行/按钮发送；历史分页、增长、复制/fork均未改 | 三个旧Scenario（手机分页、长按fork、相同消息动作资格）完整保留；既有相应测试保留 | aligned |

### Uncovered Observable Behavior

None。移动候选Enter行为、composer键盘期安全区与无失焦恢复均明确进入新delta；原manifest/字号/offset行为由原手机可用性条目覆盖。旧current另一条共同体验里的“相同Enter发送”已通过完整MODIFIED替换消除冲突，三个无关原Scenario未丢失。enterKeyHint是新输入语义提示，不另造模式或协议；桌面未改。

Outcome: **aligned**。无遗漏对外行为；full门禁最终pass，0 CRITICAL / 0 WARNING。
