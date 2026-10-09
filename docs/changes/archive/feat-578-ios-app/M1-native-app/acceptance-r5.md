# feat-578 — 原生产品功能续验 R5

> 2026-10-05 12:04 起，增量进行中。实际 native/服务端源 ba202f5d3，functional-build-r6；390 App PID72595，IM72554、主 Gateway72564，两个隔离节点 online。保留前轮有效证据。

## 已完成的窄复验 J18

通过真实原生配置入口，e2e-peer 输入24h、03:00、03:01并开启心跳。从心跳字段所在位置点击顶部保存，页面自动滚到“配置已由节点确认；聊天在下一轮采用新配置”可见区域；三个字段仍完整。退出回 Agent 详情并重新打开配置，开启状态和三个值全部保持。截图 `output/feat578/reviewer-r5/heartbeat-confirmed-visible.jpg`、`heartbeat-reopened-values.jpg`。**R3-01 关闭**。

随后关闭心跳，清空间隔/开始/结束三个文本字段，保存获节点确认。继续在 off 状态输入24h再次保存，获节点确认；退出重开后间隔24h、时段空、心跳off。截图 `heartbeat-empty-confirmed.jpg`、`heartbeat-after-empty-confirmed.jpg`、`heartbeat-after-empty-reopened-off.jpg`。**空 cadence 后再次修改误触发 operation_conflict 的行为已修复**。本次没有再暂停节点，也没有即时触发心跳。

当前正留48h未提交草稿，等待caller以同owner实际API变更非执行字段增加profile_version，再从原位置提交验证真正409反馈与恢复。该并发版本冲突独立于前轮节点 operation_conflict，不混为一项。

## 当前结论

进行中，不能宣布全 App 通过。R4-01正常成功反馈已确认进入视口，错误分支仍待下面追加；S19心跳读回缺陷已关闭，未覆盖的离线分支仍不扩为通过。其余S1–S30维持既有报告，后续追加剩余旅程实证。

### J19 真正的 IM profile_version 并发冲突

caller 同owner API仅给description追加测试标记，版本7→8，heartbeat/features不变。原生48h草稿从心跳区域点保存，页面自动滚到红色“状态冲突；草稿已保留，请重读并核对。profile_version conflict”，并显示重读入口，48h草稿仍在且表单暂禁用。点击重读、展开服务端配置，看到description测试标记、服务端24h/off、版本8；选择“保留草稿，基于此版本继续编辑”，48h/off保留，重新保存获得节点确认。截图 `config-real409-visible.jpg`、`config-conflict-recovered.jpg`。

**R4-01 关闭**，S18恢复pass（连同R1/R2/R3有效证据）。此IM版本冲突与此前节点operation_conflict明确区分。选择保留草稿后旧description随草稿保存，caller已获知测试标记被主动覆盖，无需重复API恢复；心跳保持off。

### J20 历史分页（进行中）

打开指定真人会话 iOS History Check，初始在最新065。CUA坐标scroll/drag未推动此列表，使用新鲜AX中较早消息定位逐段上移；到初始60条窗口顶部006，实际出现“更早的消息”。点击后加载001–005，页面留在早期002–008附近，没有强拉到065。截图 `history-earliest-loaded.jpg`。正在等待同测试用户新消息验证读历史时不抢滚动，后续追加草稿与真人回复。

J20续：caller用专用普通用户ioshistory在本会话发`History live 066 — native scroll check`，原生保持001–008附近，未强拉底（`history-new-message-no-jump.jpg`）；主动点“最新消息”才见066。此证明阅读位置保持，不单独证明服务端可见域已读游标。给History会话输入578066草稿，切到Access群输入578077，返回History恢复578066且无串入；发送前重写为无尾随Tab的578066，点击发送后实际显示Test User/已完成且输入清空（`human-reply-completed.jpg`）。再回Access，578077仍独立存在，随后已清除。`draft-history-restored.jpg`记录恢复。

### J21 已打开图片撤权（进行中）

Access群中打开指定合成test-gradient.png，真实预览完整显示（`access-image-before-revoke.jpg`）。已请求caller以owner移除当前nano成员，只改此测试群，不删除群/图片；等待实际撤权后验证。

J21结果：owner移除nano实际204后，已打开的图片预览自动关闭，聊天内容与原标题清空，显示“你已无法访问此聊天。”；附件/输入/发送禁用。返回列表已无Access群。截图 `access-after-revoke.jpg`。**S11撤权缓存分支pass**，其它上传失败/超限分支仍inconclusive。caller后续已恢复原成员200。caller还用ioshistory收件方实际GET确认能读到原生578066回复，sender=nano，作为J20真人双向辅助证据。

### J22 多节点创建与既有目录确认

新建选全局模式，切第二节点时模式仍全局，默认workspace变为第二节点真实目录；切回主节点仍保留模式，路径回主节点。填写ID后取消触发“放弃未保存的草稿？”，点确认框外保留了全部草稿。用已存在e2e ID提交，显示agent_id already exists，未创建副本；字段保留且可更正。

改为唯一ios-create-r5、名称578500，主节点，自定义caller刚创建并核实为空的本次隔离目录 `/private/tmp/nano-feat578-ios-runtime/.gateway-workspace/ios-existing-directory-r5`。提交要求明确确认“该目录已存在。确认使用并初始化其中的 Agent 工作文件？”，确认后显示“Agent 已创建”及该路径。完成返回列表，只有一条578500、online。截图 `create-node-mode-preserved.jpg`、`create-duplicate-id.jpg`、`create-existing-directory-confirm.jpg`、`create-custom-workspace-success.jpg`。

本段有一次CUA native pipe closed；随后fresh AX恢复，核实ID已更正但自定义开关未点击，按现场继续，没有重复提交或重启服务。S16这些分支pass，离线/路径失败/无设备创建分支仍未全部覆盖。

### J23 配置全字段与 Skills 模式

在新建专用ios-create-r5上，只改配置、不调用LLM。名称578500→578501、description=`Native configuration round 5`、群回复策略不回复；显式主模型deepseek:deepseek-v4-flash、推理max；添加luna和kimi两备用后上移kimi，最终顺序kimi→luna；Custom Instructions=`Use concise answers for this isolated test.`；关闭bash工具及记忆维护。保存获节点确认，退出重开逐项真实值保持。全局模式固定工具显示disabled并说明固定保留inbox/conversations/send_message/agent。

Skills先切默认发现并保存，重开仍默认发现；再切显式名单，逐项关闭全局目录所有选择，保存、退出、重开仍显式，目录开头开关为0。caller只读辅助确认skills=[]、skills_selection_mode=explicit_allowlist、version3，无漏选残留。模式和空列表在原生中明确区分。完整workspace/全局模式在配置归属只读且说明创建后不可改。

提示词预览真实打开，显示当前稳定提示词内容与“不包含群聊、心跳及本轮运行时上下文”说明；未逐字比对全部长文本。截图：`config-reopened-models.jpg`、`config-reopened-tool-off.jpg`、`config-default-discovery-feature-off.jpg`、`config-explicit-empty-reopened.jpg`、`config-prompt-preview-scope.jpg`、`config-fixed-workspace.jpg`。

新增 **R5-01 minor**：配置保存改名后直接回详情仍显示旧578500；重开配置已是578501，说明提交成功但详情未刷新。截图`agent-detail-stale-name.jpg`。不扩大为数据丢失。S17主要字段持久化完成；不可用能力异常目录分支未人工制造，预览全部文本一致性尚非逐字实证。

J23补充：返回Agent列表后名称578501已刷新，R5-01只影响仍在导航栈中的详情快照。caller实际GET确认新Agent唯一、global模式、自定义workspace准确。

### J24 真实消息回执丢失（进行中）

caller准备loopback fault proxy62009转发同一真实IM62008，当前此前未armed。退出nano清缓存后，原生连接设置改62009并重新nano登录；进入同一真人History会话，输入唯一578808，尚未发送时通知caller arm。代理仅针对该条发送吞响应并暂断HTTP/WS，后端照常落库；这不用于验证origin安全（fixture明确归一origin），无Agent/外部平台消息。

J24发送一次后，原生立即显示“连接中断，正在重连”“发送结果尚未确认。重试会核对同一条消息。”，底部“等待核对发送结果”与“重试核对”；输入578808保留，发送/附件禁用。未点击重试、未重复发消息。截图`send-uncertain-response-lost.jpg`。已请求caller核对服务端单条后恢复传输。

J24结果：caller真实收件方GET在故障期确认578808仅一条，上游201但响应丢失。传输恢复后第一次观察仍待确认，手动点击一次“重试核对”，断线/待确认提示消失，输入清空，只显示一条Test User/578808/已完成；caller再GET仍COUNT1且相同message id。截图`send-reconciled-single.jpg`。随后原生退出、地址改回62008、nano登录成功，History最新578808可见；caller已停自有代理并释放62009。**S8本真实故障要求pass**，无偷偷重发。

### J25 静音与知识整理

History会话静音打开，退出详情重开仍on（`chat-mute-reopened.jpg`）。回列表并进入整理界面期间，caller专用ioshistory发578901 muted；观察未见banner，返回列表存在该消息及未读1；打开能读到，随后静音恢复off。静音持久化/不丢消息已实证；未把有限观察扩大为所有后台提醒去重通过。

**R5-02 major / S9 fail**：新建与整理→整理会话知识，选安全来源iOS approval acceptance能变1且无操作时保持；点击执行Agent（fresh AX或截图对应箭头坐标）不展开菜单，反而将该来源变0，生成草稿持续禁用。全未选状态点击执行Agent及目标范围都不展开，也未把来源变1。没有选择旧私密e2e，没有生成/发送草稿。截图`distill-source-selected.jpg`、`distill-agent-click-clears-source.jpg`。不将此误报为异步刷新；重现与下一次点击相关。caller已编译两选择器的原生选择页修订，待新版窄复验。

## 本轮安全断点与结论更新（12:35）

原生仍ba202f5d3；已退出整理并回聊天列表，无在途写入/草稿。UI交还caller安装下一候选c2cbfa7a1；尚未验该版本。整体 **fail / 未收口**，新增R5-01 minor、R5-02 major；R3-01/R4-01已通过J18/J19关闭。其余未完必验分支保持inconclusive，不能由本轮大量新增通过宣称全App通过。
