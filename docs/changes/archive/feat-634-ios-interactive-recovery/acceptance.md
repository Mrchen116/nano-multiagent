# feat-634 — 原生客户端产品验收

> 对齐：spec.md / design.md；独立 reviewer；仅真实原生 GUI 操作作为客户端体验证据。
> Round 1 validation snapshot：`18e1af8b1 → bbc03566a30e9b269857d7369738a231d01e783a`。
> 当前裁决：Round 3 pass（产品验收）；冻结版本 `50a56c8ccea9c004da71a971a8536f47147d2240`。原轮问题已闭合，各轮原始结论保留如下；PR与构建来源交接由caller收尾。

## 环境与证据边界

- 专用 Simulator `Nano feat634`，UDID `8874240E-8E65-43C4-9405-CCA73C94440D`，iPhone 17 / iOS 26.4。设备 profile：1206×2622 pixels、scale 3，实际 viewport 402×874 pt。不能把它写成 design M1 的精确 390 宽证据。
- 主调度者交接并安装冻结 tree 的 Debug App `win.nanoim.ios`，0.2.0 / 634；reviewer 独立确认 checkout HEAD，未读取实现定位根因，未修改产品或测试。
- 隔离真实 IM / fixture Agent：`http://127.0.0.1:50212`；客户端经故障代理 `http://127.0.0.1:51158`。会话 `c_rzra1ze6`，卡片 `e38f0b46d9704adaba7d772395ab7725`。fixture 的确定性回执证明路由和可见回复，不证明 LLM 生成。
- 原生交互全部经 CUA Simulator；公开 API 仅用来模拟另一设备保存私人状态、读取权威消息及配置隔离故障。`simctl terminate/launch` 仅用于进程终止/恢复场景。
- 原型已独立查看：`/tmp/nano-feat634-prototype-{normal,conflict,recovery,large}.png`。本轮截图、临时对账数据位于 `/tmp/nano634-acceptance-*`，不提交截图缓存、token 或运行数据。
- 用户已明确“你模拟器测就行，测好了提pr，合入之后再发到手机”；本轮物理手机安装不适用。未触碰手机、个人浏览器账号或生产系统。

## 已完成的用户旅程事实

1. 打开聊天可读 Agent 摘要、主结论、输入及即时周结果。把分钟从35改为27，结果变189；图表三点变27/81/189。点击 View data 可读三个完整数值。主结论、控制与结果相邻；主按钮以青绿强调，与淡色恢复按钮区分。实际控件、结果和可展开数据帮助用户辨认操作后果。
2. 修改27后公开消息列表仍只有原有5条消息，私人状态 API 为27；返回列表再进入，原生字段仍为27。本地探索没有新增聊天请求。
3. 保持原生页面打开，经同一用户公开状态 API 模拟另一设备把27改为44，再在原生改为28。界面出现红色“changed on another device”及 Load latest，未静默覆盖；点击 Load latest 后原生显示44及308。证据：`/tmp/nano634-acceptance-conflict.png`。
4. 原生明确点击安排按钮，以44发出一次请求；聊天出现用户消息及 fixture 回执。服务端 `aadc65a014564024890ebb4a398595cc` 的完整 state 为44，event 含明确请求及 kind=reading。随后允许编辑为46并发起新的动作。
5. 对46动作设 `drop=true, missing=true`，让服务端保存但客户端收不到确认；出现 Delivery is unconfirmed 与 Check previous request。通过 GUI 重试，再终止/重开 App 后进入聊天，仍可核对原次请求。代理记录同 key `F7186A9A-AD87-441A-A408-02A2F8D658A4` 共3次 POST、body逐字节相同，服务端仅一条46用户消息 `52b64d383cfa46ceb5414bb5f7739369` 和一条 fixture 回执。
6. 未知期间输入后续草稿 `Later-draft-634-review`。网络恢复后点核对，画面停留 Sending…，随后 AX 仅剩 Simulator 壳、返回动作报 AXError.cannotComplete。再次终止/打开后可正常进入，46卡恢复可编辑、pending消失。后续普通输入也出现 AX 失联和部分输入，主调度者确认同时间 CoreSimulator 服务异常；因此此停滞暂不归因产品，也不以重开成功替代完整恢复体验验收。

截图：`/tmp/nano634-acceptance-local.png`、`/tmp/nano634-acceptance-conflict.png`、`/tmp/nano634-acceptance-restart-card.png`、`/tmp/nano634-acceptance-recovery-hung.png`。对账：`/tmp/nano634-acceptance-card-posts.json`、`/tmp/nano634-acceptance-messages.json`。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| normal / design 回复内探索 | 结论、控制、变化结果相邻，窄屏折行 | local截图；27→189及数据展开 | 402×874，默认字体 | 已观察内容层级 match；其他控件/大字体待验 |
| normal / 明确继续 | 明确动作、保留内容、发送状态不冒充业务完成 | 原生44/46动作与公开消息对账 | 同上 | 动作可辨且可再次发起；未知状态存在矛盾，见问题1 |
| recovery / 未知发送 | 简短核对/重试、新草稿保持 | restart-card / recovery-hung截图 | 同上，重启及丢回包 | inconclusive：环境异常中断核对完成体验 |
| conflict / 历史和冲突 | 内容可读、读取最新、有权动作受限 | conflict截图；Load latest后44/308 | 同上 | CAS冲突 match；只读/历史待验 |

## 问题与阻塞

| # | 严重度 | Regression Relation | 事实与用户影响 | Recommended Action / rationale |
|---|---|---|---|---|
| 1 | minor | direct | 重启未知卡片后，同一卡同时呈现绿色“Request sent. The Agent will reply…”与红色“Delivery is unconfirmed”，用户不能从卡片判定本次是否确认。restart-card截图可复查。 | fix-implementation：统一同一请求的状态提示；不把此局部矛盾单独夸大为数据重复。 |
| E1 | 必要证据阻塞 | unclear | Simulator AX 和系统服务异常，恢复网络后的完成状态、新草稿保留与后续普通输入无法可靠操作。 | 先恢复专用环境，再重验恢复/输入；不能因主线程或接口看似正常而判产品体验通过。 |

## 验收标准覆盖（进行中）

| Scenario（来源均为spec.md对应标题） | 真实证据与剩余范围 | 结果 |
|---|---|---|
| 阅读和本地探索 | Input、计算、LineChart、View data和Query计数已操作；条件/列表/选择、异常控件、大字体及附件审批回归待验 | inconclusive |
| 明确请求继续 | 44及46两个独立动作、完整state、重复key/body与单条消息已核对；未接工具反馈待验 | inconclusive |
| 恢复私人编辑 | 离开重进、CAS冲突和Load latest已验；其他用户私人状态隔离待验 | inconclusive |
| 发送带相关背景的文字 | 普通输入被环境异常中断；私聊/群聊背景及已发快照待验 | inconclusive |
| 历史、只读与无法呈现的内容 | 等待对应隔离测试资源 | inconclusive |
| 已保存但返回丢失后重新打开 | 卡片动作持久、重试同key/body且不重复已验；完整恢复状态、新草稿、文字/附件待验 | inconclusive |
| 提及成员发生变化后重试 | 尚未独立执行本轮GUI旅程，不能继承主调度者此前操作 | inconclusive |
| 退出、切服务或撤销权限 | 尚未执行 | inconclusive |
| 交付可合入版本 | 当前尚未完成全场景；PR及最终产物来源由收尾交接核实 | inconclusive |
| 合入后安装 | 最新用户明确安排合入后；当前尚未合入，物理安装不属本轮 | not-applicable |

## 上层文档同步

- [x] `SPEC.md`：无需更新；本轮未观察新的跨包边界。
- [x] `docs/specs/im/ios-client.md`：需要由主调度者收尾归并已验证的delta，当前尚未反映通用交互增量。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## Round 2 — 修复版补充与复验（进行中）

> Validation snapshot：`bbc03566a → 35a9c0588dfb3bd9f6c34e678c2d2cfd3396889c`；主调度者交接范围为附件确认清理、pending隐藏旧成功提示及对应测试。仍在同一402×874模拟器，保留数据覆盖安装。正常阅读、计算、CAS的前轮具体证据仍适用；以下为新版本独立GUI补验。

- 选择控件：综合卡 `ad3fd3f2ae764a5cb35644c949434198` 由15分钟选择30分钟，条件文案变为“30分钟可以读得更深入”，Each两条列表保持可读；重开后30分钟恢复。前轮没有这一证据，本轮补齐。
- 历史：本次隔离数据库种子带`read_only`的复制历史卡内容可读；点击“按选择继续”显示“Historical replies cannot submit requests”，没有新用户消息。此证据仅覆盖原生读取历史标志与提交边界，不证明服务端fork创建链。图 `/tmp/nano634-acceptance-readonly.png`。
- 不支持版本：隔离种子的future-2卡保留文字摘要，明确unsupported并提供Load latest，其他消息和composer可继续操作。图 `/tmp/nano634-acceptance-unsupported.png`。未连接Query工具在公开发布API即422拒绝，未获得原生该错误态；不能把future-2当作工具错误的替代证据。
- 私聊普通文字：原生输入并发送`Private634`，可见同文用户气泡与fixture回执；实际请求正文保持`Private634`，interaction_contexts含当时`$choice=long`及相关另一张short卡。图形与公开API对账在`/tmp/nano634-acceptance-private-context.json`。
- 修复1闭合：综合卡明确动作进入未知，重启后仍可核对；pending时没有旧绿色Request sent。重试后保持未知，输入新草稿`New634`，恢复网络点Check previous request后pending消失、控件可再次操作且新草稿仍为New634。图 `/tmp/nano634-r2-pending.png` 与 `/tmp/nano634-r2-recovered-draft.png`。同key `EDD5BC1E-3D28-4A7D-A5CC-5096DB37F77F` 两次body相同，state=long。环境恢复后相同流程不再停滞，前轮E1在此流程闭合，不作为产品bug。
- 群聊隐私：独立创建隔离群`c_tslt6hoh`，编辑卡`6dec3f90c0e2418ea92682d82b7b2218`为30分钟，再发送普通文字。实际请求没有interaction_contexts，未暗中附带私人选择。
- 改名重试：GUI从@候选选RenamedFixture，发送`@RenamedFixture mention634`，回包丢失后主调度者仅改同一成员显示名为ReviewRenamed634。终止/重开，聊天显示新名，pending仍保留原草稿。强制attempt404后GUI Retry，成功恢复；同key `F6E1E57C-7896-4792-9351-8221D75FEFB7` 两次body逐字节相同，仍提及`u_n4byg66q`，服务端仅一条`33aa071a416a4eecb983c197ee069f70`。图 `/tmp/nano634-r2-mention-{pending,recovered}.png`，对账`/tmp/nano634-r2-mention-posts.json`、`/tmp/nano634-r2-group-messages.json`。
- 附件前置仍不足：GUI Add attachment→Photos后系统选择器持续Loading并再次AX失联；尚未成功选中附件。重新启动App后普通GUI恢复。此项不以代码测试或模拟器导入图片的成功代替真实选择/发送。
- 撤权：群内发送`Revoke634`建立unknown pending。主调度者将一次性群设private并通过真实DELETE参与者API撤销测试用户。原生收到membership更新后，立即清空聊天正文、卡片、composer与Retry，显示“You no longer have access”；返回列表该群消失。恢复代理后没有重发Revoke634。图`/tmp/nano634-r2-revoked.png`。
- 退出：真实Me→Sign out→确认后回登录页，旧聊天/草稿不再显示。尝试建立Logout634 pending时发生原私聊输入/发送AX异常，代理没有对应POST；故本次仅证明真实退出入口，不能声称pending logout已验证。后续需新账号和可操作的短会话补齐。
- 真实observer：`c_bmwqm8fm`为双Agent协作私聊，nano为owner观察者。原生底部显示Agent collaboration · read only，无composer；卡片文本/列表可读，点击继续被明确拒绝。`/tmp/nano634-r2-observer.png`。这补齐只读聊天边界，不再只依赖单卡种子。
- 跨账号私人草稿与pending退出：原生nano打开`Private state 634 / c_avk2pgoy`，亲自Select15→30。发送`LogoutPending634`并通过故障代理形成unknown后，真实Me→Sign out确认；恢复网络、登录第二测试human `reviewer634`，相同卡`7b0f74a73db9476e815232c60de46ca2`仅显示本人默认15分钟，无A的Retry或composer草稿；服务器已保存的共享消息正常可读。独立API核对A为long/revision2，B为空/revision0。图`/tmp/nano634-r2-userB-private.png`。A待确认记录没有进入B，A私人选择没有公开给B。

### Round 2 当前覆盖与未闭合项

| Scenario | 结论（仅此时点） | 依据 / 待补 |
|---|---|---|
| 阅读和本地探索 | inconclusive | 默认402宽Input/Select/条件/Each/图表/Query与本地不发请求已证；精确390、大字体与附件/审批保留待补 |
| 明确请求继续 | pass | 两次独立动作可发送、完整state；故障同key/body不重复、恢复后可再操作。conversation_messages可读，非法未连接Query在公开API422拒绝，未伪装执行成功；不声称获得原生非法工具错误画面 |
| 恢复私人编辑 | pass | 自己离开重进、CAS冲突加载最新、A/B同卡私人状态隔离均有GUI+API证据 |
| 发送带相关背景的文字 | pass | 私聊Private634正文不变并携带选择，群聊mention634不含interaction_contexts；已发送请求快照保持原内容 |
| 历史、只读与无法呈现的内容 | inconclusive | 复制历史、真正observer与future版本均已验；superseded卡尚待补验 |
| 已保存但返回丢失后重新打开 | inconclusive | 文字及卡片重启恢复不重复、新草稿保留已证；附件选择器Loading阻止附件旅程 |
| 提及成员发生变化后重试 | pass | 真实候选→改名→重启→404后同body重POST→同条消息 |
| 退出、切服务或撤销权限 | inconclusive | 带pending logout后B不继承、membership撤销立即清理已证；切服务尚待补 |
| 交付可合入版本 | inconclusive | 必验范围仍有缺口；不以已出IPA替代产品体验 |
| 合入后安装 | not-applicable | 用户明确要求合入后，当前尚未合入 |

当前不能作通过裁决；不把“未改基线路径”或“主线程样本idle”转写为附件体验已通过。


## Round 2 — 390pt 补齐与裁决

相同冻结版本 `35a9c0588dfb3bd9f6c34e678c2d2cfd3396889c` 在新的专用 iPhone 16e / iOS 26.4（`9DEDB8EC-7924-4FFF-ABFF-34FAB2C544D2`，390×844 pt）继续真实 GUI 验收。旧设备停止，新设备使用相同隔离服务。系统 Photos 首次启动完成后，照片选择器可正常使用；这说明验收前置已恢复，不推断此前系统 Loading 的代码根因。

- 默认字体390pt：主结论、选择、条件、列表和继续/恢复按钮清楚可达。原综合卡 `ad3fd3f2ae764a5cb35644c949434198` 被 `1a6f7f38d36947cbbb113caff769ae91` 替代后，点击旧卡继续，原生拒绝历史请求且正文仍可读。截图 `/tmp/nano634-390-superseded.png`。
- 相同聊天中新的交互卡与既有 approval 卡同时可读，截图 `/tmp/nano634-390-card-approval.png`。只验证审批展示保留，未冒充真实执行审批成功。
- 附件恢复：通过 Add attachment → Photos 亲自选择测试图片，composer出现 `photo-0D036483.jpg` 预览。提交丢回包后显示unknown；终止/重开后原待确认附件缩略图恢复。恢复POST网络、保留attempt404，点击Retry成功，原预览和Retry消失，聊天历史图片仍在。截图 `/tmp/nano634-390-attachment-recovered.png`。两次POST使用相同key `355F80A1-0512-40D4-8551-23F45B1AEA2B`、逐字节相同body及attachment URL；对账 `/tmp/nano634-390-attachment-posts.json`。消息计数以随后公开API补证为准。
- 切服务：发送 `origin634` 形成unknown后，经真实Me退出→Connection settings将来源从故障代理51158改为直连50212→重新登录。相同后台会话正常显示权威历史 `origin634`，没有旧来源的Retry或草稿。此证据覆盖不同origin/相同backend，不夸大为迁移到不同后端。
- 大字号：经本轮允许的simulator临时设置切为 `accessibility-medium`。Private state 634中30分钟条件结果AX为完整“30分钟可以读得更深入”，但屏幕持续显示“30分钟可以读得更…”；没有展开入口。主按钮和恢复按钮可达；点恢复15分钟后短结果完整显示。因此卡片操作可用，但用户不能完整阅读操作后的结果。截图 `/tmp/nano634-390-largefont-truncation.png`。

### 新问题

| # | 严重度 | Regression Relation | 事实与影响 | Recommended Action |
|---|---|---|---|---|
| 2 | major | direct | 390pt / accessibility-medium 时条件结果被单行省略，无全文入口；用户看不到探索后的完整建议，未满足spec“窄屏、大字体时主内容和操作仍可达”。 | fix-implementation：让结果正文随大字号换行并保留完整阅读，再在同viewport与字体复验。 |

### Round 2 最终覆盖

| Scenario（来源：spec.md） | 结果 | 具体证据 |
|---|---|---|
| 阅读和本地探索 | fail | Input/Select/条件/Each/图表/Query及390默认字体均已操作；大字号结果省略，问题2阻塞。附件/审批展示保留已观察。 |
| 明确请求继续 | pass | 两次独立动作与完整state，未知重试同key/body、恢复可继续；非法未连接Query被公开API拒绝，未假称成功。 |
| 恢复私人编辑 | pass | 离开重进、CAS/Load latest、A/B私人状态隔离均有独立证据。 |
| 发送带相关背景的文字 | pass | 私聊正文不变并携带选择，群聊不带私人上下文；快照重试不变。 |
| 历史、只读与无法呈现的内容 | pass | 真实observer、历史种子、真实superseded和future版本均可读并受限。 |
| 已保存但返回丢失后重新打开 | inconclusive（附件消息计数待补） | 文字/卡片/附件均真实重启恢复；同key/body，成功清除旧pending并保留新草稿；附件历史保留。 |
| 提及成员发生变化后重试 | pass | 候选选择、改名、重启、attempt404、同body重POST及单条消息。 |
| 退出、切服务或撤销权限 | pass | 带pending退出后B不继承，真实撤权立即清理，不同origin登录不带旧Retry。 |
| 交付可合入版本 | fail | 必验阅读场景仍失败，尚不可给产品验收通过裁决。 |
| 合入后安装 | not-applicable | 用户明确要求合入后；本轮模拟器验收、尚未合入。 |

整体 verdict：**fail**。已闭合问题1及环境E1；当前新增1个major，无源码定位推测。待问题2修复后targeted复验，同时补附件单条消息计数。未失效的已完成旅程按本报告具体证据保留。


## Round 3 — 大字号 targeted 复验与最终产品裁决

- Validation snapshot：`35a9c0588dfb3bd9f6c34e678c2d2cfd3396889c → 50a56c8ccea9c004da71a971a8536f47147d2240`。caller交接范围仅Markdown正文高度适配；确认checkout HEAD，并在caller覆盖安装后的同一390×844专用模拟器实际打开。未读取实现定位，未改源码或测试。
- `accessibility-medium`：同一卡片亲自15→30，完整结果“30分钟可以读得更深入”自然分两行显示，末尾不再省略；摘要、标题、选择、两条列表与两按钮均可读可达。实际点击恢复15分钟后结果变“先从15分钟开始”。截图 `/tmp/nano634-r3-largefont-fixed.png`、`/tmp/nano634-r3-largefont-full.png`。问题2闭合。
- 默认字体 `large`：30分钟结果完整一行，摘要和主结论清楚，主/次按钮并排且样式层级保持，历史附件仍可读；截图 `/tmp/nano634-r3-default.png`。复验后恢复模拟器默认字体。
- 附件计数补证：caller经同一隔离真实API读取并交接 `/tmp/nano-feat634-attachment-count.json`，reviewer读取核对唯一消息 `6c2ad70b862745eaa5e7ed1a72bf8fad` 的会话、文件名、附件URL均与自己的两次同key/body记录对应，matching_message_count=1。结合Round 2亲自GUI的未知→重启→Retry→清理结果，附件恢复证据闭合。此计数来源明确为caller API补证，不冒充reviewer再次执行发送。

### 最终 Scenario 裁决

| Scenario（spec.md） | 结果 | 证据归属 |
|---|---|---|
| 阅读和本地探索 | pass | Round 1计算/图表/Query，Round 2选择/条件/Each/390附件与审批，Round 3大字号完整结果和默认字体复验。 |
| 明确请求继续 | pass | Round 1独立动作与完整state；Round 2未知恢复后可再次操作。 |
| 恢复私人编辑 | pass | Round 1离开重进/CAS；Round 2跨用户私人状态隔离。 |
| 发送带相关背景的文字 | pass | Round 2私聊、群聊正文与上下文对账。 |
| 历史、只读与无法呈现的内容 | pass | Round 2历史/observer/superseded/future版本。 |
| 已保存但返回丢失后重新打开 | pass | Round 2文字、卡片、附件独立GUI恢复与新草稿；本轮补齐附件单条权威消息。 |
| 提及成员发生变化后重试 | pass | Round 2同成员改名、重启、404重试仍同body且单条消息。 |
| 退出、切服务或撤销权限 | pass | Round 2真实退出、跨账号、不同origin与membership撤销。 |
| 交付可合入版本 | pass（产品门禁） | 本轮全部适用产品场景通过；PR创建、最终报告提交与制品SHA记录由caller完成，不在产品报告中虚构已交付PR。 |
| 合入后安装 | not-applicable | 用户明确安排合入后安装手机，本轮仅模拟器；尚未合入。 |

整体 verdict：**pass**。当前未解决blocking/major/minor均为0；历史问题1、2已分别在Round 2、3闭合。Round 3仅调整正文布局，未失效的行为证据逐项继承前轮；不重复全套故障测试。环境由caller管理，本reviewer未另启常驻服务；当前390模拟器字体已恢复默认、登录来源为隔离IM直连50212，后续清理由caller统一执行。
