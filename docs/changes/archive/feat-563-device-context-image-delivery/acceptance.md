# feat-563 — 验收报告

## Round 1

Validation snapshot: `0014ee0b0 → c8586a42969c12e3265286cec8b5e9648e3c802a`。2026-09-16，独立 Full 产品验收，真实 DeepSeek 模型、隔离 Web IM/Gateway。未读取实现定位或修复。

### Verdict

**fail（本轮进行中）**。已完成 Web IM 普通/群聊主旅程；发现用户可见内部状态泄漏。全局显式发送、第二执行节点、权限拒绝和真实飞书旅程尚待环境提供及执行。

### 环境与证据

- IM `http://127.0.0.1:50098`，PID 10923；Gateway PID 10948。两进程 cwd 均为本 unit worktree，Gateway 使用 `.gateway-config.yaml`；HEAD 与指定 validated_at 一致。
- 初始旧前端 Open chat 返回 422 missing body.type，群聊创建无响应。root 重建当前源码产物后导航获得新前端；dist index.html 时间 10:58:41。此项作为环境准备问题，不计本 unit 缺陷。
- 专用账户 nano，独立聊天 `c_kv7ksmn5`、群 `c_v82ijii3`。PNG 为 reviewer 生成的 160×100 纯色测试图，位于 `/private/tmp/feat563-acceptance-images/`，在 Agent workspace 外。
- 产品 API 历史证据 `/private/tmp/feat563-acceptance-evidence/c_kv7ksmn5.json` 和 `c_v82ijii3.json`。浏览器 CUA 实际查看，viewport 1280×720；截图见本审查会话工具输出。报告不包含凭据。

### 用户旅程体验

1. Agent 配置页 Preview stable system prompt：Runtime 指明用户可能在另一设备，channel 是用户沟通渠道，Web IM URL 为测试入口；Reply Images 使用绝对路径，没有 exports 指令，普通路由要求直接回复。
2. 普通单聊请求原路径 1.png：消息 `a16479cb59404388ab1e2d5232788e47` 显示“图一”与蓝色图片，可放大。
3. 五图中第三张 missing.png：消息 `af6bf7f76bbc4c189554cb400f91324b` 只发布一次完整五图。产品 Process 显示先输出原五图，随后收到 image 3 file_not_found，改为 3.png 后成功；没有首份失败正文、缺图占位或重复气泡。
4. 移走原 1.png，成员下载仍 200 image/png 314 bytes，匿名同 URL 401，专用已登录非成员 feat563-outsider 同 URL 404；浏览器刷新后图片仍可见。随后恢复测试源文件。
5. 另一设备请求预览：消息 `077147de554b4192bb38860a11f1adaa` 说明回环指用户本机，未猜测远端 IP，建议已知通道或补充目标主机；识别当前 Web IM 地址。未配置 execution_access_address 的未知场景符合预期。
6. 群聊 @e2e：`1db57839eeba4d9ab00bd35631adce36` 显示“群聊图二”与紫色图片，未 @ 的 peer 无额外回复。
7. 群聊无法恢复缺图：`1495f4474be04b6cbbac2fa3be686daf` 如实说明文件不存在、图片未送达，未生成/替代图片，无成功虚假承诺。

### Reference Artifacts Reviewed

N/A。无前端 must-match 原型；原始生产截图是故障材料，不是视觉设计目标。实际图片展示已通过浏览器观察。

### 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| P1 | major | 成功图片交付后，单聊和群聊 sidebar 的最后消息预览显示 `suppressed_by=empty_visible_reply`。刷新仍存在；正文图片正确。用户看到了内部状态，而非正常最后消息预览。 | 已即时报告 root，待修复与复验。 |
| E1 | blocking | 未提供 global/第二执行节点/权限拒绝隔离 fixture；真实飞书尚待切换栈。 | 等待 caller 环境，不以单测替代产品验收。 |

### 验收标准覆盖

| Requirement / Scenario | 期望来源 | 证据 | 结果 |
|---|---|---|---|
| 设备上下文 / 用户从另一台设备请求网页预览（已知入口） | spec.md | 尚无 execution_access_address fixture | inconclusive |
| 设备上下文 / 访问条件未知 | spec.md | 旅程5 | pass |
| 设备上下文 / 更换执行节点 | spec.md | 当前仅单节点 | inconclusive |
| 本地图片 / 从原项目目录发送截图 | spec.md | 旅程2、6；工作区外原路径 | pass |
| 本地图片 / 无权发送的本地文件 | spec.md | 未提供 deny fixture | inconclusive |
| 本地图片 / 成功图片长期回看 | spec.md | 旅程4，成员200/匿名401/已登录非成员404 | pass |
| 失败恢复 / 五张截图中一张准备失败后恢复 | spec.md | 旅程3，完整五图单气泡 | pass |
| 失败恢复 / 网络或本地来源错误可由 Agent 修正 | spec.md | 旅程3本地缺图，网络/上传失败尚未覆盖 | inconclusive |
| 失败恢复 / 无法恢复交付 | spec.md | 旅程7 | pass |
| 跨入口 / 普通回复与显式发送跨渠道一致 | spec.md | 普通Web已验，global/飞书待补 | inconclusive |

### 上层文档同步

- [x] `SPEC.md`：需 orchestrator 检查候选输出 SDK 边界是否需摘要同步。
- [x] `docs/specs/`：需要归并 kernel/gateway/im delta-spec；reviewer 不修改权威契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。


## Round 2

Validation snapshots: Web/Feishu online and second node `8ffd1318a8d29eb0e245651393622dbe3c9aeaa4`; Feishu IM-offline targeted check `24bad8b2f` (caller refreshed Gateway before outage). This round inherits Round 1 evidence where unaffected. Second fixture IM/Gateway PIDs 19795/19822, node `wt-feat563-second-node-19767`, runtime `/private/tmp/feat563-second-node`, source worktree documented in fixture-validation.json. The second node is an isolated logical execution node on the same physical Mac; no claim of a second physical computer being tested.

### Verdict

**fail（本轮进行中）**。P1 closed; new major P2: offline successful image is labelled failed after shadow backfill. Upload failure injection pending.

### 新增真实旅程与证据

- R2-A: `http://127.0.0.1:52318`, second-global explicitly sent workspace-external image. Conversation `c_56xeleds`, message `fe750aaaf4924cd7bd0c4ff3d19518eb`: rendered gold image, actual second-node workspace `/private/tmp/feat563-second-node/.gateway-workspace/second-global`, execution address `172.20.10.2`, Web IM URL `http://127.0.0.1:52318`. Missing source then corrected explicit send produced only one additional public message `031350c5d2394a11820dca5fb02f3b76` with gold image. Actual CUA screenshot viewed at 1280×720.
- R2-B: second-e2e ordinary reply `3e113321c2304362b07ac4a2af067f36` supplied `http://172.20.10.2:4176`, stated network/listen conditions unverified, and displayed workspace original acceptance-image.png. No previous node path or old IM URL carried over. This validates use of configured known address, not physical remote reachability.
- R2-C: initial second-deny fixture merely disabled auto mode, which was not a deny policy; its first successful image is excluded from deny evidence. Fixture owner added explicit hard-deny image sending policy. New request in `c_ri01efre`, message `50c2bb93a93a46ac8efe7fadb8aa4f63`: only “本次图片未发送” plus explanation, no new image, no retry. Existing older authorized image remains history.
- R2-D: real authorized dedicated Feishu profile, verified user identity and configured test App. User sent to dedicated test Bot; real post `om_x100b659434ab70a8b36af26a9731514` has one image resource, downloaded 314 bytes and visually matches purple original. IM shadow `c_ee7l6qh4` / `658dc50437d940c99b636e81552c23e7` displays same image; Agent correctly identifies Feishu channel.
- R2-E: Feishu five images with missing third recovered to single post `om_x100b659430dd68a8b4b3ca26dc56c5f`; five image resources downloaded. IM shadow `f4a99fe886ca4e0e8f5f52e1d1c03844` shows five images in order, no failed draft/duplicate. Local evidence `feishu-five.json`.
- R2-F: caller stopped only IM :51856 while Gateway remained running. Test user sent offline request at 11:10:24. Real Feishu post `om_x100b6594c49fa080b482515df00b966` delivered image four, downloaded resource available. After IM recovery, shadow `5bdb968c135a4e97b335cab679046fc6` includes correct image; however footer visibly says `failed` and product API `delivery_status=failed`. Evidence `feishu-offline.json`, `feishu-shadow.json`, actual browser screenshot in review session.
- R2-G: second-node ordinary loopback HTTP image rejected and corrected to workspace file. `c_w5fbs489` / `02fcf93b737944e0bbaf7425768df734` contains one actual image after source correction, explains original draft withheld. No raw placeholder or duplicate. Product history demonstrates error distinguished from missing local file.
- R2-H: successful ordinary/global/Feishu images now show meaningful last-message previews; no `suppressed_by=empty_visible_reply`. P1 closed at 8ffd1318a.

All exported API evidence resides `/private/tmp/feat563-acceptance-evidence/`; second-node files use conversation IDs. No credentials included in report.

### 问题继承与新增

| # | Severity | State | Evidence / disposition |
|---|---|---|---|
| P1 | major | closed | R2-H, sidebar actual UI no longer exposes suppressed_by. |
| E1 | blocking | closed | Caller provided second node/global/explicit deny fixtures and authorized real Feishu test Bot. |
| P2 | major | open | R2-F: successful offline Feishu image + correct backfilled image is labelled failed to user. Reported immediately to caller. |

### Scenario coverage (inherits Round 1)

| Scenario | Evidence | Result |
|---|---|---|
| 用户从另一台设备请求网页预览 | R2-B configured known address, no reachability overclaim | pass |
| 访问条件未知 | R1 journey 5; R2-B | pass |
| 更换执行节点 | R2-A/B isolated second logical node | pass |
| 从原项目目录发送截图 | R1 journeys 2/6; R2-A/B/D | pass |
| 无权发送的本地文件 | R2-C explicit hard deny | pass |
| 成功图片长期回看 | R1 journey 4 including authenticated outsider404 | pass |
| 五张截图中一张准备失败后恢复 | R1 journey3; R2-E real Feishu | pass |
| 网络或本地来源错误可由 Agent 修正 | R1 missing; R2-G loopback; upload failure pending | inconclusive |
| 无法恢复交付 | R1 journey7 | pass |
| 普通回复与显式发送跨渠道一致 | R2-A/D/E/F, blocked by false failed status P2 | fail |


## Round 3

Validation snapshot: `8b99f43eb502c03c150d587fe3b0a9220915955d`。Targeted: upload failure recovery and P2 offline reconciliation. Unaffected scenarios inherit Round 1/2.

### 上传失败旅程

Caller added one-shot HTTP 503 at the isolated IM POST images boundary, without changing production application source. Gateway PID26551, IM PID26523, :51856. Real model request in `c_iqywfkrb` consumed fixture; `/private/tmp/feat563-upload-fault-consumed.txt` records `/im/v1/conversations/c_iqywfkrb/images`.

The original image draft was withheld; product Process shows model receiving temporary upload failure and retrying once. Only one Agent public message `137bcfd4ca4f43fdaf3bd48b711fdb10` exists, contains actual red image five and completed status. Browser 1280×720 displays image and normal preview, no internal placeholder or duplicate. Evidence `/private/tmp/feat563-acceptance-evidence/upload-r3.json` and browser screenshot in this review session. Agent appended a conditional fallback sentence; it does not claim a failed image was delivered.

Scenario 网络或本地来源错误可由 Agent 修正: **pass** (R1 missing file, R2 loopback source, R3 actual HTTP503 upload).

### 离线影子复验与最终 Verdict

**PASS**。P2 closed，remaining blocking/major/minor: **0 / 0 / 0**。

在 `8b99f43eb` 保持 Gateway 在线、IM 停止期间再次发送原图三，真实 Feishu post `om_x100b6594fe17c8b8b24a1fe13519520` 只有一次、一个图片资源，下载字节与原图完全一致。恢复同数据库 IM 后，聊天 `c_ee7l6qh4` 自动补齐一条 `d85165096cf6476c8bd8a84e09a74f5a`，API `delivery_status=completed`，浏览器紫色图可见，footer 显示正常 `11:21 4.0s`，不再 failed。无重复 Agent 消息。证据 `feishu-offline-r3.json`、`feishu-shadow-r3.json` 与 1280×720 实际截图。Round2 旧失败样本仍留历史，不把不回写旧记录当新缺陷。

最终逐 Scenario：已知入口预览 pass（R2-B）；未知可达性 pass（R1-5）；切换节点 pass（R2-A/B）；原目录图片 pass（R1-2/6、R2-A/B/D）；无权发送 pass（R2-C）；历史回看/非成员边界 pass（R1-4）；五图缺一恢复 pass（R1-3、R2-E）；本地/网络/上传错误修正 pass（R1-3、R2-G、R3上传）；无法恢复 pass（R1-7）；普通/显式跨渠道一致 pass（R2-A/D/E、R3离线复验）。

仅保留测试范围说明：第二节点为同物理机隔离执行节点，不证明任意用户设备网络实际可达；代码承诺本身不包含自动打通网络。专用 Feishu 上完成真实普通回复、缺图恢复、IM离线恢复；显式 send_message 在真实 Web IM global入口验证。两入口与两渠道均覆盖，不将未测的笛卡尔积组合夸称逐一走过。

上层文档同步结论沿用 Round1；canonical delta归并和服务清理仍由 caller 拥有。Reviewer未启动服务、未修改源码/配置；仅写本报告。


## Round 4 — 初始气泡并发修复的最窄产品复验

Validation snapshot: `5a03c61510d73d76d0ac3272cddbe4966e27e892`。Targeted，2026-09-16 11:37。Caller说明 delta 为普通 managed reply 与 stream running 共享首次气泡创建；本 reviewer 不读实现、不把确定性测试结果当产品证据。范围仅重新验证普通图片完整发布、气泡身份和分轮顺序；Runtime、权限、来源错误恢复、全局发送、飞书和离线补齐沿用 Round1–3 未失效证据。

隔离入口 `http://127.0.0.1:57081`，node `wt-feat563-second-node-33224`，IM33253 / Gateway33283，cwd `/private/tmp/feat563-second-node`。fixture版本证明 `/private/tmp/feat563-second-node/race-fix-validation.json` 对应上述源码HEAD；Gateway cwd另经进程核验。账号nano，ordinary Agent second-e2e，聊天 `c_90rvphxd`。本轮内置浏览器连接不可用，改用 CUA 操作 Chrome 新建临时页；仅看测试页并在验后关闭。

- 单次普通一图：真实模型直接回复 `39e60c6c65114d94bff6e6143a1145a7`，只有一条“单气泡验收”加蓝色原图，图片真实渲染，sidebar显示正常文本摘要，footer正常4.0s，API completed；没有空/重复气泡、占位或failed。
- 同一运行内跨工具两轮：请求先图一，再执行pwd，再图二。真实结果按顺序为 `b3bd18f9a2924d07bed7617f88d1398f`（蓝色图一）和 `6c5e6c78eab24cc897e1dac3a290461d`（紫色图二与pwd结果），恰好两条完整气泡，每条原图各一次。两条API均completed，浏览器footer正常5.3s与793ms；第一轮Process显示1 tool，未出现内容覆写或重发。

实际截图见本review会话CUA输出（Chrome窗口截图1312×768，站点缩放80%）；API完整记录 `/private/tmp/feat563-acceptance-evidence/race-fix-r4.json`。无新must-match原型。这里只证明真实用户旅程，不声称浏览器这一轮确定性触发了所有线程交错。

**PASS**，新增 blocking/major/minor **0/0/0**。受影响的“从原项目目录发送截图”“普通回复与显式发送跨渠道一致”的普通Web路径复验通过，其余全部Scenario保留Round3结论。无需追加需求/设计变更。服务由fixture owner清理；本reviewer只修改本报告。
