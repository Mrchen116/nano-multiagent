# Verification Report: feat-578 UX R1

> Validation snapshot: `5fde316f3c2d9e31984bfbbac41f5ce53af38b53 → ba261e12f5c5bba36e8f513d7a3cce74d3f417cc`

2026-10-06。`verification_mode: corrected-delta`，按 caller 派发的 UX 修正及直接受影响契约核对；不重新验收整个 Full unit。独立执行 `change-verifier`，只读产品源码、测试与现行/active 契约，仅新增指定报告。`requires_full_verification: false`：本轮没有改变共享 Python/Web 业务实现、权限边界或协议，发现的问题可在本轮原生范围闭环。原 Full 全面驗证仍不因该值而完成。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 本轮输入/身份/内容/媒体/列表/群/任务/Work/表单/状态/已读均有实现映射；真实 UI 和设备门槛由 product reviewer 继续执行 |
| Correctness | 2 WARNING：名称草稿在成员移除后仍被覆盖；头像与 Web hash 不等价 |
| Coherence | 原生客户端/复用 API/权限与 secret 生命周期保持；Web 配色继承存在实质偏离 |
| Corrected delta outcome | `implementation-mismatch` |
| Gate status | 本轮静态核对未 pass；不支持 Full 完成、Ready PR、merge 或 waive |

## Scope and evidence

读取了 `docs/README.md`、active `spec.md` / `design.md` / `specs/im/ios-client.md`、三份 `ux-audit-*-r1.md`、`ux-correction-r1.md`、progress、current IM `web-chat-ux.md` / `task-graphs.md` / `agent-work.md`、测试与证据规范及本轮所有产品 diff。current 文档作为被复用业务契约，active delta 仍是目标状态，未归并成 current。

- Native 回归：复用 caller 在修正后、冻结前执行并在 `ux-correction-r1.md` 记录的实际原生日志 `/tmp/nano-feat578-ux-batch-tests3.log`。日志可直接核实命令 `xcodebuild -project src/IM/ios/NanoIM.xcodeproj -scheme NanoIM -destination 'platform=iOS Simulator,id=861AD10A-8A44-4028-8A4A-29CF1308E25D' -derivedDataPath /tmp/nano-ios-build -disableAutomaticPackageResolution -onlyUsePackageVersionsFromResolvedFile test`，2026-10-06 20:41：23 XCTest、10 Swift Testing、0 failure、`TEST SUCCEEDED`。xcresult `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.06_20-41-10-+0800.xcresult`。日志本身未嵌 commit SHA，其候选归属来自 caller 的冻结交接与修正记录；不能把测试成功扩张为 UI 或物理 IME 通过。
- 静态 diff：冻结 range 的 `git diff --check` 通过。原生未 import Python kernel/product 包，改动仍通过 `IMClient` 使用现有 API。没有新增 iOS 后端、WebView、后台推送或任务写入权限。
- Docs：在写完本轮两份报告后，用主仓现有 `/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs_check.py` 独立执行，297 maintained sources / 75 routes 通过；不从文档完整性推导产品完整性。worktree无自己的`.venv`，系统python缺yaml的前置尝试未通过，后续复用了仓库既有环境，没有安装依赖。原 Python4120/Web808 证据仅在其此前有效 scope 保留，因为本轮这些源码未变化。
- 独立额外确认仅做头像算术对照，无 Simulator/phone 或真实业务 mutation。结果在 `code-review-ux-r1.md`，可用记录的短算法重现。

## Correctness and completeness mapping

`静态对齐`表示实现/调用链成立，不表示产品体验通过；UI/权限/设备的退出证据须由相应 owner 提供。

| 契约/本轮修正 | 实现定位 | 回归/直接证据 | 状态与边界 |
|---|---|---|---|
| S7 与 delta“聊天输入和身份延续 Web 体验”：@/slash、保留前后文、仅预填 | `ChatText.swift:61-80`; `ConversationView.swift:166-210,212-257` | `ChatTextTests.swift:29-47` 覆盖 emoji UTF-16 caret、正文后缀、非触发/选区、slash | 静态对齐；新冻结包软件键盘/中文 IME/焦点仍须实际复验 |
| 提及目标稳定、前缀/同名不任意路由 | `ChatText.swift:15-43`; 发送调用 `ChatStore.swift` 的 wire 转换 | `ChatTextTests.swift:6-27` 覆盖群命令目标、人名、email、同名回退到 actor ID | 静态对齐；不增加新 mention wire/schema |
| S7 同名跨页固定配色、聊天改名不变对方头像 | `CommonViews.swift:36-68`; `ChatModels.swift:27-31`; ChatList/Message/Info、Agents/Profile、RootTabs 调用 | peer 名来源不依赖 chat.title；独立 hash 对照 | **WARNING V2**：原生页内一致，Web 实际配色算法未继承 |
| S9 可见复制，S10 图文顺序 | `ConversationView.swift:55-58`; `MarkdownView.swift:17-81,125-133` | `MarkdownContentTests.swift:7-17,19-42` 覆盖交错/链接内图、粗体、列表/表格/链接/代码；ChatText display 覆盖结构 mention | 已修正正常段落与引用/列表中的图文顺序及整条正文复制；没有宣称所有复制入口提示都已改造 |
| S10/S11 可辨认待发图片/状态，授权读 | `ConversationView.swift:126-164`; `UI/MediaViews.swift:4-35`; `IMClient.swift:36-40` | 成功项走受会话约束的 ProtectedImageView；上传/失败项使用已持有 data；移除不发送 | 静态对齐；实际选择/取消/失败/失权分支仍由产品/设备验收补齐 |
| 建聊直接入口、联系人搜索/加载/零匹配、空群名 | `ChatListView.swift:55-69,94-129`; `ChatStore.swift:20,138` | search 匹配名称/Agent ID/user ID/设备，空群名取所选姓名，创建仍单请求 | 静态对齐；未改变创建/访问权限 |
| 群多选单次提交、名称草稿及返回 | `ChatInfoView.swift:19-24,57-84,97-114` | selection Set →一次 participants请求；取消清选择；偏好 PATCH 只更新已提交title；添加成员保留title | **WARNING V1**：成功移除成员仍丢未保存名称 |
| S14 真实祖先、选定候选、关系含义 | `TasksView.swift:77-96,114-117,139-142` | ancestor 根据 container_id，按钮更新 browsingScopeID；selected_candidate_id 明示；图例按 plan/explore | 静态对齐；现有服务拒绝循环容器，不新增防御图遍历；三层/深链 UI 验证不由源码替代 |
| Tasks 加载/查询无结果 | `TasksView.swift:20,34,58` | initial loaded 与 loading 分离，非空query有独立提示 | 静态对齐；未更改任务查询/分页协议 |
| S15 Work语义与待授权展开 | `AgentWorkModels.swift:13-24,38-40`; `AgentWorkView.swift:23-39,104-131` | 实际 trigger/origin决定语义；技术信息折叠；online waiting_permission自动展开 | 静态对齐；离线仍显示unknown且不可审批；真实待授权UI继续由reviewer核实 |
| 账号/设备/策略dirty离开和顶部保存 | `CommonViews.swift:101-115`; `MeView.swift:119-120`; `SettingsNodesView.swift:106-107`; `SettingsPoliciesView.swift:61-62` | 默认back改dirty确认；保存沿用真实条件与API；取消dialog继续保留草稿 | 静态对齐；真实返回/大字体/键盘可达仍待UI复验 |
| S16 创建主操作、S17备用模型收放 | `AgentsView.swift:158,200-204`; `AgentConfigView.swift:160-174` | 顶部创建共用canCreate/原创建逻辑；备用模型DisclosureGroup不删字段或顺序 | 静态对齐，不引入新的模型/节点能力 |
| S20 通道cancel保护及secret生命周期 | `AgentChannelsView.swift:120-123,155-179` | 普通dirty确认/禁止滑走，secret仅SecureField内存、提交/离开/后台清空；keep/replace与revision未改 | 静态对齐；秘密不写持久草稿或报告 |
| Agent详情公开状态重读 | `AgentsView.swift:71-76,119-130` | paginated contacts(kind:agent)按stable user_id匹配；失败说明最后已知，保留公开/owner管理边界 | 静态对齐，未把在线未知推导成执行成功 |
| S27 提醒来源且不暴露正文 | `NanoIMApp.swift:163-173`; `ChatStore.swift:104-109` | 已授权list提供title/peer头像；选定聊天/静音/自发/历史floor沿旧条件 | 静态对齐；真实两聊天提醒及前后台分支不因此通过 |
| S6 实际viewport已读 | `ConversationView.swift:63-81`; `ChatStore.swift:171-176` | global row frame与实际ScrollView viewport交集，排除lazy仅onAppear；selectedID限制真实read请求 | 静态对齐；长历史/Latest/键盘重排与权威未读需产品复验，S6仍开放 |

## Coherence / reference contract

| Design决定 | 核对 |
|---|---|
| 原生SwiftUI/必要UIKit、AST渲染，全部管理入口保留 | 本轮沿用既有实现；没有引入容器或新后端 |
| Feature store持有草稿；界面不因reload丢存活草稿（design:77,90） | V1尚未成立；需修复成员移除后读取 |
| 通道secret不是可恢复普通草稿（design:88） | 保持，仅普通dirty确认改善离开语义 |
| Web六色配色、同名同色、私聊对方身份（design:119） | 对方身份/原生同名同色已接线；V2为算法偏离 |
| P1–P6与M1-W2真实SwiftUI/viewport/字体/键盘证据 | 本轮独立product复验另行执行；早期20:24 dirty安装报告不能证明冻结候选。旧P6不覆盖用户本轮否定范围 |
| M1-R1 S1–S30、M1-W3无费安装/续签/到期恢复 | 未重新评审或豁免；仍保留caller明确列出的未完成分支 |

## Issues

### CRITICAL

本轮受影响实现范围未确认新的CRITICAL。该值不清空原Full未完成退出标准。

### WARNING

- **V1 — 群改名草稿被成员移除刷新覆盖。** `ChatInfoView.swift:114` 成功路径调用 `load()`，`:94`无条件重置title。契约是design:77,90的存活草稿，以及本轮修正的群名称保护。按本轮添加成员已采用的保存/恢复语义处理成员移除刷新，并从“未保存改名→移除成员成功”的真实路径或最低合适行为seam核验；不要静默改契约允许丢失草稿。
- **V2 — Web配色hash与原生不等价。** `CommonViews.swift:49-50` 每步回绕，Web `avatar.tsx:22`仅移位回绕。正常名称Personal Assistant索引分别4/0；见独立运算表。对齐Web实际算术，并保留一个代表该差异的行为保护/真实对照。该问题是明确设计偏离，不是主观视觉评分。

### SUGGESTION

无。未将审视报告中的pending发送模型、原任务来源返回、自动顶部历史分页等尚未定为本轮实现目标的建议机械升级成新阻塞。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/im/ios-client.md:17-21` 输入直接候选、焦点/正文保留、仅预填、附件菜单 | ChatText caret与Conversation candidate/UIKit接线 | ChatTextTests; 早期实际候选证据仅retained其原scope | aligned（实现契约层；实际新包/物理IME仍待验） |
| 同一delta的固定头像及私聊身份，active S7/design:119 | peer identity来源成立；palette算法不等价 | 独立算术对照明确不同正常名称 | implementation-mismatch |

### Uncovered Observable Behavior

本轮其余外显修正（消息时间/可见复制/图文/待发预览/列表状态/群多选/任务路径/Work摘要/表单保护/公开状态/提醒/viewport）均可映射已有S6/S9-S11/S14-S17/S20/S24-S27、current复用契约与既有design Feature store/原生视图决定；无需为UI改善复制全套业务契约。V1是本轮涉及流程的实现遗漏。未将三份审视的未实施提案写成自动通过的新目标。

Outcome: **implementation-mismatch**。冻结候选待上述有限修正与关联窄复验。旧 Full **S2/S6/S9/S10/S21/S27/S29/S30**仍有未完成分支。物理原版免费安装、信任、HTTPS登录、唯一peer42是各自有限事实，不代表中文IME/全部UX/同网刷新或自然到期恢复。未建议Ready PR、merge、豁免或部署。
