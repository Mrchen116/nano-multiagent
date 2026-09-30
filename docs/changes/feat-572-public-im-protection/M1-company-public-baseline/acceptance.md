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
