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
