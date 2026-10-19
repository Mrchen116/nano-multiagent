# feat-617 — 验收报告

> Round 1 · 独立真实产品验收 · 2026-10-19 16:34–16:50 Asia/Shanghai
>
> Validation snapshot: `aaa6bfc24 → aaa6bfc24`。验收起点 HEAD 确认为 `aaa6bfc24a052e4da3da1eeeec4a819f47d7a142`；期间 caller 更新到 `0a7b187a8`，仅增加证据与报告，产品代码和运行产物未变。前端构建由 caller 于 16:31 提供，后端包含受验后端代码；未重建数据库、未改实现。

## Verdict

**fail**。1 项 major 阻塞、1 项 minor。正常交互、配置、持久化、多人隔离、故障重试和历史只读可以完成；离线时缺少明确的“已保存待处理”结果，未满足 design 与 R3 的如实反馈要求。

## 用户旅程体验

本轮从真实 Web IM 登录和自然语言输入开始，未读取实现定位原因，也未使用 M1 的成功叙述作为结果。专用浏览器 `feat617review`，第二用户浏览器 `feat617peer`；主模型由 caller 固定为 `codexOAuth:gpt-6.1-sol`。

摘要、卡片标题、字段和继续按钮在同一 Agent 消息内，用户可先理解范围再修改；提交后生成本人浅绿色消息及独立选择区，原卡片禁用。普通 Agent 对“10:30 到达、最多步行 2 公里、咖啡休息”逐项响应；普通和 Global 的草稿修改都保留了用户手写的“不发送”要求及具体时间地点。控制区域并未被当成执行已完成的凭证。

1440×1000 保留会话侧栏和底部输入；768×900 保留侧栏，卡片单列可操作；390×844 转为聊天单屏，返回导航与底部输入保留。长比较卡片通过消息主滚动区阅读，表格需横向滚动，字段与按钮无额外纵向滚动层。较短提醒和草稿能在手机连续阅读。按钮采用蓝色而非原型绿色，视觉上显眼且操作含义明确，这属于允许的组件适配，未单独认定为问题。

离线提交的截图中，Agent 状态点已灰色，但卡片仍只提示 `Choices submitted to the Agent`，本人选择消息只有时间，没有“等待处理”。用户不能据此区分已被 Agent 接手与仅存入中心服务。这是当前整体交付阻塞。

### 现场操作与实际结果

- **T1 普通 Agent 行程**：`/chat/c_8iutij8v`，16:35 自然语言请求比较轻松步行/骑行并调整时间偏好。Agent 生成比较表、出发时间、方式、偏好和继续按钮。编辑为“上午10点半到达西湖 / 轻松步行 / 最多步行2公里，必须有咖啡休息”，刷新后恢复。16:37 模拟 POST 网络失败显示 `Submission is unconfirmed. Retry the same submission.`，字段保留；解除拦截点 Retry 后生成一条本人选择消息，原卡片只读；后续真实模型按三项实际修改给出安排。
- **T2 Global 草稿与双页面冲突**：`/chat/c_igsjsbh2`，16:35 请求可直接编辑的测试同伴邀请，16:36 得到草稿。编辑为周日15点北山街，另一页面载入同一草稿；另一页改16点，本页改17点，得到真实草稿冲突提示 `Another device updated this draft. Load the latest version to continue.`，17点仍保留。点 Load latest draft 后手写“先别发送，把语气改得随意一点；务必保留我编辑后的时间和地点”，本人消息原文完整，独立选择区保留17点/北山街/半小时；16:39 模型正确保留这些信息并明确未发送。
- **T3 Features**：`/settings/agents/e2e` 初始 Intelligent UI 勾选；取消并 Save Agent，刷新后仍未勾选（profile v5）。16:40 请求可编辑活动草稿，模型明确当前交互未启用并返回文字。重新勾选保存后，16:42 新请求生成读书会邀请卡片；旧卡片、已提交结果仍在。未指定配置的默认值通过已存在测试 Agent 初始勾选观察，未另建默认配置 Agent。
- **T4 普通草稿与文字继续**：16:42 新读书会草稿编辑为“测试同伴，周一晚上8点线上聊《小王子》，半小时。”，手写“先别发，帮我改得更简短，保留这些具体信息。”，公开原文和选择分开显示，模型返回精简草稿并保留书目、时间、线上形式、时长且未发送。
- **T5 双用户提醒**：`/chat/c_o0bf5oiy`，16:40 通过产品 @ E2E Peer Agent，请其生成周六中午前确认周一读书会提醒。owner 编辑“参加 / 仅本人草稿：我会带茶叶”；独立登录 `ui-peer` 后刷新，仍是空备注和未选项，未泄漏 owner 草稿。peer 提交“不参加 / 同伴有其他安排”，owner 提交“参加 / 仅本人草稿：我会带茶叶”，两条公开选择各归本人。16:41 Agent 分别确认两人的真实选择，只在本群记录，见 [群内分别提交](evidence/review-group-submissions.png)。
- **T6 Global 行程与离线**：16:42 Global 生成周六公园两小时散步/骑行比较卡片。改为11:30、骑行。16:43 仅停止本 checkout Node（CLI 返回 STOPPED），界面离线后点击继续。确认消息持久化、原卡片只读，但没有待处理提示（问题 A1）；摘要显示 `bike`（A2）。随后立刻恢复同一 Node，CLI 返回 pid 12581，界面恢复在线，模型后续处理了11:30/骑行。未停止 IM。
- **T7 Global 提醒与简单文字**：16:44 请求周三前确认读书会报名，Global 生成参加/暂不参加、备注和“仅在本聊天记录选择与备注”按钮。实际选择参加、备注“确认书目后再实际报名”并提交。16:45 请求4+5只给数字，16:46 得到纯文字 `9`；普通 Agent 16:43 同样以纯文字 `5` 回答2+3，没有强迫卡片。
- **T8 替代与 fork**：普通聊天的纯文字 `5` 消息经真实 Branch from here 创建 `/chat/c_uyylfjg0`，复制的交互为 `Historical reply · read only`，输入和继续按钮禁用，公开选择仍可读。返回原聊天，16:45 要求作废精简邀请、以周四前确认提醒替代；新卡片出现后旧精简邀请同样只读、不能点击。Global 对已提交公园卡片的替代请求也返回新提醒，旧卡片保持不可操作；Global 旧卡片的提示仍是已提交，不能据此单独证明替代标识。
- **T9 降级**：仅在浏览器 GET 响应中把 interactive source 替换成未知组件，模拟渲染失败；390×844 显示 `This reply cannot be displayed interactively. Use the text summary above.`，原摘要完整、输入仍可用。移除拦截并恢复正常响应。此项为受控故障注入，不是自然生成损坏数据。
- **T10 重复与明确409**：16:47 从真实 Global 卡片点击“继续审阅草稿”，捕获本次请求，使用同一浏览器会话原样重试，返回201及同一个已提交消息 `5ef6f71e58fa440683d6be1ce4d5960a`；改为不同手写正文、去掉 action_id 再发，实际服务返回409，code `interaction_already_submitted`，同一 submission_message_id。公开消息只出现一次。该409是协议配合验证；UI冲突观察来自 T2，未将 API 输出冒充另一设备提交冲突画面。

## Reference Artifacts Reviewed

已读 `spec.md`、`design.md`、`prototype.html`、共同体验标准、当前 `docs/specs/im/web-chat-ux.md`，并实际查看原型手机截图。以下对照覆盖全部 must-match；字段布局和上游组件外观属于 may-adapt。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype.html 正常/编辑 | 同一回复内摘要在前，选择与主动作相邻 | [桌面编辑](evidence/review-desktop.png)、[窄屏编辑](evidence/review-768-edited.png)、[手机编辑](evidence/review-390-edited.png)、[摘要](evidence/review-390-summary.png)；T1/T4/T5 | 1440×1000 / 768×900 / 390×844 | match；长内容需主区滚动，选择区仍紧邻主动作 |
| prototype.html 编辑/提交/失败 | 即时编辑、本人选择回显、提交卡片只读 | [1440提交](evidence/review-1440-reminder.png)、[768提交](evidence/review-768-reminder.png)、[390提交](evidence/review-390-reminder.png)、[失败](evidence/review-390-failure.png)、[草稿冲突](evidence/review-conflict.png) | 三种宽度；提交与网络失败；T1/T2/T4 | 核心操作 match；离线反馈 deviation A1，选择回显可读性 deviation A2 |
| prototype.html 替代/降级 | 文字仍可读，旧卡片不执行，输入可用 | [替代](evidence/review-390-old-replaced.png)、[fork](evidence/review-390-fork.png)、[降级](evidence/review-390-fallback.png)；T8/T9 | 390×844 | match；历史只读提示较泛化，但不可再提交、正文与输入保留 |

## 问题清单

| # | 严重度 | 现象与用户影响 | 处置 |
|---|---|---|---|
| A1 | major / blocking | Node 离线时点击卡片，只有 `Choices submitted to the Agent`，本人消息无已保存待处理状态；无法判断 Agent 是否已经接手。设计明确要求离线显示消息已保存待处理。见 [离线截图](evidence/review-offline.png)，T6，16:43，Global。 | 交 caller 修复后复验离线提交、恢复处理以及正常提交文案。 |
| A2 | minor | 可见选项为中文“骑行”，公开选择摘要变成内部值 `bike`，确认结果与操作语言不一致，增加回看时的理解负担。见 [离线截图](evidence/review-offline.png) 的活动方式。 | 选择快照展示用户看到的标签，复验单选/多选与刷新历史；不把该词汇问题单独扩大为整体视觉失败。 |

## 验收标准覆盖

### Requirement: Agent 可配置 Intelligent UI — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 默认启用并可关闭 | spec.md / design Features | T3 初始勾选、关闭保存刷新、请求新回复、重开生成新卡片 | T3 具体操作与profile v5；T4真实新卡片 | pass | 既有历史保留；未另建 Agent 验证缺失字段配置分支 |

### Requirement: Agent 按任务需要选择表达形式 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 多种领域任务使用交互回复 | spec.md；M1 R1 | 普通行程/草稿/提醒，Global行程/草稿/提醒，均由真实模型产生 | T1/T2/T4/T5/T6/T7/T8；三宽度截图 | pass | 提示为自然语言任务，无组件名；普通提醒不局限PA |
| 简单回答与自然语言继续交流 | spec.md | 普通2+3、Global4+5；两种Agent手写附带草稿继续 | T2/T4/T7，实际纯文字5/9及未发送结果 | pass | 无额外表单要求 |

### Requirement: 交互能衔接理解、选择与后续行动 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 调整方案后继续推进 | spec.md / must-match 2 | 编辑后按钮继续、手写继续、群记录 | T1/T2/T4/T5，模型正确使用修改 | pass | 纯编辑不产生本人提交消息；手写要求完整保留 |
| 执行有明确对象与实际结果 | spec.md / design离线结果 | 请求仅在群记录；断网失败重试；重复请求与409；离线请求 | T1/T5/T6/T10；离线/失败/群截图 | fail | A1阻塞；A2局部可读性；没有向真人或群外外发 |

### Requirement: 交互回复是可持续阅读的聊天内容 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 离开、刷新与回看 | spec.md / must-match 3 | 刷新恢复草稿、另一页面恢复、双账号隔离、替代/fork只读 | T1/T2/T5/T8；fork与替代截图 | pass | 第二设备为独立页面模拟，同步读取服务端草稿；未宣称真实手机硬件测试 |
| 生成过程与失败 | spec.md / must-match 3 | 观察真实运行过程；网络失败；注入未知组件 | T1/T9；[降级](evidence/review-390-fallback.png) | pass | 旧文字与输入保留，失败未显示成功；一次交付完成卡片 |

### Requirement: 延续现有 Web IM 体验 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 桌面与移动端 | spec.md / 全部must-match | 1440、768、390实际读写、滚动、点击、失败、历史 | Reference表截图、T1/T4/T8/T9 | pass | 不以可点击代替阅读判断：字段/按钮关系清楚，手机主滚动与常驻输入可用；摘要内部值另记A2 |

### M1 reviewer gates

- R1：pass，普通/Global各三类真实卡片及文字、三个viewport均已观察。
- R2：pass，编辑无需模型请求，按钮/手写均带实际状态，公开选择与后续结果分开；重复返回同一消息，实际服务409拒绝不同语义。
- R3：fail，A1离线反馈阻塞。刷新/另一页面/双用户/fork/替代已覆盖；本轮未接入原生App或外部channel，不能声称完成真机或外部渠道验收。公开摘要本身在浏览器降级下已证明可独立阅读。

## 现场与证据边界

- 仅使用 `http://127.0.0.1:58769`，测试账号 nano 与 ui-peer，受授权三条对话及新建分支。没有联系林悦、生产或群外对象。
- Node 已用同一 `.gateway-config.yaml` 恢复，界面在线且后续模型回应；IM未停止。全部浏览器故障拦截已撤销。保留新建测试分支供复查。
- 多页面并行一度出现既有 `Real-time updates are busy` 提示，刷新后能读到消息；关闭多余页面后继续。未据此推断实现根因，也未将忙碌页面上的未刷新状态直接认定交互失败。
- 文本/截图证明的是本次真实模型样本，不承诺所有模型生成稳定性；未改源码、测试、设计或受版本控制配置。

## 上层文档同步

- [x] `SPEC.md`：无需由 reviewer 更新；跨包顶点边界未在本次产品验收中发现新增裁决。
- [x] `docs/specs/im/`、`docs/specs/gateway/`：本 unit 有对应 delta，最终行为需由 orchestrator 修复收口后归并 canonical，reviewer 不改契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。
