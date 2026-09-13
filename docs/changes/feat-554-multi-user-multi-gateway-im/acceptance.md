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
