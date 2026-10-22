# feat-636 — 验收报告

## Round 1 — Web 独立验收，原生待交接

- reviewer: `/root/uiux_product_gate`，2026-10-22 11:03–11:12（Asia/Shanghai）。
- executed_base: `d846b015b8774461bb26b172e458443ce1eb071d`。
- validated_at: `unit/feat-636-ios-uiux-polish` 的 2026-10-22 11:03 working tree；非 commit。`/tmp/nano-feat636-web-build2.log` 显示 built in 15.13s；caller 交接的同 worktree dist 由隔离 IM `http://127.0.0.1:54071` 提供。
- 范围：本轮先验 Web，原生模拟器仍由 caller 使用。只读需求/设计/原型契约/current personal-agent，不读实现定位；只写本报告。真实登录测试用户 nano 与 uiux-observer；无生产、外发、付费模型操作。
- 独立浏览器 session: `feat636review`、`feat636observer`。截图根目录：`/Users/czj/.codex/artifacts/feat-636-uiux/reviewer/`。

### Verdict

**fail：1 major；原生与逐项 before/after 尚待验收。** Web PA 正常发现、直接配置、搜索、无 PA、他人 PA 权限及读取失败恢复通过；新增 PA 卡片在有未保存配置时直接离开，违反 design 明确保留的保护。此结论不能用于放行完整 Full unit。

### 用户旅程体验

1440×960 桌面与 390×844 移动 Web 的“我的个人助手”均位于搜索之后、普通列表之前。浅青背景、头像、个人助手类型及“配置 ›”组成一个清晰动作，普通列表不再重复本人 PA；无需辨认 agent ID 即能找到本人入口。点击实际进入 `/settings/agents/pa_d6cc22742f62` 且配置标签选中，名字、聊天访问和既有配置内容可见。移动端为完整列表及返回式详情，未把桌面双栏挤入窄屏。

列表和桌面详情侧栏搜索“小陈”（owner 显示名）保留其助手；搜索“研究”只剩研究助手并隐藏不匹配 PA；搜索“个人助手”只保留 PA 卡。普通助手长名称在旧侧栏仍截断，PA 卡本身没有这一辨认障碍，本轮不把既有普通列表视觉问题扩大为新门禁。

只在本人浏览器阻断 `/im/v1/personal-agent` 请求后，顶部出现“个人助手暂不可用 · 重试”及重试按钮，其他联系人仍可读；联系人里仍有实际本人 PA，未伪装为新建成功。撤去阻断后实际点击重试，恢复本人卡片并去重。仅模拟客户端网络失败，未修改后台。

无 PA 的真实第二测试身份 uiux-observer 在桌面没有“我的个人助手”专属区域，仍能看到 nano 的公开 PA 联系人。点击后仅 Profile、Managed by 小陈 与 Message，无私人配置、Work 或保存入口；390×844 下相同。PA 名称恰叫“我的个人助手”，是联系人名称，不是本人入口。caller 确认以此真实公开联系人覆盖他人权限边界，不额外制造普通公开 fixture。

未保存保护不成立：在研究助手配置编辑描述后，画面明确显示“● 有未保存改动”，保存按钮可用；点击侧栏 PA 卡立即跳到 PA 配置，没有确认或保留原编辑页。此问题发生在用户切换常用助手的直接路径，可能丢失尚未保存的工作，构成 major。

### Reference Artifacts Reviewed

已核对 spec、design、prototype-review、Gate 2 最终 R3 Approved 与共同体验标准。Web 对照 `prototype.html` 的 PA 窄屏/桌面/错误区域及 design 决定 6；原型只承担信息关系，真实 UI 截图单独判断。

| Reference | Required contract | Actual product evidence | Viewport/state | Comparison |
|---|---|---|---|---|
| design 前端原型：Web 与原生 PA；prototype PA 区 | 本人置顶区、直接配置 | web-desktop.png、web-mobile.png、web-mobile-config.png | 1440×960 / 390×844；本人 binding | Web match；原生待验 |
| design 决定 6：失败单独反馈、重试 | 不阻断普通列表，不冒充无 PA | web-pa-error.png、web-pa-recovered.png | 390×844；实际请求中断及恢复点击 | match |
| spec Web 与原生查找 PA / 无 PA | 他人不获得本人入口或私人配置 | web-observer-no-pa.png、web-other-pa-profile.png、web-other-pa-mobile.png | 第二真实身份，无 PA | Web match |
| design 决定 6：保留未保存离开拦截 | 草稿状态切换仍有保护 | web-dirty-before-pa.png、web-dirty-pa-result.png | 1440×960；描述 dirty 后点击 PA | deviation，R1-M1 |
| design 其余 must-match | 创建、模型、Work、任务、正文/表单 | 原生尚未交接 | 原生 default / accessibility-medium | inconclusive |
| spec 用户确认前 | 每优化点真实同条件前后对照 | caller gallery 尚未交接 | 平台/字号/内容明确 | inconclusive |

### 问题清单

| ID | 严重度 | 现象与复现 | 处置 |
|---|---|---|---|
| R1-M1 | major | `/settings/agents/ux-research` → 描述填“验收临时草稿不保存” → 看到有未保存改动/保存可用 → 点击侧栏“配置 我的个人助手” → 直接跳 `/settings/agents/pa_d6cc22742f62`，无离开确认。独立重复两次，未点保存。 | caller 修复；针对 dirty 保留/放弃和普通进入配置回归。原因未调查。 |

### 验收标准覆盖

以下逐 Scenario 保留完整 Full 范围。Web 子结论不代替双端要求；后续 Round 追加。

| Requirement | Scenario | 期望来源 / 验证 | 证据 / 当前结果 |
|---|---|---|---|
| 创建助手从目的出发，模型配置有常驻入口 | 创建与高级设置 | spec；design M1-A | inconclusive，待原生 |
| 同上 | 管理模型服务 | spec；design M1-B | inconclusive，待原生 |
| 同上 | 修改未完成 | spec；design M1-B | inconclusive，待原生 |
| 完整阅读消息和工作结果 | 大字号普通 Markdown | spec；design M1-F | inconclusive，待原生 |
| 同上 | 工作轨迹阅读 | spec；design M1-C | inconclusive，待原生 |
| 配置与表单清晰表达当前状态 | 群回复策略 | spec；design 决定 4 | inconclusive，待原生 |
| 同上 | 表单与文案 | spec；design M1-F | inconclusive，待原生 |
| 默认字号下能比较任务并理解结构 | 任务总览与定位 | spec；design M1-D | inconclusive，待原生 |
| 同上 | 子任务与结构 | spec；design M1-D | inconclusive，待原生 |
| 双端突出当前用户 PA 的配置入口 | Web 与原生查找 PA | spec；design M1-E / 决定 6；真实双身份和搜索 | fail，Web正常路径通过，但 R1-M1；原生待验 |
| 同上 | 无 PA 与读取失败 | spec；真实第二身份及本页网络中断/恢复 | inconclusive，Web通过，原生待验 |
| 以真实画面对照交付 | 用户确认前 | spec；完整真实 before/after gallery | inconclusive，待交接；未创建 PR |

### 上层文档同步

- `SPEC.md`：无需更新，未改跨包架构。
- `docs/specs/im/`：需要最终按 delta-spec 归并；目前不以验收报告覆盖 current。
- `AGENTS.md` / `CLAUDE.md`：无需更新。
- `docs/specs/CONTRIBUTING.md`：无需更新。

报告未提交；reviewer 未修改其他仓库文件、后台配置或测试资源。未启动/停止共享服务或操作原生模拟器。浏览器临时 route 已撤销；Web 阶段结束关闭本人两个 session。

## Round 2 — 原生真实旅程与异常恢复

- reviewer: `/root/uiux_product_gate`，2026-10-22 11:14–11:38（Asia/Shanghai）。
- validated_at: caller 在 11:03 交接的原生模拟器包，`/tmp/nano-feat636-after/Build/Products/Debug-iphonesimulator/NanoIM.app`；review 期间 caller 修改的 build4 尚未安装，因此以下问题和证据对应旧包，不混称最新实现。
- 真机形态：iOS 26.4 Simulator，390×844 pt，浅色；默认 `large` 与辅助 `accessibility-medium`。独占操作后已交回 caller。
- 仍不读实现；真实操作产品入口、使用本次隔离 Node/IM 与本地模型服务。未发送聊天、触发真实付费模型或接触生产。

### Verdict

**fail：新增 1 major（R2-M1）；R1-M1 等待修复后定向复验。** 创建、模型服务异常恢复、Work、任务与主要表单正常路径已实走。大字号 Markdown 的列表下半段截图和原生无 PA/他人权限/读取失败仍未独立完成，不把 Web 覆盖替代原生。完整截图 gallery 待交接。

### 用户旅程体验

从新建入口先读名称与用途，选择研究用途后说明自动出现，技术标识与目录默认折叠。展开高级设置可见生成标识、工作模式、自定义目录开关。使用隔离服务的 research-test 创建 Review Research，直到真实“助手已创建”才进入空聊天。成功链路成立，但创建模型选项与选中值堆叠内部 provider UUID，选中后的中间省略隐藏了 research-test，无法确认自己选了哪个模型，构成 R2-M1。

“我的”与本人设备都有常驻模型服务入口。独立编辑已有 UIUX models 服务，已有密钥不回显，空密钥继续沿用，两个模型保留。以 `/fail/v1` 的真实 401 测试失败后，反馈自动进入视野并保留草稿；以 `/slow/v1` 真实延迟验证时停止等待，产品明确后台可能继续，不提前报成功，之后重读得到真实保存结果。caller 通过隔离 API 改同服务名称以制造并发版本，我从旧 revision 保存得到明确冲突与本地/远端对比；选择保留草稿并读取最新版本后再保存成功。

节点离线场景仅暂停本次隔离 Node PID 51954（caller 明确授权），不动 IM。保存等待后显示不可确认结果及重读恢复，草稿仍在；恢复 Node 后重读发现排队操作实际已保存，产品没有把超时冒充确定失败。最终恢复为 UIUX models 与 `/v1`。尝试移除被新建助手引用的服务被拒绝，显示 Review Research 及“配置”动作，点击进入正确助手配置，服务未删除。

Work 默认先呈现在线/空闲、轮次摘要，执行信息与上下文收起；展开工具结果与技术详情仍保持“工作轨迹”标题，结果可读，明确提示工具结果与聊天发送分别记录。仅验收既有 fixture 轨迹，不宣称真实模型本轮完成研究。

默认任务卡保留标题、状态、负责人和子任务线索，多卡可同时比较。“完成 1”摘要实际定位到含完成组的下方区域；顶部明确已加载 6/共 6。直属子任务页显示 3 条、各状态计数及完成情况；结构总览适应屏幕，点击节点打开完整长标题与任务说明，详细视图显示正常阅读尺寸，能返回总览。辅助大字号下根任务长标题仍可能两行省略，但点详情可读全；本轮需求针对默认比较及避免固定高度裁切，不将这一可展开摘要判为阻断。

E2E Agent 配置显示“群回复策略 · 仅被提及时回复”，菜单有选中勾；改为始终回复再返回，明确提示放弃草稿，确认离开未保存。资料/系统策略/设备页有持久字段标签及唯一顶部保存入口；资料改名草稿可放弃，系统步数 0 禁止保存并提示大于零，设备别名真实保存后可见成功，随后恢复原别名。帮助页文案可读。任务详情关闭页面按钮为“关闭”，不使用“完成”冒充任务状态变化。

原生本人 PA 位于搜索后、普通列表前，点卡直接进现有配置；搜索 ux-research 隐藏不匹配 PA；普通列表未重复本人 PA。辅助大字号下名称/设备换行，不再单行省略，状态仍独立可见。默认 Markdown 的两条列表完整可读；辅助大字号首条段落换行完整，列表第一条继续到屏幕下方。但本轮 CUA 对聊天的 wheel/drag/Page_Down 未移动，AX 未暴露消息滚动容器，故列表下半段及表格横向操作暂列未完成，不据工具行为判定产品故障。

### 问题与证据

| ID | 严重度 | 用户可见问题 | 证据与处置 |
|---|---|---|---|
| R2-M1 | major | 新建助手主模型选项显示内部 nano-UUID/research-test 和 provider UUID，选中后中间截断令实际模型名不可见。用户不能可靠确认服务与模型。 | `reviewer/ios-create-selected-model.png`；caller 已安排 build4，待定向复验。 |
| R1-M1 | major | Web PA 直接入口丢失未保存配置保护。 | Round 1；caller 已安排 Web build3，待独立重验保留与放弃。 |

模型证据：`reviewer/ios-model-failed.png`、`ios-model-stop.png`、`ios-model-conflict.png`、`ios-model-offline.png`、`ios-model-dependency.png`、`ios-created-chat.png`。视觉对照新增：`after/02-model-entry.png`、`03-work.png`、`03-work-expanded.png`、`04-policy.png`、`09-markdown-default.png`、`10-profile.png`、`11-system-policy.png`、`13-help.png`、`14-device.png`、`15-agents-large.png`、`15-agents-large-scrolled.png`。均在 `/Users/czj/.codex/artifacts/feat-636-uiux/`。

### 验收标准增量覆盖

| Scenario | 本轮结果 | 剩余边界 |
|---|---|---|
| 创建与高级设置 | fail，成功闭环及高级字段通过，R2-M1 | 新包主模型可辨认复验 |
| 管理模型服务 | pass：入口、编辑、多模型、空密钥保留、验证后保存 | 新增服务由 caller 先前实走，本 reviewer 主要验证编辑及异常 |
| 修改未完成 | pass：失败、停止等待、冲突、离线重读、依赖阻止移除 | 不宣称离线必不执行；最终状态以重读确认 |
| 大字号普通 Markdown | inconclusive：默认列表/大字号段落通过 | 大字号列表下半段、复制与横向表格待补 |
| 工作轨迹阅读 | pass | fixture 轨迹，非真实 LLM 调研 |
| 群回复策略 | 部分通过：可见已保存值/菜单/草稿放弃 | 无关字段保存后策略不变待补 |
| 表单与文案 | pass | 无新增边界 |
| 任务总览与定位 | pass | 六个真实 fixture 根任务 |
| 子任务与结构 | pass | 真实点节点、详情、详细视图/返回 |
| Web 与原生查找 PA | fail，原生本人正常路径通过 | R1-M1；原生他人权限待补 |
| 无 PA 与读取失败 | inconclusive，Web 已通过 | 原生第二身份与读取失败待补 |
| 用户确认前 | inconclusive | 完整 gallery/新包截图和用户确认尚未完成；无 PR |

### 清理与归属

模型服务恢复 UIUX models、`http://127.0.0.1:63681/v1`，Node 已 SIGCONT 并确认恢复运行；设备别名、资料、系统策略草稿恢复/放弃。新建 `agent-4dcd8232` / Review Research 为本次一次性测试数据，caller 已将其列表投影标记 stale 以恢复截图基线，明确这不是产品删除；空聊天保留创建证据，运行配置随隔离环境 teardown 清理。辅助字号在交回时仍为 accessibility-medium，caller 知情。没有修改其他仓库文件。

## Round 3 — Web 草稿保护定向复验

- 2026-10-22 11:39–11:41，隔离 Web build3，中文、1440×960；同真实 nano 身份和 ux-research。
- **R1-M1 closed / pass**：等研究助手配置完整加载后填写与 Round 1 相同的“验收临时草稿不保存”，确认 dirty 后点本人 PA 卡，出现“未保存，是否确认退出？”对话框。点“继续编辑”仍在 ux-research，实际读取描述仍为该草稿、dirty=true；再次点 PA 卡并“确认退出”才进入 pa_d6cc22742f62 的配置。
- 对照图 `after/19-web-leave-draft.png`（已实际看图），补充 `reviewer/web-dirty-continue-fixed.png`、`reviewer/web-dirty-leave-fixed.png`。测试草稿未保存，session 已关闭。
- 一次连续自动操作在研究配置尚未加载完成时填到了旧页面，未用于判断产品回归；以上有效复验明确等待目标标题与 dirty 状态，排除工具时序误判。
- 完整 Full verdict 仍等待原生 build4/语言修正定向复验及剩余场景、最终 gallery，不因本项修复提前整体放行。

## Round 4 — 最终原生包与剩余 PA 场景

- 2026-10-22 11:43–11:49；caller 冻结版本 `b1d926f27`，test4 完成后安装并重新启动的最终原生包；390×844 pt、浅色、默认 large。本轮本人独立操作，不用 caller 的测试通过代替体验。
- **R2-M1 closed / pass**：创建页主模型菜单直接显示 `research-test · UIUX models`，菜单文字换行完整，选中值完整可辨认；长平台默认标签也完整换行。`after/18-model-label.png` 已看图，`after/01-create.png` 与 `after/04-policy.png` 更新为最终包。
- 资料语言当前值已由空白变为“中文”，字段和顶部唯一主保存仍清晰，已独立目视。
- 群策略补验：E2E Agent 只改名为 E2E Agent review，真实保存出现“配置已由节点确认”；重新读当前值仍“仅被提及时回复”。随后改回原名并再次保存成功。`reviewer/ios-policy-unrelated-save.png`。caller 另经真实 API `agents/e2e/config?source=mirror` 窄读确认最终 `display_name=E2E Agent`、`group_reply_policy=manual`，此 raw 值核对作为补充证据，不替代页面观察。
- PA 读取失败：本机临时反向代理 63683 将其他 HTTP/WS 原样转至隔离 IM 54071，仅 GET personal-agent 返回 503；从原生正常登录 nano。页面清楚显示“个人助手暂时无法读取，其他助手仍可使用。”与重试动作，普通联系人仍完整；初次没有成功缓存时不伪造本人区，已有成功缓存时保留已知本人区并同时显示错误。实际点重试时服务仍 503，错误仍保留；恢复代理后后台再次读取自动恢复本人区并移除错误。恢复发生在下一次点击前，不把自动刷新冒称手动点击导致成功。`reviewer/ios-pa-error.png`、`ios-pa-recovered.png`。
- 原生真实第二身份 uiux-observer：没有本人 PA 专属区域，普通“Other assistants”仍显示 nano 的公开 PA。进入详情仅 Message、Owner 小陈、工作模式与公开资料说明，没有配置、Work 或保存入口。`reviewer/ios-observer-no-pa.png`、`ios-other-pa-profile.png`。名称“我的个人助手”属于该联系人，不表示当前账号拥有它。
- 大字号普通列表补验：在聊天列表先切 accessibility-medium，再进入同一研究聊天，实际看到第一条“周六能否在九点前/出发？”和第二条“更偏向自然路线/还是城市漫步？”完整两行，无省略。`reviewer/ios-markdown-large-final.png`。前轮段落/default 列表结论保留；复制与横向表格仍待操作证据。
- 清理：代理已设 enabled=false；终止代理 origin 的 App 并以 54071 重启，确认恢复 nano 中文聊天列表；字号恢复 large，浅色。原服务未停止，代理由 caller 统一清理。新建标签草稿已放弃，没有新增助手。

本轮增量：创建/群策略/双端 PA 发现、无 PA、读取失败 Scenario 均 pass；两个 major 均关闭。最终 verdict 尚待 gallery must-match 与 Markdown 原有复制/横向浏览证据收口。

## Round 5 — 最终真实画面对照检查

- 2026-10-22 11:50–11:52，打开 `http://127.0.0.1:63682/comparisons/index.html`，独立从“选择优化点”逐一选择全部 21 组，等待两张图片真实解码，保存 `reviewer/gallery-01.png` 至 `gallery-21.png`，逐张目视检查两侧内容。没有只靠文件存在或 caller 的 gallery-check 结论。
- 原图均真实可辨识，图中结构与本 reviewer 产品操作一致；iOS 默认/辅助字号及 Web 桌面/窄屏明确分开，没有用全局缩小正文冒充密度改善。辅助大字号 Markdown 已注明滚动位置不同；新增模型标签与草稿保护明确标作“本轮验收发现→修正”，不冒充旧版已有流程。

### Must-match 对照裁决

| Must-match | 最终画面/真实操作依据 | 结论 |
|---|---|---|
| 创建目的优先与高级信息按需 | gallery 01；Round 2 实际展开高级、创建入聊天；Round 4 模型标签 | match |
| 模型服务持久入口、真实状态 | gallery 02/16/20；Round 2 失败、冲突、离线、依赖闭环 | match |
| Work 状态/摘要优先、正文与技术详情分层 | gallery 03/04；实际展开工具与技术层，标题保持工作轨迹 | match |
| 群策略可见真值、表单标签与唯一主保存 | gallery 05/12/13/16；真实无关保存后 manual 保留 | match |
| 任务比较、状态定位与结构总览/详情 | gallery 06/07/08/14；真实状态跳转、节点详情和详细视图切换 | match |
| 双端本人 PA 优先区、直接配置、他人边界与恢复 | gallery 09/18/19/21；两真实身份、双端失败恢复、Web 草稿保护 | match |
| 默认与辅助字号正文完整 | gallery 10/11/17；Round 4 大字号两条列表完整目视 | 正文 match；复制/横向浏览操作另待收口 |
| 逐项真实前后交付、条件诚实 | 21组42图，时刻/未读/构建变化已说明 | match；下述两处说明补齐后关闭 |

发现两处对比说明可更准确，已交 caller 文案补充，不要求重拍：默认 Markdown 也有滚动位置差异；设备页运行 Agent 数 4→5 来自本轮创建测试，不能当作改进。其余图文与实际证据一致。新建入口图的高级设置在首屏以下，文案“按需展开”由本 reviewer 实操支撑；结构缩略图中的字本来不可直接细读，用户通过明确的详细视图和节点详情完成阅读，不把缩小后的文字当作正文可读证明。

本 reviewer 的 gallery session 已关闭。无新的实现问题；两个 major 已在 Round 3/4 关闭。

### 累计 Scenario 状态（截至 Round 5）

| Requirement / Scenario | 来源 | 累计证据 | 状态 |
|---|---|---|---|
| 创建助手 / 创建与高级设置 | spec；design M1-A | Round 2 创建成功实际聊天；Round 4 标签修复；gallery 01/20 | pass |
| 创建助手 / 管理模型服务 | spec；design M1-B | Round 2 常驻双入口、编辑、验证成功、多模型与凭据保留；caller 初始新增流程；gallery 02/16 | pass |
| 创建助手 / 修改未完成 | spec；design M1-B | Round 2 真实401、停止等待、冲突、Node暂停恢复和依赖拒绝 | pass |
| 完整阅读 / 大字号普通 Markdown | spec；design M1-F | Round 2 默认正文；Round 4大字号完整列表；gallery 10/11 | inconclusive：原有复制/横向表格操作证据待收口 |
| 完整阅读 / 工作轨迹阅读 | spec；design M1-C | Round 2实际层层展开；gallery 03/04 | pass |
| 配置与表单 / 群回复策略 | spec；design 决定4 | Round 4无关改名真实保存、原值保留与API raw manual补证；gallery05 | pass |
| 配置与表单 / 表单与文案 | spec；design M1-F | Round 2资料/策略/设备保存放弃；Round 4语言；gallery12–16 | pass |
| 默认比较 / 任务总览与定位 | spec；design M1-D | Round 2多卡比较、状态点击定位；gallery06 | pass |
| 默认比较 / 子任务与结构 | spec；design M1-D | Round 2完成情况/结构总览/节点完整详情/详细视图；gallery07/08 | pass |
| 双端PA / Web与原生查找PA | spec；design M1-E、决定6 | Round 1/4双身份；Round 3草稿保护；gallery09/18/19/21 | pass |
| 双端PA / 无PA与读取失败 | spec；design决定6 | Round 1 Web选择性失败；Round 4原生503重试和自动恢复、无PA真实身份 | pass |
| 真实对照 / 用户确认前 | spec | Round 5逐项21对真实看图；尚未创建PR；等待用户确认属于交付约束 | pass，条件说明补齐待核 |

必验项存在 inconclusive 时，按 change-reviewer 门禁不能整体放行；这里保留未覆盖操作的具体边界，不把全部视觉和核心旅程通过改写为全部通过。后续若 caller 提供真实体验证据，应追加最终 Round 关闭该边界，而不覆盖本记录。

## Round 6 — 用户追加的消息布局与剩余阅读操作

- reviewer `/root/uiux_product_gate`，2026-10-22 12:15–12:25；caller 完成 test5 后安装的 Chat metadata final 包，同一隔离 iPhone 16e、浅色、large 与 accessibility-medium。仅局部复验，不重复已有效通过的全轮。
- 期望来源：spec「消息内容与会话元信息分层」、design M1-G 与「用户追加的消息布局」、delta-spec 对应 Requirement；仍不读实现代码。caller 报告 44 XCTest + 21 Swift Testing 通过，不将其代替以下产品体验。

### 实际体验与证据

单聊研究助手在默认和辅助大字号下直接进入正文，不再逐条重复对方名称、时间与“已完成”；独立时间分隔仍可见。长段落与两条列表实际完整换行。秋季群聊在两种字号均把对方名称放到气泡上方，自己消息不重复姓名，头像、正文与系统任务通知仍可辨认。新增 `before/22-chat-direct.png`、`before/23-chat-group.png` 与最终 after 同名图、`after/25-chat-group-large.png` 已逐张独立看图，与实操一致。

时间及状态使用隔离会话 `c_fpy57por`「聊天信息层级检查」的八条展示种子，明确不是实际模型执行成败证据。实际页面显示首条 `2026年10月21日 23:58`，相邻一分钟不重复时间；跨午夜出现独立 `00:00`；不足五分钟不重复；满五分钟出现独立 `00:09`。点击 iOS 状态栏返回首条后实际目视，证据 `reviewer/ios-message-time-boundaries.png`。今天的分隔沿用时分格式，过往日期显示完整日期。

同一真实页面同时显示“进行中”与递增耗时、红色“失败”，已完成消息仅保留 `100 tokens` 与 `1.2s`，没有“已完成/已发送”标签。证据 `reviewer/ios-message-states.png`。展示种子的 running 随后被隔离服务 120 秒无事件扫描转为 failed，这是 caller 预先说明的种子寿命，不作为消息样式回归，也不把种子状态当作实际模型产出。

复制正文已本人调用页面公开的“复制正文”辅助操作，实际出现“已复制正文”toast；没有发送或粘贴内容。表格在默认和辅助大字号均通过可见表头/单元格的横向滚动，从项目列移到右端，完整看见“预留改签空间 / 近车站，可取消 / 不赶路，留出午休”。辅助字号右端证据 `reviewer/ios-table-right-final.png`，两条列表同时完整可见。故 Round 5 的复制与横向浏览 inconclusive 关闭。额外反向回左尝试在当前 CUA 中未产生位移，与此前 up 方向相同，未将该未证实动作写成通过；本轮已经直接证明表格可横向浏览到所有列，原必验要求已满足。

最终 gallery 文案源已核对：默认 Markdown 与辅助字号均说明滚动位置差异；设备运行计数说明随验收创建变化；新增22/23明确前图是本轮首版 `b1d926f27` 用户追加反馈前的基线。两处 Round 5 说明项关闭。未新开浏览器；新增图直接从文件查看，原21组交互走查结论保留。

### 最终 Verdict

**pass。** 原全部 Scenario 与新增「单聊与群聊」Scenario 已有真实产品或明确补充证据，must-match 全部 match；两个 major 均已在 Round 3/4 关闭，本轮无新阻断。Round 5 的「大字号普通 Markdown」由 inconclusive 更新为 pass，「真实对照」说明条件已补齐。其余累计 pass 保持。

本结论限本次隔离环境的产品体验和视觉对照；不代表生产部署、真机安装或真实 LLM 任务质量。用户确认后才进入 PR 的约束仍有效，本 reviewer 未创建 PR。默认字号 large、浅色已恢复；12:24 明确交回模拟器控制权。仅更新本 acceptance.md，未修改实现或其他仓库文件；未开启新的浏览器窗口。

## Round 7 — PA 行样式校正 targeted 验收

- 2026-10-22 14:34–14:44，reviewer `/root/uiux_product_gate`；validated_at 为 caller 冻结的 PA 行样式 working tree（Gate 2 R5 Approved、静态 R5 无问题后构建的 Web/iOS）。范围仅 design「PA 行样式校正」与 M1-E 受影响交互；Round 1–6 已通过且未失效的创建、模型服务、消息、任务及权限/恢复结论保持，不重新执行。
- 新现场 `http://127.0.0.1:63878`、nano 专用身份、本人 PA `pa_a40eeba6d62a`，真实节点 `wt-nano-multiagent-22994`。本轮重新建环境，不能将联系人顺序、节点 ID、在线状态与旧图视作同一数据快照。

### 独立实际体验

Web 英文 1440×960 列表中 PA 与普通行的头像/间距/字体一致，Configure 消失；保留“我的个人助手”分区、本人身份与整行入口，不再用另一种卡片视觉。实际浏览器测得 PA、E2E Global Agent、E2E Agent 高度均为 56 CSS px。点 PA 进入正确 ID 的配置，详情侧栏显示同一行的 active 高亮；实际截图 `reviewer/web-pa-row-active.png` 已看图。

390×844 下三行均为 67.25 CSS px，PA 姓名、个人助手副标题与箭头清晰，未被 Configure 挤占。实际点 PA 后进入同一正确配置 URL。`after/25-pa-row-web-mobile.png` 已保存并目视。桌面证据 `reviewer/web-pa-row-desktop.png`；与 caller 的 after24 相同新布局。

研究助手配置改描述为 `PA row review draft`，点 PA 弹离开确认；继续编辑后实读描述仍为原草稿，再次点 PA 并放弃才跳转正确 PA。草稿未保存。额外中文截图使用实际在线节点的 E2E Agent：填写“验收临时草稿不保存”后点 PA，实际出现中文确认弹层，确认退出后离开；`reviewer/web-pa-row-unsaved-confirm.png`。这张图与旧图的被编辑助手不同，但保护语义相同，不能描述为同一配置快照。

创建页最初进入等待后显示 `503 (target_node_id is not connected)`，未据此把侧栏判 pass。caller 核实为本轮展示 fixture 不实现创建能力请求，停掉该 fixture relay 后保留真实节点；完整 reload 创建页后真实在线节点成为默认选项，创建内容及 PA 侧栏均实际正常显示，`reviewer/web-pa-row-create.png` 已覆盖早先 Loading 截图并独立看图。本轮未执行创建。后半段 fixture 联系人因此显示离线，这一环境状态变化与行样式无关。

原生每次操作前核对 full AX 的窗口为 `Nano UIUX 636`，未接触并行 feat635。默认 large 下 PA 和相邻普通行使用一致头像、左右边距与文本布局，无特殊底色与“配置”字样；整行实际进入本人配置后返回。辅助 accessibility-medium 下 PA 名称/副标题/在线/箭头完整，普通 E2E Global 和长旅行名称按内容自然换行增高，没有为了统一固定高度裁切。`reviewer/ios-pa-row-large.png` 已拍；默认 after26 与实操一致。大字号这里允许不同正文长度导致行高不同，不用短 PA 行与多行普通名称强行要求像素等高。

### Delta 判定与清理

| 受影响项 | 来源 | 结果 |
|---|---|---|
| Web 桌面/窄屏 PA 与普通行视觉统一 | 用户反馈；design M1-E 校正 | pass，实际行高与目视一致 |
| 列表整行直达与详情 active | 原 M1-E；校正保持条款 | pass，两宽度直达正确 PA |
| 原草稿继续编辑/放弃保护 | 原 M1-E；校正保持条款 | pass，真实草稿未保存 |
| 创建侧栏布局 | caller targeted 范围；共用行契约 | pass，环境修正后真实页面 |
| 原生默认/辅助字号、长名与直接配置 | design M1-E；原生 may-adapt | pass，无裁切/突出卡片样式 |

**Round 7 delta verdict：pass；累计最终 verdict 保持 pass，新增问题 0。** 新 must-match 行关系与真实页面相符。历史对照图需注明重建环境及上述配置对象差异，不把数据变化当作视觉优化。

已关闭交接的唯一 headless browser `feat636pa`，没有新开 headed 浏览器或操作用户 Chrome；原生已恢复 large/light、Agent 列表并交回 caller，未关闭设备/共享服务。仅追加本报告，未读实现定位或修改源码。用户确认前不得创建 PR 的交付约束保持。


## Final sync — retained（2026-10-22）

- 用户已确认本轮效果并要求提 PR。
- validated_at: `09eb0e45855705e76bad50419df34e51141534f6`（最新 PA 行 delta；此前 full 的实际执行版本见上文）。
- executed_base: `d846b015b8774461bb26b172e458443ce1eb071d`。
- effective_base: `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a`；effective_through: `aa63af9b5f5856533df2419d200237fccc599f54`，及随后仅作相同 delta 的 canonical 归并、unit 归档和交付记录的提交。
- main 增量仅为独立 feat-635 的设计/需求/原型与证据，没有产品代码、当前 specs、依赖或 CI 改动。逐项核对无影响本报告的范围、交互、权限与测试前提，保留前述 full 与最新局部通过结论；不把本次 retained 判断描述为重新执行全部门禁。
- corrected delta 保持此前独立逐项核对通过的原文，按所属 area 归并 canonical；不引入新的产品要求。
