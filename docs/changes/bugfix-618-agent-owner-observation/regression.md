# bugfix-618 — 回归验证

> 对齐: [incident.md](incident.md) / [design.md](design.md)
> Validation snapshot: `9b110168359b9c9ae5937d07a77b697e03a61d65 → 03d1d5a65550061a10c944552f0078dac9085408`

## Round 1 · 2026-10-19 · Full

### Verdict

**fail — 必验体验仍有 inconclusive 项。** 已完成的 Web 双 owner 发现/只读/实时/刷新/撤权与普通成员发送、原生只读/新消息/撤权均成立。原生列表真实长按/侧滑、详情表单，以及下表列出的媒体和严格断线重放等必验项没有足够独立证据，不能以 API、AX 或其他人的通过叙述补齐。

本 reviewer 独立观察到 0 个 blocking、0 个 major、1 个 minor 产品问题；另有 4 组必要证据缺口。主 Agent 另通知已核实 pending 审批卡仍有可点击选项，这是另一份审查的发现，本报告没有亲自复现，不能当成本轮独立观察。

### 版本、环境与范围

- reviewer 开始时 `git rev-parse HEAD` 为上述 validated_at，受审源码无 dirty 修改。fixture PID 23351 的 cwd 为本 worktree，Vite PID 21404 的 cwd 为本 worktree `src/IM/frontend`，现场 lsof 核实。前端由 Vite 即时提供。没有读取产品实现定位原因、修改代码/测试/设计或提交。
- 真实 HTTP 服务 `http://127.0.0.1:58054`；Web/Vite `http://127.0.0.1:53186`；fixture 控制 `58055`。仅合成 alice/bob/charlie、alpha/beta/gamma/palpha/pbeta 与专用群使用。
- Chrome 实际桌面截图 1538×944；窄屏 DevTools iPhone 16 393×852。窄屏截图由真实页面取得，不是原型。未精确覆盖契约中的 1280/390，已覆盖更接近 390 的 393 窄宽；精确尺寸仍可在补验时核对。
- iPhone 17 Pro / iOS 26.4，UDID `1CE31893-672F-495A-B2B5-3ACF39A7A257`。安装版本与构建路径由 caller 交接；reviewer 未独立重建或做二进制源版本证明，原生版本证据依赖 caller 的集中环境交接。
- 原生最初 origin 58054 持续显示 Disconnected. Reconnecting。caller 将同一 App 单次重启为 Vite origin 53186（PID 29299），服务器和 DB 不变。reviewer 重新登录后该提示消失，成功观察新消息；此项作为隔离环境接线更正记录，不归因为产品权限 bug。
- 原生系统密码弹窗由 caller 排障解除；此后所有下述实际观察由 reviewer 完成。没有保存密码或改系统设置。服务均由 caller 管理，本 reviewer 未启停服务。

### Reference Artifacts Reviewed

AGENTS.md、docs/README.md、current `docs/specs/im/auth-tenancy.md` 与 conversations-messages 的适用接口、incident.md、design.md（含 runbook/must-match）、prototype.html 的 UI/状态契约、change-reviewer skill/报告模板/交接规则、共同体验标准；只读 fixture.mts 作为合成数据驱动说明。未加载 worker 成功叙述或读产品实现。

### 复现验证与逐场景结果

修前现象来自 incident 的既有调查，本轮没有重新启动旧版本；修后独立实际操作如下。已有历史是本 fixture 在 reviewer 登录前已经存在的数据，不能等同于实际生产旧库升级验证。

| 来源 Scenario | 结果 | 实际操作和证据 |
|---|---|---|
| 同一 owner 两 Agent | pass | Alice Network 中 alpha↔beta 仅一项，进入 c_fa93g7p3 看到既有“同 owner 协作历史。”；API列表也仅一项。 |
| 不同 owner 公司 Agent | pass | Alice、退出再登录 Bob，均经 Network 打开同一 c_b3ko73cm；双方看到原始 alpha 请求和 gamma 回复。Bob列表只有该私聊。见 review-web-readonly.png、review-web-bob.png。 |
| 私人空间协作 | pass | Alice 打开 c_10v0ifpw 读取 palpha↔pbeta 历史；Bob/Charlie直接读该历史均404 resource not accessible。 |
| 已有协作历史 | pass（限定fixture既有记录） | 未再次seed、未加入聊天，Alice首次登录可读既有消息；刷新和Bob重新登录仍能读取同样消息ID与作者。没有执行数据库升级。 |
| 打开只读会话 | pass（普通文字消息） | Web桌面/393窄屏双方名、作者、节点名和固定底栏可辨；无输入/发送/加入/改名/Config/Tasks控件。iOS实际进入聊天，底栏明确Agent collaboration · read only，无composer或加入。详情与审批卡不含在此有限结论。 |
| 绕过界面发送 | inconclusive（已验证文字拒绝） | Alice POST /conversations/c_b3ko73cm/messages 返回404；详情仍显示仅alpha/gamma两参与者、is_observer=true/is_member=false/can_write=false/can_join=false。附件发送、冒用Agent、工作副作用无新增未独立覆盖，不能把一次文字拒绝泛化。 |
| 不扩大其他写权限 | inconclusive（部分通过） | Alice PATCH聊天改名、POST participants均404；未实际请求消息修改/撤回及附件写入。普通文字消息只有Copy操作。iOS详情写表单未操作。 |
| 实时往来与重连 | inconclusive（主要路径通过） | Web现场send与send-back各一次，增加22:00两条消息；刷新前后同8个message ID，无新增重复。桌面滚到历史顶部成功。iOS更正origin后send-back新增10:06消息，点击Latest messages能跳到新消息。未严格断网跨游标重放、分页边界、单条超长消息验证。 |
| 不相关账号或资格失效 | pass（已观察文字/REST范围） | Charlie为无关管理员，GET列表items=[]、跨owner详情404；同账号同空间仅revoke alpha owner，Web自动返回列表、清空正文、移除该项并提示不可访问；iOS清空正文/只读底栏变不可访问；Alice详情/历史均404。未覆盖媒体卸载、账号停用与旧事件重放。见两端revoked图。 |
| Network分类 | inconclusive（私聊通过） | Alice Network显示三条Agent私聊并排除普通真人成员群；Bob只见跨owner项。未准备全Agent群、普通真人私聊和人机直聊做完整分类对照，不能声称全部通过。 |
| Agent继续交流 | pass（固定节点协议范围） | reviewer查看时实际节点send/send-back成功，原作者仍为alpha/gamma；两真人未加入，API参与者保持两Agent。不代表DSH模型自主协作验证。 |
| 真人成员正常聊天 | pass（Web） | Alice打开“发布计划协作”仍有Config/Tasks和composer；输入“验收核对：发布清单已确认。”按Enter，出现持久消息dd7b41802b514a1a950ed6f86bd73f16及列表预览；没有被误判只读。见review-web-member.png。 |

### 整体体验与 must-match 对照

桌面沿用左侧列表和右侧消息流：列表标题直接把两个Agent对应起来；气泡上方作者和节点名使用户能区分谁提出、谁回复，底部固定只读说明取代成员群的输入区。窄屏保留双方标题与返回入口，正文换行不横向截断，只读说明完整可读。多条消息足以形成滚动，桌面实际滚回早期请求成功。原生使用现有导航和底部说明，进入后看到作者与消息正文；新消息到达时出现Latest messages，实际点后抵达新消息。上述使用户能阅读协作并理解无法插话的原因，普通文字观察体验可接受。

| must-match | 对照结论 |
|---|---|
| Network条目双方身份，桌面/窄屏 | 桌面pass；窄屏会话标题pass，窄屏列表交互inconclusive：尝试返回/滚动被CDP Input.dispatchMouseEvent超时阻止。 |
| 双方作者、只读提示、无输入/发送/加入 | 普通文字状态两端pass；审批卡状态另审查有缺口，不以普通消息结果覆盖。 |
| 新消息追加、长内容滚动 | Web新增/刷新/桌面滚动与iOS最新消息跳转pass；长单条/严格分页未覆盖，完整项inconclusive。 |
| 失效不可访问且不继续交付 | 前台撤权清正文和REST拒绝pass；媒体与断线旧事件未覆盖。 |
| 原生无composer/加入、无长按/侧滑写动作 | 底栏pass；AX显示观察行只有Cancel而成员行有Pin/Mute，仅为辅助证据。实际坐标点击/拖动报noWindowsAvailable，索引click(durationMs)实际上只是进入聊天，不能算长按。详情导航栏未被AX暴露，坐标操作也失败，故长按/侧滑/详情inconclusive。 |

### Issues 与证据缺口

1. **minor / direct / fix-implementation**：原生撤权后主区显示红色 `conversation_id not found`，底栏才显示可理解的 `This conversation is no longer accessible.`。期望统一说明已失去访问权；实际内部字段名增加理解负担，但正文确已清空、底部说明存在，属局部提示改进。复现：Alice打开跨owner私聊→仅/revoke→下一轮检查。证据 review-ios-revoked.png。
2. **必要证据缺口 / 原生交互**：详情、真实长按和左右侧滑未操作成功。需要可控制的模拟器交互入口补验；AX动作缺失不能替代手势结论。
3. **必要证据缺口 / 边界读写与恢复**：附件/媒体、消息修改撤回、冒用Agent、账号空间资格失效、严格WS断线重放、分页与长单条内容未独立覆盖。补齐真实API/WS及两端相应UI，不用worker测试结果代替必要体验。
4. **必要证据缺口 / 分类与窄屏**：全Agent群及真人/人机私聊排除的组合未准备；393窄屏截图已观察，但返回/列表/滚动交互受CDP超时影响。
5. **必要证据缺口 / 审批卡**：caller通知静态审查已在真实单线程双Agent私聊核实可点击审批选项；本轮普通文字fixture没有该状态，需修复后加入真实只读卡片场景独立复验。

Highest Required Action: **fix-implementation**（审批卡发现由caller负责归并；本 reviewer 不作根因判断）。needs_re_review=true；gh_issues_filed=0。

### 自动化测试增量

本角色没有新增或运行实现测试，也没有以自动化通过结论替代体验；测试增量及验证由worker/静态门禁报告承担。

### 上层文档同步

- [x] SPEC.md：本轮不提出跨包架构改动，预计无需更新；最终由orchestrator核对。
- [x] docs/specs/im/：需要归并双方owner只读、Network、原生、资格失效等delta；本轮不写current。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

### 证据文件

本unit evidence下：review-web-readonly.png、review-web-bob.png、review-web-member.png、review-web-narrow.png、review-web-revoked.png、review-ios-readonly.png（修正origin前）、review-ios-live.png、review-ios-live-latest.png、review-ios-revoked.png。截图是本轮实际客户端画面；本报告记录的HTTP状态来自reviewer现场请求。

报告未提交，遵循caller“只写报告/截图，不提交”指令。自启服务为零，fixture已恢复alpha owner=alice。

## Round 2 · 2026-10-19 · Targeted follow-up

> Validation snapshot: `d9be419c7 → 1823aef433264a8732ae56461a73deea60ada701`
> 修复范围：caller交接 `03d1d5a65..3786dd735`；合入main仅issue模板/文档。reviewer实际核实HEAD，git status干净；仅查看修改路径确认保留边界，未读实现。Web仍53186，IM58054，control58055；DB重建，新跨owner ID `c_pyam0xq4`。

### 当前结论

**inconclusive，因此门禁仍 fail。** 本轮可执行的Web审批卡、长内容/分页、媒体与真实WS恢复补验均通过，没有新增已确认产品问题。原生两项修复的可视复验和实际长按/侧滑/详情，以及窄屏返回/列表补验仍受系统UI控制阻塞，不能宣告完成。

R1中未受此次修复影响且证据充分的具体结论继续保留：同owner唯一会话、跨owner双方读取、私人空间隔离、既有历史、普通文字观察无composer/加入、普通成员Web发送。普通文字R1结论不覆盖审批卡；R1原生内部错误提示问题须本轮实际观察后才能关闭。

### 独立补验结果

| R1缺口/修复 | R2结果 | 实际证据与边界 |
|---|---|---|
| Web pending审批卡 | pass | 实际打开私聊，卡片显示bash、NEEDS REVIEW、deploy --check及说明，无Allow/Deny/决定按钮、理由表单。正文因fixture超时显示relay idle/failed，但卡仍NEEDS REVIEW；这是持久pending卡只读观察状态，不冒充正在运行节点审批。见review-r2-web-card-media.png。 |
| Web媒体查看与无上传 | pass | review-icon.png缩略图正常，实际点击Enlarge image进入大图；消息只有附件读取控件、没有上传composer。文本附件点击触发系统另存为面板，未保存；HTTP直接读取确认实际内容“Synthetic release checklist: login, messages, rollback.”。 |
| 已挂载媒体撤权清理 | pass | 大图预览正在打开时，仅/revoke，页面自动回列表，大图和正文消失，旧项移除并提示不可访问。见review-r2-media-revoked.png。随后restore。 |
| 附件授权 | pass | 图片及文本URL从typed timeline的message.attachments提取；Alice、Bob均200且分别image/png、text/plain；Charlie均404；revoke后Alice两个URL均404。 |
| 附件写入/冒用Agent | pass | 真人Alice POST /im/v1/uploads?conversation_id=c_pyam0xq4&file_name=forbidden.txt，text/plain合成body，404 conversation_id not found；POST messages带sender_id=agent:alpha及sender Actor也404。前后完整typed history JSON一致，没有新增或篡改。 |
| 修改/撤回消息 | not-applicable于已声明入口 | current spec未声明这两项HTTP操作，实际消息操作仅Copy；不为验收新建功能。曾尝试未核实路径的请求不是有效授权证据，不据其返回码声称“全部写入口已测”。已有发送/上传/改名/成员写接口的实际拒绝分别保留R1/R2证据。 |
| 长单条内容滚动 | pass（桌面） | 实际滚动100行长清单，从15–51行至71–100行，再到附件/审批卡；底栏持续只读，行文没有被固定高度裁切。见review-r2-web-long.png与review-r2-web-approval.png（该图实际是长清单尾部）。 |
| 历史分页 | pass（Web） | 初次50条从历史20开始；向上滚动后实际加载历史01–19及最初alpha请求/gamma回复，显示No earlier messages。见review-r2-web-history.png。没有用API取全量替代这一UI动作。 |
| 双方WS实时/断线重放 | pass | reviewer先完整阅读/tmp/nano618-http-ws-audit.mts再独立运行真实ws-ticket→带同源Origin的/im/ws/user→resume。原脚本默认50条分页导致计数50!=53；只在内存把历史读取增加limit=200后再执行，最终71条=本次基线+3，双方live、Bob断线后resume补回、Charlie无受保护live、撤权Alice停止后续live、参与者仍两Agent全部断言通过。该改动只修正审计脚本取数范围，不改受审代码/文件。 |
| 撤权后旧事件重放 | pass | 独立新建Alice socket，先revoke再ws-ticket/resume after_event_id=0，收到12帧但目标私聊事件0；恢复owner。结合上条Bob真实补发证明不是仅“没有任何连接输出”。 |
| 真人/人机分类排除 | pass（桌面） | All实际显示“真人沟通”“我的助手”和成员群；点击Network后只剩三Agent私聊。没有给owner加入或获得其他群权限。 |
| 既有纯Agent群分类 | not-applicable于本次owner旁观权限增量；保留原分类保护 | 纯Agent群仍依成员或公开群访客资格，不因管理owner获得群旁观。本fixture没有符合原读取路径且加入列表的纯Agent群；caller明确旧分类分支未改、组件保护保留。本报告不声称实际新验了纯Agent群，不扩大权限来制造验收场景。 |
| 原生审批卡/友好撤权修复 | inconclusive | 确认Simulator窗口iPhone17Pro iOS26.4。重新登录Alice后，真实列表显示三Agent私聊及真人/人机；点击跨owner已进入会话。但系统“保存密码？”浮层遮挡，AX只有宿主，Raise→Escape→Tab本轮未解除，故未观察审批卡与修复后的失效提示。未使用其他UI驱动。 |
| 原生真实长按/侧滑/详情 | inconclusive | 仍保留R1控制限制，没有将AX缺少Pin/Mute当作手势证据，也没有把索引click(durationMs)当长按。 |
| 窄屏返回/列表 | inconclusive | R1 393×852画面仍有效；本轮准备切换时Chrome实际停在文本附件的“保存为review-checklist”系统面板。点击取消后CUA timeoutReached，随后AX读取同样超时。没有保存到默认私人目录，未盲试后续输入。桌面DOM仍可操作不代表窄屏路径已完成。 |

### 工具/环境限制及交接

Chrome另存面板是reviewer点击合成文本附件触发；文件未保存。Simulator密码提示未保存。两项均已及时交caller处理；用户关于是否允许替代原生UI驱动的答复仍由caller接收，reviewer未自行切换技术。所有受审服务保持运行，alpha owner最终restore为alice。

新增截图：review-r2-web-card-media.png、review-r2-media-revoked.png、review-r2-web-long.png、review-r2-web-history.png、review-r2-web-approval.png。均为真实Web。原生本轮没有可用修复验收截图，不复用R1图片冒充新版本。

剩余必验：原生审批只读与友好失效、原生列表长按/侧滑/详情、窄屏返回/分类实际操作。修复后的整体Web观察流程已可接受：审批内容可理解但不提供决定入口；媒体可读且撤权清理；长消息和前页历史可达。整体Full验收仍不能因Web通过而放行原生缺口。报告未提交；needs_re_review=true，gh_issues_filed=0。

## Round 3 · 2026-10-19 · 窄屏交互定向补验

> validated_at仍为 `1823aef433264a8732ae56461a73deea60ada701`，executed_base仍为 `d9be419c7`；仅补R2的窄屏返回/分类/滚动缺口，未读实现。

**本轮范围 pass。** R2的窄屏inconclusive关闭；Full整体仍受原生必验缺口阻塞，不据本轮Web结果放行原生。

使用公开CUA browser viewport capability，新建独立Chrome页1805414649进入53186，现有Alice会话正常恢复。最初set(390,844)因浏览器已有80%缩放，现场只读DOM确认innerWidth=487、innerHeight=1055、devicePixelRatio≈0.8；将override校正为312×675后，DOM实测**390×844 CSS像素**，未改变浏览器缩放设置。以下验收均在后者尺寸完成，结束已调用viewport.reset()。

| 必验点 | 实际操作与结果 |
|---|---|
| 返回列表 | 进入alpha↔gamma→点击真实Back按钮→回到All列表；长历史阅读后再次Back成功。返回后All恢复是实际既有行为，没有将其误写成保留Network筛选。 |
| 分类排除 | All中真人沟通、我的助手及成员群可见；点People仅真人沟通，点Agent仅我的助手，点Network仅三条Agent私聊。按钮全部可点击，双方名称完整可辨。 |
| 长单条滚动 | 在390宽私聊实际向上滚动，读到长清单91–100行，再向上读到标题与1–6行；正文正常折行，固定只读条持续可见，无输入/发送/加入入口。 |
| 历史分页 | 实际向前滚动触发前一页加载，再继续滚动看到No earlier messages、最初alpha请求/gamma回复和发布历史01–06；不是只检查隐藏DOM。 |

体验结论：窄屏列表中筛选、标题与预览的层级清楚；点击进入后标题和返回保持固定，长内容纵向可达，底栏没有覆盖已滚到的正文。列表与会话往返不需要依靠屏外控件或猜测导航，未发现新问题。审批卡/媒体的独立修复结论仍引用R2，本轮没有点击文本附件或操作原生系统弹窗。

证据：`review-r3-narrow-network-390.png`（390 CSS宽真实Network）、`review-r3-narrow-long-end.png`、`review-r3-narrow-long-middle.png`（该图实际为长清单开头及相邻历史）、`review-r3-narrow-history.png`。`review-r3-narrow-network.png`为校正前487 CSS宽，不用它声称390验收。

剩余必验仅原生：审批卡只读、友好失效修复、列表长按/侧滑和详情。未使用替代UI驱动，报告未提交，新增产品问题0。
