# feat-572 — 独立产品验收 Round 1

> Validation snapshot: `7340a7805 → d5de5f9f7abeb33a3ba2959d8ef602ea0b222b96`；mode=full；2026-09-30 22:05–22:33 Asia/Shanghai。

## Verdict

**fail**。Highest Required Action: **fix-implementation**。1 major 产品失败、1 minor 原型偏差；另有未完成真实验收项。未读源码定位/修改实现，未复用 implementation.md 成功叙述。公网与飞书必须保留 inconclusive。

运行：same-origin `http://127.0.0.1:50620`，初始IM PID21201 cwd本unit、HEAD固定；caller在测试中用 `git archive d5de5f9f7` 的 `output/feat572-review-baseline/src/IM` 重启为PID27203，同DB/端口/原env。浏览器JS/CSS与本unit既有dist字节一致（runtime-evidence.json）。后续工作区实现修复不属于本报告受审版本。模型deepseek:deepseek-v4-flash。浏览器独立sessions feat572-review / feat572-review-admin / feat572-review-auth；原型8572未停止。

所有下述 evidence 相对路径位于 [`../evidence/reviewer-round1-20260930/`](../evidence/reviewer-round1-20260930/)。截图不含地址栏绑定token；private日志、会话token、测试脚本不提交。

## 用户旅程体验

- J1：UI新建reviewer572a，pending访问Tasks退回membership；管理员批准，刷新继续原Tasks深链。第二用户reviewer572b重复UI注册批准。普通成员无公司成员入口、策略六字段只读；直接API负向见api/qualification证据。
- J2：peer整机交给reviewer572a后，在Review572B(c_lh8o0qse)由feat572-peer把tg_c1d2b5b5.n3描述追加独立验收标记，rev3→4。nano在Review572A(c_ojo75qof)用另一个Gateway的e2e更新n2结果，rev4→5。两群任务入口分别保留节点；手机回聊保留草稿并追加引用而不发送。第三个Review572 Empty(c_8ubil5a1)显示空态。
- J3：从A群移除reviewer572a后原群拒绝，Tasks仍可打开同图；admin解散A群后任务与结构保留。
- J4：本机bind链接→网页接受→本机yes，peer归属reviewer572a，Me显示1台在线。中断bind后重新执行可继续确认。管理员停用弹窗准确提示1node/1agent；取消保持active，再确认使已打开聊天立即变suspended。之后本机将同peer交回nano，node/Agent IDs保留，reviewer572a仍停用。旧机器身份拒绝矩阵没有完整独立证据。
- J5：新增隔离global Agent review572-global（workspace为本unit/output/feat572-review-global）。nano交办17×19子任务；普通成员reviewer572b查看主Work、工具轨迹和子执行323，只有Profile/Work无Config。global新建tg_5508fe90；同一聊天两次明确要求删除均失败（问题P1）。保留该图/Agent供复验。
- J6：粘贴有效PNG，e2e识别REVIEW与红方块。16MiB附件保留文件错误chip和正文；仅发送文字后失败附件仍在。经caller授权用两条明确review572-*账本fixture分别触发owner1GiB/service10GiB，真实上传API拒绝、普通UI简短提示、仅文字发送与真实回复成功、管理员容量告警可见。不是实际上传GiB的负载测试。两fixture已精确清理，剩余0。
- J7：同refresh并发200/401，旧refresh401；同版本重启后已轮换/已退出refresh401，仍有效refresh200。登录第11次错误429，Retry-After898秒，伪造来源头不能绕过，UI保留输入；自然冷却恢复未完成。

## Reference Artifacts Reviewed

已读spec/design的全部Scenario与must-match表、prototype.html真实浏览器，以及prototype-visual-20260930中login-error/pending/members/bind/group-tasks/policies截图。下表关键状态均为真实客户端截图；未拍全的异常状态不推定通过。

| Reference/契约 | 实际证据（png） | viewport/状态 | 对照结论 |
|---|---|---|---|
| 认证/pending/suspended | login-error-1440/390；pending-1440/390；suspended-1440/390；login-cooldown-1440/390 |1440×900、390×844|准入状态/输入保留match；错误红色卡片deviation P2|
| 成员入口、批准、停用影响 |members-1440/390；suspend-impact-1440/390；member-me-390|双视口|功能层级/取消/影响说明match；批准失败分支未测|
| 公司Tasks |shared-task-390；task-after-dissolve-390；global-delete-still-present-1440|双视口加载/受保护来源|公司可见/图节点保留match；搜索错误/无结果未覆盖|
| 当前群任务完整路径 |group-a-task-1440；group-b-task-390；group-empty-1440/390；return-draft-390|双视口有活动/空态/回聊|紧凑任务名→总目标→状态时间、手机全宽、桌面侧栏match；同图/草稿match|
| 完整设备交接 |bind-receive-1440/390；bind-await-local-1440/390；member-me-390|双视口接受/等待本机/归属结果|整机说明/目标账号/本机确认match；过期/取消状态未覆盖|
| 聊天附件反馈 |attachment-error-1440；attachment-too-large-390；attachment-text-only-390；capacity-error-1440/390|双视口失败/仅文字|文件级chip保留/仅文字match；另有顶部toast不作为唯一反馈。格式/网络/冷却逐分支未覆盖|
| 管理员容量 |capacity-admin-1440/390；service-capacity-admin-390；policies-member-1440/390|双视口，账本fixture|仅管理员见用量告警、普通聊天不要求清理match；用fixture触发，不冒称真实GiB上传|
| 既有菜单/Me/策略 |member-me-390；policies-admin-1440/390；policies-member-1440/390|双视口只读/可编辑|六字段双卡/身份节点数量保留match；双语全菜单与保存失败重试未完整覆盖|

## 问题清单

|#|Severity|Regression Relation|现象/复现与期望|Recommended Action / Action Rationale|
|---|---|---|---|---|
|P1|major|direct|global Agent在c_ga10oz1b成功创建tg_5508fe90。22:27与22:29两次真实人类明确要求删除指定整图，5次实际delete工具记录均confirmation_required，图仍可打开。期望明确交办可删除。证据global-delete-tool-evidence.json、global-delete-failed-1440/390、global-delete-reconfirm-failed-1440、global-delete-still-present-1440。|fix-implementation；打通有效global来源的人类删除授权，保留无明确授权时拒绝；不得用模型自报confirmed绕过。需真实global targeted复验。|
|P2|minor|direct|登录错误双视口仍为带红背景/边框/图标alert卡片。design全局规则明确要求对齐输入框的简短红字，不用大块红色卡片。证据login-error-1440/390，reference prototype-visual/login-error-390。|fix-implementation；落实must-match错误呈现与关联表单的可访问反馈，再双视口对照。|

### Side Findings / 环境限制

- peer第一次bind会自动后台启动，reviewer随后额外前台启动同config，造成重复实例污染；之后出现旧placeholder在成功答复后relay idle120s。**不作为单实例产品回归**。证据late-relay-error-1440仅供环境记录；caller已确认该干扰。后续停止我启动的peer PID26362，第一Gateway、IM、原型未停。
- suspended退出跳登录时短暂出现authentication service unavailable；不阻断退出，未单独重验，记录minor side finding。
- R6缺当次实际上线授权；R7专用Bot被其他unit占用。需要caller准备授权后的真实域名部署、可独占的原专用飞书窗口。严禁以localhost或mock补pass。

## 验收标准覆盖

表中pass仅限所述真实旅程；inconclusive不是产品失败断言，也不是通过。首文档每个Scenario均列出。


### Requirement: 正常用户只需 Nano IM 账号即可从公网访问

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|本机通过实际域名访问与实时使用|spec.md同名Scenario|R6缺当次上线授权；未访问生产，不能以localhost替代。|inconclusive|
|朋友公开注册|spec.md同名Scenario|J1；pending-390/1440.png|pass|
|待批准账号不能进入公司内部协作|spec.md同名Scenario|J1；qualification-evidence.json（聊天/任务/Agent/节点/Work直接请求403）|pass|
|管理员批准后进入公司协作空间|spec.md同名Scenario|J1/J5；批准后原Tasks深链与共享联系人、真实Agent、Work可用|pass|
|普通用户不能批准自己或他人加入|spec.md同名Scenario|api-evidence.json：普通成员approve403；pending无公司入口|pass|
|匿名访客只能进入公开认证入口|spec.md同名Scenario|J1；api-evidence.json：匿名聊天/任务/Work/nodes401|pass|

### Requirement: 管理员可停用成员并保留协作记录

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|停用后既有登录与实时连接不再提供公司访问|spec.md同名Scenario|J4；suspended-1440/390.png；qualification-evidence.json|pass|
|停用不删除历史协作记录|spec.md同名Scenario|J4；停用后admin仍见Review572B历史，tg_c1d2b5b5保留|pass|
|普通成员不能停用他人|spec.md同名Scenario|api-evidence.json：ordinary-suspend403|pass|
|停用成员同步撤销名下机器接入资格|spec.md同名Scenario|人类会话已实时撤销；停用后机器实际拒绝/其他同事不可用反馈未独立充分捕获，且早期peer双实例污染。|inconclusive|
|停用接入保留资源记录且不改变机器归属|spec.md同名Scenario|J4；停用后本机交回nano时仍显示同node/Agent ID|pass|

### Requirement: 注册与认证具有实际生效且可恢复的滥用防护

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|单一来源反复尝试被节流|spec.md同名Scenario|第11次429与表单冷却已见；完整898秒自然恢复未等待完，未覆盖注册限流恢复。|inconclusive|
|同一账号的分散密码猜测受到限制|spec.md同名Scenario|自报来源变化仍限流；没有多个真实公网来源，完整冷却恢复未覆盖。|inconclusive|
|客户端不能伪造来源绕过防护|spec.md同名Scenario|rate-evidence.json：逐次改变X-Forwarded-For和CF-Connecting-IP仍第11次429；公网真实来源另属R6|pass|
|合理少量用户与会话恢复可用|spec.md同名Scenario|J1；两账号UI注册/批准、并发refresh与重启有效refresh200；冷却输入保留|pass|

### Requirement: 刷新凭据吊销在并发和服务重启后仍可靠

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|刷新轮换后旧凭据保持失效|spec.md同名Scenario|api-evidence.json + refresh-restart-evidence.json：旧401、有效200|pass|
|并发刷新不能重复恢复会话|spec.md同名Scenario|api-evidence.json：并发200/401|pass|
|退出后失效状态跨重启保留|spec.md同名Scenario|refresh-restart-evidence.json：logged_out401、valid200|pass|

### Requirement: 系统级管理与既有协作权限有明确边界

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|系统策略仅管理员可写|spec.md同名Scenario|普通成员PATCH403与只读UI通过；本轮未完成管理员修改保存/失败重试的完整UI往返。|inconclusive|
|新注册不能自动获得系统管理权|spec.md同名Scenario|普通注册角色member与无管理入口已见；携带伪造管理员字段注册未独立探测。|inconclusive|
|既有共享 Work 保持|spec.md同名Scenario|J5；shared-work-child-1440/390.png；普通成员可展开其他owner主轨迹与子执行323|pass|
|成员和 owner 边界保持|spec.md同名Scenario|私聊/附件/他人node负向已见；完整所有Agent管理数据矩阵未展开。|inconclusive|
|共用 Gateway 统一管理、共同使用|spec.md同名Scenario|J5；普通成员reviewer572b使用nano的e2e识图成功，Profile无Config|pass|

### Requirement: Gateway 可由本机确认整体换绑给有效公司成员

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|有效成员自行接入或换绑 Gateway|spec.md同名Scenario|J4；本机bind→网页接受→本机yes→Me设备在线；bind-receive/await-local双视口|pass|
|仅知道节点标识不能远程抢绑|spec.md同名Scenario|attachment-boundary-evidence.json：仅node_id请求422；J4接受网页后仍须本机确认|pass|
|不能换绑给尚无有效公司资格的账号|spec.md同名Scenario|pending/suspended公司API拒绝已见；未执行真实网页接收挑战的两种失败状态。|inconclusive|
|原管理者停用后设备可合法交接|spec.md同名Scenario|J4；reviewer572a停用后peer换回nano，IDs保留，原账号仍suspended403|pass|

### Requirement: 有效公司成员与具备任务能力的有效 Agent 可查看全部任务

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|公司任务跨账号与聊天可见|spec.md同名Scenario|J2/J5；初次批准即看其他owner图；private-origin-company-task-390.png|pass|
|任务可见不授予原聊天与附件访问权|spec.md同名Scenario|J2/J3/J5；非成员任务无回原聊入口；移出群原聊天拒绝；nonmember附件404|pass|
|跨 Gateway 和账号的 Agent 可读取同一任务图|spec.md同名Scenario|J2；nano/e2e与reviewer572a/feat572-peer实际读写同tg_c1d2b5b5|pass|
|任务读取仍要求有效身份和已授予的工具能力|spec.md同名Scenario|两个有效Agent成功；pending/suspended人类拒绝；未独立覆盖未配置工具/失效机器矩阵。|inconclusive|
|Agent 按需读取而非自动摄取全部任务|spec.md同名Scenario|按需工具调用、没有自动执行已见；每轮上下文摄取是实现层，未读取源码推断。|inconclusive|
|飞书沿用现有主人识别与 Agent 公司资格|spec.md同名Scenario|R7专用Bot被unit-feat-569占用，不抢占/不绕锁；未用mock替代。|inconclusive|

### Requirement: 公司成员通过 Agent 共同维护任务且变更可辨认

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|跨账号和 Gateway 新建与修改任务|spec.md同名Scenario|J2/J5；两个owner两Gateway同图rev3→4→5；global实际新建tg_5508fe90|pass|
|删除任务需要明确要求或确认|spec.md同名Scenario|J5/P1；两次明确删除仍confirmation_required，图存在|fail|
|修改者与来源真实可辨认|spec.md同名Scenario|J2；节点详情Last updated by feat572-peer/Last updated in Review572B；另一节点由e2e更新|pass|
|并发修改不能静默覆盖|spec.md同名Scenario|两Agent顺序更新通过；本轮未制造真实过时revision提交。|inconclusive|
|任务写入保持有效身份与工具边界|spec.md同名Scenario|有效写入与人类资格拒绝通过；未独立覆盖机器失效和关闭任务工具后的写入。|inconclusive|
|外部渠道任务写入按 Agent 资格判定|spec.md同名Scenario|R7资源占用，真实飞书待验。|inconclusive|

### Requirement: 群内便捷查看本群新建或编辑过的任务

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|群任务入口展示本群工作|spec.md同名Scenario|J2；group-a-task-1440/group-b-task-390/group-empty双视口，链接指向同图真实节点|pass|
|总任务与子任务跨群持续协作|spec.md同名Scenario|J2；A/B群分别保留n2/n3，第二次更新不丢B关联；同图revision5|pass|

### Requirement: 任务独立于群成员与群聊生命周期

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|退群不撤销公司任务读取资格|spec.md同名Scenario|J3；task-after-removal-390.png，原群导航退回/chat|pass|
|解散群不删除公司任务|spec.md同名Scenario|J3；task-after-dissolve-390.png，图仍存在且两个子节点保持|pass|

### Requirement: 自动附件处理不能访问任意服务端目标

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|正常上传与 Agent 图片理解保持|spec.md同名Scenario|Web实际识图REVIEW/红方块通过；外部频道附件属于R7，未完成。|inconclusive|
|伪造地址和附件引用被拒绝|spec.md同名Scenario|非成员附件404；三个伪造URL消息201后Agent明确下载失败；未设置目标监听器证明没有网络触达，不把失败回复等同SSRF全面通过。|inconclusive|

### Requirement: 公网滥用不能无界消耗服务的有限资源

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|超限上传和请求有明确拒绝|spec.md同名Scenario|16MiB附件错误chip、owner/service累计拒绝通过；超长消息/流式超限对象完整性未独立覆盖。|inconclusive|
|附件空间不足不阻断文字聊天|spec.md同名Scenario|J6；capacity-error/text-only/admin与service-capacity截图；账本fixture+真实UI/API，非GiB实际上传|pass|
|实时连接受控且可恢复|spec.md同名Scenario|正常Web实时往返与停用撤销通过；过量连接与限流恢复未独立覆盖。|inconclusive|

### Requirement: 发布与恢复可验收，凭据不随运维证据公开

| Scenario | 期望来源 | 验证/证据 | 结果 |
|---|---|---|---|
|公网仅开放预定 IM 服务|spec.md同名Scenario|R6缺上线授权，未上线。|inconclusive|
|运维证据不包含可复用凭据|spec.md同名Scenario|本报告/截图/JSON脱敏；未全面审阅运行访问/错误日志，不宣称所有日志无泄露。|inconclusive|
|故障时可停止公开访问并恢复|spec.md同名Scenario|R6未发布；只完成同版本重启凭据复验，不等于生产备份恢复演练。|inconclusive|
|免费部署范围可核对|spec.md同名Scenario|R6未上线，未核对Cloudflare账号与域名续费。|inconclusive|

## 上层文档同步

- [x] SPEC.md：本unit公司资格/整机交接改变长期边界，需由orchestrator核对最终归并；本reviewer不修改。
- [x] docs/specs/im 与 gateway：需要按最终实现归并unit的6份delta；本轮仍见current auth文档旧契约，不能视为完成。
- [x] AGENTS.md / CLAUDE.md：无需本次验收补充。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

## 收尾与复验范围

仅报告及脱敏证据可提交；未触碰源码/测试/受控配置。保留reviewer572a suspended、reviewer572b active、review572-global与失败图供targeted复验。容量fixture已清理；peer已停止（caller如需重启须确保仅一实例）。R6/R7及本表所有inconclusive在后续Round继续继承；不能因P1/P2修复就自动提升完整验收为pass。


---

# 独立产品验收 Round 2（targeted + 本地未决补验）

> 2026-09-30 22:41–23:04 Asia/Shanghai。主体验证 `ce0c557c41542e3d7774d739e3b69603ab2f4093`（产品改动 `bf9fde9e3`）；最终增量验证 `7df455679`。前端仍为bf9fde批次dist，HTTP资源哈希与本地dist相同。先前有效证据继承，不冒充全部在最终HEAD重跑。

## Verdict

**fail**。Highest Required Action: **pass**（仅指当前无新增必须实施的修复；完整验收仍fail，须补足缺失证据，不代表交付/发布通过）。本轮未留已复现的major实现失败；Round1 P1真实global来源与P2认证视觉均收口。保留1项minor UX限制记录UX1。必验inconclusive仍存在，故不能给完整pass或发布许可。

IM由caller从33315/Gateway33655统一更新至IM41358/Gateway41369；同隔离50620、DB和配置。最终ticket脱敏及真实global重启恢复在7df455679上验证。无生产变更、无飞书占用抢夺、未停第一Gateway/IM/8572原型。只提交本报告与脱敏证据。

本轮证据：[reviewer-round2-20260930](../evidence/reviewer-round2-20260930/)。本节所列png均同时有1440×900及390×844版本，除另有说明。前端故障注入与真实后端边界证据明确区分。

## 新增真实旅程

- **R2-J1 global删除**：长句明确要求删除仍需确认；随后在同聊天真实发送精确“删除 tg_5508fe90”，global工具deleted=true、deleted_ids=n1/n2、revision3，get拒绝，其他成员Tasks列表移除。global-delete-tool-evidence与global-delete-success双视口证明；P1 closed。认证错误同样实际错误密码触发，现为与输入框对齐的简短红字，输入保留；login-error双视口与原型对照match，P2 closed。
- **R2-J2失败不丢输入**：管理员策略14→15保存，刷新仍15；拦截该浏览器PATCH制造网络中断，14草稿与Unsaved changes保留；恢复真实网络后重试保存回14。批准C时单浏览器断网，仍pending，恢复后Approve成功。Task search无结果/失败/恢复双视口已补。原型信息层级与主要控件可用，英文和中文Me身份/节点数量/菜单保持。
- **R2-J3附件**：真实坏PNG被拒为Unsupported format，正文和文件chip保持；单浏览器中止上传请求产生网络失败，可Retry；显式注入429/Retry-After测试冷却UI，恢复真实上传后成功。两种注入只作为UI故障反馈证据。另通过真实后端发送2.2MB JSON与16MiB chunked上传分别413，上传预留回到0。未重复写GiB容量fixture，继承R1真实额度拒绝。
- **R2-J4交接/停用**：peer本机bind→B网页Cancel，CLI退出，旧链接失效且归属不变；另建操作，仅将本次操作expires_at置过去以观察过期双视口（明确fixture，非自然等待）。新操作正常交给B，bind自动启动唯一peer PID38019，不另开实例。管理员刷新后确认1node/1agent影响，停用B，B打开页面即时membership、peer离线且重连403。nano向peer发消息得到503未连接且草稿保留。旧owner凭据和停用机器凭据在真实gateway端点403；机器HTTP凭据本就不能访问人类API，HTTP401不单独作为撤销证明。随后本机合法交回nano，IDs保持，B仍suspended；旧身份仍403。
- **R2-J5任务边界**：global用合法但过时base_revision1对n3写入，真实version_conflict current_revision5；只读复核原描述和时间戳未变。peer Task Graphs UI关闭并保存，后续真实群内请求读写时Agent明确无task_graph、无工具调用、没有绕行；图仍revision5。验后UI重新开启并保存。代码/权限结构未由reviewer阅读或修改。
- **R2-J6资源与来源**：普通新注册携带伪造admin/active字段，真实结果仍pending/member；有效bind挑战对pending和suspended403。C批准后对nano私聊读写、Agent/节点管理数据和配置负向拒绝，而global Work正常共享。临时本机HTTP canary收到0请求、global附件明确unavailable；没有用一句模型“下载失败”替代目标监听证据。
- **R2-J7实时与日志**：新会话真实10张ticket成功，第11张429，自然冷却后200；C已有浏览器加4条测试WS接入，再多2条拒绝，70KB帧1009，关闭测试连接后浏览器可用。另单浏览器注入429验证倒计时与重新登录入口，解除后自动恢复。发现旧启动方式原始ticket日志后caller修正，最终新日志ticket全部[redacted]。最终真实global回复“已恢复”，不是只看HTTP健康。

## 必需原型对照补齐

| must-match区域 | 本轮新增状态/证据前缀 | 实际双视口结论 |
|---|---|---|
|认证|login-error|简短红字、无大块红卡、输入保留；P2修复match|
|公司成员|member-approve-failure|失败仍pending、操作可重试；恢复Approve成功，停用1node1agent影响继承R1/R2真实行为|
|公司Tasks|task-search-empty / task-search-failure|无结果、失败与重试清晰；共享图/受保护来源继承R1|
|群任务回聊|继承R1 group-a/b/empty/return-draft|本轮未改相关前端，原match仍有效|
|设备交接|bind-cancel / bind-cancel-invalid / bind-expired|取消返回聊天；旧/过期链接不可接受，主按钮不会窄屏断字；正常完整交接真实通过|
|附件|attachment-format / attachment-network / attachment-cooldown|逐文件错误、正文保留、恢复重试；原型容量/仅文字继承R1|
|容量管理|继承R1 capacity/service-capacity|未重复制造大额fixture；原权限与视觉证据有效|
|既有Me/策略/实时反馈|me-zh / policy-failed / ws-cooldown / restart-recovered|六字段双卡、只读/可写层级保持，故障草稿与冷却清晰；重启正常往返|

## 问题与关闭记录

| ID | Severity / relation | 结论与行动 |
|---|---|---|
|R1-P1|major / direct|closed：短明确确认后真实global删除闭环成功；无绕过人工授权。|
|R1-P2|minor / direct|closed：真实双视口与认证原型match。|
|R2-LOG|major / operational|closed on7df455679：实际最终IM日志所有ticket值脱敏，旧原始日志只留隔离本机，不提交。|
|UX1|minor / direct|长自然语言即使明确提图名/ID仍要求精确短指令。旧批次Agent错误建议换会话/从Web删除；caller随后更新工具错误为可回复“删除 <graph_id>”。最终新话术未单独再次造图重验，不冒称已闭合；核心短指令删除已通过。建议保留为确认体验限制，不放宽成字符串包含或模型自报授权。|

## Round 2合并覆盖

每行期望来源仍为spec.md同名Scenario；Round1 pass保留，新增结果仅以本轮实际证据更新。inconclusive不能以worker测试/实现叙述补成pass。


### Requirement: 正常用户只需 Nano IM 账号即可从公网访问

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|本机通过实际域名访问与实时使用|inconclusive|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|朋友公开注册|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|待批准账号不能进入公司内部协作|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|管理员批准后进入公司协作空间|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|普通用户不能批准自己或他人加入|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|匿名访客只能进入公开认证入口|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

### Requirement: 管理员可停用成员并保留协作记录

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|停用后既有登录与实时连接不再提供公司访问|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|停用不删除历史协作记录|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|普通成员不能停用他人|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|停用成员同步撤销名下机器接入资格|pass|R2-J4：单peer进程，B停用后即时offline、重连403；旧/停用机器身份gateway WS403，普通人发消息503且保留草稿。|
|停用接入保留资源记录且不改变机器归属|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

### Requirement: 注册与认证具有实际生效且可恢复的滥用防护

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|单一来源反复尝试被节流|inconclusive|R1登录错误第11次429，R2约22:47同账号正常UI登录证明自然恢复；尚未独立完成注册来源限额和来源级登录限额的完整冷却旅程。|
|同一账号的分散密码猜测受到限制|inconclusive|R1修改声明头不能绕过、R2同账号自然恢复已见；仍缺多个真实来源同时对同账号尝试的独立证据。|
|客户端不能伪造来源绕过防护|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|合理少量用户与会话恢复可用|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

### Requirement: 刷新凭据吊销在并发和服务重启后仍可靠

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|刷新轮换后旧凭据保持失效|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|并发刷新不能重复恢复会话|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|退出后失效状态跨重启保留|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

### Requirement: 系统级管理与既有协作权限有明确边界

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|系统策略仅管理员可写|pass|R1普通成员403；R2-J2管理员14→15保存刷新保留，断网保存14失败保留草稿，恢复后保存回14。|
|新注册不能自动获得系统管理权|pass|R2 boundary-evidence：注册携带active/admin字段仍201 pending/is_company_admin=false。|
|既有共享 Work 保持|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|成员和 owner 边界保持|pass|R1成员/非成员附件与群；R2 owner-boundary：C对nano私聊读写404、Agent config读写404、node配置/管理数据404，而global Work200。|
|共用 Gateway 统一管理、共同使用|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

### Requirement: Gateway 可由本机确认整体换绑给有效公司成员

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|有效成员自行接入或换绑 Gateway|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|仅知道节点标识不能远程抢绑|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|不能换绑给尚无有效公司资格的账号|pass|R2-J4 pending真实bind深链返回membership；同有效挑战pending/suspended accept均403。|
|原管理者停用后设备可合法交接|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

### Requirement: 有效公司成员与具备任务能力的有效 Agent 可查看全部任务

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|公司任务跨账号与聊天可见|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|任务可见不授予原聊天与附件访问权|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|跨 Gateway 和账号的 Agent 可读取同一任务图|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|任务读取仍要求有效身份和已授予的工具能力|pass|R1有效两Agent读取；R2关闭peer Task Graphs实际无工具，停用机器/旧身份gateway拒绝、不能发起读写。|
|Agent 按需读取而非自动摄取全部任务|inconclusive|真实按需get/search和不自动执行已见；本reviewer没有每轮实际发送给模型的完整输入证据，不能从无工具调用推定不注入任务正文。|
|飞书沿用现有主人识别与 Agent 公司资格|inconclusive|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

### Requirement: 公司成员通过 Agent 共同维护任务且变更可辨认

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|跨账号和 Gateway 新建与修改任务|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|删除任务需要明确要求或确认|pass|R2-J1：精确“删除 tg_5508fe90”真实global delete返回deleted=true,n1/n2删除，其他成员原图不存在。长句需要确认，见UX1。|
|修改者与来源真实可辨认|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|并发修改不能静默覆盖|pass|R2-J5：真实global apply base_revision=1返回version_conflict,current_revision=5，回读n3原描述/updated_at不变。未以base_revision=0参数错误替代冲突。|
|任务写入保持有效身份与工具边界|pass|R2-J4/J5：停用机器WS拒绝；关闭工具后真实peer无task_graph且不绕过，图仍revision5。|
|外部渠道任务写入按 Agent 资格判定|inconclusive|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

### Requirement: 群内便捷查看本群新建或编辑过的任务

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|群任务入口展示本群工作|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|总任务与子任务跨群持续协作|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

### Requirement: 任务独立于群成员与群聊生命周期

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|退群不撤销公司任务读取资格|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|解散群不删除公司任务|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

### Requirement: 自动附件处理不能访问任意服务端目标

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|正常上传与 Agent 图片理解保持|inconclusive|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|伪造地址和附件引用被拒绝|pass|R1非成员附件404/伪造file与metadata下载失败；R2本机临时HTTP canary提交伪造附件，真实global inbox attachment_unavailable，10秒listener 0 hits，聊天明确无法读取；普通任务URL文字链接仍可展示。此pass限所验入口，不声称穷尽全部SSRF编码。|

### Requirement: 公网滥用不能无界消耗服务的有限资源

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|超限上传和请求有明确拒绝|pass|R1大小/累计限额；R2 2.2MB JSON413，16MiB chunked无Content-Length上传413，结束uploading预留0。|
|附件空间不足不阻断文字聊天|pass|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|实时连接受控且可恢复|pass|R2真实第11张ticket429，自然冷却后200；C原浏览器+4测试WS可用，额外2拒403，70KB帧1009。释放后浏览器恢复、重启后真实聊天“已恢复”。冷却UI用显式429注入单独验证，不冒充后端限流证据。|

### Requirement: 发布与恢复可验收，凭据不随运维证据公开

| Scenario | 结果 | 本轮证据/继承依据 |
|---|---|---|
|公网仅开放预定 IM 服务|inconclusive|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|运维证据不包含可复用凭据|pass|R2发现直启日志原始ticket后caller修复。7df455679新进程.im-final.log所有用户WS票据[redacted]；报告不含secret。历史私有日志不提交、旧ticket已消费/过期；完整生产日志仍归R6。|
|故障时可停止公开访问并恢复|inconclusive|继承Round1同名Scenario及其证据；本轮未使该证据失效。|
|免费部署范围可核对|inconclusive|继承Round1同名Scenario及其证据；本轮未使该证据失效。|

## 尚需资源与剩余证明

1. **R6实际域名/发布恢复**：当次生产上线授权、Cloudflare/源站控制窗口以及实际域名验证仍缺；含公网只开放IM、生产日志/备份恢复、免费项核对。localhost不能替代。
2. **R7真实飞书**：原专用Bot被unit-feat-569使用；需要caller安排独占窗口。未抢占、未使用新Bot或mock冒充。包括外部图片理解与任务读写资格。
3. **认证完整冷却**：登录用户名限额自然恢复已见，注册/来源限额完整自然冷却与多真实来源同账号攻击仍缺独立旅程；可以安排多来源测试窗口，不能把伪造头当真实来源。
4. **模型实际输入**：缺对应真实轮次的完整发送输入，不能单从工具轨迹推定未自动注入全部任务；需限定该测试会话的请求证据，避免读取/提交无关私聊。

## 清理与交接

peer已交回nano，Task Graphs恢复开启，随后用官方stop清理本轮自己启动的后台服务；第一Gateway/IM/原型继续由caller管理。A/B保持suspended、C为active测试成员。tg_5508fe90已删除；原协作图tg_c1d2b5b5 revision5保持。容量fixture未再添加；过期fixture仅本轮自建binding操作（现终态），无活动上传预留。所有浏览器网络故障拦截已撤销；测试WS全部关闭。代码、测试、受控配置、spec/design均未由reviewer改动。报告仍需caller随最终交付push，不把本地commit当远端已同步。

caller最终清理通知：本轮现场复验完成后已停止其第一Gateway41369与IM41358，50620无listener；运行DB/config保留，8572原型继续HTTP200。此为caller收尾记录，不冒称reviewer另做现场复验。


---

# 独立产品验收 Round 3 — C6真实模型输入定向复验

> 2026-09-30；targeted=C6。产品冻结 `7df455679`。本轮只读核对指定隔离真实会话的既有请求，未重启服务，未运行新Agent。历史请求跨R1/R2及最终重启，不宣称94个请求均发生在最终commit。

## Verdict与覆盖更新

**完整验收仍fail**，Highest Required Action仍为**pass**（无新增实施修复要求，缺失验收不是发布许可）。C6由inconclusive改为**pass（有界实际会话证据）**；合并覆盖为**43 pass / 9 inconclusive**。Round2其余结果及UX1说明保持；C5尚未完成，不能因caller正在测试而补pass。

| Scenario | 期望来源 | 独立观察与证据 | 结果 |
|---|---|---|---|
|Agent 按需读取而非自动摄取全部任务|spec.md同名Scenario|读取指定review572-global会话的全部94个实际上游请求文件；现存图先于会话创建，前69个完整输入未含图ID、标题或正文片段；首次ID来自人类指定图的inbox结果，正文随后才来自明确task_graph get；所有94个system均无两张验收图的ID/标题或既有图正文片段；查询后无新agent委派，图仍revision5。|pass|

## C6证据链

- 独立读取 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-09-30_22-24-55_971_sess_5c56f53a24a4b57e` 内94个 `*-req-anthropic_messages.json`，没有只采信caller摘要。只读运行DB再次核对 `tg_c1d2b5b5` / `572跨群发布计划` 的创建时间为13:38:55 UTC，早于该会话首请求14:24:55 UTC。
- 首3个完整请求实际配置 `task_graph` 工具且messages分别1/3/5条；从system、工具schema和全部messages整体检查，均没有现存图ID/标题/正文片段。扩展到首次引用前的69个完整请求，结论相同。因此本会话不是因关闭工具而“看不到任务”，也没有在处理其他工作时自动摄取现存公司图。
- 首次ID位于 `22-57-05_133` 请求的 `inbox read` 工具结果，内容为本reviewer此前实际发送的版本冲突验收消息。该消息由人类明确点名图ID并交办操作。
- 首次标题/正文位于 `22-57-08_114` 请求的 `task_graph get` 工具结果，调用参数是指定图与scope=n3；返回revision5、根节点和指定scope。此后图内容留在普通会话工具历史里，是按需读取结果的上下文保留，不能误判成每轮system自动注入全部公司任务。
- 全部94个请求system都没有测试图ID/标题/现存图正文片段；首次查询后无`agent`新委派。后续apply均有上述显式人类交办且被参数/版本校验拒绝，实际图保持revision5。查询没有替用户自动接单或唤醒另一Agent。

脱敏证据：[model-input-evidence.json](../evidence/reviewer-round3-c6-20260930/model-input-evidence.json)。仅提交文件名、SHA-256、计数、布尔marker和消息块位置；**未提交完整system、工具schema、用户/模型消息或完整请求**。证据范围严格限这一隔离真实会话，不推广为所有provider/channel的穷举证明。

## 清理

已关闭本reviewer持有的4个浏览器会话：feat572-review、feat572-review-admin、feat572-review-auth、feat572-prototype-review。仅关闭浏览器，不停止8572原型服务；其HTTP200仍保留。生产代码、测试、配置和C5环境均未触碰。


---

# 独立产品验收 Round 4 — C5来源限流与自然冷却定向复验

> target=C5；生产代码冻结 `7df4556795567602333771351fc4bd75ec322e94`。后续`cfbd481a4`仅caller测试桩接口/全量验证记录，不混作本轮产品变更。未扩大到公网或飞书。

## 最终合并结论

**完整验收仍fail**：**45 pass / 7 inconclusive**。C5两条Scenario由inconclusive改为pass；C6沿用Round3有界pass。Highest Required Action仍为**pass**（没有新增实施修复要求；不是完整验收/上线许可）。剩余7条均是R6/R7实际外部验收缺口。Round2 UX1作为minor确认体验限制保留，不要求放宽人类授权边界。

| Scenario | 期望来源 | 独立复核证据 | 结果 |
|---|---|---|---|
|单一来源反复尝试被节流|spec.md同名Scenario|真实源A注册5次201、第6次429，源B注册201；A累计30次登录尝试后429，B对同账号200。301.85秒A登录200，901.34秒A注册201。|pass|
|同一账号的分散密码猜测受到限制|spec.md同名Scenario|两个真实TCP源轮流对同账号10次错密均401；之后B正确密码仍429；自然902.61秒后B正确密码200。R1/R2认证UI错误采用不区分未知账号/错密的通用反馈。|pass|

## 独立核对与范围

读取caller提供的完整隔离`server.py`、`qualify.py`、`results.json`和实际`peers.jsonl`，并只读核对`auth.db`。没有只采信`complete=true`摘要，也没有修改业务数据或重跑消耗计数的请求。

- 服务入口仍是生产`IM.app:app`，外层只记ASGI `scope.client`与时间；Uvicorn `proxy_headers=False`。客户端使用`HTTPTransport(local_address=...)`绑定两个本机真实TCP源，`trust_env=False`，无来源声明头伪装。
- 独立按started/finished时间筛选48条实际HTTP记录：A注册7、B注册1、A登录32、B登录8；与脚本请求次数、相邻阶段时间和恢复请求来源完全对应。额外两条不在测试时间窗内，未计入。
- 脚本根据真实Retry-After计算deadline并自然sleep；没有修改时钟、常数或SQLite计数。注册/账号冷却分别899/898秒，来源登录剩余292秒；实际恢复时间为301.85、901.34、902.61秒。三个恢复请求都由相应真实源发送，而非换源冒充恢复。
- 只读DB有7用户、35认证会话，与7次注册创建会话加28次成功登录一致。进程PID43433的命令/cwd属于本unit独立auth实例；没有复用生产数据库。
- 这是**单机loopback与LAN源地址的真实TCP双源验证**，不是两台Internet客户端，也不证明Cloudflare/真实域名上的来源识别。该外部路径仍属R6，绝不据此补pass。

脱敏证据：[auth-source-evidence.json](../evidence/reviewer-round4-c5-20260930/auth-source-evidence.json)。仅发布source_A/source_B、计数、相对时间、结果、脚本/记录哈希；不发布原始IP、测试密码、凭据、数据库、完整服务日志或脚本。

## 仍未验收的全部7条

| Scenario | 归属 | 状态/前置 |
|---|---|---|
|本机通过实际域名访问与实时使用|R6|inconclusive；缺当次上线授权与域名实测窗口|
|公网仅开放预定 IM 服务|R6|inconclusive；未上线，不以本机监听替代|
|故障时可停止公开访问并恢复|R6|inconclusive；缺真实发布/恢复演练窗口|
|免费部署范围可核对|R6|inconclusive；缺Cloudflare账号/实际部署免费项核对|
|飞书沿用现有主人识别与 Agent 公司资格|R7|inconclusive；原专用Bot仍被unit-feat-569占用|
|外部渠道任务写入按 Agent 资格判定|R7|inconclusive；未抢占专用Bot，未以mock替代|
|正常上传与 Agent 图片理解保持|R7关联|Web真实理解已pass；Scenario含外部渠道附件，飞书部分尚缺，整行仍inconclusive|

caller最终只读复核通知：飞书原锁仍指向unit-feat-569，相关PID15775存活；8572原型HTTP200。reviewer未操作该Bot或进程。

## 最终清理

完成只读核验并通知caller后，reviewer仅向独立auth PID43433发送TERM；已确认该进程退出且其专用端口无listener。先前4个验收浏览器均已关闭；8572原型继续保留。无生产服务、配置、数据或源码变更。报告/脱敏证据以外文件不stage，远端同步由caller统一完成。
