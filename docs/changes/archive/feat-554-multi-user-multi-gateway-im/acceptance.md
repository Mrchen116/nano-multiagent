# feat-554 — 独立产品验收

## Round 1 — full

> 对齐：[spec.md](spec.md) 全部 18 个 Scenario、[design.md](design.md) 原型 must-match 与既有能力承接矩阵、[reviewer-runbook.md](reviewer-runbook.md)。
>
> Validation snapshot: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4 → 1f14e77dbfb6461dd7700c631802f2d71884af76`
>
> 验收时间：2026-09-14；reviewer：独立 product_review；mode：full。

### Verdict

**fail**。Highest Required Action：**fix-implementation**。共 5 项实际问题（4 major、1 minor），另有未完成的必验覆盖，需 targeted 复验。没有创建外部 issue。

主要协作路径已能完成：无设备账号找人和 Agent、跨账号消息、跨管理归属的群内交办、群成员批准、聊天隔离、公开 Work 主执行及子执行。当前版本仍存在私聊标题误认、手机设置缺项、配置生效提示缺失及全局 Agent 图片交付失败。不能据已通过的主路径宣称全部原有功能已回归。

本轮只记录上述运行版本。验收期间 owner 提交了后续修复，未将这些提交当作本轮已验证内容；IM 更新窗口开始后的结果归入后续轮次。

### 环境与证据边界

- 专用真实栈：`http://127.0.0.1:50563`，运行根 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat554-review-blaj_fyd`。IM、三 Gateway、模型代理、HTTP/WS 均为真实链路；没有 mock SDK/LLM 或拦截网络响应。
- A 小陈：A1 上 Iris（single_thread）、Atlas（global），A2 上 Nova（global）；B 小李：零设备；C 小王：C1 上 Muse（single_thread）。另从真实注册表单创建零设备用户 `review新同事`。使用独立 `feat554-review-a/b/c/d` 浏览器 session，与 owner 的浏览器隔离。
- 实际 Agent ID 为 `feat554-iris/atlas/nova/muse`。本轮未把示例名字替换成真实产品能力。
- 前端构建来源 `58c86434d`，到 validated_at 的前端源码 diff 为空。专用运行根 `frontend-build.json` 保存构建目录、validated_at 与产物 SHA256；`launch.py` 指向对应 dist。临时 bootstrap 仅把现有 Skill/config 运行根 seam 指到 runtime/shared，未改 HOME 或日常 Skill 根。
- 截图均在 unit worktree 的 `output/playwright/`，不提交二进制、凭据、数据库或运行日志。下文以此目录为截图相对根。浏览器原始快照也保留在 `.playwright-cli/`；报告摘录真实对象 ID 和结果以免只依赖临时截图。
- 原型通过只读 `http://127.0.0.1:18554/prototype.html` 查看，桌面 1440×960、手机 390×844；真实产品另外检查 767/768px 导航分界。原型测试条及假数据不当作正式产品要求。
- C1 的离线与恢复由 owner 控制；A1/A2/IM 保持运行。没有停止用户服务或日常 Gateway。真实旧数据转换按用户指定留给部署 agent，本轮没有实施迁移或编写兼容代码。

### 用户旅程体验

**J1：新同事与跨账号私聊。** B 无 Gateway 可直接打开 New chat，搜索小王显示 Person，搜索不存在的 `review-nobody-undefined` 显示 No contacts found，未创建错误会话。B→C 私聊 `c_d8u24y7n` 双向发送 `review-b-to-c` / `review-c-to-b`，刷新保留且发送者正确；但 C 的标题、侧栏与输入提示显示小王自己（I1）。独立注册的新用户可在空聊天页直接查到人及四个 Agent。证据：`review-human-dm.png`、`review-mobile-contacts-new-user.png`、`review-empty-nodes.png`。

**J2：多设备归属与离线。** A 的 Nodes 显示两节点和对应 Agent，B 显示零设备，C 只有 C1。A 在 Nodes 保存 A1 别名 `review-A1`，聊天/联系人仍显示原节点 ID（I2）。B 看 Nova 公开资料只有资料、发消息及 Work，不能进入完整 Config；用实际 B JWT 对 Iris Config GET 与合法 PATCH（profile_version、display_name、group_reply_policy）均为 404，对 A1 节点 PATCH 也是 404。C1 单独断开后末次 Heartbeat 保留，Muse 离线，C 仍可向 B 发人际消息，B→Nova 收到 `review-Nova仍在线`。C1 恢复后 Muse 再次真实回复。证据：`review-nodes.png`、`review-c1-offline.png`、`review-offline-other-node-works.png`。

**J3：三人混合群及个人状态。** A 用建群 UI 创建 `c_qanmoqrx`（最初 `review-协作项目`），选 B/C/Iris/Atlas；C 再从群设置添加自己的 Muse，三身份见同一组六成员。B @Iris 得到 `review-iris-确认 / 发起人：小李`，A @Muse 执行真实任务。B 把群改名为 `review-群名已修改`，C 刷新同步；B 设置 pin/mute 后 C 的对应设置仍为 false。B 移除 C 时，C 正打开的群设置和聊天立即清空；移除后新消息 `review-移除后仅剩余成员可见的消息-0948` 在 C 重载后不可见，DOM 的群、该消息、composer 均不存在。随后由 B 重新添加 C 继续配置验收。另建纯人群 `c_fkphyq4g`，发消息后仅创建者 A 有 Dissolve group，B 只有 Leave group；A 确认解散后 B 的群、消息、composer、dialog 同时清空。证据：`review-create-group.png`、`review-mobile-group.png`、`review-member-removed.png`、`review-group-dissolved.png`。

**J4：群成员批准与重复决定。** A 在上述群要求 Muse 向其隔离 workspace 的 `.gitconfig` 写验收哨兵。B 既不是管理者也不是发起人，仍看到 Allow once / Deny / Allow for session 并实际点击 Allow once；C 随即见相同已批准结果。实际文件内容与工具轨迹吻合。原 message `90c8a18f4c91493cb7ca8c265757adb4`、request `42862b10-cffa-4c18-bea3-c43eb9bbe412` 持久记录为 allow_once，decided_by 为 B。随后 A 对同一请求提交 deny，HTTP 200 返回的仍是 B 的同一 allow_once 决定，未改变结果，轨迹只有一次 write。未独立完成 IM 重启中的并发/重连闭环；该项保持 inconclusive，不能用 owner 正在执行的旅程替代。证据：`review-approval-pending.png`、`review-mobile-approval-resolved.png`。

**J5：私聊与公开 Work 的两种可见性。** B 从 Nova 资料发消息进入普通私聊 `c_29l7m2vr`，要求子 Agent 计算 17+25，真实回复 42。C 非管理者、非聊天成员仍在 Nova Work 展开主轮次 `turn_003912999cd8d5fc`，看见完整私聊输入及工具结果；关联子执行 `sess_0d132ffd45549ada` / `turn_341f99f270e2135a` 的双向计算和 42 也完整可读，刷新后保留。原消息链接指向该私聊；C 打开该目的地无法读历史，返回 Work 后记录仍可见。对私聊详情、messages 和保护附件 `4d1a117a7b854df694cf76538dffd1a5` 的真实请求：B=200，A=404，C=404，无凭据=401。Agent 管理者 A 也不能借管理归属读取 B 的私聊。证据：`review-nonmember-work-main.png`、`review-nonmember-work-child.png`。

**J6：两种模式的原能力。** Nova 的真实子 Agent、bash、send_message 过程没有产生人工批准卡；完整过程在 Work 中，消息附加 View Work 入口。Iris 的 single_thread 过程继续内联、已完成 direct 回复可 Branch from here。A 的普通 Iris 聊天 `c_kqn7i8hc` fork 为 `c_tm2ws7fd`，原聊天与新分支分别保留。对这两段 idle 来源从侧栏 Generate skill 分别选 agent/global scope，真实 preflight 后新建 `c_58z4d217` / `c_vjbuytuz`，原样预填且尚未发送时 No messages yet，没有自动执行。手动发送后，agent 范围实际创建 `review-agent-checklist-0941`（3478 bytes），路径在 A1 Iris 的 `.nanoassistant/skills/`。global 范围初次模型认为 fork 来源重复而不新建；随后按用户补充指令把已存在内容创建为 global `review-global-checklist-0943`（3749 bytes），路径在专用 runtime/shared/.nanoassistant/skills，原 agent 版本仍在。两次均有真实 skill_manage 成功及 skill_view 回读；不声称 initial global distillation 首次就创建成功，也不把 fork 说成两份独立观察。证据：`review-distill-agent-prefill.png`、`review-distill-global-prefill.png`、`review-agent-skill-created.png`、`review-global-skill-created.png`。

**J7：设置、语言及保留入口。** B 在混合群输入 `/` 可见动态命令、`/effort` 和已启用技能；两个节点同名 Skill 保留两行，同节点 Iris/Atlas 的相同位置合并来源 Agent。C 的 Muse 管理页保留 Overview/Config/Channels/Skills/Sessions 五入口（single_thread 无 Work），Overview/Sessions 显示原空态，Config 完整表单与 Prompt Preview、Heartbeat/Cron 等入口仍存在，Channels 有 Add 入口。英语切中文后立即重绘，重载语言保持，消息内容不翻译；切语言时 textarea 中 `review-切换语言草稿` 保留。桌面 UserMenu 的线条图标、红色退出与 EN | 中控件保留；手机语言独立一行、原分段按钮保留，但缺系统策略入口（I3）。390px 聊天隐藏底栏、返回列表恢复；767px 只有手机导航，768px 只有桌面顶栏，未重现上下双主导航。证据：`review-member-slash.png`、`review-owner-sessions-empty.png`、`review-desktop-menu.png`、`review-mobile-me-zh.png`、`review-me-767.png`、`review-me-768.png`。

**J8：配置边界与图片交付。** C 在 Muse Config 保存 custom instructions 标记 `review-boundary-0950`，B 在 A 创建的群要求 `review状态`，Muse 确实回复新标记，证明使用新配置；A 刷新聊天仍未见配置生效的独立系统提示（I4）。B 粘贴自制 120×60 左黄右绿 PNG 到 Nova 私聊，发送、预览及权限读取正常；Nova 正确识别颜色。首次要求“原样复制输入图片”导致模型长时间寻找路径，owner 用 /stop 停止；此要求超出了本轮需证明的输入消费方式，不据此认定产品故障。随后明确只在 workspace 新生成 PNG 并正常回传，message `9719207524cb4bc8b4f52654d5df3209` 的图片仍指向 `/private/var/.../nova/.nanoassistant/exports/review-generated.png`，naturalWidth=0，页面实际破图（I5）；输入图片 naturalWidth=120。证据：`review-config-adopted.png`、`review-global-generated-image.png`。

### Reference Artifacts Reviewed

以下对照的是原型信息层级、入口与操作资格；字号/间距不作逐像素判断。`review-reference-desktop.png` 与 `review-reference-mobile-me.png` 是本轮实际打开原型的参考截图。已目视核对关键产品截图，单独存在一个按钮不代表对应深层操作通过。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype 新聊天；design must-match 1 | 人/Agent 可辨认、零设备可用、无结果不误建聊天 | J1；review-mobile-contacts-new-user.png；review-human-dm.png | 1440×960、390×844；新账号空聊天、联系人搜索 | 联系人搜索 match；私聊标题 deviation（I1） |
| prototype 建群/成员；must-match 2 | 选择人及自己的 Agent，空选择禁用，跨管理归属共同成群 | J3；review-create-group.png | 1440×960；空/已选、C 加自己的 Muse | 桌面及真实群结果 match；手机建群底部弹层未独立补齐，inconclusive |
| prototype 群时间线；must-match 3 | 发送者、Gateway、在线状态明确，群内实时回复 | J2/J3；review-mobile-group.png；review-c1-offline.png | 桌面/390×844、多 Gateway、C1 离线 | 身份与状态 match；已保存别名未显示 deviation（I2） |
| prototype 单 Thread 批准；must-match 4 | 非 owner 能用卡片选项，其他身份见相同决定 | J4；review-approval-pending.png；review-mobile-approval-resolved.png | B 桌面操作、C 手机观察已处理 | 可见选项和 Allow once 跨身份结果 match；并发重连补验见 U1 |
| prototype Work；must-match 5 | 非 owner 完整主/子执行可读，原聊天不随之开放 | J5；review-nonmember-work-main.png；review-nonmember-work-child.png | C 桌面、私聊非成员、刷新回看 | match |
| prototype Agents/Nodes；must-match 6 | 仅本人完整配置、多设备/零设备/离线独立状态 | J2；review-nodes.png；review-empty-nodes.png；review-c1-offline.png | A/B/C；两设备、零设备、离线 | 权限与状态 match；别名显示 deviation（I2）；完整创建写入见 U2 |
| prototype 语言；must-match 7 | 原控件、中英文即时/持久、正文/草稿不改 | J7；review-desktop-menu.png；review-mobile-me-zh.png | 桌面菜单、390px“我的”、重载 | 已测语言路径 match；新增全部错误/深层表单文案未逐项穷举 |
| prototype 多聊天 Skill；must-match 8 | 两范围、同 node、失败不建空聊天、预填不发送，桌面/手机入口 | J6；四张 distill/skill 截图与实际 scope 路径 | 桌面；两段 idle 来源、两范围成功 | 已测成功路径 match；缺能力/离线/路径失败和手机多选未验证，inconclusive（U2） |
| prototype 既有入口；must-match 9 | 保留 fork/slash/草稿/管理入口及原操作资格 | J6/J7；review-member-slash.png；review-owner-sessions-empty.png | 1440×960、390/767/768px | 已测 fork/slash/navigation match；完整承接矩阵尚未闭环，inconclusive（U2）；回图 deviation（I5） |
| prototype“我的”；must-match 10 | 独立设备/账号/系统策略行，图标、EN \| 中、手机分段控件 | review-reference-mobile-me.png 对照 review-mobile-me-zh.png；review-desktop-menu.png | 桌面、390×844、767px | 图标/语言/独立设置层级 match；手机缺 Policies deviation（I3） |

### 问题清单

| ID | Severity | Regression Relation | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| I1 | major | direct | C 收到 B 的私聊时，标题/侧栏/输入提示显示 C 自己 | fix-implementation | 人际 IM 的对方身份应稳定可辨认，发送者正文正确不能补偿会话对象错误 |
| I2 | minor | direct | A1 别名已保存为 review-A1，联系人/聊天设备标注仍为 node ID | fix-implementation | 仍可用不同 ID 区分 Gateway，故不是阻断性权限或投递问题；但没有体现用户保存的设备名字 |
| I3 | major | direct | 手机“我的”没有系统策略整行入口 | fix-implementation | 明确 must-match 和既有能力保留要求，桌面入口不能代替手机入口 |
| I4 | major | suspected-regression | C 的 Muse 在 A 创建的群已经采用新配置，但没有配置生效系统提示 | fix-implementation | runbook 与当前 UX 要求群成员能辨认配置边界；模型输出新标记不能替代系统提示 |
| I5 | major | suspected-regression | global Nova send_message 回传 workspace PNG，实际聊天出现破图 | fix-implementation | 图片生成和文本投递成功后，用户仍拿不到可见图片；违反资源交付补充旅程 |

I1 复现：B New chat 找 C→发送消息→C 打开 `c_d8u24y7n`。期望显示小李，实际显示小王。证据见 J1 与 review-human-dm.png。

I2 复现：A Nodes 保存 A1 别名 `review-A1`→新聊天/群时间线查看该节点 Agent。期望设备名随保存显示，实际仍为 `feat554-a1-blaj_fyd`。证据见 J2。未把 ID 暴露本身描述为安全故障。

I3 复现：切 390 或 767px→底栏“我的”。期望身份卡后独立设备/账号/系统策略入口，实际仅设备、账号、语言、退出；参考原型有系统策略。证据见 J7、Reference 表。

I4 复现：C 保存 Muse custom instructions 标记 `review-boundary-0950`（profile v2）→B 在 `c_qanmoqrx` @Muse 请求标记→A 刷新。期望独立的配置生效提示；实际有新标记正式回复，缺系统边界。不得用后续修复版本补回旧记录来替代新配置生效的复验。证据见 J8。

I5 复现：B→Nova `c_29l7m2vr` 要求新建纯黄 PNG 并正常 send_message 回传→查看 message `9719207524cb4bc8b4f52654d5df3209`。期望受保护图片可加载；实际 DOM img.src 为本机绝对路径、complete=true、naturalWidth=0；输入 PNG 的同项为 120。review-global-generated-image.png 已目视确认破图。模型关于“不支持 global 图片”的自述不作为根因结论；这里只报告实际产品结果。

### 未完成覆盖（不等同已证明的实现缺陷）

- **U1：同一批准请求的并发/重连。** 顺序重复决定和单次工具轨迹已完成；IM 重启窗口、多人同时提交及恢复后的单次副作用还未由本 reviewer 完整观察。需携带原请求 ID、新的决定及恢复结果补验。
- **U2：既有能力承接矩阵剩余操作。** 手机蒸馏多选/右键、选择同 node 的实际锁定，以及缺 distiller、缺 skill_view、离线、路径失败均不创建空聊天；普通文件上传、目标格式历史资源在合法 fork 中回看；消息复制/长按/代码复制、跨聊天草稿、私聊改名；指定在线节点完整创建 Agent、Skills 管理操作、Channels 完整常规操作、Account/Policies 保存及退出清理。这些本轮未得到足够独立产品证据，不能以原型/入口存在/自动测试替代。两种 scope 的实际创建已经完成，后续无需无理由重跑。
- **U3：群附件读取边界。** 已验证新图片在私聊中对成员/非成员/无凭据的真实 HTTP 边界，也验证群成员移除后的实时/重载收敛；尚未独立完成同一群的附件 URL 对非成员取回失败，不能自动外推为群附件已测。
- **U4：群解散证据的版本窗口。** J3 的纯人群创建/解散发生于 01:02:24–01:03:23，与 owner 的 IM 更新窗口相邻；未把这段补充观察归为 validated_at 的结果。Round 1 的改名/成员移除结果已确定，解散在下一轮对新运行版本正式归档。
- shadow 富消息调和、owner JWT 刷新与机器凭据轮换属于 runbook 的实现集成证据范围；本轮不以 UI 验收替代这些证据，也不进行源码根因审查。由 owner 汇集相应真实集成证据后明确记录来源。

### 验收标准覆盖

#### Requirement: 用户无需 Gateway 即可注册登录并查找联系人 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 无 Gateway 的用户开始沟通 | spec；design must-match 1 | D 真实注册后立即找人/Agent；B 零设备使用 | J1；mobile contacts 截图 | pass | 无绑定前置 |
| 没有匹配联系人 | spec；design must-match 1 | 不存在的名称搜索 | J1；No contacts found | pass | 未创建错误聊天 |

#### Requirement: 人与人可以跨账号私聊并持久回看 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 两个账号实时沟通 | spec；design 联系人及稳定身份 | B/C 双向发送、刷新回看 | J1；c_d8u24y7n | fail | 消息/发送者正确；会话对方标题 I1 |

#### Requirement: 一个人可以管理多个 Gateway 及其 Agent — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同一人绑定多台设备 | spec；design must-match 6 | 已绑定 A1/A2 的 A 查看所属 Agent、自己配置及节点 | J2；Nodes 截图 | pass | 两节点归属可辨认；I2 是别名显示问题；完整新绑定旅程不冒称重做 |
| 协作者不能修改他人的设备或 Agent 配置 | spec；design must-match 6 | B 公开资料与真实 GET/合法 PATCH 拒绝 | J2；404 实际响应 | pass | 自己的 owner 配置保持原值；未仅看隐藏按钮 |
| 单台设备离线 | spec；design must-match 3/6 | C1 单独断开，C 发人际消息、Nova 回复，C1 恢复 | J2；offline 截图 | pass | 末次心跳保留，未把离线工作显示完成 |

#### Requirement: 用户可以直接私聊其他人管理的 Agent — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 跨管理归属交办工作 | spec；runbook 图文交付补充旅程 | B 私聊 A 的 Nova，真实子执行/读图/回图 | J5/J8 | fail | 文本与读图成功，回图 I5 |

#### Requirement: 多人与不同 Gateway 上的 Agent 可以在同一群协作 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 建立混合成员项目群 | spec；design must-match 2 | A 建群、C 加自己 Muse、三身份核对六成员 | J3；c_qanmoqrx | pass | 手机建群视觉补验仍见 U2/Reference |
| 不同群成员共同交办工作 | spec；design/runbook 配置边界补充 | B→Iris、A→Muse、B 在 C 更新后继续交办 | J3/J8 | fail | 跨成员回复正常；配置边界 I4 |
| 群成员与群名变更 | spec；design 既有群操作 | 改名/个人偏好/移除并重加/纯人群解散 | J3；c_fkphyq4g 解散后 B DOM 全部清空 | inconclusive | 改名/移除通过；解散补充证据与版本切换相邻，见 U4 |

#### Requirement: 工具批准遵循工作模式且不新增人员权限配置 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 全局模式不弹批准卡 | spec；design must-match 4 | Nova 真实子 Agent/bash/投递，无批准卡 | J5/J6/J8 | pass | 未通过页面按钮绕过授权 |
| 单 Thread 模式的群成员可操作批准卡 | spec；design must-match 4 | A 发起/C 管理、B 点 Allow once、C 见相同结果 | J4；pending/resolved 截图 | pass | 三个原选项均可见；实际执行 Allow once |
| 同一张卡被多人操作 | spec；runbook 并发/重连 | B 已批准后 A 对原请求再提交 deny | J4；原 request ID、保持 B 决定 | inconclusive | 顺序重复通过；U1 尚待闭环 |

#### Requirement: 聊天按成员可见，全局 Agent Work 详情完整可见 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 未参与者不能读取私聊 | spec；design must-match 5 | B 的 Nova 私聊与图片，A/C/匿名直接请求 | J5；B200/A404/C404/匿名401 | pass | A 管理 Nova 也不能读 B 原聊天 |
| 未加入的群不可读取 | spec；runbook 资源边界 | 移除 C 后立即及重载不能读/发/收新群消息 | J3 | inconclusive | 消息边界通过；群附件专门旅程 U3 未完成 |
| 全局 Work 不按来源聊天过滤 | spec；design must-match 5 | C 非成员查看 B 私聊输入、主执行及关联子执行、刷新 | J5；两张 Work 截图 | pass | 原记录未遮盖，未用管理者身份替代 |
| Work 链接不授予原聊天访问权 | spec；design must-match 5 | 查看原消息链接目的地、C 打开该私聊及直接附件 | J5 | pass | 原聊天拒绝；Work 记录仍在 |

#### Requirement: 既有使用数据和工作能力在升级后保留 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 原用户继续使用 | spec；design 承接矩阵及 must-match 7–10；runbook | 目标格式的持久回看/fork/两种 Skill scope/slash/设置/语言/资源 | J6/J7/J8；Reference 表 | fail | I3/I4/I5；U2 剩余。正式存量转换由部署 agent 按 migration-prompt.md 验证，本轮没有宣称迁移成功 |

18 行均列明：11 pass、4 fail、3 inconclusive。任何必验缺口未关闭前不进入 pass。

### 上层文档同步

- [x] `SPEC.md`：跨包 import 边界不变，无需重写架构；最终若其产品可见性摘要仍为 owner 全隔离，owner 应同步校正。
- [x] `docs/specs/im/` 与 `docs/specs/gateway/`：**需要更新**。本轮读取的 IM Purpose 仍写“登录后只能看到自己的数据”，与公开 Agent/完整 Work 的目标不同；由 owner 在最终行为通过后归并 unit delta，并更新索引摘要。此处未修改 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新，工作红线与包边界未变。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新，本 unit 未改变文档规范。

收尾责任：owner 保持本轮运行根与未决批准现场，完成修复/targeted 后统一清理自己启动的专用栈及测试 Skill；reviewer 不销毁共享验收现场。报告外未修改产品源码、测试、配置或设计。

## Round 2 — targeted revalidation

> Validation snapshot: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4 → 513ee21637917dabe16f2f2080136ed63510f7d9`
>
> 验收时间：2026-09-14；mode：full；revalidation_mode：targeted；fix_delta_range：`1f14e77db..513ee2163`；prior_acceptance_paths：本报告 Round 1（报告提交 `fc5c093c7`）。范围为 I1–I5、U1–U4；其他已通过且未失效的旅程继承 Round 1。

### Verdict

**pass**。Highest Required Action：**pass**。I1–I5 全部关闭，U1–U4 补齐；18 个 Scenario 在 runbook 规定的实施期验收范围内均为 pass。未关闭的本 unit 产品问题为 0；另记录 1 项既有普通文件模型入参限制，不将它描述成此次已支持的能力。没有创建外部 issue。

此结论适用于上述实测版本。正式旧数据转换仍由部署 agent 按 `migration-prompt.md` 执行，未在本轮提前宣称迁移完成。owner 随后提交的 `274ad07bc` 图片引用修复及 `c3046c6a2` 测试文件整理不是本轮运行版本；其窄 delta 有效性由 owner／后续验证门禁判断，不把更新后的 HEAD 冒充实测版本。

### 运行版本与观察边界

- 继续使用 Round 1 的专用 IM、三 Gateway、独立身份与浏览器。Round 2 最终三个 Gateway 均重启到 `513ee2163`，A1/A2/C1 PID 分别为 41363/41365/41367。最终前端 `index--ymP6Kyu.js` 的来源为 `00dff29be`，到 `513ee2163` 前端源码不变；运行根 `frontend-build.json` 已读，bundle SHA256 为 `b9f5cde51aedc8a9801c22f2f7e166e68f550410f13df1c7d0eedf56cd74f698`。Round 1 的 manifest 另存，未覆盖其历史证据。
- I1/I2/I3 的首个修复后观察、部分承接操作与 U4 解散发生在期中 IM `4e93`／前端 `a62b98d45` 版本；owner 确认相关实现未在最终 `513ee2163` 改变。最终 bundle 又实际观察到设备别名、手机 Policies、私聊对方名称、蒸馏错误与图片新交付。报告保留这段版本边界。
- U1 由 owner 保留数据库/JWT/端口真实重启 IM：PID 16913→57800；C1 保持原 PID 41367 和原待批内核。曾尝试暂停 C1，但 tmux 恢复了直接子进程，该暂停窗口作废。有效旅程是正常 Gateway 重连后恢复同一 pending 请求，再并发提交；没有声称 Gateway 在重启窗口一直冻结，也没有声称独立观察到 submitted 状态跨断线保留。
- 必要的缺源文件与离线前置由 owner 操作，reviewer 从产品观察结果。临时移走的 `sess_54a52fc17eb28657.jsonl` 已恢复原路径，owner 回报并在 restore 记录确认 SHA256 仍为 `d60c3749d5ef2a299619970ac9c7346671e3918c64e12f661ade0cf3637d8203`。没有删除来源、修改数据库或触及日常 Skill 根。帮助 Agent 的 distiller 与 skill_view 均已用管理 UI 恢复启用。
- 截图仍在 `output/playwright/`，不提交缓存。桌面 1440×960、手机 390×844；767/768px 导航边界继承 Round 1。下列新截图已目视核对；移动长按用真实浏览器内合成 touchstart 事件触发，不冒称物理手机手势测试。

### 修复复验与补充旅程

**R2-J1：对方身份、设备名和手机设置。** C 打开原人际私聊 `c_d8u24y7n`，标题与侧栏为小李，副标题小李·小王，输入提示也是给小李；修复前的自称错误已消失。随后 C 通过菜单改为 `review-人际私聊改名`，刷新仍保持自定义标题。A1 已保存别名 `review-A1` 出现在 Iris/Atlas 的联系人、聊天头部和发送者设备标注中，管理页的技术 node ID 仍作为标识保留。D 手机“我的”现在有独立策略行、线条图标与原语言分段按钮；实际进入 Policies，把保留天数 30→31 保存并重载确认，再恢复 30。账号显示名保存为 `review新同事已保存`，Account 重载保持；退出后访问 `/chat` 回到登录，再次登录后显示新名字且中文保持。证据：`review-round2-human-peer.png`、`review-round2-single-image-alias.png`、`review-round2-mobile-me-final.png`。

**R2-J2：他人创建的群实际看到新配置边界。** C 在 Muse Config 再保存不同标记 `review-boundary-0130`；A 在 A 创建的 `c_qanmoqrx` @Muse 发新请求。A/B/C 时间线出现独立分界“Agent 配置已更新 · 后续请求将不再命中此前的上下文缓存”，位置在首条采用新配置的请求之前，刷新后仍只有该边界。第一次请求受到之前普通 txt 附件的既有入参限制影响；下一条无附件请求实际回复 `review-boundary-0130`，证明新配置采用与可见边界同时成立。旧轮缺失的边界没有被回填。证据：`review-round2-config-boundary.png`；此截图也如实保留第一次图片误报，见 Side Finding。

**R2-J3：全局 Agent 生成及重发 workspace 图片。** B 在原 Nova 私聊 `c_29l7m2vr` 要求正常生成一张 120×60 绿色 PNG 后 send_message 回传，message `4bfbe7436eeb454a8063e679cffa12bd` 使用受保护 URL `/im/v1/conversations/c_29l7m2vr/images/2743d30942994ab4981cbd29d870303e`。浏览器实际显示绿色图，naturalWidth=120，放大预览可见。再要求发送已存在的 `review-generated.png`，message `80d70a433ec046ff8fcfe9e96325b6c4` 得到新资源 `/im/v1/conversations/c_29l7m2vr/images/ab63574975a84424a2dc6dc9a298de3e`；刷新后实际显示黄色图，naturalWidth=120。A/C 直接读取新绿色资源均 404，B 200，无凭据 401；消息继续有 View Work。历史 Round 1 失败消息仍破图，不将旧记录重写说成修复条件；本轮证明新生成与再次发送已有 workspace 文件两条路径可用。证据：`review-round2-global-image-preview.png`、`review-round2-existing-image.png`。single_thread 图片与合法 fork 的实际显示另见 R2-J6。

**R2-J4：原待批卡经 IM 重启恢复，多人并发只执行一次。** A 在 `c_qanmoqrx` 让 C 管理的 Muse 新建 `review-approval-0132` 目录、先 read 尚不存在的 `.gitconfig`，再用 write 写单行 `# review-once-0132`。B 手机实际看到三个原批准选项。原 message 为 `c963e485f86a420c846229f93e9f2a1a`，request 为 `5cfc86d9-4be9-4c7f-bdca-4cdd11a6a5d9`，run 为 `run_7a83bd8c90f9d343`，路由为 C1/Muse。owner 重启 IM 后，reviewer 独立刷新观察同一 pending 卡，并核对同一 request/run 与文件尚不存在。

reviewer 用真实 A/B 登录令牌、同步屏障和两条并发 HTTP 请求提交 allow_once：二者均返回 200/submitted，decision 均为 allow_once，decided_by 均为 A（`u_btms4c9h`）。随后 C 对同一请求提交相反的 deny，返回 resolved，仍保持 A 的 allow_once。最后原消息 resolved，工具轨迹只有一次完成的 write（tool_call `call_00_ZpB3LEySE3FZNmJXqRJM7569`，approval=user_allow）；实际文件内容恰为 `# review-once-0132\n`，没有第二次 write。此前唯一 read 失败是预先要求验证文件不存在，不计作第二次副作用。B 英文与 C 中文均看到同一完成结果和 1 次批准/1 次允许。原进程、IM 变更及 gateway_frozen=false 记录在运行根 `independent-reconnect-window.json`；reviewer 的实际并发响应及最终工具记录在 `review-concurrent-decisions.json`、`review-concurrent-final.json`。截图：`review-round2-permission-pending.png`、`review-round2-before-restart.png`、`review-round2-permission-resolved.png`。这组独立证据关闭 U1，没有借用 owner 自己群内的成功过程。

**R2-J5：单 Thread 多聊天 Skill 的剩余操作与失败路径。** A 从指定在线 A1 真正创建 `review-helper-0110`（single_thread），并从 A2 创建 `review-peer-0128`；后者在普通聊天 `c_o9ga6ixe` 实际回复 `review-peer-ready`。在选择 A1 Iris 来源后，A2 review-peer 来源显示 Different Gateway 且复选框禁用。桌面侧栏底部、会话右键 Distill to skill 均可进入；390px 上实际选择两段 Iris 聊天、执行 helper、切 scope，底部操作可用。两种 scope 的真实 Skill 创建和原样预填不自动发送继承 Round 1，不以新建 helper 代替这两次模型结果。

对同一来源 `c_kqn7i8hc/c_tm2ws7fd`，通过 helper 管理 UI 分别禁用 distiller、恢复后再禁用 skill_view：Start 分别提示启用相应能力，均未建空聊天。恢复两项后，owner 临时移走一份来源 JSONL，Start 因源不可用失败且保留选择；恢复源后真正成功预填到 `c_hrrs6ey4`，尚未发送。owner 随后实际停止 A1 并确认进程退出，Start 因 Gateway 不在线失败，仍未建聊天；此前无效的 SIGSTOP 不作为离线证据。A1 恢复到最终版本后，再次临时移走相同来源，用最终前端复验为友好英文提示：“Could not prepare the selected chats. Check that their Gateway is online and their history is available, then try again.” 当前 `/chat`、来源、helper 与 scope 保留，没有原始 HTTP/JSON 或空执行聊天；源现已恢复并核对哈希。截图：`review-distill-cross-gateway-lock.png`、`review-mobile-distill-selection.png`、`review-distill-no-distiller.png`、`review-distill-no-skill-view.png`、`review-distill-offline.png`、`review-round2-distill-friendly-error.png`。

**R2-J6：文件、历史资源、fork 与消息操作。** B 在三人群上传普通文件 `review-group-file.txt`，正文为 `review-group-file-0109\n`；message `6903785234d14b4f8b5baf53f5558af0`，附件 `/im/v1/conversations/c_qanmoqrx/attachments/df8aaa46dba84b6295f6730d91585158`。真实请求 A/B/C 都是 200 且字节相同，非成员 D 404、无凭据 401；旧 `/im/uploads/review-group-file.txt` 为 404。B 在浏览器点击附件下载并读取文件确认字节，不只记录接口状态。群消息的实时移除隔离继承 Round 1；这里单独关闭群资源 U3。

B 作为非管理者，在已完成的 Iris 图片 direct 回复使用 Branch from here，原聊天 `c_0qsml7dd` 生成 `c_22kfp1v4`。输入图片及 Agent 输出均实际加载（naturalWidth=480），刷新后仍可回看。再在此聊天上传普通 `review-fork-file.txt`，正文 `review-file-for-fork-0124\n`，并在下一条无附件请求得到真实代码块 `review-code-0127`；Copy code 的剪贴板内容精确匹配。于已完成回复继续 fork 为 `c_xapqwfg5`，txt 附件被改写为新聊天资源 `/im/v1/conversations/c_xapqwfg5/attachments/64c50ee979b0499494c96d63f6b21685`，B 重载后下载字节正确，A/C 404、无凭据 401；图片也继续可见。由此证明目标格式历史资源随合法 fork 可用，不假称测试了正式存量转换。截图：`review-fork-protected-images.png`、`review-fork-file-and-code.png`。

另从 C 工具栏复制人际消息，剪贴板与正文相同；B 手机以合成 touchstart 等待 700ms 触发真实消息长按菜单，Copy/Branch 操作出现。Iris 离线时 fork 禁用并显示原因，恢复后可用。C 的人际聊天草稿 `review-独立草稿H-0119` 与群草稿 `review-独立草稿G-0119` 在两个聊天切换后各自保留；等待目标标题加载后再输入，未把自动化导航竞态误报为产品丢稿。证据：`review-mobile-message-menu.png` 及独立剪贴板结果。

**R2-J7：管理页面与群操作补齐。** helper 的创建、模型选择、Config 技能/工具保存均走正式 UI；Iris Skills 显示真实使用统计（含 distiller 使用），Overview/Sessions 原空态与顺序继承 Round 1。Channels 的 Add 打开实际 Feishu 向导，空保存分别给出 App ID/App Secret 必填校验，Cancel 不留下渠道。runbook 明确本轮不开 Feishu channel、不需要外部租户，因此此处证明原入口、操作资格与表单行为，没有声称连通真实第三方租户。D Account/Policies 的实际保存和退出已在 R2-J1 完成。B 手机 New group 为底部弹层，空选择时创建禁用，零 Gateway 账号只显示可选人；实际混合群建成及由 C 加自己的 Agent 继承 Round 1。截图：`review-round2-mobile-create-group.png`、`review-mobile-public-agent.png`。

U4 的纯人群 `c_fkphyq4g` 创建/解散 01:02:24–01:03:23 正式归入期中 IM `4e93` 的本轮观察，相关 IM 实现到最终版本不变：A 创建者可确认 Dissolve，B 仅有 Leave，解散后 B 正打开的群设置、消息、composer、dialog 全部清空。记录实际版本后关闭 U4，不将它逆归入 Round 1，也未为同一无变化结果再解散其他群。证据：`review-group-dissolved.png`。

### Reference Artifacts Reviewed

继续对照 Round 1 已打开的 `prototype.html` 与 design must-match 1–10；旧有对照截图保留。结论只要求约定的信息层级、入口、状态及操作资格，不要求像素一致。以下结合新截图与未失效前轮证据关闭所有原型对照缺口。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| 新聊天，must-match 1 | 人/Agent、无设备、空搜索、正确私聊对象 | Round 1 J1；R2-J1；review-round2-human-peer.png | 1440×960、390×844；对方私聊/零设备 | match；I1 关闭 |
| 建群与成员，must-match 2 | 桌面弹窗/手机底部弹层、空选择禁用、本人 Agent 选择 | Round 1 J3；R2-J7；review-round2-mobile-create-group.png | 1440×960、390×844；三人混合群/手机空选择 | match；手机缺口关闭 |
| 群时间线，must-match 3 | 发送者、设备名字与在线状态 | Round 1 J2/J3；R2-J1；review-round2-single-image-alias.png | 桌面/390×844；多节点及离线 | match；I2 关闭 |
| 批准卡，must-match 4 | 原三个选项、非 owner 可用、全体同一处理结果 | R2-J4；review-round2-permission-pending.png、review-round2-permission-resolved.png | B 手机；重启前后、并发批准后 | match；U1 关闭 |
| 全局 Work，must-match 5 | 完整主/子执行可读，链接不开放原聊天 | Round 1 J5；R2-J3 新图片仍受聊天保护且保留 View Work | C 桌面、B 手机；非成员/刷新 | match；完整 Work 证据继承 |
| Agents/Nodes，must-match 6 | 只管理自己的配置，多设备/空设备/离线 | Round 1 J2；R2-J1/J5/J7；review-mobile-public-agent.png | A/B/C/D；两节点、零节点、他人 Agent | match；指定节点创建与配置写入补齐 |
| 中英文，must-match 7 | 原控件、即时持久、正文/草稿不翻译 | Round 1 J7；R2-J1/J4/J5；review-round2-mobile-me-final.png | 桌面 EN \| 中、390px 分段按钮；重载/批准/错误 | match；新错误提示也可理解 |
| 多聊天 Skill，must-match 8 | 同 Gateway、两 scope、失败不建聊天、预填未发送 | Round 1 J6；R2-J5；六张 distill 截图与真实创建结果 | 桌面/390×844；成功/缺能力/离线/缺路径 | match；U2 对应缺口关闭 |
| 既有聊天与管理入口，must-match 9 | 原菜单/fork/slash/草稿/管理操作资格 | Round 1 J6/J7；R2-J1/J5/J6/J7；review-fork-protected-images.png、review-mobile-message-menu.png | 桌面/手机；本人/协作者、在线/离线、历史资源 | match；I4/I5 与 U2 剩余项关闭；第三方连接范围见 R2-J7 |
| 设置层级，must-match 10 | 独立设备/账号/策略行、图标、原语言控件 | 原型 review-reference-mobile-me.png 对照 review-round2-mobile-me-final.png；桌面菜单继承 Round 1 | 390×844、桌面；保存后/零设备 | match；I3 关闭，无语言区域嵌套其他设置 |

### 问题收口与 Side Finding

| ID | 原 Severity / Relation | 本轮实际结果 | 状态 / Required Action |
|---|---|---|---|
| I1 | major / direct | 对方标题、侧栏、composer 一致；显式改名持久 | closed / pass（R2-J1） |
| I2 | minor / direct | 保存的 review-A1 显示在 Agent 与聊天设备标签 | closed / pass（R2-J1） |
| I3 | major / direct | 手机独立 Policies 行可进入并真实保存/重载 | closed / pass（R2-J1） |
| I4 | major / suspected-regression | 新配置的系统分界与实际采用同时出现，刷新保持 | closed / pass（R2-J2） |
| I5 | major / suspected-regression | global 新生成和既有 workspace 图片回传可见，仍有成员保护 | closed / pass（R2-J3） |
| U1 | 先前 inconclusive | 独立观察原请求经 IM 重启恢复、A/B 并发、C 相反重复、一次真实 write | closed / pass（R2-J4） |
| U2 | 先前覆盖不足 | 失败前置、手机选择、同 Gateway、消息/草稿/fork/文件、本人管理与设置操作补齐 | closed / pass（R2-J1/J5/J6/J7） |
| U3 | 先前覆盖不足 | 群文件 A/B/C 可读，D/匿名不可读；浏览器下载字节一致 | closed / pass（R2-J6） |
| U4 | 版本未归档 | 解散证据明确归入期中 4e93，行为到最终版本不变 | closed / pass（R2-J7） |

**SF1 — 既有普通文件模型入参限制（nonblocking；Regression Relation：unrelated-existing，由 owner 的基线比对归类）。** B 给 Iris 附 txt 的 message `21140bc730264d7ea049a7b394c5c955` 得到“这张图片我无法识别…”；群内之前未消费的 txt 也影响了 Muse 第一次新请求。下一条无附件请求可正常完成。普通文件的上传、浏览器下载、历史与 fork 读取均已实际通过，但这些结果不意味着 Agent 能理解任意文件。owner 独立核对基线到本 unit 的现有 adapter/resolver：所有 URL 附件原先即进入图片解析，未按 MIME 排除 txt；本次变化只涉及受保护读取身份。reviewer 未阅读源码定位根因。按本轮已确认范围，此既有入参限制不作此次权限/资源改造的新增失败，也不将任意文件模型处理算作已验能力；未外发 issue。

### 验收标准覆盖

以下每一行均对应 spec 的原 Scenario；本轮继续继承前轮 fail/inconclusive 行并逐一关闭。“继承”仅表示相关实现未失效，不表示把新 HEAD 当成旧旅程的运行版本。

#### Requirement: 用户无需 Gateway 即可注册登录并查找联系人 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 无 Gateway 的用户开始沟通 | spec；must-match 1 | 继承 D 注册/B 零设备沟通；D 保存/退出/重登 | Round 1 J1；R2-J1 | pass | 无绑定前置 |
| 没有匹配联系人 | spec；must-match 1 | 继承真实无结果搜索 | Round 1 J1 | pass | 不误建聊天 |

#### Requirement: 人与人可以跨账号私聊并持久回看 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 两个账号实时沟通 | spec；联系人稳定身份 | 重看原双向私聊、标题、改名与重载 | R2-J1；review-round2-human-peer.png | pass | 关闭原 fail/I1 |

#### Requirement: 一个人可以管理多个 Gateway 及其 Agent — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同一人绑定多台设备 | spec；must-match 6 | 继承真实双节点；分别指定 A1/A2 新建 Agent 并交办 | Round 1 J2；R2-J1/J5 | pass | 别名 I2 关闭；节点独立 |
| 协作者不能修改他人的设备或 Agent 配置 | spec；must-match 6 | 继承真实拒绝，B 继续公开资料/fork/交办 | Round 1 J2；R2-J6/J7 | pass | 未扩大完整管理能力 |
| 单台设备离线 | spec；must-match 3/6 | 继承 C1 离线；补 A1 真实退出与恢复 | Round 1 J2；R2-J5 | pass | 末次 Heartbeat/其余节点可用证据继承 |

#### Requirement: 用户可以直接私聊其他人管理的 Agent — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 跨管理归属交办工作 | spec；runbook 图文交付 | 继承 Nova 真实文本/识图；新生成/既有 PNG 回传并预览 | R2-J3；两张图片截图；R2-J6 single_thread 图片 | pass | 关闭原 fail/I5；历史失败消息不改写 |

#### Requirement: 多人与不同 Gateway 上的 Agent 可以在同一群协作 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 建立混合成员项目群 | spec；must-match 2 | 继承真实群；补手机空选择/底部弹层 | Round 1 J3；R2-J7 | pass | 手机 Reference 缺口关闭 |
| 不同群成员共同交办工作 | spec；runbook 配置边界 | C 再保存配置，A 请求，三人见边界与新结果 | R2-J2；review-round2-config-boundary.png | pass | 关闭原 fail/I4；SF1 单列 |
| 群成员与群名变更 | spec；既有群操作 | 继承改名/偏好/移除；归档实际解散 | Round 1 J3；R2-J7；review-group-dissolved.png | pass | 关闭原 inconclusive/U4 |

#### Requirement: 工具批准遵循工作模式且不新增人员权限配置 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 全局模式不弹批准卡 | spec；must-match 4 | 继承实际多工具轮次；新增 Nova 回图未弹卡 | Round 1 J5/J6；R2-J3 | pass | 按原工作模式 |
| 单 Thread 模式的群成员可操作批准卡 | spec；must-match 4 | 继承 B 非 owner 批准；补同卡多人状态 | Round 1 J4；R2-J4 | pass | 原三个选项保留 |
| 同一张卡被多人操作 | spec；runbook 并发/重连 | 原 pending 跨 IM 重启恢复；A/B 并发；C 相反重复；真实文件 | R2-J4；原 request/run、并发响应与一次 write | pass | 关闭原 inconclusive/U1；未伪造冻结窗口 |

#### Requirement: 聊天按成员可见，全局 Agent Work 详情完整可见 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 未参与者不能读取私聊 | spec；must-match 5 | 继承历史/消息；对新图、fork 文件再次请求 | Round 1 J5；R2-J3/J6 | pass | owner A 仍不能读 B 原聊天资源 |
| 未加入的群不可读取 | spec；runbook 资源边界 | 继承移除即时/重载；对群文件多身份直读与浏览器下载 | Round 1 J3；R2-J6 | pass | 关闭原 inconclusive/U3 |
| 全局 Work 不按来源聊天过滤 | spec；must-match 5 | 继承 C 非成员完整主执行/子执行及刷新 | Round 1 J5；Work 两张真实截图 | pass | 不按来源遮盖 |
| Work 链接不授予原聊天访问权 | spec；must-match 5 | 继承原聊天目的地拒绝；新资源边界复核 | Round 1 J5；R2-J3 | pass | Work 与聊天两规则并存 |

#### Requirement: 既有使用数据和工作能力在升级后保留 — 组内结论：pass（实施期范围）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 原用户继续使用 | spec Q9/Q10；承接矩阵/must-match 7–10；runbook | 目标格式历史、两 scope 实际创建及全部失败前置、fork/文件/菜单/草稿/管理/设置 | Round 1 J6/J7；R2-J1/J2/J3/J5/J6/J7；Reference 表 | pass | 关闭原 fail/I3/I4/I5/U2；真实存量转换仍是正式部署验收事项，第三方渠道连通及任意文件模型处理未宣称已测 |

合计 18 pass、0 fail、0 inconclusive；此计数遵循 runbook 的实施期范围，不替代部署 agent 对旧库转换与保真核对的单独结论。

### 上层文档同步与交接

- [x] `SPEC.md`：架构 import 边界不变；公开目录/Work 与成员聊天的产品摘要应由 owner 在收尾核对，避免仍表达“全部只看本人数据”。
- [x] `docs/specs/im/`、`docs/specs/gateway/`：**需要归并本 unit 的最终 delta**，责任仍在 owner／verifier。Round 1 已指出 current IM 的 owner 全隔离文字；本 reviewer 不改 canonical，也不以实施成功叙述替代同步核对。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

最终源码窄 delta 判定、canonical 归并和迁移 Markdown 与最终接口核对交由 owner／verifier。报告没有改写设计或要求新增旧版本兼容代码。专用服务、浏览器、测试 Agent/Skill 暂按 owner 要求保留到其后续核对完成，再由各自生命周期 owner 清理；恢复过的源 JSONL 已完成哈希核对，Policies 与缺能力前置已复原。没有仍待用户补充才能完成的产品验收项。

## Round 3 — targeted public Agent profile visual revalidation

> Validation snapshot: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4 → 255903e3ef4771cde484d2606decf4d119d444e7`
>
> 验收时间：2026-09-14 08:27–08:34（Asia/Shanghai）；mode：full；revalidation_mode：targeted；fix_delta_range：`a7610b283..255903e3e`；prior_acceptance_paths：本报告 Round 1、Round 2。仅重验用户指出的公开 Agent 资料页与原有本人详情风格不一致问题，以及直接受影响的导航、语言、Work 和聊天入口；不重跑原 18 个 Scenario。

### Verdict

**pass**。Highest Required Action：**pass**。本轮发现 0 个 blocking／major、1 个既有共享样式 minor（SF2）；公开页的视觉不一致问题已关闭。范围内没有待复验项。其余场景及真实模型收发、管理 API 拒绝、原聊天成员隔离等证据继承 Round 2；本轮没有把旧证据的实际运行版本改写为当前 HEAD。

### 运行版本与观察边界

- 独立浏览器会话为 `feat554-public-review`，实际入口为 `http://127.0.0.1:54719`。登录 `nano`（小陈，Nova 管理者）和 `xiaoli`（小李，无设备）；不使用原型或实施者浏览器代替真实产品。
- 开始时确认分支 `unit/feat-554`、HEAD 为上述完整 `validated_at`，无 tracked 源码变更。入口及浏览器加载 `index-BTHZ1Afl.js`、`index-BDySxW--.css`；独立读取 HTTP 产物，与该 worktree 的实际 dist 文件逐字节一致。JS SHA256：`0770d8a5e2da1d8a101d614b2a8dd798dec2c0033e353af715aa35eb0dfbd3fe`；CSS SHA256：`4eb78432a195675d45c0330136eabe5396f7d7d137ee60d9fd3dfe139ee0e9f6`。构建与版本关联由 caller 提供，本轮核实 HEAD、入口和实际所服务产物，没有重建或重启共享体验服务。
- 按 caller 的现场保留约束，只做登录、页面读取、切语言及进入已有私聊，没有新增消息、配置保存或测试资源。正常打开聊天会按产品机制更新该测试账号已读状态。原模型回复只作为既有历史显示证据，不冒称本轮新发消息或新完成模型任务。
- 截图位于 `output/playwright/r3-*.png`，全部为真实页面并已目视核对；视口为 1440×960、390×844、767×844、768×844。测试为 Chromium 桌面浏览器的移动视口，不冒称物理手机操作。

### Reference Artifacts Reviewed

用户本轮两张附图分别展示本人 Nova 原详情与 Muse 旧公开页，明确要求统一原产品风格。按 design「本次改动来源与原型标注」「UI 结构」「原型对齐契约」及 spec 的既有能力承接要求，本轮以真实 Nova 管理页作为视觉主对照；公开目录语义仍按 design must-match 5／6／7／9。独立 HTML 原型只继承前轮已经核实的入口及操作资格，不用其重绘风格替代本人原页面。

| 受影响旅程／对应要求 | 实际观察与证据 | 结果 |
|---|---|---|
| 桌面公开资料沿用本人详情风格；用户本轮反馈、design 原有页面承接 | 小陈从目录先开 Nova，再开 Muse；小李从目录开 Atlas。公开页均使用同样白色页头、圆头像及在线点、同级标题／ID 与设备副标题、右侧绿色消息按钮、底线标签、灰色正文背景及居中白色圆角卡片。原 Muse 单独大号返回行和散落字段已消失，设备归属不再在同一副标题重复拼接管理员。`r3-owner-nova-desktop.png`、`r3-public-muse-desktop.png`、`r3-public-atlas-desktop-zh.png`。 | pass |
| 手机详情与返回、主导航；design UI 结构及 runbook 390／767／768 | 390 下公开 Muse／Atlas 与本人 Nova 均有同式页头返回按钮、头像标题和正文卡片；Muse 返回实际进入 Agents 列表。390／767 仅底部主导航；768 改为顶部主导航，详情手机返回消失。未出现上下重复主导航；卡片和按钮可见。`r3-owner-nova-mobile-en.png`、`r3-public-muse-mobile-en.png`、`r3-public-muse-767.png`、`r3-public-muse-768.png`，以及 Atlas Work 两张断点截图。4px 共享横向滚动单列 SF2。 | pass |
| 中英文与刷新；must-match 7 | 从手机“我”实际切换 EN→中→EN；公开 Profile／资料、Managed by／管理员、Device／设备、工作模式、Message／发消息及 Work／工作均按语言切换，名字和设备内容保留。英文下重载 Atlas Work，语言、已选 Work 与展开记录仍保留。`r3-public-muse-mobile-en.png`、`r3-public-muse-mobile-zh.png`、`r3-public-atlas-mobile-en.png`、`r3-public-atlas-mobile-zh.png`。 | pass |
| 非管理者公开全局 Work；must-match 5 | 小李的“我”显示 0 已拥有／0 在线；Atlas 资料点击工作，展开真实轮次 `turn_1ee5c6b162bc6217`，看到四次工具、Agent 正文及已记录的原私聊内容。再切回资料，页头和选中标签一致；390、767、768 可继续查看 Work，英文重载仍有真实记录。`r3-public-atlas-work-desktop.png`、`r3-public-atlas-work-mobile.png`、`r3-public-atlas-work-767-en.png`、`r3-public-atlas-work-768-en.png`。 | pass |
| 公开资料仍可进入普通聊天；跨管理归属交办、must-match 9 | 小陈在 Muse 390px 中文公开资料点击“发消息”，实际进入既有普通私聊 `/chat/c_7wzxrj9d`，标题 Muse、设备小王工作站、历史 Agent 回复及 composer 正常；具体聊天隐藏底栏，浏览器返回恢复公开资料。由于 caller 要求不新增体验数据，本轮未再发送消息；真实交办结果继承 Round 2 R2-J3／J6。 | pass |
| 风格统一不扩大管理配置可见范围；must-match 6 | 小陈看 Muse 只有资料；小李看 Atlas 只有 Work／资料。两者没有 Config／Channels／Skills／Sessions、配置字段或保存按钮；本人 Nova 保留 Work／Overview／Config／Channels／Skills／Sessions 与原完整表单。公开 Work 展开仍是执行轨迹，没有成为配置入口。管理 API 的服务端拒绝证据继承 Round 1 J2／Round 2 对应行，本轮不把 UI 隐藏冒充重新验证 API 授权。 | pass |

### Side Finding

**SF2 — 390px 详情面板已有 4px 横向滚动（minor；Regression Relation：unrelated-existing/shared-style，经 caller 确认保留；Recommended Action：记录后单独处理）。** 在公开 Muse／Atlas 的 390×844 资料页底栏上方看到横向滚动条；独立 DOM 测量 document/body 宽度均为 390，详情 panel/header 的 clientWidth=390、scrollWidth=394。本轮真实本人 Nova 手机截图也有同样滚动条，因此不是“他人 Agent 独有的另一套风格”。767px Muse 资料 panel/header 无横向溢出。证据：`r3-public-muse-mobile-en.png`、`r3-public-atlas-mobile-en.png`、`r3-owner-nova-mobile-en.png`。内容、返回、语言、标签和消息操作未受阻；caller 明确本轮只收口公开页与原有页一致性，不扩大为共享样式整修。本报告不声称已解决该 minor，也不据此降低任何 blocking／major 门槛。

### 上层同步与收尾

本次只统一呈现，未改变 spec 的成员关系、公开 Work 或管理资格，无需为此新增权限／数据契约。Round 2 的其他 Scenario 结论及迁移由部署 agent 执行的边界保持；本轮没有重新宣称完成正式存量迁移。独立 `feat554-public-review` 浏览器已关闭，现有 IM／Gateway、caller 浏览器及用户体验数据继续保留；未重启／停止服务，未修改源码、测试、配置或设计。仅追加本报告，按 caller 明确分工由 root 统一提交，reviewer 不另 commit。
