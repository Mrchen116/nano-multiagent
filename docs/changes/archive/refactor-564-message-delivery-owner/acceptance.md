# refactor-564 — 产品验收报告

> 对齐 motivation.md 用户侧不变性，以及 feat-563 保留的产品场景。

## Round 1 — 2026-09-16

Validation snapshot: `6ee83e2e35cb02006295d59d042d4d2d2e1d442f`；Web/Feishu真实旅程由该版本启动的 Gateway PID53934 执行。验收期间 caller 并行修复后台路径，未用未重启的进程证明新修复。最终交付须追加新版本 targeted 记录。

### Verdict

**fail（最终版本验收待 Round 2）；本轮已执行主旅程通过。** 本轮直接观察无 blocking/major。后台通知路径由 caller 独立审查发现需修复，尚未由本轮运行证明，不能将本轮结论外推至待交付新版本。

### 环境与实际操作

- 独立 worktree `/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-564`，隔离 Web IM `http://127.0.0.1:64713`，测试用户 nano，node `wt-unit-refactor-564-53546`。启动时 HEAD、git status、进程 cwd 已核实。IM53902 / Gateway53934 均源自该 worktree；前端由 caller 在该版本构建，浏览器实际加载。
- 浏览器 CUA 实际操作，1280×720：登录→Agent→Open chat→发图→放大→重开飞书影子历史。截图保留在本 reviewer 工具输出，无 must-match 原型。
- 测试图为 `/private/tmp/feat563-acceptance-images/1.png` 至 `5.png`，均160×100 PNG，工作区外原文件。仅向授权专用 Feishu profile `e2e-feishu-testagent` 的测试 Bot 发送；发送前验证非 default profile、App 与 Bot 一致。未使用生产身份。
- 初始 e2e 工具清单不允许 send_message；实际验证拒绝后，通过隔离产品配置 API 加入该能力以执行正向旅程。创建独立 global Agent `r564-global` 与测试群；这些是测试资源，不修改源码或生产配置。
- 真实 API/Feishu记录存于 `/private/tmp/refactor564-acceptance-evidence/`，不含登录 token。报告只提交验收文件，运行数据不入库。

### 用户旅程证据

1. **权限拒绝与 Runtime**：聊天 `c_jtxlmd21` 初次五图请求未发布图片；空正文过程气泡 `b9d5981d279c48a489c48dabd8f39f6d` 标失败，随后 `f33462a56feb499a97ef877dc849e3c2` 如实解释图片未送达。无图片外泄、无图片错误占位。回复准确区分 macOS 执行机、隔离 workspace、Web入口64713和用户localhost未知可达性。证据 `r564-A.json`。
2. **获准原图与放大**：开启相应测试能力后，`f28e021d8d9c40a380b2eab8afa98ebc` 仅一条完整五图，R564-B-1至5顺序正确、状态completed。浏览器看到不同纯色图，点击第五张显示 Image preview 真图。证据 `r564-B.json` 与 CUA截图。
3. **缺五修正**：首次第五图引用不存在路径；失败草稿 `d94a9e8102c14a5e80adc5357d981237` 正文为空，未显示四张残品。Agent收到内部反馈后，`15965aaf0c1d478cb759b2f7ce096424` 显示完整五图各一次，completed。浏览器与 `r564-C.json` 一致。过程失败气泡仍保留，成功成品无重复。
4. **跨工具多轮**：同一请求先图一→bash printf→图二；`03e9cdcca2da464eb9c777434d719ce2` 和 `5f783e4f6e6543b597e15b39fff6b123` 分别显示一张图片，前者Process含bash，均completed，无覆写/重复。证据 `r564-multi.json`。
5. **群聊和全局显式发送**：群 `c_friewuob` @e2e 收到一条R564-GROUP图，未@peer无回复；global聊天 `c_tgynsupa` 收到 `b2aeee1cdce642ffb179364498dbe4f4` 一张图。global再请求loopback来源失败后改原文件，最终仅新增 `e80bd005065642249a08d4ffa50f5c45` 一张完整图片，无失败占位。证据 group-result/global-result/global-repair JSON；产品 Agent Work API 导出 `global-work.json` 明确记录真实 send_message：loopback 返回 failed，原5.png返回ok，首次原4.png亦ok。
6. **不可恢复**：永久缺图后 `f75677d03195416286ce4b885ecbac3e` 明确本图未发送、未新建或替换图片。此前有一条“无法确认送达”的谨慎说明，未假称成功；最终无图片/坏链接成品。证据 `r564-unrecoverable.json`。
7. **真实飞书在线**：post `om_x100b6595bd6548a0deb5ad2839663f4` 含两张图片资源和正确Feishu channel/当前IM入口。专用用户下载第一张314bytes，SHA256与原1.png一致（a8482ad907cf2cf445ecccaa6a19569c9a75e58017de7a08b0bd9c289eb62c08），已实际查看蓝色图。IM影子 `c_kzookevz` 同步成功。证据 `r564-fs-online.json`。
8. **真实离线、删源、恢复**：先SIGSTOP模拟超时，飞书最终收到一图但Agent经历target_not_accessible修正；不以此样本证明干净离线恢复。随后SIGTERM仅停止IM53902，TCP连接明确拒绝(61)，Gateway继续运行。R564-OFFLINE2在IM离线时得到一条真实post `om_x100b65964b8468a0c21df846cabbb6f`。收到后删除专用来源 `/private/tmp/r564-offline2.png`，再以相同DB/JWT/端口重启IM PID57004（tmux refactor564-im）；影子自动补为 `4e14cbfb276e4473bb0ec2341770536c`，completed，浏览器真实紫红图与正常14.3s footer，无failed。成员下载200 image/png 314bytes，与原4.png字节完全一致；源文件不存在；匿名401、专用已登录非成员404。证据 `r564-offline2-during.json` / `r564-offline2-after.json`、CUA截图与下载校验。

### 边界证据的范围

Runtime已知执行地址与切换节点沿用 feat-563 acceptance Round2-A/B 的真实逻辑第二节点证据：`c_56xeleds`、`c_w5fbs489`等；caller确认 Runtime/access/register 代码未改。这里只继承未失效场景，不把旧成功叙述当成新交付实现的证明；图片/修正/飞书/离线核心路径全部在本轮重走。

精确ACK丢失、部分目标成功、准备期间新输入、人工权限批准/拒绝/stop、reset反馈撤销不能仅靠随机浏览器时序证明。独立运行27项聚焦测试通过（runtime_access_context、pa_candidate_recovery、pa_delivery_manual_permission、pa_delivery_input_admission、session_run_coordinator_delivery_feedback）；caller补充37项通过记录 `/private/tmp/refactor564-acceptance-contracts.log`。这些为真实coordinator/SDK/SQLite配合受控网络的下层证据，不宣称为真实飞书ACK丢失注入；并行修复树上的测试须由最终版本门禁再确认。

### 验收标准覆盖

| Scenario（motivation.md） | 实际证据 / 范围 | 结果 |
|---|---|---|
| 不同入口及执行环境 | 旅程1/7；已知地址/第二逻辑节点仅继承不变Runtime证据 | pass |
| 本地及多轮图文 | 旅程2/4/5/8；普通、群、global、原图、放大、删源回看及非成员边界 | pass |
| 来源或上传失败 | 旅程3/5/6；缺图、loopback、真实IM超时触发准备失败后恢复 | pass |
| 权限、新输入和取消 | 旅程1真实拒绝；人工审批/新输入/stop/reset按上述确定性下层证据 | pass |
| 外部送达与内部离线 | 旅程8真实飞书先到、删源、IM恢复一次且completed | pass |
| 回执丢失与部分成功 | pa_candidate_recovery 精确原身份/未确认目标下层验证；真实正常双渠道不重复见7/8 | pass |

feat-563保留Scenario逐项：已知入口预览pass（保留Round2-B）；未知访问条件pass（旅程1）；更换执行节点pass（保留Round2-A/B）；原项目截图pass（2/5/7）；无权发送pass（1）；长期回看pass（8）；五图缺一恢复pass（3）；网络或来源错误修正pass（3/5/8）；无法恢复pass（6）；普通与显式跨渠道一致pass（2/5/7/8，不声称逐一遍历所有笛卡尔积组合）。

### Reference Artifacts Reviewed

N/A：本unit没有视觉must-match原型。原生产截图是问题证据而非目标布局。实际浏览器图片及放大、离线恢复状态已查看。

### 上层文档同步

- [x] SPEC.md：需随最终边界归并由orchestrator确认；reviewer不改。
- [x] docs/specs/：需归并本unit最终delta及保留feat-563产品行为，由orchestrator负责。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

清理所有者为caller；已通知额外IM tmux refactor564-im / PID57004。Reviewer未操作生产。

## Round 2 — 后台通知路径 targeted（2026-09-16 12:58–13:00）

Validation snapshot: `6ee83e2e3 → 4e6093e32a53c79bc4a60925d2cdcb14bf011d4d`；源码基线 `c4ba604625001290f0191be06ae7ad741c9b4626`。Gateway已由caller重启为PID58260，IM57004未重启；两者cwd核实为本worktree，节点online。其后c2d8c1422仅测试fixture变化，未混称重启了源码。

**Verdict: fail。1 major，阻塞。** Round1未受影响证据保留；原待验后台路径现有具体失败如下。

- BG1正常回推：真人消息 `3a024d5966e243829a7d19df17abaa3c` 要求bash `run_in_background=true` 执行sleep5。`5b2d863c1553475db4930c2e1f6ed826` 先回复R564-BG1-START；没有后续真人输入，后台通知自动生成 `2d80e3b72e3d4e33a8521723ce7a1fb3` 一张原1.png、completed。真实工具参数和结果在 `r2-background1.json`。
- 普通群图smoke：`c_friewuob` / `7d2c395fc3ec4026afea4cb24e175f36` 正常显示原3.png，completed；`r2-smoke.json`。
- **P1 major：后台来源修正后有效图片被拒绝**。真人 `d4afb93c438d4ebeb7c8d0a3c61cdcb8` 要求后台任务完成后先尝试missing路径，收到反馈后改为已获准原2.png。`ca1e4e52adae48efaa19ec746f0da6e3` 回复START；自动通知形成的缺图草稿 `9eb3df82903b41ed864f164f772e69db` 空正文failed。最终 `5f40fde130f447688a37331c96253c94` 明确有效原2.png再次投递被权限拒绝、图片未发送。没有成功修正图片。观察到的产品结果为修正无法完成；不根据模型解释臆断实现根因。相同测试Agent此前BG1、普通图已成功，产品配置依然允许send_message（`r2-profile.json`）。`r2-background2.json`和1280×720浏览器截图记录实际未交付说明。

| 继承/新增Scenario | Round2证据 | 结果 |
|---|---|---|
| 本地及多轮图文：后台通知正常原图 | BG1及普通群smoke | pass |
| 来源或上传失败：后台来源错误后修正 | P1有效原图未交付 | fail |
| 权限边界：后台反馈运行保留有效授权 | P1；未发生越权泄露，但获准任务无法完成 | fail |
| 其余Round1场景 | Runtime、普通/群/global、Feishu在线/离线删源恢复及访问边界保持前轮证据 | pass |

修复路由：已实时通知caller，reviewer未读取实现定位或改源码。待修复新版本后仅复验P1及共享普通路径；未关闭前不能PASS。最终全量门禁由caller单独完成，不用尚未结束的全量测试宣称通过。

### Round2 补充诊断与对照（不覆盖原失败事实）

Caller报告已核对该次权限分类器真实LLM响应：12-59-22_863，将测试消息“不调用send_message”理解为拒绝该权限，因此阻断普通图片外发；不是工具allowlist缺失。Reviewer只记录caller诊断，不把它冒充独立源码定位。该现象与设计中“普通候选复用send_message权限”存在直接关系；原测试输入同时要求普通图片发送与禁止对应工具，存在权限语义歧义。补测BG3明确允许读取及聊天外发，只指定普通回复入口，观察真实工具记录是否仍没有显式send_message，不通过禁止权限表达测试路由。

BG3对照当前为 **inconclusive**：同聊天真人 `4e531519823c4b4db042300117b7b202`，START `acf90cbae44849c8b4d06ebda9603336` 后自动草稿 `03d72895aaf549a9bffc49be57003425` 持续running/空正文，约3分钟观察窗内尚无最终图或说明（`r2-background3.json`）。不根据空白推断进程卡死，也不能判对照成功。已通知caller。caller决定修复可信权限操作上下文，并要求最终重验原“不调用send_message”的BG2约束，P1继续开放。

Caller随后核对运行日志，报告BG3进入人工审批，但审批卡turn_start携带Bash background_return被IM协议拒收（仅支持subagent/workflow）。结合产品实际只有空running且无审批卡，将其记录为 **P2 major（开放）**：后台交付需要权限时，用户无法看到并处理审批，流程无可操作结果。协议根因由caller提供；独立产品证据是BG3 API和浏览器未出现审批操作。此项随可信操作上下文一起窄修，最终targeted必须关闭P1并验证后台审批卡可用，不能仅通过无需审批的成功样本关闭P2。

## Round 3 — P1/P2 targeted（2026-09-16 13:13起）

Validation snapshot: `4e6093e32 → d4a59af212690dfe50af77a1b689e572ad32499c`（P1可信权限上下文150fbe30d，P2后台返回卡投影d4a59af21）。Gateway PID61742、IM57004，cwd及HEAD已核实，节点online。IAB连接本轮不可用，改用CUA操作Chrome新建独立测试标签页；未操作用户其他网页。Chrome窗口截图1312×768，站点80%缩放。

- **P1 closed**：BG4保留“不调用send_message”约束且明确允许普通回复图片。真人 `cf398b036ea243509eda23bf09340dfc`；START `f9528a004f934df3b0130961f57d18e6` 的真实Bash run_in_background=true、sleep5。缺图草稿 `03ba0989ef624ba6a400516a21bcec96` 空正文failed；无新增真人输入，修正 `2c06e5e4b2a541d2a2664b16d422176a` 自动显示原2.png、completed。无显式send_message工具记录。实际Chrome紫色图片与3.2s正常footer；`r3-background4.json`。
- P2人工审批fixture由caller只在隔离e2e workspace临时设置soft_deny及deny_limit1。BG5正常有效图的原生BACKGROUND_TASK为无人值守来源，被拒绝并如实说明；并未进入人工审批，因此此样本不用于P2关闭。真人 `45557d0916d44e95803b56bc39ad4764`、终态 `0e1e4c9a02b740fd9aeb62b8a9e3fef3`；`r3-manual-bg5.json`。caller确认沿用既有权限来源规则，接着用原BG3缺图反馈产生可交互修正的路径验证人工卡片。

- **P2 closed**：BG6重复原缺图→有效图的后台反馈路径，START `2a51ca5e0f394a9580855c5ee992d82a`，缺图草稿 `02eded5d22014755b84dd1e9056db8b3` 空正文failed。有效图修正出现真实新审批卡 `a3211353-ccab-4b71-b73e-994c25bdeb0a`，Chrome AX列出目标当前聊天、原3.png、四个选项。Reviewer通过UI点击 **Allow once**，先见Decision submitted，随后产品API记录 `status=resolved`、`decision=allow_once`、`decided_by=u_mswcw1yl`、`run_id=run_bbfcd310ef497c9f`。消息 `11cd95dc77584c8cb99c5571807159e7` 显示真实原3.png、completed；Chrome实际紫色图与43.1s正常footer。无后续真人输入、无显式send_message工具执行。证据 `r3-manual-bg6.json`、本轮CUA操作及截图。审批期间正文未提前公开；批准后仅一次图片。

| 原开放项 | 新实际证据 | 当前状态 |
|---|---|---|
| P1 后台缺图修正被误拒绝 | BG4保留禁显式工具约束，普通修正图completed | closed |
| P2 后台修正审批卡不可操作 | BG6真实卡片→UI Allow once→resolved→图片completed | closed |
| BG3旧对照未完成 | 保留旧失败历史，不回写；BG6覆盖同一审批边界 | 已由新旅程覆盖，不当作旧消息恢复 |

### Round3 最终收口

Caller删除临时审批fixture后，reviewer独立确认 `.gateway-workspace/e2e/.nanoassistant/config.yaml` 不存在。最终普通群图smoke `c_friewuob` / `c848fdeb55dc406492ad785ec661f4a3` 一次完整原4.png、completed；Chrome实际紫红图、正常4.0s footer，无审批等待、重复图或错误占位。证据 `r3-final-smoke.json`。验收后关闭本轮新建Chrome标签页。

**最终 Verdict: pass。开放 blocking/major/minor = 0/0/0。** P1、P2均已用真实产品路径关闭；motivation六个Scenario及feat-563保留的十个Scenario全部通过（本轮仅重验后台、权限与普通共享路径，其余明确继承Round1有效证据）。不将受控ACK/精确取消时序测试夸称真实飞书故障注入，不将同机第二逻辑节点证据夸称第二物理设备。

版本范围：产品运行源码已验证至d4a59af21；测试fixture及后续报告提交不改变该产品snapshot。最终全量/CI属于caller独立门禁，不由本报告替代。服务清理由caller负责，最后核验IM57004、Gateway61742；已提醒额外tmux `refactor564-im` 和 `refactor564-gateway`。报告未提交，交caller归档/提交。
