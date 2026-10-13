# feat-584 — 产品验收报告

## Round 1 — Full，2026-10-13

> 对齐：[spec.md](spec.md) 全部 26 个 Scenario、[design.md](design.md) R1–R5 / P1–P5。
>
> Validation snapshot: `a3b2c8aa5a7e8aa23d0b57c2adb0289ccd5a541d → 51ce5e396855ca35b2c70237cf339e5b5f834aa2`。
>
> 受审后 HEAD 增加的 `code-review.md` / `verification.md` 不改变受审代码。独立 reviewer 未修改实现，未将作者成功叙述作为结论。

### Verdict

**fail**。两个原生交互 major 阻塞 P2/P4。旧库迁移及换装后的原生 P3/P5 已在本轮收敛前补验。不能因为 Web 和 Agent 路径可用而认定三端一致。

功能结果：Web 的层级、创建/编辑、跨层筛选、权限与删除已可完成；真实 PA/DSH 的通知处理已观察到。原生常规查看/创建/领取及历史读取可用，但私密建群与并发恢复有阻塞。

视觉组织：桌面根总览及五组外框、直属层范围、覆盖式详情与窄屏纵向分组符合原型主结构。原生使用 SwiftUI 分组与 sheet，可辨认父级路径和直属完成数量。没有把完成记录数表现成工作量百分比。

交互成本：Web 详情与进入子层分开，返回后保持当前层；负责人查询明确标记跨层。原生遇并发冲突时被卡在禁用 Save 的表单，缺少可完成的恢复步骤；建群可见范围点击产生相反结果，不能接受。

### 环境与版本边界

- 专用 checkout：`/Users/czj/.codex/worktrees/unit-feat-584/nano-multiagent`，分支 `codex/feat-584-task-progress-permissions`；IM `127.0.0.1:58435`、Web `127.0.0.1:58436`，隔离运行目录 `/tmp/nano-feat584-e2e`。
- 测试真人为 Test User（公司管理员）与 Web 584 Guest（普通成员）；Agent 为 e2e（single_thread/always）、e2e-peer（single_thread/mention_only）、e2e-global（global/mention_only），另建 mention_only observer。全部是专用测试群、测试任务。
- 原生为 iPhone 17 / iOS 26.4 Simulator `7CB77F12-2282-4AA0-BCC9-D368A4DD1122` 上的 SwiftUI App，不是 Web 容器；不是物理设备证明。
- 初始已安装 App 与交接构建不一致。发现差异后安装 `/tmp/feat584-ios/Build/Products/Debug-iphonesimulator/NanoIM.app` 并重新启动，两个候选问题以及根总览、15 项直属层、3 项深层、历史结果、新建根/领取均重新观察。**旧安装包结果不作为两个 finding 的最终证据。**
- 换装后安装目录 `0151189C-5A0C-4B8D-9F21-2B503EE0D21A/NanoIM.app` 与交接包哈希一致：`NanoIM` SHA256 `c185a8b463406892b12886bbe10c2dfad880c6dd9c5cd8a49671266d3170348a`，`NanoIM.debug.dylib` SHA256 `419643c31c90e21b1576a525867fa1523e42b55e8817043ef3cca35afc785dba`。
- 为离线场景仅停止专用 Node，恢复为 PID `25659`，已更新 `.gateway.pid`；IM/Vite/专用模拟器交回主 Agent 清理。未操作生产。

### 用户旅程与证据

**J1 分层浏览与跨层筛选。** Web 根总览不自动进入第一棵树；`tg_8cdd0fed` 有 15 个直属任务，第二层有 3 个后代。实际切换 Progress/Internal structure、详情及面包屑，直属层没有混入深层。Web 1440、1024、390 宽度均实看；详情覆盖主区。原生换装后同图依次显示直属 To do 5 / In progress 3 / In review 3 / Done 2 / Closed 2（Paused 留在 To do），进入“验证原生 iOS 状态筛选及长内容显示 12”后显示 1 todo / 1 doing / 1 done。负责人视图含根与深层，补群名/父路径。换装后原生选择 By assignee · all levels → Test User，实际包含多个根与深层验证任务1/2/3；点击深层任务1的 Open parent scope，打开该节点详情，关闭后正位于发布任务→验证原生 iOS 状态筛选及长内容显示12的三项直属层。探索图 `tg_2b8330f4` 的 closed 方向单独保留，done=0；进入 pending 方向 n3 显示两个 Plan 子节点，未选方向未自动变成执行任务。

**J2 真人和 Agent 维护。** Web 自建 `tg_d0448fb7`，操作子任务领取、结果、in_review、直接 done、改派；Web 冲突保留草稿并在明确读取最新后重试。真实 Agent 创建 `tg_fa2658e3`，creator=e2e，n2 分给 e2e-peer，n3 分给真人，n4 未分配；改派后 creator 不变。Global 通过 conversations 自行加入公开 `c_vw3v3x57`，创建/领取 `tg_724740db` 并提交 `GLOBAL_REVIEW584_OK` 为 in_review，真实 Work 记录含相应工具结果；私密图读取被拒绝。换装后的原生创建标题 `584777` 的根任务，创建者 Test User、未分配/todo；点击 Claim 后负责人 Test User、状态 doing，Web/服务读取同一事实。原生并发失败见 F2。

**J3 会话权限、固定归属和删除。** 测试公开群 `c_y71t0r92` 的访客可读 `tg_e40f8eef`，读取未自动加入；写入拒绝，加入后可领取，creator 仍为原创建者，普通负责人删除拒绝。普通群创建者不能切范围。管理员非成员对 `c_maex5oyq` / `tg_c71f8ae1` 读、删、自助加入、改范围均被拒绝；另建 Guest 与 e2e-peer 的私聊任务 `tg_766ed09e`，管理员虽然管理该 Agent，仍读不到任务。Web 访客 UI 提供 Join，加入后出现群操作。已入群管理员双向范围切换保留成员与内容。Global 从 B 群用工具更新 A 群 `tg_fa2658e3/n4` 描述为 `CROSS_GROUP_REVIEW584`，conversation_id 保持 `c_cr331zjv`。

独立新建 `tg_a67b6a60` 的根由 Test User 创建、后代 n2 由 Guest 创建且负责；Web 删除确认明确“2 tasks including other members’ work”，确认后回总览，原图查询 404，没有逐个请求后代创建者审批。此项只删除明确 disposable 图。

**J4 解散历史。** `c_y71t0r92` 解散前 root doing，Guest 子项 n2 done/result=`PRESERVED_RESULT`，n3 in_review。解散后 root/n3 closed，n2 done/result 保留；Web 显示 Dissolved group · read-only history，无可写按钮。换装后原生 Tasks 仍可进入该图，n2 详情显示 Creator=Guest、Dissolved history、Read-only history、Done 和完整 `PRESERVED_RESULT`，无编辑/领取/删除操作。

**J5 通知与真实执行。** 专用群 `c_ak9hqekq` / 图 `tg_4a9b49de`，真人先明确授权测试 Agent 对该群后续通知简短确认，未授权通知本身修改或删除任务。下面时间为 UTC，可在专用群及 Global Work 中复核；原始无凭证响应保留在 `/tmp/review584-notifications-final.json`、`/tmp/review584-global-final-work.json`，不提交运行日志。

| 操作 | 实际产品结果 |
|---|---|
| 15:59:32 首次分配 root 给 peer | 一条系统消息 `1270991b…` 有有效 @peer；peer 自主回复已收到，always e2e 也处理，未 @ observer 不运行；root 仍 todo。 |
| 16:00:03 peer→global 改派 | 一条 `cc1647ac…` 同时有效 @原/新负责人；两者及 always 接收，observer 没有被该消息触发。 |
| 16:01:25 忙碌时分配 n2/n3 | Global 正在执行七图只读核对；16:02:32 完成既有核对，16:02:40 自主明确回复收到 BUSY global notice。single_thread peer 的旧回复被复核，随后新轮处理通知；未另开冲突执行。 |
| 16:03:26 Node 离线时分配 n4/n5 | 系统消息先保留；Node 恢复后 16:03:28 peer、16:03:50 global 自主回复各自 OFFLINE 任务，无真人再次发话。 |
| 16:07:32 `/stop`，随后 16:07:34 分配 n6/n7 | Global Work turn 9 状态 interrupted；新通知触发 turn 10。peer 16:07:34 回复 AFTER STOP peer；global 16:09:34 回复 AFTER STOP global。无持久停止位。 |
| 三层 n1→n2→n8，n8=observer；暂缓 n1 | `3f7f3ec5…` 只 @直属已分配 peer/global，未 @深层 observer；n1 paused，n2–n8 状态保持。n8 本次首次分配的独立消息合法 @observer，与父暂停消息区分。 |
| n3 提交 in_review/result | `d5e0122b…` 一条消息 @创建者 Test User 与父负责人 global，链接定位 n3；root 保持 paused，结果在任务详情中读取。 |
| 取消 n4 分配 | `d955e27c…` 一条消息 @原负责人 peer；没有重复私信或额外交接回执。 |

消息实物为轻量事件，带真实修改者、任务链接和有效 @，没有重复“任务动态”标题或结果展开控件。分配事实与 doing 明确分开。单轮模型偶有 task_graph 参数错误，记录为模型执行轨迹，不据此宣称工具完成；涉及创建/加入/跨群写入的结论均以成功工具结果与最终任务事实交叉核对。

**J6 独立旧库迁移。** 收敛前 caller 交接 schema1 测试快照 `/tmp/feat584-migration-aYUtCQ/backup.sqlite` 与原始造数记录 `/tmp/feat584-migration-check.ts`。reviewer 仅复制至 `/tmp/review584-migration/old.sqlite`，独立执行 guidance 的 CLI dry-run→填写有据映射→dry-run→apply→verify。先得到 requires_mapping，填入图tg_old所属c、n1/n2创建者user:u（不是latest modifier）、未分配后得到 mapping_valid；apply报告1图2节点，verify报告verified。独立读库对照：ID/revision3/层级/description=retain/result=original result均保留，n1仍todo，n2 dropped→closed，群c=private，created_by=u、assignee=null，messages和relay_tasks仍0。重复apply明确拒绝覆盖v2；将备份复制恢复后schema1且哈希与备份完全相同。该样本不含非空依赖/探索边，不能冒称生产数据迁移已经完成。

换装后的原生 P5 补验：打开 notification laboratory 的提交待确认系统消息，点击任务文字后实际进入 n3 详情，显示 In review、Creator=Test User、Assignee=E2E Global、完整结果 `REVIEW584_PARENT_NOTIFY_RESULT`；所属群保持不变，见原生回链结果（历史图片 `acceptance-r1-ios-notice-result.png`，按用户要求不随 Git 交付）。

### Reference Artifacts Reviewed

已读取并实际打开 [prototype.html](prototype.html)，逐项对照 design 原型契约。下列截图均来自实际客户端，不用 prototype 代替验收。

| Reference / required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|
| P1 根总览、框线五组、直属计数、逐层导航、覆盖详情 | 根总览（历史图片 `acceptance-r1-web-overview.png`，按用户要求不随 Git 交付）、1024（历史图片 `acceptance-r1-web-1024.png`，按用户要求不随 Git 交付）、390（历史图片 `acceptance-r1-web-390.png`，按用户要求不随 Git 交付）、原生深层（历史图片 `acceptance-r1-ios-layer.png`，按用户要求不随 Git 交付）、探索（历史图片 `acceptance-r1-web-exploration.png`，按用户要求不随 Git 交付） | Web 1440/1024/390；原生 402 pt、1206×2622 capture；根/直属/第二层 | 已观察布局与层级语义 match；原生换装后重新核对层级。 |
| P2 创建/编辑/领取/改派、删除范围、冲突恢复 | Web 冲突（历史图片 `acceptance-r1-web-conflict.png`，按用户要求不随 Git 交付）、删除范围（历史图片 `acceptance-r1-web-delete-scope.png`，按用户要求不随 Git 交付）、原生冲突（历史图片 `acceptance-r1-ios-conflict.png`，按用户要求不随 Git 交付） | 桌面覆盖详情；原生编辑 sheet 冲突态 | Web match；原生 deviation，见 F2。 |
| P3 明确跨层负责人、群/父路径 | 负责人汇总（历史图片 `acceptance-r1-web-assignee.png`，按用户要求不随 Git 交付） | Web 1200，Test User，父子/多树匹配 | Web与换装后原生实走 match；未把整个父子树推定为同一负责人，原生 Open parent scope 定位正确。 |
| P4 公开默认、私密可选、访客加入、范围切换与历史 | 历史看板（历史图片 `acceptance-r1-web-dissolved.png`，按用户要求不随 Git 交付）、原生建群点击前（历史图片 `acceptance-r1-ios-group-before.png`，按用户要求不随 Git 交付）、点击后（历史图片 `acceptance-r1-ios-group-after.png`，按用户要求不随 Git 交付） | Web 桌面；原生 402 pt 建群 sheet，已校验安装包 | Web与历史读取 match；原生新群 private 选择 deviation，见 F1。 |
| P5 轻量系统消息、修改者、回链、有效 @；无结果摘要/额外通道 | 聊天系统消息（历史图片 `acceptance-r1-web-chat-notice.png`，按用户要求不随 Git 交付）、J5 实际消息与 Work | 桌面时间线；窄屏自然换行；原生真实时间线已观察文本与 @ | 消息事实/目标/真实执行 match；换装后原生回链定位 n3 并读到完整结果，见 J6 后补验记录。 |

### 问题清单

| # | 严重度 | 现象与复现 | 处置 |
|---|---|---|---|
| F1 | major / blocking | 换装并校验哈希后：Chats → + → Create group on → 点击 Visibility/Public，Create group 反而 off，群名/范围行消失，不能选择 Private。CUA 完整 AX 路径 `container → switch Create group(value=1) / text field Group name / pop up button Visibility,Public`；最终复验调用 `app.click(93)` 后 switch=0。此前 AX51 及截图相对坐标 `[625,692]`、标签 `[165,693]` 同结果。Simulator CUA 截图约 782×1684；原生像素图 1206×2622。字段点击可正常输入、既有群设置的 Visibility picker 可正常选择，未把问题泛化为所有 picker。 | 修复后用冻结新包重验公开默认、选择 Private、完整建群、Web/Agent 读取一致。 |
| F2 | major / blocking | 原生打开 `tg_d0448fb7/n1` 编辑，result 草稿填 `584888`（revision11）；另一真实 API 修改 description 推 revision12。原生 Save 后显示 `Read the current graph before adjusting this change`，草稿在，Save 灰，完整 AX 没有 `Conflict · draft preserved` / `Read latest content`；滚动2页也无恢复按钮。截图显示完整 error Section。取消后详情显示新 description，不能把取消/丢弃草稿算恢复成功。 | 修复后重验真实409、草稿保留、读最新、明确重试；也回归非冲突保存。 |

### 验收标准覆盖

所有来源均为 [spec.md](spec.md) 对应同名 Requirement/Scenario；P 编号补充 [design.md](design.md) must-match。每行是完整场景结论，不能把“已有部分成功”当成完整通过。

| Requirement | Scenario | 期望来源 | 验证方式/证据 | 结果 |
|---|---|---|---|---|
| 每个拆分层级提供结构与完成情况视图 | 比较根任务并进入下一层 | spec；P1 | J1 根总览、独立子层入口、覆盖详情；原生换装后根入口 | pass |
| 同上 | 查看大任务并逐层进入 | spec；P1 | J1 Web结构/完成切换、15直属与3深层；原生新包深层截图 | pass |
| 同上 | 探索与计划嵌套 | spec；P1 | J1 `tg_2b8330f4` closed方向及 n3→2个Plan，根done=0 | pass |
| 每个节点独立记录创建者与负责人 | 同一任务树由不同主体负责 | spec；P2 | J2 e2e父、peer/真人子项、未分配n4 | pass |
| 同上 | 经 Agent 创建及后续改派 | spec；P2 | J2 creator=e2e保持，改派改变assignee | pass |
| 人与 Agent 在相同权限原则下维护任务 | 人直接操作及成员共同维护 | spec；P2 | J2/J3 Web/原生创建、Guest共同维护、真实Agent工具 | pass |
| 同上 | 先入群再分配 | spec；P2/P4 | J3成员候选与非成员拒绝、Global先join再创建领取；分配未加人 | pass |
| 同上 | 分配与领取分离 | spec；P2 | J2/J5分配后todo，原生584777明确Claim后doing；他人负责人删除/越权写不因指派放开 | pass |
| 任务可见范围跟随固定所属会话 | 公开可读、加入后操作 | spec；P4 | J3 API读后is_member=false、写拒绝，Web Join后可写 | pass |
| 同上 | 私密群和私聊 | spec；P3/P4 | J3私密`tg_c71f8ae1`、私聊`tg_766ed09e`管理员/Agent owner均404 | pass |
| 同上 | 在另一群讨论公开任务 | spec；P3 | J3 Global从B群写A群n4，固定归属仍c_cr331zjv | pass |
| 群类型具有明确默认值、加入方式与切换资格 | 创建和加入 | spec；P4 | Web/Agent默认公开/私密及加入可用；原生F1 | fail |
| 同上 | 更改可见范围 | spec；P4 | J3已入群管理员双向切换；非管理员creator/非成员管理员拒绝 | pass |
| 删除采用独立权限并包含所选节点整个子树 | 删除父任务 | spec；P2 | J3 Web明确2节点含Guest后代，删除后404 | pass |
| 同上 | 只有编辑权或只有管理员身份 | spec；P2/P4 | Guest负责人删非自创拒绝、管理员删无权私密拒绝 | pass |
| 六种状态表达进展，验收采用引导而非强制门禁 | 提交结果 | spec；P2/P5 | J2真实Global提交in_review与结果；真人可直接done | pass |
| 同上 | 普通父子状态变化 | spec；P1/P5 | J2/J5子done不改父，父paused不改7后代、不等于执行stop | pass |
| 任务协作通知使用所属会话的一条系统消息 | 改派双方获知 | spec；P5 | J5 cc1647ac…一条系统消息有效@两方，回链原任务 | pass |
| 同上 | 暂缓／关闭逐层传达 | spec；P5 | J5 3f7f3ec5…只@peer/global，不@深层observer，后代状态不变 | pass |
| 同上 | 结果向上反馈 | spec；P5 | J5 d5e0122b…@creator和直属父assignee，父仍paused | pass |
| 通知遵循已有 Agent 群接收策略及忙闲处理 | always 与仅 @ 的 Agent 同群 | spec；P5/R5 | J5三种命中、observer未@不运行，真人授权后的真实PA/DSH回执 | pass |
| 同上 | 空闲、忙碌、离线与取消当前执行 | spec；P5/R5 | J5 idle/busy/offline；Global turn9 interrupted/turn10自主处理 | pass |
| 负责人视图跨层汇总其直接负责的任务 | 一人负责多棵树的深层节点 | spec；P3 | J1 Web和新包原生跨层负责人、深层Open parent scope定位 | pass |
| 解散群关闭未完成工作并保留任务成果 | 群解散时仍有任务 | spec；P4 | J4 Web与新包原生历史/结果/只读 | pass |
| Web、原生 iOS 和 Agent 工具操作一致 | 跨入口维护同一任务 | spec；P1–P5 | J2基本一致；F1/F2导致原生建群与冲突旅程不可完成，P3/P5原生已补验 | fail |
| 部署 Agent 一次性整理存量数据 | 旧群及旧任务升级 | spec；migration-guidance | J6 独立schema1快照映射/迁移/verify/恢复；不代表生产部署 | pass |

### 上层文档同步

- [x] `SPEC.md`：reviewer 未发现需要改动跨包职责的新决策；无需由本报告改写。
- [x] `docs/specs/<包>/`：需要最终归并本 unit delta；当前仍是旧行为契约，不能以本 fail 报告宣告已完成。归并属 orchestrator 收尾职责。
- [x] `AGENTS.md` / `CLAUDE.md`：无需因本轮发现改动。
- [x] `docs/specs/CONTRIBUTING.md`：文档体系未改变，无需更新。

下一轮保留本轮全部 fail：F1/F2 的原生真实交互；本轮原生换装后的补验及独立迁移证据已闭合，不再列为 inconclusive。修复影响范围外的 Web、权限与真实通知证据可引用本轮，不降低验收标准。


## Round 2 — Full / targeted，2026-10-13

- `validated_at`: `5b530f925f137409481a0306d4711e6f0e2252d1`。
- `executed_base`: `b70d4a7bd80b4424fea430e507390c5dde7c0a05`。
- `fix_delta_range`: `e9edbdc5c907f0b9f51ce483b54b6ce486dbf3a1..5b530f925`。
- `prior_acceptance_paths`: 本文件 Round 1。受派范围：F1/F2、V1 解散探索选择、V4 两端分页、V5 Web 公开访客实时消息；其余前轮有效证据继承。V2/V3 的静态核对由独立静态 reviewer 负责，本报告不冒充该门禁。

### Verdict 与证据边界

**fail（一个必要体验证据项 inconclusive）**。F1/F2 已通过独立真实交互关闭；没有新增已确认的产品 major/blocking 缺陷。剩余项仅为原生 51 条分页列表的尾部 Load more 与未加载空列文案，因本轮原生自动化无法滚动该容器而无法下结论。不能把工具不可操作写成产品缺陷，也不能用静态测试或 API 结果替代实际体验。

功能结果：原生私密建群、真实冲突恢复和普通保存均通过。Web 分页、公开访客停留页内收到后续系统消息、解散时探索选择协调均通过。原生分页首屏已显示正确的已加载范围，尾部操作未验证。

视觉组织：原生建群把开关与群设置分开，Public/Private 两个选项同时可见且选择清楚；冲突说明和恢复入口位于编辑表单顶部，草稿和服务端版本有独立分组。Web 五组列标题和总范围都明确限定当前页，不将未加载的 Done 当全局为空。读历史与当前选择的视觉语义保持一致。

交互成本：冲突无需取消并丢失草稿；读取最新后按钮明确为 Retry save，服务端内容需一次正常的 Form 向下滚动即可比较。Web 分页 Previous/Next 固定在总览底部且可直达；公开访客不需要刷新或先加入。原生 Load more 的查找和操作成本尚无足够证据。

### 本轮环境证明

独立确认 checkout HEAD 为上述 `validated_at`，开始时只有既有未跟踪 `output/`。IM PID38549 的命令指向本 worktree `apps/im-server/lib/main.js`、端口58435；Vite PID2094 指向本 worktree 前端、端口58436；Node PID25659 指向本 worktree 与 `/tmp/nano-feat584-e2e/.gateway-config.yaml`。沿用 caller 已按目标版本构建的隔离栈，无无条件重启。

原生仍为专用 `Nano feat584` / Simulator `7CB77F12-2282-4AA0-BCC9-D368A4DD1122`，安装目录 `F374445B-42E9-4277-9A4A-12FE473C1A47/NanoIM.app`。reviewer 独立计算安装包 SHA256：`NanoIM=b1c89db3aeb163f56e52fee1c9f4079233938264c513527ba3d3b6580f241d90`；`NanoIM.debug.dylib=17094930a60427b629768d516d8cf6ce12900f7e77d8c1ef4502d2dd32ecb7e9`，与 caller 交接构建一致。途中 Simulator 当前窗口一度切至另一测试窗口 `Nano feat587`，未在该窗口操作产品；通过 Window 菜单重新选择 Nano feat584 后继续，其他窗口结果不计入本报告。

### Targeted 旅程与实际结果

| 范围 / 来源 | 实际旅程与可复查证据 | 结果 |
|---|---|---|
| F1；spec「创建和加入」；P4 | Chats→+→Create group；默认 Public；点击 Private 后开关仍 on，输入584992、选择专用 Observer→Create，真实进入584992聊天。API独立读得 `c_12uzi86a.visibility=private`。见私密选择（历史图片 `acceptance-r2-ios-private.png`，按用户要求不随 Git 交付）。 | pass，关闭F1 |
| F2；spec「跨入口维护同一任务」；P2 | 原生编辑 `tg_d99a06d3/n1`，revision4 description草稿584993；另一端通过真实apply将description改REMOTE584993、revision5。原生Save后出现冲突、草稿仍584993、顶部Read latest content；点击后Retry save明确可见。通过AX容器的Scroll Down实滚动，看到Latest server content分组及REMOTE584993/result584123；明确Retry save后详情为584993，revision6。再普通编辑change_note=584994并Save，revision7且description仍584993。见比较远端内容（历史图片 `acceptance-r2-ios-compare.png`，按用户要求不随 Git 交付）。 | pass，关闭F2 |
| V4 Web；spec「比较根任务并进入下一层」；P1 / design已加载范围 | Tasks搜索584999，51根；第一页20/51、todo20 on this page，其他列0 on this page / No tasks on this page；Next第二页20，再Next末页11/51，其中todo10、done1，Next禁用、Previous可用。1200×734实看五组布局及按钮。见首屏（历史图片 `acceptance-r2-web-page1.png`，按用户要求不随 Git 交付）、末页（历史图片 `acceptance-r2-web-page3.png`，按用户要求不随 Git 交付）。 | pass |
| V4 iOS；同上 | 搜索584999首屏明确Loaded 50 / 51 tasks，To do 50 loaded，见原生首屏（历史图片 `acceptance-r2-ios-loaded.png`，按用户要求不随 Git 交付）。AX根container仅返回showing 0–100 of 123 items，不暴露Scroll Down；app.scroll(20 pages)、drag和Page_Down均未改变可见画面。没有到达Load more，也没有实际看到未加载空列。 | inconclusive，仅尾部体验证据缺口 |
| V5；spec「公开可读、加入后操作」；P4/P5 | 通过Discover public groups进入 `c_h1yjg4un`，Test User仍is_member=false，页面Read only / Join，输入禁用。保持页面不导航、不刷新，另一测试Guest创建并分配 `tg_157e1909`（Review584R2 LIVE visitor notice），新系统消息自行出现并带正确任务链接和@Guest；仍只读。见访客实时通知（历史图片 `acceptance-r2-web-visitor.png`，按用户要求不随 Git 交付）。 | pass |
| V1；spec「群解散时仍有任务」及「探索与计划嵌套」；P1/P4 | 专用公开群 `c_x153ngzf` 中新建两棵explore图，各有选中候选与理由/结果。Web Config→Dissolve group→确认。`tg_ffa8870d`原doing候选n2变closed、root.selection=null，REASON_doing与RESULT_doing仍保留，Web历史不再显示Current choice；`tg_eb8a0c73`候选n2仍done、root.selection=n2，REASON_done/RESULT_done保留，Web继续显示Current choice及理由；两图只读。见未完成选择取消（历史图片 `acceptance-r2-web-dissolved.png`，按用户要求不随 Git 交付）、已完成选择保留（历史图片 `acceptance-r2-web-done-selected.png`，按用户要求不随 Git 交付）。理由保留由服务端事实交叉核对；未选中后Web不展示旧理由，未声称界面可读取该旧理由。 | pass |

**前轮 F2 证据限定。** Round 1 的“滚动2页也无恢复按钮”只说明当时 CUA 操作没有让该区域进入可见范围，不能证明真的到过 Form 底部，更不能证明旧代码没有按钮。Round 2 实测 Form 的 `performSecondaryAction(..., "Scroll Down")` 可以真正滚动，而通用 scroll/drag 在该模拟器场景无效。前轮保留原记录作为过程证据，以本段限定其结论；本轮新版本恢复入口位于顶部且完整恢复旅程已独立走通。

### 26 个 Scenario 的继承与本轮状态

本轮不重复影响范围外的真实PA/DSH、忙闲/离线/stop通知旅程、迁移和无关权限组合。以下序号按Round 1覆盖表自上而下；每项继续以同名spec Scenario为来源。

| # | Scenario | 本轮结果 / 依据 |
|---|---|---|
| 1 | 比较根任务并进入下一层 | inconclusive：前轮层级结果保留，新增原生分页尾部证据未闭合；Web分页pass |
| 2 | 查看大任务并逐层进入 | pass，继承J1 |
| 3 | 探索与计划嵌套 | pass，继承J1并补V1 |
| 4 | 同一任务树由不同主体负责 | pass，继承J2 |
| 5 | 经Agent创建及后续改派 | pass，继承J2 |
| 6 | 人直接操作及成员共同维护 | pass，继承J2/J3，补原生普通保存 |
| 7 | 先入群再分配 | pass，继承J3 |
| 8 | 分配与领取分离 | pass，继承J2/J5 |
| 9 | 公开可读、加入后操作 | pass，继承J3并补V5访客实时消息 |
| 10 | 私密群和私聊 | pass，继承J3 |
| 11 | 在另一群讨论公开任务 | pass，继承J3 |
| 12 | 创建和加入 | pass，F1已闭合，其他入口继承前轮 |
| 13 | 更改可见范围 | pass，继承J3 |
| 14 | 删除父任务 | pass，继承J3 |
| 15 | 只有编辑权或只有管理员身份 | pass，继承J3 |
| 16 | 提交结果 | pass，继承J2/J5 |
| 17 | 普通父子状态变化 | pass，继承J2/J5 |
| 18 | 改派双方获知 | pass，继承J5 |
| 19 | 暂缓／关闭逐层传达 | pass，继承J5 |
| 20 | 结果向上反馈 | pass，继承J5 |
| 21 | always与仅@的Agent同群 | pass，继承J5；本轮不替代独立V2/V3静态复核 |
| 22 | 空闲、忙碌、离线与取消当前执行 | pass，继承J5 |
| 23 | 一人负责多棵树的深层节点 | pass，继承J1 |
| 24 | 群解散时仍有任务 | pass，继承J4，补V1探索选择 |
| 25 | 跨入口维护同一任务 | pass，F1/F2闭合；分页证据缺口单列#1 |
| 26 | 旧群及旧任务升级 | pass，继承J6；仍不代表生产部署 |

### 收尾与上层同步

本轮只追加本报告与精选截图，无产品代码/测试/配置/设计修改。P1仅原生分页尾部为inconclusive；P2/P4修复后match，P3继承前轮，P5补访客实时消息并继承真实执行证据。上层文档归并仍由orchestrator在门禁通过后处理，不能由本轮fail宣告完成。

关闭reviewer专用浏览器review584r2；没有启动额外服务。共享栈与Nano feat584模拟器交还caller，原生留在Tasks搜索584999首屏，供caller处理明确的工具限制。未关闭或改变Nano feat587进程；既有未跟踪output/保留。


## Round 3 — Q41 Full / targeted，2026-10-13

### Metadata 与判定

- `validated_at`: `6c87d7f160caf56cba64052e8180cbff5f02da6a`；`executed_base`: `6275f271d8af552c065ce7cca35dd044f926eb67`；`fix_delta_range`: `34dbf88..6c87d7f16`。
- 来源：[spec.md](spec.md) Q41及新增两项Scenario、[design.md](design.md) Q41/P1/P3/P4/R1/R3/R4、[design-review.md](design-review.md) Gate2 Round8；沿用共同体验标准。本轮只追加报告，不读取实现定位原因。
- 时间：独立浏览器证据 `2026-10-13T02:34:36Z–02:49Z`；Web Chromium session `review584r3`，1440×960、1024×768、390×844；原生为既有专用iOS模拟器。
- 开始HEAD与目标一致，仅有既有untracked `output/`；途中HEAD变为`4215b6faf`，独立核对从受审HEAD到该提交仅有作者截图与implementation.md，产品源码未变，故本轮证据继续对应上述`validated_at`。未把作者报告当独立结论。

**Verdict：fail。1 major契约偏差＋1 minor文案问题；0 inconclusive。** 原生V4遗留证据已闭合，F1/F2保持关闭。Web独立自然追加、短列首屏、完整总数、轮询保留累计、窄屏有界列表、公开群发现新旅程均可用；但搜索/负责人切走再切回时恢复旧累计页，违反已冻结的五列重置要求，见R3-F1。追加失败错误地称为刷新失败，见R3-F2。

功能结果：根总览和负责人跨层查询均从各状态独立取数，滚动不推进其他列；原生用户完成Load more后的结果已独立观察。公开群从＋菜单连续进入访客页，未自动入群。视觉组织：1440/1024五列外框与短列并列，390保持五组顺序、长列表高度有界；发现弹窗采用头像行和内容高度，手机为底部sheet。交互成本：不再为短Done翻遍Todo；失败保留原内容并可恢复。筛选恢复旧累计页让“切换后重新从首批浏览”的范围不成立；两种失败共用文案增加判断失败阶段的成本。

### 环境与原生遗留项关闭

独立核对IM PID68253、Web PID2094、Node PID25659均指向本worktree；IM58435/Web58436，Node配置仍在专用`/tmp/nano-feat584-e2e`。IM于10:18从目标6c87 build启动，Web使用Vite HMR。Node PID25659于00:03启动，早于最终build，不能表述为目标提交新启动；Q41未改变PA通知语义，相关真实执行/通知证据仅按影响面继承前轮。reviewer无额外服务重启、生产操作或配置修改；Web验收后已通知caller可进入Node重启窗口。

原生专用UDID仍为`7CB77F12-2282-4AA0-BCC9-D368A4DD1122`；安装目录仍为Round2记录的`F374445B-42E9-4277-9A4A-12FE473C1A47/NanoIM.app`。`5b530f925..6c87d7f16`的`src/IM/ios` diff为空，沿用Round2已核验安装包；本轮Web修正不需要伪造原生新包。

**操作来源必须区分：** caller转交用户明确在Nano feat584按住鼠标上拖、点击Load more并确认“好了”。reviewer没有代做或声称自动化完成这一手势。reviewer随后独立读取专用窗口AX及实际截图：底部In progress0、In review0、Done1，Done中为`584999 Page 00`，Closed0，底部已无Load more。再通过点击iOS状态栏返回顶部，独立看到`Loaded 51 / 51 tasks`、To do50。见原生末页（历史图片 `acceptance-r3-native-tail.png`，按用户要求不随 Git 交付）、完整计数（历史图片 `acceptance-r3-native-loaded.png`，按用户要求不随 Git 交付）。这关闭Round2唯一inconclusive；原生累计读取由用户操作＋模型独立观察共同提供证据，不是物理设备验收。未另外声称完成原生主动刷新测试。

### Q41 连续旅程

| 旅程 / 来源 | 独立证据与实际用户结果 | 结果 |
|---|---|---|
| 根总览五列；新增「Web五列独立自然加载」；P1 | 搜索584999：Todo真实总数50、首批20，Done1的Page00直接在首屏；其他三列0。鼠标在Todo列内滚动，20→40；多次3秒轮询的真实GET包含第一页和第二页，画面仍40、scrollTop2679.5，其他列0滚动。再到末页共50、All loaded · 50；Done始终1。没有Previous/Next整页翻页。见1440首屏（历史图片 `acceptance-r3-root-initial-1440.png`，按用户要求不随 Git 交付）、长列末页（历史图片 `acceptance-r3-root-complete.png`，按用户要求不随 Git 交付）。 | 加载与轮询pass；筛选重置fail，见R3-F1 |
| 负责人跨层；P3/R3 | 新专用私密群`c_uayh55i1`、图`tg_13efc5d6`（query584996）：Test User根doing，41直属待办（40todo＋1paused）、1done；Guest另负责1todo。Test User视图首批todo20/41，同时显示doing根和done子项，卡片保留群名/父路径；滚动20→40→41。切Guest只显示该人的1条，不混入其他负责人。见1024负责人（历史图片 `acceptance-r3-assignee-1024.png`，按用户要求不随 Git 交付）。 | 跨层/列范围pass；切回累计页fail，见R3-F1 |
| 初次读取、追加、刷新失败恢复；Gate2R8加载状态契约 | 仅在reviewer自己的浏览器临时拦截指定Todo请求返回503，成功响应仍取真实IM。首次query584999 Page失败：Todo计数—，明确Could not read task records/Refresh，没有虚假No tasks，Done1仍可看。解除拦截并点Refresh后20条恢复、alert消失。追加第三页失败时原40条保留、Done不移动，但文案错称Refresh failed。恢复网络后自动轮询读齐50。另对已加载50条的刷新请求返回503，保留50条和位置，解除拦截并明确点击Refresh后alert消失、仍50条、scrollTop7653.5。见首读失败（历史图片 `acceptance-r3-initial-error.png`，按用户要求不随 Git 交付）、刷新失败（历史图片 `acceptance-r3-refresh-error.png`，按用户要求不随 Git 交付）、追加失败（历史图片 `acceptance-r3-append-error.png`，按用户要求不随 Git 交付）。拦截已移除，错误不是生产故障。 | 恢复功能pass；文案minor |
| 响应式；P1/P3 | 实看1440×960、1024×768、390×844的根总览/负责人布局。1024五列仍可读；390无横向溢出，Todo body为464px（55dvh），整页继续向下可看其他组；长Todo内滚动20→40，其他组数量与滚动位置不变。见390根总览（历史图片 `acceptance-r3-root-390.png`，按用户要求不随 Git 交付）、手机Done及后续组（历史图片 `acceptance-r3-phone-done.png`，按用户要求不随 Git 交付）。未把桌面resize截图代替手机选择群的流程。 | pass |
| 从已有会话入口发现公开群；新增Scenario；P4/R4 | 桌面先进入584992聊天，再＋菜单，保留New chat/Create group/Discover三项；点击Discover后菜单关闭，搜索获焦。1440弹窗约420×440，有群头像、群名、成员数、Joined标记；搜索无匹配显示No public groups found，搜FIX584仅1行，1024弹窗随内容缩为约420×196，没有固定大片空白。Escape和Close均关闭弹窗、回原`/chat/c_12uzi86a`，document.activeElement为New conversation。见桌面发现（历史图片 `acceptance-r3-discover-1440.png`，按用户要求不随 Git 交付）、搜索后内容高度（历史图片 `acceptance-r3-discover-search-1024.png`，按用户要求不随 Git 交付）。 | pass |
| 手机发现→非成员查看；P4 | 390真实从聊天Back回列表→＋→Discover，底部sheet及头像名单可辨认；点FIX584 Public visitor refresh整行，sheet和列表关闭，进入正确`c_h1yjg4un`，显示Read only / Join group，消息输入禁用，既有历史可读，没有自动加入。见手机发现（历史图片 `acceptance-r3-discover-390.png`，按用户要求不随 Git 交付）、手机访客（历史图片 `acceptance-r3-visitor-390.png`，按用户要求不随 Git 交付）。 | pass |

### Issues

**R3-F1 — major / blocking：返回既有搜索或负责人条件时没有重置累计页。**

- 来源：spec新增「Web五列独立自然加载」要求搜索或负责人变化同时重置五列；design Q41首批20；Gate2 R8对R7-W2的闭环明确要求切走再切回首批20，不带旧累计。
- 实际复现A：query584999已自然加载50；搜`584999 Page 0`得到Todo9/Done1，scrollTop0；再搜回584999，DOM及可见列表恢复50条、scrollTop0，而不是20条。
- 实际复现B：query584996＋Test User已加载40/41；切Guest为1/1；再切Test User，恢复40/41、scrollTop0。该模式在两个真实入口独立复现。
- 影响：改变筛选后只重置位置，旧的累计读取范围仍随条件恢复；与已确认的首批重新开始语义不一致，已加载多页也继续参与该条件的后续读取。未发现跨主体内容泄漏，不扩写为权限问题。需要修正重置行为后，仅重验搜索/负责人切换及同筛选轮询保留的区别。

**R3-F2 — minor：追加失败错误地称为刷新失败。**

- 在Todo已有40/50、第三页cursor（after graph_id=`tg_2a80e5bd`）被503拒绝时，列尾显示`Refresh failed. Showing the previously loaded graph; this is not the latest record.`和Refresh；实际失败是读取下一批，不是已有40条的刷新。
- Gate2R8通过的是区分追加失败与刷新失败保留；当前文案无法告诉用户缺的是后续任务。已有内容及其他列未丢失，恢复网络后能继续读齐，所以不单独定为功能阻塞。修正应区分失败阶段并保留本列恢复入口，无需改其他列或引入新流程。

### Scenario 与前轮证据继承

Q41明确使Round2的Web全局分页、独立侧栏Discover按钮/旧裸弹层通过证据失效，本轮不恢复它们。当前28个Scenario中：

| Scenario集合（名称对应Round2覆盖表） | 本轮状态 / 依据 |
|---|---|
| 新增「Web五列独立自然加载」 | fail：R3-F1；其余自然追加/总数/轮询/有界移动端部分已通过，不能替代完整Scenario |
| 新增「从已有会话入口发现公开群」 | pass：本轮桌面与手机连续发现/关闭/搜索/访客旅程 |
| 原#1「比较根任务并进入下一层」 | pass：层级语义继承J1；原生51条遗留证据本轮闭合；新Web独立加载的重置问题单列新增Scenario |
| 原#23「一人负责多棵树的深层节点」 | pass：原J1多树层级证据保留；本轮补真实根＋子项的独立列和群/父路径，筛选重置fail单列新增Scenario |
| 原#2–#22（不含新增两项）、#24–#26 | pass，分别继承Round2同名行及其引用的Round1 J1–J6：大任务逐层/探索嵌套、独立创建者与负责人、真人/Agent维护、先入群再分配、领取、公开/私密/私聊与固定归属、建群/范围、整子树删除、六状态、系统消息与PA/DSH策略/忙闲离线stop、解散历史、跨入口维护、独立迁移。Q41没有改变这些权限/写入/通知/执行语义；没有借本轮UI操作重述成新真实Agent证据。 |

P2/F1/F2关闭保持；P5真实通知链与Round2访客实时消息保持；P1/P3本轮仅R3-F1未匹配；P4新版已独立匹配。原生剩余inconclusive不再延续。上层current spec归并仍交orchestrator，不能以本轮fail宣告整体完成。

### 清理与交接

只追加acceptance.md及精选实际客户端截图，未改产品代码/测试/配置。关闭独立浏览器review584r3，临时网络故障仅在该浏览器且已移除；共享IM/Web/Node保持给caller。原生留在Tasks搜索584999的51/51首屏，未操作其他模拟器。既有output/保留；本轮专用测试群/任务留在隔离数据库便于复验。


## Round 4 — R3-F1/R3-F2 targeted closure，2026-10-13

### Metadata 与判定

- reviewer: `/root/feat584_final_product`；`validated_at`: `6052ec92e54f6f7123523f53129a7f5a3fe031b7`；`executed_base`: `6275f271d8af552c065ce7cca35dd044f926eb67`；`fix_delta_range`: `e0dfc371b..6052ec92e`（产品提交 `f3b8c498d`）。
- 来源：spec Q41「Web五列独立自然加载」、design Q41/P1/P3、Gate2 Round8加载状态/筛选重置契约及共同体验标准。只验R3两项与直接波及的同筛选轮询；没有读取作者成功叙述或实现源码来替代产品观察。
- 实际浏览器：独立Chromium session `feat584r4`，2026-10-13 03:20–03:25 UTC，1440×960及1024×768；真实Test User，查询584999/584996，第二负责人Web 584 Guest。
- 环境：重启后caller从冻结源码重建的隔离IM `127.0.0.1:51283`、Vite `127.0.0.1:58436`，fixture位于`output/acceptance-runtime/fixture.json`。独立确认IM PID2777使用本worktree的`apps/im-server/lib/main.js`，构建时间10:17:31；cwd为本worktree的acceptance-runtime；Vite PID3107 cwd为本worktree frontend。开工及收尾HEAD相对validated_at无差异，tracked源码干净，仅既有output/。没有重启共享服务或访问生产。

**Verdict：PASS。0 blocking / 0 major / 0 minor / 0 inconclusive；R3-F1、R3-F2均closed。**

### 独立连续旅程与闭环

| 来源 / 问题 | 操作与实际结果 | 结果 |
|---|---|---|
| R3-F1；P1搜索重置与同筛选轮询 | 真实根总览584999首批To do20/50，Done1同时可见。鼠标在列内自然滚动20→40；等待至少两次3秒轮询仍40，真实网络请求包含第一/第二页；继续滚动至50，再等轮询仍50并请求三页。搜索`584999 Page 0`得到Todo9/Done1，再搜回584999为20/50、scrollTop0，不恢复旧50。见搜索返回（历史图片 `acceptance-r4-search-reset.png`，按用户要求不随 Git 交付）。 | pass / closed |
| R3-F1；P3负责人重置与同筛选轮询 | 1024真实By assignee，query584996＋Test User首批20/41，doing根1、done子1同时可见，卡片保留群/父路径。鼠标滚至40后等待6.5秒仍40；选Web 584 Guest为1条；选回Test User重置20/41、scrollTop0。见负责人返回（历史图片 `acceptance-r4-assignee-reset.png`，按用户要求不随 Git 交付）。 | pass / closed |
| R3-F2；追加失败/Retry | reviewer只在自己的浏览器拦截指定Todo下一页请求返回503，其他请求仍走真实IM。先验第三页失败：已有40/50保留，Done1保持；文案为`Could not load more tasks. Previously loaded tasks are still available.`、按钮Retry。移除路由后实际点击Retry得到50/50。为留下完整可见恢复入口，再以`584999 Page`复验第二页失败20/50，向列尾再滚一下即可看到完整提示、Retry与加载范围；解除后点Retry恢复40。见追加失败（历史图片 `acceptance-r4-append-error.png`，按用户要求不随 Git 交付）。 | pass / closed |
| R3-F2；刷新失败/Refresh | 已有50条时仅拦截Todo刷新请求；提示`Could not refresh this column. Showing previously loaded tasks.`、按钮Refresh。失败保留50条及scrollTop7653.5，解除后实际点Refresh清除提示、仍50条且scrollTop7653.5。另在40/50状态留存完整列尾截图，仍明确是本列刷新及旧任务，其他列保持可读；解除后点Refresh恢复。见刷新失败（历史图片 `acceptance-r4-refresh-error.png`，按用户要求不随 Git 交付）。 | pass / closed |

功能结果：变化条件从首批重新开始，固定条件的轮询保持已展开范围；追加与刷新恢复均已实际操作。视觉组织：独立实看上述截图，错误仍在本列内容之后，列头真实总数、短Done列、卡片与恢复入口层级清晰；文案没有再把列列表称为graph。交互成本：只需在当前列尾读取提示并点击对应恢复按钮；错误出现后可能需继续短距离滚到列底，按钮可达，不需要离开页面或重置其他列。没有新增体验问题。

### 保留证据与Scenario对账

- 新增「Web五列独立自然加载」由Round3其余自然追加/总数/短列/窄屏有界证据＋本轮筛选重置与轮询/错误恢复合并为pass；P1/P3的R3偏差已闭合。
- `retained_from: Round3`：新增「从已有会话入口发现公开群」、1440/1024/390响应式、新菜单/头像弹窗/手机sheet/访客旅程、首读失败恢复，均未受本轮修正影响；不恢复旧Web Previous/Next或裸发现弹层证据。
- 原#1、#23的原生51/51证据继承Round3：用户实际执行Load more，reviewer随后独立观察尾部及Loaded51/51。原生代码未变，本轮没有重做原生操作，也不将其说成物理设备或原生主动刷新验收。
- 原#2–#22、#24–#26按Round3对账及其引用的Round1/2逐项pass保留：层级/探索、创建者与负责人、真人/Agent维护、入群分配/领取、访问边界、建群、整子树删除、状态、通知/PA/DSH/stop、解散、跨入口维护、迁移。修正局限于Web筛选累计与错误呈现，未改变上述写入/身份/消息/执行语义；本轮没有新发生产/LLM消息。
- 因此28个Scenario的必要证据均已闭合；P2既有F1/F2、P4新版发现与P5通知证据保持。静态一致性/代码审查及current spec归并由相应角色完成，本报告不冒充其结论。

### 清理

全部临时浏览器fault routes已移除，恢复按钮已操作，独立浏览器已关闭。共享IM/Vite/Node保留给caller统一清理。只追加本报告与四张精选截图，未改源码、测试、配置或设计；既有output/保留。

## Round 5 — Q42 原生 targeted，2026-10-13（用户终止后续验收）

### Metadata 与范围裁决

- reviewer: `/root/ios_q42_product`；`executed_base`: `b7e367cc08a642133dea28e372816cd79038818d`；`validated_at`: `7c8ad1ade6053e2075b78a89276497b422440b38`。执行期间 HEAD 更新至 `ed047ffb0dbc2594daa8c7e7661d037e18f135f4`，独立 diff 确认仅报告及证据变化，受审源码未变。上述 SHA 是本次实际执行来源，后续图片历史清理不改变其历史含义。
- 来源：spec Q42、`ios-experience.md`、`ios-prototype.html`、current `ios-client.md` / `task-graphs.md` 及共同体验标准。未读实现源码或作者成功叙述代替产品验收。
- 专属 Simulator `Nano feat584`，iPhone 17 / iOS 26.4，UUID `7CB77F12-2282-4AA0-BCC9-D368A4DD1122`，中文、默认字体、约402pt设备宽；CUA截图含外框778×1676。仅使用隔离 IM `http://127.0.0.1:62306`、测试真人陈子健/nano 和林悦/lin584，未操作生产或另一模拟器。
- 安装包 `win.nanoim.ios` 的 `NanoIM.debug.dylib` 与交接冻结 Debug 构建 SHA256 均为 `6dd1e8a3f9addadc26146b7bacc732fd35e2c2b61d322fd125e9e40ac2b8a3c0`。冻结构建日志的项目、derivedDataPath、destination 对应本 worktree、`/tmp/nano-feat584-ios-q42/ios` 和专属 UUID；版本来源还包含 caller 冻结源码交接。build/test/archive 不是产品体验通过证据。

**Verdict：partial / inconclusive，完整 Q42 原生验收未完成，不能记为 PASS。**

2026-10-13 用户明确指示「那就跳过ios验收」，随后要求删除本需求的图片证据以免占用 GitHub 空间。立即停止剩余原生操作，不再请求人工输入；本轮只追加文字报告，不新增仓库图片。此为用户对后续验收范围的明确豁免，不把未观察场景改判通过或不适用。没有新增已确认 blocking/major 产品缺陷，但必要证据尚不完整；恢复完整 Q42 门禁时仍须补齐下列 inconclusive 项。

### 独立原生用户旅程

1. **阅读与编辑。** 「完成首次登录流程」详情依次展示会话、标题、待确认状态/E2E Agent、任务说明、当前结果、直属完成1/6、收起的创建与修改信息，编辑是底部主要操作。打开编辑后字段名持续可见，标题突出，状态/负责人位于紧凑浅底区域，描述与结果按当前内容排布。默认字体和当前长度下信息顺序清楚，不需先穿过审计信息才能读目标和结果。
2. **选择面板。** 状态 sheet 六行均有图标/名称、选中底色/勾选、关闭入口及保存才生效的提示。选择暂缓后回到草稿。负责人 sheet 显示未分配、两位真人头像/身份及 Agent 机器人标识、当前选中反馈；搜索「不存在成员」实际出现空态，清除后选择林悦，编辑页显示该真人。未验证陈旧成员和全局筛选面板。
3. **取消与继续。** 将状态改为暂缓后点取消，出现「放弃本次修改？任务尚未保存。」及放弃按钮。点击弹层外回编辑，暂缓仍保留。系统使用点外部取消的原生 popover；本轮未实际点击放弃修改或测试脏草稿滑动关闭。
4. **真实409及再次冲突。** 通过原生 UI 把状态改为暂缓、负责人改为林悦；fixture helper 以另一测试身份将远端状态改为进行中、说明改为第一版。原生点保存后进入独立比较页：状态显示我的修改/最新内容，无预选、保存禁用；本地独改负责人林悦保留，远端独改说明单独列出。选本地暂缓后，再以 helper 将远端状态改为待办、说明改为第二版；原生确认保存后重新比较，选择再次为空，本地负责人保留。明确选择最新待办并保存，详情实际显示待办、林悦、第二版说明及原有结果。API仅制造并发，保存与字段选择均为原生UI操作；没有把既有结果保留冒充本地文字结果编辑成功。
5. **直属层及第三层。** 从详情的独立子任务入口进入直属层，五组计数2/1/1/1/1，暂缓并入待办而保留标签，卡片标题优先、身份次级、子层独立可点。经「梳理首次使用的引导文案」进入第三层，面包屑保留根/父路径，仅一项已完成孙任务和四个紧凑零组。打开添加子任务，表单明确显示会话/父任务、默认待办/未分配、持久字段标签及结构选择；未输入成功或保存创建。

已观察部分的内容优先、身份次级、浅分隔与克制强调色符合确认方向；选择与保存分开，冲突页可辨认本地/远端字段并作决定。不能从这些代表页推断总览、聊天、长列表及窄屏/大字体全部可交付。

### 本地证据与 must-match 对照

所有本轮截图仅保留在 `/tmp/nano-feat584-ios-q42/`，未加入Git；临时文件不是长期归档保证。以下为实际查看并形成结论的路径，不作为仓库图片链接。

| Reference / must-match | 实际证据及对照结论 |
|---|---|
| 详情：会话→标题→状态身份→描述→结果→子任务；次级信息收起 | `reviewer-detail.png`。实际信息顺序及可读性符合文字契约；原型detail的HTML已读，但未完成该状态的独立渲染画面对照，完整视觉must-match仍inconclusive。 |
| 创建/编辑：父上下文、持久标签、内容密度 | 实际子创建表单已见，并独立查看批准的子创建原型截图；默认未分配、上下文及空字段密度符合方向，结构控件位置可原生适配。输入/保存/返回原层未完成。 |
| 状态/负责人：具名面板、身份、选中反馈、明确保存 | `reviewer-status.png`、`reviewer-actor.png`。默认尺寸实际呈现及操作符合文字契约；未完成所有原型状态的独立渲染对照与陈旧成员检查。 |
| 草稿离开与保存冲突：保留、字段名、我的/最新、明确确认 | `reviewer-dirty.png`、`reviewer-conflict.png`、`reviewer-conflict-repeat.png`、`reviewer-saved.png`。状态字段冲突及独改保留/再次冲突/保存实际成立；完整文字、多字段冲突及所有离开分支仍未齐。 |
| 五组、空组密度、独立子层入口 | `reviewer-third-layer.png`，已独立查看批准的总览截图。第三层五组/卡片层级符合；全局总览与分页末页未执行，不能判整体match。 |
| 跨层负责人、群任务、聊天返回 | 批准原型截图已独立阅读；实际路径未执行，inconclusive。 |
| 320pt或最接近可用窄设备、大字体、复制及按钮可达 | 仅现有iPhone17默认字体，不声称已选最窄可用设备；inconclusive。 |

### Q42 场景覆盖

| Scenario / 来源 | 本轮结论与边界 | 结果 |
|---|---|---|
| 总览比较、详情/子层独立入口及返回；R1 | 详情→直属层→第三层已走；全局总览起点、返回及位置保留未验 | inconclusive |
| 详情信息顺序、次级信息收起、编辑主操作 | 默认字体当前长度已独立观察 | pass（仅代表状态） |
| 六状态与独立选择面板 | 六行可见、待确认选中→暂缓草稿，未隐式保存 | pass |
| 真人/Agent/未分配/搜索与成员资格；R2 | 身份、搜索空态及改派真人已验；未分配清空、陈旧成员未验 | inconclusive |
| 根/子创建、会话/父上下文及创建后返回；R1/R2 | 子创建上下文已见；根创建、实际保存未验 | inconclusive |
| 本地标题/说明/结果文字编辑保存；R2 | CUA多行输入未可靠生效，原有结果只在冲突中保留 | inconclusive |
| 脏草稿取消/继续/放弃/滑动保护；R2 | 取消确认、点外部继续保留已验；放弃/滑动保护未验 | inconclusive |
| 真实409、逐字段选择、远端独改/本地独改、明确保存 | 状态冲突、负责人本地独改、说明远端独改实际协调，原生保存后核对详情 | pass（状态冲突旅程） |
| 比较后再次409 | 新比较重新要求选择，保留草稿负责人，显式选最新后保存 | pass |
| 无同字段冲突的合并确认、同值、多字段文字冲突、返工原因 | 未执行 | inconclusive |
| 权限拒绝、父/目标删除时保留草稿供复制且不重建 | 未执行新编辑恢复流程 | inconclusive |
| 跨层负责人筛选及定位；R3 | 未执行 | inconclusive |
| 群/聊天入口、同一事实及返回原聊天；R4 | 未执行 | inconclusive |
| 分页末页51/51、追加保留已加载内容及位置；R1 | 本轮未执行；旧原生证据不替代改版重验 | inconclusive |
| 窄设备、大字体、长内容复制、主操作可达、VoiceOver名称 | 仅默认字体402pt及AX名称，其他未验 | inconclusive |

工具边界：普通搜索TextField的setValue可用；多行Group尝试click/typeText/setValue后截图未可靠变化，一次AX value短暂变化也未形成脏草稿，因此不认定输入成功。列表scroll/drag后画面不移动；已暴露AX子层按钮可点，但不等于用户滚动长列表验收。曾协调人工输入，用户在协助前明确取消后续验收；未运行未获授权的XCUITest，未用实现源码或私有自动化替代界面。

### 前轮继承、文档与收尾

- `retained_from: Round4`：未改Web的Q41自然加载、筛选重置、轮询保留、刷新/追加恢复保持结论；backend/Agent/任务权限/通知/真实PA/DSH/迁移语义按Round4引用Round1–3保留。Q42仅改变原生任务呈现与草稿协调，本轮未重跑这些路径。
- 原生布局/创建/编辑/分页受Q42影响，旧结论不能覆盖本轮未验项，以上表为准。前轮已关闭缺陷未凭空重新定为产品失败。
- `SPEC.md`、`AGENTS.md`、`docs/specs/CONTRIBUTING.md`无需本轮更新；`docs/specs/im/`草稿/冲突最终current归并由caller按最终实现及用户范围裁决，此报告不代写契约。
- 用户豁免只授权停止剩余验收，不证明每项规范通过，也不构成真机、签名或推送证据。
- 仅追加本报告；未新增仓库图片、未改代码/测试/配置/设计/其他报告、未提交。Simulator保留未保存子创建表单，不执行保存或放弃；隔离IM/App/Simulator交回caller统一清理。本轮未自行启动服务。
