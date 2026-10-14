# feat-604 — 产品验收报告

## Round 1

- mode: full；revalidation_mode: full；日期：2026-10-14。
- Validation snapshot: `9ebe12f8553a593f6179784b0276849fb14e5358 → a2f3a66688e3bc1e17920f2976506bf1d222bc16`。
- 树与运行：验收前 HEAD 精确匹配 validated_at，工作树干净；初始 IM PID 23516 的 cwd 已核实为本 worktree。使用交接的真实 dist（index.html 构建时间 11:33:10），直接由 19765 IM 提供。没有改源码、测试、设计或受控配置，没有继承实施者的通过结论。
- 入口：真实 `/settings/account`、`/settings/policies`，并实际进入 `/settings/nodes`、`/membership`、`/settings/company`、`/onboarding`。Cua 独立临时标签，桌面 1280×720/800、390×844、320×740。

## Verdict

**fail — S7 后台重新读取与草稿/保存交错的必要产品证据尚不足（inconclusive）。**

已实际观察的整体信息架构、视觉层级、角色分流、输入校验和真实停服恢复可交付；不能据这些成功推定后台刷新保护通过。产品实测确认缺陷 0 项；阻断的验收证据缺口 1 项。最高所需动作：补齐 S7 的可控后台刷新产品验收；caller 已通知另有独立代码审查发现，应由其统一裁决修复范围，本报告不把该静态发现记成产品复现。

## 用户旅程体验

账号页先呈现头像、显示名和 @用户名，资料编辑位于同一阅读区，ID/加入时间折叠到账号详情。空间资格和电脑摘要在独立区块，资料保存不会暗示改变成员资格。实际从账号进入电脑页，后者保持设备清单、版本、离线说明及管理动作，账号没有重复这些内容；与电脑页的浅背景、白色表面、青绿色动作和标题节奏一致。管理员只有一台电脑时不突出首次设置；零电脑成员能通过键盘进入助手设置。

策略页先让管理员判断实际容量，再进入明确标注“尚未接入执行”的预设。实际初始值 1.7 GiB / 10 GiB、剩余 8.3 GiB；展开后成员满额文字与管理员可上传状态可分别辨认。插入本次临时 reserved fixture 后，实际读到 10 GiB 占用、1.7 GiB 已用、8.3 GiB 上传中、0 B 剩余，以及上传暂停但文字聊天仍可用的提示。只读成员显示文字值，没有灰色输入表单、容量卡或保存条，因此权限与阅读任务一致。

手机保持单栏，320px 英文长文自然换行，底部导航、末尾字段和操作均可触达。390px 中文长表单真实停服时，失败提示与“放弃修改 / 保存策略”同时可见；320px 英文账号失败也在当前保存区域给出错误，用户无需返回页首。英文容量说明在 320px 与刷新按钮并排时换行较多，但读数、满额警告和主要操作清楚，没有形成阻断。实际 Tab/Enter 可聚焦并触发放弃修改及助手设置入口；输入有标签，实际状态 DOM 补充检查为 role=status。本轮没有声称完成 VoiceOver 朗读验证。

### 实际操作记录

1. 管理员显示名由 `Alex Chen · 设计测试` 改为 `陈晓 · 产品验收`，保存反馈出现，顶栏同步；刷新后保留。展开账号详情可见用户 ID 与加入时间。
2. 显示名纯空格立即出现有效值提示、保存禁用；放弃恢复原值。策略空白模型、留存 0 分别出现原位错误并禁用保存；放弃恢复。后续键盘放弃把留存 34 恢复到已保存的 32。
3. 策略留存改 32，SIGSTOP 本次 IM 后提交，字段/放弃/保存均禁用且显示保存中；对同一进程 TERM+CONT 使真实请求失败，32 保留，底部出现重试提示。恢复相同 DB/secret 服务，点击保存成功，未保存状态退出。
4. 停服时点击刷新用量，容量变为明确失败及重试，预设草稿仍可编辑；恢复后重试重新显示用量。另从 Me 的真实客户端导航进入账号/策略，分别观察资料读取错误与两个独立策略/容量重试入口；恢复后策略和容量 Retry 成功。
5. 320px 英文账号改 `陈晓 · 恢复验证`，真实停服后保存失败仍保留内容；恢复服务后重试成功。
6. 分别登录 member604/private604/pending604/suspended604：admin 为管理员；member 为有效成员、个人空间未启用；private 为个人可用且未加入；pending 为个人可用且待批准；suspended 为个人可用且团队停用。未加入与待批准入口实际进入对应 membership 页；私人继续使用返回账号页。管理员实际进入成员管理。未进行真实审批/停用操作。
7. 只读 member604 在 320px 英文查看分组文字预设。账号零电脑摘要提供管理电脑和助手设置；实际 Tab/Enter 进入 onboarding。

## Reference Artifacts Reviewed

独立观察真实产品后，打开 design 指向的 `prototype.html` 桌面账号/策略画面。以设计契约而非逐像素一致性裁决。

| Reference | Required contract | Actual product evidence | Viewport / state | Conclusion |
|---|---|---|---|---|
| prototype.html 账号；design 身份/空间/关联管理 | 主操作明确，身份/资格/设备职责分开 | 下列账号/停用截图；操作1、6、7；实际电脑页 | 桌面、390、320；五类身份、零/一电脑 | match |
| prototype.html 策略；design 容量与分组预设 | 实际占用与未生效预设可辨认，成员明细按需看 | 满额、只读及桌面截图；操作3、4；临时 reserved fixture | 桌面、390、320；正常/满额/未知/只读 | match |
| prototype.html 保存区域；design 编辑反馈与恢复 | 输入不丢、错误有位置、结果可感知，包含后台更新 | 账号失败截图；操作2–5 | 390中文/320英文真实停服失败与重试 | **inconclusive**：通常失败恢复 match；后台 GET 与草稿/保存交错未独立观测 |

### 代表性画面

- [320英文账号](M1-settings/evidence/review-r1/review-account-320-en.png)
- [390英文账号](M1-settings/evidence/review-r1/review-account-390-en.png)
- [320英文账号真实保存失败](M1-settings/evidence/review-r1/review-account-failure-320-en.png)
- [320英文满额与上传中](M1-settings/evidence/review-r1/review-capacity-full-320-en.png)
- [桌面英文策略](M1-settings/evidence/review-r1/review-policies-desktop-en.png)
- [320英文只读策略](M1-settings/evidence/review-r1/review-readonly-320-en.png)
- [320英文停用资格](M1-settings/evidence/review-r1/review-suspended-320-en.png)

## 问题清单

| # | Severity | Regression relation | 期望 / 实际 / 证据 | Recommended action | Action rationale |
|---|---|---|---|---|---|
| R1-G1 | blocking（验收证据） | unclear | S7要求后台重新加载不丢草稿；实际已观测两页真实失败/重试及策略挂起锁定，但没有独立证明后台 GET 返回发生于编辑中或 PATCH 成功之后。见操作3、5。 | 补齐可控后台重新读取的产品验证；若已按独立代码审查修复则在新 validated_at targeted 复验 S7 | 必验场景的部分成功不能代替剩余条件；不是已复现产品缺陷 |

无额外 Side Findings；不因主观间距偏好阻塞。

## 验收标准覆盖

| Scenario | 期望来源 | 实际验证与证据 | 结果 |
|---|---|---|---|
| S1 身份与资料编辑 | spec S1 / design 决策1、4 | 操作1；身份、详情、顶栏同步、刷新保留；账号截图 | pass |
| S2 电脑管理与空状态 | spec S2 / design 决策1 | 管理员一电脑摘要→真实电脑页；member零电脑→onboarding；操作7 | pass |
| S3 团队资格 | spec S3 / design 决策2 | 五身份实际登录；资格/个人空间区分；membership和管理员成员管理入口；操作6 | pass |
| S4 容量与预设分层 | spec S4 / design 决策3 | 正常、展开、上传中满额 fixture、三组预设及不执行声明；满额截图 | pass |
| S5 只读成员 | spec S5 / design 决策5 | member604真实登录、文字值/无保存/无容量；只读截图 | pass |
| S6 放弃与合法输入 | spec S6 / design 决策4 | 空白名称、空白模型、留存0原位错误/保存禁用；两页放弃；策略Tab/Enter放弃 | pass |
| S7 保存失败与后台刷新 | spec S7 / design 决策4 | 两页失败重试、策略提交锁定均通过；后台GET交错证据不足，R1-G1 | **inconclusive** |
| S8 加载与容量故障 | spec S8 / design 决策5 | 真实停服+客户端导航，资料/策略/容量均出现局部错误和Retry；容量失败不挡预设；恢复Retry成功 | pass |
| S9 桌面、手机与语言 | spec S9 / design 决策6 | 桌面中文两页及电脑参照、桌面英文策略，390中文策略/英文账号、320中文策略/英文两页；真实截图、键盘Tab/Enter、标签及status语义；320实际DOM宽度320辅助确认 | pass |

## 环境与清理

- 只操作 `/tmp/nano-feat604/im.sqlite3` 和本次隔离IM。reserved容量fixture `review604-reservation` 已删除恢复原容量数据；没有改原角色或设备。
- 测试管理员显示名现为 `陈晓 · 恢复验证`，策略留存32天（真实产品保存结果）；其他字段保留。
- 原IM23516因故障验证已停止，恢复服务当前PID **32125**，同cwd/DB/secret/19765；交回caller继续复验，不能清理生产进程。
- reviewer自己的临时标签已关闭，viewport override已reset。截图为本报告必要证据，不包含secret。
- 没有提交；按caller要求只交回报告和小型截图。

## 上层文档同步

- [x] `SPEC.md`：无需更新，未改变跨包架构。
- [x] `docs/specs/im/auth-tenancy.md`：**需要更新**，当前长期契约尚未含本unit界面职责/预设语义/恢复体验增量，由orchestrator最终校正并归并delta-spec。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## Round 2 — S7 targeted revalidation

- 日期：2026-10-14；mode=full；revalidation_mode=targeted。
- Validation snapshot: `9ebe12f8553a593f6179784b0276849fb14e5358 → 49795346290faadb5039fb1b371db5f6d145562a`。
- fix_delta: `a2f3a6668..497953462`；focus：S7 / R1-G1；prior：本报告 Round 1。
- 开始时 HEAD 精确匹配、工作树干净。新 dist/index.html 构建时间11:51:00；继续由同一 worktree IM32125提供。只读核对差异文件列表与caller的修复边界，没有读取产品源码定位问题。

### Verdict

**pass**。R1-G1 已通过真实后台 GET 的可控返回顺序补齐；当前未解决问题0，最高所需动作pass，无需再次产品复验。

本轮独立验证两页编辑中后台返回不丢草稿，以及较早读取在保存成功之后返回不会让已保存值回退。结合R1的真实保存失败/重试与提交锁定证据，S7完整通过。用户可见的新值、成功反馈、禁用保存和刷新后的持久化结果相互一致，修复没有在这条旅程中引入新的理解或操作负担。

### 方法与边界

IAB旧句柄不可用，浏览器扩展连接也失败；按runbook使用Cua native API新建专用Chrome无痕窗口，内含产品19767和同源health两个本地标签。使用真实Ctrl+Tab切出切回触发页面可见性变化，没有注入脚本、调用React或QueryClient、修改DOM状态。

19767是caller准备的透明传输fixture，产品资产/API/WS均转发同一19765 IM；只暂扣下一次指定GET的真实响应。每组都先通过fixture state确认`held`目标路径，按预定顺序release。保存后的场景，必须先记录PATCH200、浏览器成功状态，再release旧GET。本轮只证明本地客户端的竞态恢复，不作为代理或生产安全验收。

### 实际顺序与结果（UTC）

| 路径 / 顺序 | 已捕获的实际事件 | 浏览器观察 | 结果 |
|---|---|---|---|
| 账号：编辑中返回旧GET | arm03:57:43.442；held `/im/v1/me` 03:57:49.077；release03:58:02.925 | 草稿`S7 Draft Protected`仍在输入框，身份摘要仍是尚未更改的`陈晓 · 恢复验证`，`Unsaved changes`和保存动作保留 | pass |
| 账号：保存后返回旧GET | held03:58:21.589；PATCH200 03:58:52.034；确认`Changes saved.`后release03:59:09.975 | 输入、身份摘要、顶栏均为`S7 Draft Protected`，旧GET返回后不回退，保存禁用；Cmd+R后仍为新值并显示`No changes` | pass |
| 策略：编辑中返回旧GET | held `/im/v1/policies` 03:59:30.426；release03:59:43.100 | 原留存32，编辑值37在旧GET返回后保留，`Unsaved changes`与保存动作保留 | pass |
| 策略：保存后返回旧GET | held03:59:56.723；PATCH200 04:00:29.518；确认`Changes saved.`后release04:00:46.304 | 留存37与成功反馈保留，保存禁用；Cmd+R后仍为37并显示`No changes` | pass |

PATCH响应并非即时到达，两次分别在held后约30秒和33秒出现；等待期间真实页面显示Saving并禁用字段/放弃/保存。没有在PATCH200之前提前释放，未把此次等待时间归因成产品缺陷。

### Reference Artifacts Reviewed

| 契约 | 本轮真实产品依据 | 结论 |
|---|---|---|
| design编辑反馈与恢复must-match：输入不丢，结果可感知，后台更新保护 | 上表四条真实顺序；[账号旧GET释放后](M1-settings/evidence/review-r2/r2-account-after-old-get.png)、[策略编辑中返回](M1-settings/evidence/review-r2/r2-policies-draft-after-get.png)、[策略旧GET释放后](M1-settings/evidence/review-r2/r2-policies-after-old-get.png) | match；R1的inconclusive闭合 |
| 身份/空间/关联管理must-match | 保留R1五身份、零/一电脑与真实导航证据，修复未改变该契约 | match retained |
| 容量与分组预设must-match | 保留R1正常/满额/未知/只读实际画面与操作证据，修复未改变该契约 | match retained |

### 场景继承与最终覆盖

| Scenario | 本轮处理 | 最终结果 |
|---|---|---|
| S1 | 保留R1身份/详情与保存刷新证据；本轮补充保存后旧GET返回及再次刷新 | pass |
| S2 | 保留R1一电脑真实电脑页/零电脑助手设置旅程；不受保存竞态修复影响 | pass |
| S3 | 保留R1五类真实身份、membership返回和管理员成员入口；权限/导航未变 | pass |
| S4 | 保留R1正常、上传中、满额与分组预设证据；容量/信息层级未变 | pass |
| S5 | 保留R1真实member只读值、无保存/容量；角色呈现未变 | pass |
| S6 | 保留R1无效输入/放弃/未变禁用证据；校验与放弃未变 | pass |
| S7 | 本轮四条后台读取顺序补齐；保留R1两页真实失败重试；本轮再次观察两页提交锁定 | pass |
| S8 | 保留R1资料/预设/容量真实停服错误和恢复；局部读取失败呈现未变 | pass |
| S9 | 保留R1桌面/390/320中英文、键盘/标签/status证据；布局文案和导航未变 | pass |

### 交回与同步

- 两页当前测试数据：显示名`S7 Draft Protected`，留存37天；均通过真实UI保存并刷新确认。
- fixture state最终armed=null、held=null；无暂扣请求。IM PID32125、proxy PID37001继续运行交回caller，没有重启服务。
- 专用Chrome无痕测试窗口及其两个本地标签保留，供caller接续；没有导航/关闭用户既有窗口或标签。native窗口没有IAB markHandoff接口，故通过保留窗口交接。
- 上层文档同步结论保留R1：auth-tenancy需要由orchestrator最终归并，其余无需更新。
- 只追加本报告与三张截图，未提交；无新增issue、无产品/测试/设计/受控配置修改。
