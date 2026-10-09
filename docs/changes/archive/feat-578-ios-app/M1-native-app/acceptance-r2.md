# feat-578-ios-app — 原生产品验收 R2

> Review date: 2026-10-05；full 续验，R1 有效证据保留。本轮已停止：用户明确否定当前登录界面视觉，caller 要求先重做界面再安排视觉复验。
> 安装版本分段：第一段 `1708bdd74`（开始时工作树 HEAD `20851d4f1`，不能将 HEAD 当作 binary）；第二段 `28ba862fc70eb7c558ea4bb5a4db914f4b3e52a3`，caller 重新安装并启动 PID 52157。后续若安装新包，另记边界。

## Verdict

**fail**。用户已明确判定当前视觉不合格；原型信息语义 match 不能作为视觉通过。此项为 caller 转达的用户验收结论，并非用实现或测试推断。功能方面，本轮新增两个观察缺陷（图片 sheet 裁切、中文错误密码英文提示）均已在 `28ba862fc` 真实复验修复；未完成的必验分支仍为 inconclusive，不降低验收标准。

Highest Required Action: **fix-design-and-implementation**，先按用户视觉反馈重做原生界面，再安排视觉复验与剩余功能验收。收到停止指令后没有继续 UI 点击、Cron 删除、配置 pending、分页或安装；Simulator 已释放给 caller。

## 环境与方法

沿用 R1 的 iPhone 17 Pro / iOS 26.4 Simulator、CUA 原生入口及隔离 IM `127.0.0.1:62008`。IM PID 45898、主测试 Gateway PID 45904 由 caller 管理。真实 LLM、审批、任务图、子执行、Skills 使用和 cron 数据由 caller 准备；产品结果从 App 检查。仅写报告和不提交的截图；不读实现、不修改产品、不接触生产或手机。照片只使用 caller 准备的 600×400 渐变测试图；绑定链接不记录到报告或聊天。

## 已完成续验旅程

### J6 图片选择、上传与比例修复

`1708bdd74` 的照片入口实际打开系统 Photos，选中测试图后出现待发项，发送到测试群 578100（c_ptpu3rt7），出现已发送的 photo-451196A7.jpg。点击缩略图的图片 sheet 将图片横向严重裁切；文件名入口 Quick Look 保留 3:2。分享面板可打开，Save Image 触发系统权限并选择有限照片访问；尚未去 Photos 核对导出结果，不能将保存声称完成。

`28ba862fc` 重新打开同一图片，sheet 呈现完整渐变，画面约 631×421，保持 3:2，裁切问题修复。截图：`output/feat578/reviewer-r2-photo-preview.png`、`reviewer-r2-photo-quicklook.png`、`reviewer-r2-photo-fixed-28ba.png`。R1 照片选择器问题的核心入口已复验通过，S10 全部文件/导出分支仍需完成。

### J7 真实审批与持续时间

真实 iOS Permission Check Agent 请求 web_fetch。第一单选择 allow_once 后真实执行并回复 Example Domain。第二单选择 Deny，在 caller SIGSTOP 主测试 Gateway 后提交，UI 显示“已提交，等待确认”，批准/拒绝操作消失；等待期间计时从 3:27 继续到 3:36。caller SIGCONT 后，UI 变为已处理 deny，Agent 回复说明未获取网页，未重复执行。

首单处理中计时从 1:37→1:48→1:56→最终 134.2s，数分钟后回看仍为 134.2s。统计展开可见输出175、上下文2382/262144、缓存3584（78%），未把工具完成等同于整个任务完成。截图：`reviewer-r2-approval-timer.png`、`reviewer-r2-approval-submitted.png`、`reviewer-r2-approval-resolved.png`、`reviewer-r2-metrics-expanded.png`。

### J8 任务子层级和主子 Work

真实探索图 tg_6fe2e220 含 n1 探索、n2 本地、n5 远程选项，n2 下有 n3/n4；从选项进入子图与详情并返回父层级，结构和层级可辨。搜索 578999 得到空结果；尚未完成分页位置恢复。

578002 的主执行 sess_fd35bc3ed629df6d 可进入真实子执行 sess_410e171e8ee013af，Compute 987+654 的结果为1641；子执行呈现上下文9930、输出18、缓存3840（38.7%）、1.07s，并可自然返回主轨迹。

普通有效成员 iosmember 登录后，聊天为空而不是 A 的内容。打开同一全局 Agent 可读 Work、子执行和1641，但只有发消息/Work，没有配置入口。普通成员从同一公司任务节点只见“No conversation linked”及复制引用，不出现返回 A 私聊按钮。截图：`reviewer-r2-task-subgraph.png`、`reviewer-r2-child-work.png`、`reviewer-r2-member-work.png`、`reviewer-r2-member-task-no-chat.png`、`reviewer-r2-member-empty-chats.png`。

### J9 绑定双端确认

输入 caller 准备的待绑定 wt-feat578-bind-check 链接，检查当前账号和设备。接受后明确显示等待设备；caller 在 Gateway CLI 确认后，再检查同一链接变为完成，设备列表出现 ios-binding-check。接受没有被误报为最终绑定。拒绝/过期路径尚未验。截图：`reviewer-r2-binding-pending.png`、`reviewer-r2-binding-complete.png`。

### J10 账号隔离、暂停与错误语言

退出 A 有清除本机会话/待发内容的确认，之后回到登录；正确登录 B 后只见空聊天。B 进入公司管理显示 Administrator access required；策略字段全部只读，保留天数仍为31；B 的我的设备为空。caller 暂停 B 后 App 自动返回登录，重新登录 B 后只显示本人“Your account is suspended. Contact your administrator.”及 Refresh status / Sign out，没有公司缓存。

旧包中文登录页错误密码返回英文 invalid credentials，记为本轮已观察缺陷。`28ba862fc` 复验显示“用户名或密码不正确。”，错误仍允许修正密码再登录成功。截图：`reviewer-r2-member-policy.png`、`output/reviewer-r2-member-suspended.png`、`reviewer-r2-login-error-28ba.png`。

### J11 Skills 真实使用记录

`28ba862fc` e2e-peer→Skills 使用情况显示 nanoassistant-docs，来源用户创建、active、使用次数1；展开有真实最近使用时间、趋势、session sess_e1d41ce19af60e67 与 tool call ID。截图：`reviewer-r2-skill-usage.png`。心跳/Cron 尚未完成。配置长说明滚到 Workflow 中间时，CUA AX 不再提供滚动容器，滚轮/拖动无效；已通知 caller，暂未将驱动滚动障碍单独定为产品缺陷。

## 逐场景功能覆盖（不代表视觉通过）

| Scenario | 当前结果 | 证据及仍缺分支 |
|---|---|---|
| S1 | pass | R1 四入口与本轮任务/Work/账号自然返回 |
| S2 | inconclusive | 中文组合输入、复制、VoiceOver 实际导航、大字体和多尺寸仍缺 |
| S3 | inconclusive | 本轮真实登录与暂停本人状态已完成；原生注册/待批准及重启恢复仍缺 |
| S4 | inconclusive | A→B隔离及暂停踢出已完成；429/临时网络/迟到附件响应仍缺 |
| S5 | inconclusive | R1 建群/Agent私聊；真人私聊、成员增删/解散仍缺 |
| S6 | inconclusive | R1改名置顶；静音/可见域已读/历史不强拉底仍缺 |
| S7 | inconclusive | R1文字/slash；有效群提及、分页/草稿隔离仍缺 |
| S8 | inconclusive | 故障发送窗口、幂等和恢复补齐未验 |
| S9 | inconclusive | 长按复制/fork 驱动不支持；蒸馏草稿未验 |
| S10 | inconclusive | J6照片选择/上传/两种预览已完成且裁切修复；文件/导出未完全验 |
| S11 | inconclusive | 上传失败/超限/撤权附件缓存未验 |
| S12 | inconclusive | J7/J8统计/子执行/回看；未知项和全部后台返回语义仍未完整覆盖 |
| S13 | pass | J7真实 allow_once、Deny、延迟回执和禁止重复提交 |
| S14 | inconclusive | R1 DAG回聊、J8探索/子图/非成员私聊隔离；分页/失效关联仍缺 |
| S15 | inconclusive | J8主子Work及非owner隔离已完成；分页历史仍缺 |
| S16 | inconclusive | R1在线真实创建；多节点/路径确认/重复ID/草稿保护仍缺 |
| S17 | inconclusive | R1改名与预览；完整字段逐项保存仍缺 |
| S18 | inconclusive | R1真实冲突恢复、J8非owner边界；节点延迟保存确认仍缺 |
| S19 | inconclusive | J11真实Skill用量；心跳保存/Cron删除仍缺 |
| S20 | inconclusive | 独占测试Bot验证被外部网络EOF阻塞，未连接生产Bot；仅R1必填/安全输入证据 |
| S21 | inconclusive | 同S20，缺真实通道连接/停止/删除回执 |
| S22 | inconclusive | J9真实双端接受确认；拒绝/过期仍缺 |
| S23 | inconclusive | R1别名/创建、J9第二节点；节点开关/离线恢复仍缺 |
| S24 | inconclusive | R1语言与J10中文错误修复；默认设备/个人资料所有字段仍缺 |
| S25 | inconclusive | R1批准/停用/最后admin拒绝，J10普通成员及客户端停用；分页/名下机器仍缺 |
| S26 | inconclusive | R1管理员保存，J10普通成员只读；失败草稿/owner容量仍缺 |
| S27 | inconclusive | R1实际轻提示；跳转/关闭/静音/后台重放去重仍缺 |
| S28 | pass | 保留R1帮助与权限边界证据 |
| S29 | inconclusive | 真机/Apple账号/免费签名按用户安排延后 |
| S30 | inconclusive | Mini AltServer/同网续签/自然过期实证按用户安排延后 |

## 停止位置及后续边界

- 最后安装并实际验收的 binary 仍为 `28ba862fc70eb7c558ea4bb5a4db914f4b3e52a3`。caller 正在改折叠说明，但本 reviewer 没有安装或验收后来实现。
- 停止时已修正测试密码重新登录 nano，UI 回到聊天入口；系统可能有保存密码提示，下一位操作人需 fresh AX/screenshot。未保存账号密码到系统。
- Skills/Cron/pending 的未完成不是通过；刚准备的 History 65条和撤权图片群还没有进行 UI 验收，不列入实证。
- 真机、免费签名、Mini AltServer/同网续签、自然过期恢复，以及中文 IME/VoiceOver/长按复制等需真机或可支持的操作方式；S20/S21独占外部Bot仍受验证网络阻塞。
- 报告未 commit；截图在 output 中不提交；无 reviewer 启动服务，主/第二 Gateway 及 IM 由 caller 清理。
